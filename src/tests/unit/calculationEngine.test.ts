/**
 * Unit tests for CalculationEngine.calculateLeakage
 *
 * These are pure unit tests — no network calls, no LLM, no mocks needed
 * beyond suppressing the module-level @google/adk instantiation.
 */
import { describe, it, expect, vi } from 'vitest';

// Suppress module-level LlmAgent / FunctionTool instantiation
vi.mock('@google/adk', () => ({
  FunctionTool: vi.fn(),
  LlmAgent: vi.fn(),
}));

import { CalculationEngine } from '@/agents/margin-analyzer/surgeon';
import type { MenuItem, CompetitorPrice, CommodityTrend } from '@/lib/types';

describe('CalculationEngine.calculateLeakage', () => {
  // ── helpers ──────────────────────────────────────────────────────────────

  const item = (overrides: Partial<MenuItem> = {}): MenuItem => ({
    item_name: 'Grilled Burger',
    current_price: 10.00,
    category: 'Mains',
    ...overrides,
  });

  const competitor = (price: number, item_match = 'Grilled Burger'): CompetitorPrice => ({
    competitor_name: 'Rival',
    item_match,
    price,
    source_url: '',
  });

  const commodity = (ingredient: string, inflation_rate_12mo: number): CommodityTrend => ({
    ingredient,
    inflation_rate_12mo,
    trend_description: '',
  });

  // ── pass-through fields ───────────────────────────────────────────────────

  it('preserves all original MenuItem fields on the result', () => {
    const src = item({ description: 'Juicy patty' });
    const result = CalculationEngine.calculateLeakage(src, [], []);
    expect(result.item_name).toBe('Grilled Burger');
    expect(result.current_price).toBe(10.00);
    expect(result.category).toBe('Mains');
    expect(result.description).toBe('Juicy patty');
  });

  // ── competitor median ────────────────────────────────────────────────────

  it('uses current_price as median when no competitors exist', () => {
    const result = CalculationEngine.calculateLeakage(item(), [], []);
    expect(result.competitor_benchmark).toBe(10.00);
  });

  it('uses competitor price directly for a single competitor', () => {
    const result = CalculationEngine.calculateLeakage(item(), [competitor(14.00)], []);
    expect(result.competitor_benchmark).toBe(14.00);
  });

  it('computes the median for an odd number of competitor prices', () => {
    // sorted: [10, 12, 14] → index floor(3/2)=1 → 12
    const rivals = [competitor(14.00), competitor(10.00), competitor(12.00)];
    const result = CalculationEngine.calculateLeakage(item(), rivals, []);
    expect(result.competitor_benchmark).toBe(12.00);
  });

  it('computes the median for an even number of competitor prices', () => {
    // sorted: [10, 14] → index floor(2/2)=1 → 14
    const rivals = [competitor(14.00), competitor(10.00)];
    const result = CalculationEngine.calculateLeakage(item(), rivals, []);
    expect(result.competitor_benchmark).toBe(14.00);
  });

  it('ignores competitors whose item_match does not exactly equal item_name', () => {
    const result = CalculationEngine.calculateLeakage(item(), [competitor(99.00, 'Fish Tacos')], []);
    // No exact match → falls back to current_price
    expect(result.competitor_benchmark).toBe(10.00);
    expect(result.confidence_score).toBe(50);
  });

  // ── confidence score ─────────────────────────────────────────────────────

  it('sets confidence_score to 50 when no matching competitors', () => {
    expect(CalculationEngine.calculateLeakage(item(), [], []).confidence_score).toBe(50);
  });

  it('sets confidence_score to 90 when at least one competitor matches', () => {
    expect(CalculationEngine.calculateLeakage(item(), [competitor(12.00)], []).confidence_score).toBe(90);
  });

  // ── commodity inflation ──────────────────────────────────────────────────

  it('applies commodity inflation when the ingredient name appears in the item name (case-insensitive)', () => {
    const src = item({ item_name: 'Beef Burger', current_price: 12.00 });
    const result = CalculationEngine.calculateLeakage(src, [], [commodity('Beef', 20)]);
    // inflationaryPrice = 12 * 1.20 = 14.40, targetBase = 14.40, recommended = 14.40 * 1.05 = 15.12
    expect(result.commodity_factor).toBe(20);
    expect(result.recommended_price).toBe(15.12);
  });

  it('applies Eggs inflation when item is in the Breakfast category (even if item name lacks "eggs")', () => {
    const src = item({ item_name: 'Classic Omelette', current_price: 9.00, category: 'Breakfast' });
    const result = CalculationEngine.calculateLeakage(src, [], [commodity('Eggs', 40)]);
    // inflationaryPrice = 9 * 1.40 = 12.60, recommended = 12.60 * 1.05 = 13.23
    expect(result.commodity_factor).toBe(40);
    expect(result.recommended_price).toBe(13.23);
    expect(result.price_leakage).toBeCloseTo(13.23 - 9.00, 2);
  });

  it('does NOT apply Eggs inflation to non-Breakfast categories', () => {
    const src = item({ item_name: 'Pasta', current_price: 12.00, category: 'Mains' });
    const result = CalculationEngine.calculateLeakage(src, [], [commodity('Eggs', 40)]);
    expect(result.commodity_factor).toBe(0); // no match
  });

  it('uses only the highest inflation rate when multiple commodities match the item', () => {
    const src = item({ item_name: 'Beef Burger' });
    const commodities = [commodity('Beef', 15), commodity('Burger', 30)];
    const result = CalculationEngine.calculateLeakage(src, [], commodities);
    expect(result.commodity_factor).toBe(30);
  });

  it('uses inflation 0 when no commodity matches the item', () => {
    const result = CalculationEngine.calculateLeakage(item(), [], [commodity('Lobster', 50)]);
    expect(result.commodity_factor).toBe(0);
    // inflationaryPrice = current_price * 1.0, so commodity adds nothing
  });

  // ── recommended price formula ─────────────────────────────────────────────

  it('recommended price = max(inflationaryPrice, medianPrice) * 1.05', () => {
    // No inflation, competitor median $14 > inflationaryPrice $10
    // targetBase = 14, recommended = 14 * 1.05 = 14.70
    const result = CalculationEngine.calculateLeakage(item(), [competitor(14.00)], []);
    expect(result.recommended_price).toBe(14.70);
  });

  it('uses inflationaryPrice as targetBase when it exceeds competitor median', () => {
    // 50% inflation → inflationaryPrice = 15, competitor median = 8
    const src = item({ item_name: 'Chicken', current_price: 10.00 });
    const result = CalculationEngine.calculateLeakage(
      src,
      [competitor(8.00, 'Chicken')],
      [commodity('Chicken', 50)],
    );
    // targetBase = max(15, 8) = 15, recommended = 15 * 1.05 = 15.75
    expect(result.recommended_price).toBe(15.75);
  });

  it('rounds recommended_price to 2 decimal places', () => {
    // current_price = 7.33, no competitors, no inflation
    // recommended = 7.33 * 1.05 = 7.6965 → rounds to 7.70
    const src = item({ item_name: 'Soup', current_price: 7.33 });
    const result = CalculationEngine.calculateLeakage(src, [], []);
    expect(result.recommended_price).toBe(7.70);
  });

  // ── price leakage ─────────────────────────────────────────────────────────

  it('price_leakage equals recommendedPrice minus currentPrice', () => {
    const result = CalculationEngine.calculateLeakage(item(), [competitor(14.00)], []);
    // recommended = 14.70, current = 10.00, leakage = 4.70
    expect(result.price_leakage).toBe(4.70);
  });

  it('price_leakage is always >= 0 (never negative)', () => {
    // Even with a competitor priced far below, leakage is clamped at 0
    // targetBase always >= inflationaryPrice >= current_price (for non-negative inflation)
    // so recommended >= current_price * 1.05 > current_price
    const result = CalculationEngine.calculateLeakage(item(), [competitor(1.00)], []);
    expect(result.price_leakage).toBeGreaterThanOrEqual(0);
  });

  it('rounds price_leakage to 2 decimal places', () => {
    const src = item({ current_price: 7.33 });
    const result = CalculationEngine.calculateLeakage(src, [], []);
    const decimals = result.price_leakage.toString().split('.')[1]?.length ?? 0;
    expect(decimals).toBeLessThanOrEqual(2);
  });

  // ── rationale string ──────────────────────────────────────────────────────

  it('rationale includes the competitor median price and max inflation rate', () => {
    const rivals = [competitor(14.00)];
    const commodities = [commodity('Burger', 10)];
    const src = item({ item_name: 'Grilled Burger' });
    const result = CalculationEngine.calculateLeakage(src, rivals, commodities);
    expect(result.rationale).toContain('14');
    expect(result.rationale).toContain('10');
  });
});
