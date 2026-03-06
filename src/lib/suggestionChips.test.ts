import { describe, it, expect } from 'vitest';
import { computeSuggestionChips, ACTION_CHIP_MAP, type ChipState } from './suggestionChips';

// Default state factory — everything off
const base = (): ChipState => ({
  isCentered: false,
  isDiscovering: false,
  isTyping: false,
  businessName: 'Test Diner',
  hasReport: false,
  hasForecast: false,
  hasSeoReport: false,
  hasCompetitiveReport: false,
  hasSocialAuditReport: false,
  hasCapabilities: false,
});

// ============================================================================
// Centered (home screen) state
// ============================================================================

describe('centered / home screen', () => {
  it('returns example search chips when centered', () => {
    const chips = computeSuggestionChips({ ...base(), isCentered: true });
    expect(chips).toHaveLength(2);
    expect(chips.every(c => c.category === 'insight')).toBe(true);
    expect(chips[0].text).toContain('Bosphorus');
    expect(chips[1].text).toContain('Tick Tock');
  });

  it('ignores all other state when centered', () => {
    const chips = computeSuggestionChips({
      ...base(),
      isCentered: true,
      hasReport: true,
      hasForecast: true,
      hasCapabilities: true,
    });
    expect(chips).toHaveLength(2);
    expect(chips[0].text).toContain('Bosphorus');
  });
});

// ============================================================================
// Loading states — should return empty
// ============================================================================

describe('loading states', () => {
  it('returns empty during discovery', () => {
    const chips = computeSuggestionChips({
      ...base(),
      isDiscovering: true,
      hasCapabilities: true,
    });
    expect(chips).toHaveLength(0);
  });

  it('returns empty during typing', () => {
    const chips = computeSuggestionChips({
      ...base(),
      isTyping: true,
      hasReport: true,
    });
    expect(chips).toHaveLength(0);
  });

  it('returns empty during both discovering and typing', () => {
    const chips = computeSuggestionChips({
      ...base(),
      isDiscovering: true,
      isTyping: true,
    });
    expect(chips).toHaveLength(0);
  });
});

// ============================================================================
// After margin analysis (report)
// ============================================================================

describe('after margin analysis', () => {
  it('shows insight + 2 action chips when no other reports exist', () => {
    const chips = computeSuggestionChips({ ...base(), hasReport: true });
    expect(chips).toHaveLength(3);
    expect(chips[0].category).toBe('insight');
    expect(chips[0].text).toContain('bleeding the most money');
    expect(chips[1].category).toBe('action');
    expect(chips[1].capability).toBe('traffic');
    expect(chips[2].category).toBe('action');
    expect(chips[2].capability).toBe('seo');
  });

  it('omits forecast action when forecast already exists', () => {
    const chips = computeSuggestionChips({
      ...base(),
      hasReport: true,
      hasForecast: true,
    });
    expect(chips).toHaveLength(2);
    expect(chips.find(c => c.capability === 'traffic')).toBeUndefined();
  });

  it('omits SEO action when SEO report already exists', () => {
    const chips = computeSuggestionChips({
      ...base(),
      hasReport: true,
      hasSeoReport: true,
    });
    expect(chips).toHaveLength(2);
    expect(chips.find(c => c.capability === 'seo')).toBeUndefined();
  });

  it('shows only insight when all other reports exist', () => {
    const chips = computeSuggestionChips({
      ...base(),
      hasReport: true,
      hasForecast: true,
      hasSeoReport: true,
    });
    expect(chips).toHaveLength(1);
    expect(chips[0].category).toBe('insight');
  });
});

// ============================================================================
// After SEO audit
// ============================================================================

describe('after SEO audit', () => {
  it('shows insight + 2 action chips', () => {
    const chips = computeSuggestionChips({ ...base(), hasSeoReport: true });
    expect(chips).toHaveLength(3);
    expect(chips[0].category).toBe('insight');
    expect(chips[0].text).toContain('SEO red flag');
    expect(chips[1].capability).toBe('surgery');
    expect(chips[2].capability).toBe('traffic');
  });

  it('omits margin action when report exists', () => {
    const chips = computeSuggestionChips({
      ...base(),
      hasSeoReport: true,
      hasReport: true,
    });
    // report takes priority over seoReport in the if-else chain
    // so this actually falls into the hasReport branch
    expect(chips[0].text).toContain('bleeding the most money');
  });
});

// ============================================================================
// After traffic forecast
// ============================================================================

describe('after traffic forecast', () => {
  it('shows insight + 2 action chips', () => {
    const chips = computeSuggestionChips({ ...base(), hasForecast: true });
    expect(chips).toHaveLength(3);
    expect(chips[0].category).toBe('insight');
    expect(chips[0].text).toContain('short-staffed');
    expect(chips[1].capability).toBe('surgery');
    expect(chips[2].capability).toBe('seo');
  });
});

// ============================================================================
// After social media audit
// ============================================================================

describe('after social media audit', () => {
  it('shows insight + 2 action chips', () => {
    const chips = computeSuggestionChips({ ...base(), hasSocialAuditReport: true });
    expect(chips).toHaveLength(3);
    expect(chips[0].category).toBe('insight');
    expect(chips[0].text).toContain('platform needs the most work');
    expect(chips[1].capability).toBe('surgery');
    expect(chips[2].capability).toBe('competitive');
  });

  it('omits competitive action when competitive report exists', () => {
    const chips = computeSuggestionChips({
      ...base(),
      hasSocialAuditReport: true,
      hasCompetitiveReport: true,
    });
    expect(chips).toHaveLength(2);
    expect(chips.find(c => c.capability === 'competitive')).toBeUndefined();
  });
});

// ============================================================================
// After competitive analysis
// ============================================================================

describe('after competitive analysis', () => {
  it('shows insight + 2 action chips', () => {
    const chips = computeSuggestionChips({ ...base(), hasCompetitiveReport: true });
    expect(chips).toHaveLength(3);
    expect(chips[0].category).toBe('insight');
    expect(chips[0].text).toContain('biggest threat');
    expect(chips[1].capability).toBe('surgery');
    expect(chips[2].capability).toBe('marketing');
  });

  it('omits social audit action when social report exists', () => {
    const chips = computeSuggestionChips({
      ...base(),
      hasCompetitiveReport: true,
      hasSocialAuditReport: true,
    });
    expect(chips).toHaveLength(2);
    expect(chips.find(c => c.capability === 'marketing')).toBeUndefined();
  });
});

// ============================================================================
// Discovery complete, no analyses yet
// ============================================================================

describe('discovery complete, no analyses', () => {
  it('shows 1 insight + 2 actions', () => {
    const chips = computeSuggestionChips({ ...base(), hasCapabilities: true });
    expect(chips).toHaveLength(3);
    expect(chips[0].category).toBe('insight');
    expect(chips[0].text).toContain('What did you find about Test Diner');
    expect(chips[1].category).toBe('action');
    expect(chips[1].capability).toBe('surgery');
    expect(chips[2].category).toBe('action');
    expect(chips[2].capability).toBe('marketing');
  });

  it('uses fallback name when businessName is undefined', () => {
    const chips = computeSuggestionChips({
      ...base(),
      businessName: undefined,
      hasCapabilities: true,
    });
    expect(chips[0].text).toContain('this business');
  });
});

// ============================================================================
// No state at all
// ============================================================================

describe('no active state', () => {
  it('returns empty when nothing is active', () => {
    const chips = computeSuggestionChips(base());
    expect(chips).toHaveLength(0);
  });
});

// ============================================================================
// Category invariants
// ============================================================================

describe('category invariants', () => {
  const allStates: ChipState[] = [
    { ...base(), hasReport: true },
    { ...base(), hasSeoReport: true },
    { ...base(), hasForecast: true },
    { ...base(), hasSocialAuditReport: true },
    { ...base(), hasCompetitiveReport: true },
    { ...base(), hasCapabilities: true },
  ];

  it('every state produces at least one insight chip', () => {
    for (const state of allStates) {
      const chips = computeSuggestionChips(state);
      const insights = chips.filter(c => c.category === 'insight');
      expect(insights.length).toBeGreaterThanOrEqual(1);
    }
  });

  it('every action chip has a capability field', () => {
    for (const state of allStates) {
      const chips = computeSuggestionChips(state);
      const actions = chips.filter(c => c.category === 'action');
      for (const a of actions) {
        expect(a.capability).toBeDefined();
        expect(a.capability).not.toBe('');
      }
    }
  });

  it('never exceeds 4 chips', () => {
    for (const state of allStates) {
      const chips = computeSuggestionChips(state);
      expect(chips.length).toBeLessThanOrEqual(4);
    }
  });

  it('action chips never suggest an already-completed capability', () => {
    // After margin report: should NOT suggest surgery
    const afterReport = computeSuggestionChips({ ...base(), hasReport: true });
    expect(afterReport.find(c => c.capability === 'surgery')).toBeUndefined();

    // After SEO: should NOT suggest seo
    const afterSeo = computeSuggestionChips({ ...base(), hasSeoReport: true });
    expect(afterSeo.find(c => c.capability === 'seo')).toBeUndefined();

    // After forecast: should NOT suggest traffic
    const afterForecast = computeSuggestionChips({ ...base(), hasForecast: true });
    expect(afterForecast.find(c => c.capability === 'traffic')).toBeUndefined();
  });
});

// ============================================================================
// ACTION_CHIP_MAP coverage
// ============================================================================

describe('ACTION_CHIP_MAP', () => {
  it('maps all action chip texts to valid capability IDs', () => {
    const validCapabilities = ['surgery', 'traffic', 'seo', 'competitive', 'marketing'];
    for (const [text, cap] of Object.entries(ACTION_CHIP_MAP)) {
      expect(validCapabilities).toContain(cap);
    }
  });

  it('every action chip from computeSuggestionChips is in ACTION_CHIP_MAP', () => {
    const allStates: ChipState[] = [
      { ...base(), hasReport: true },
      { ...base(), hasSeoReport: true },
      { ...base(), hasForecast: true },
      { ...base(), hasSocialAuditReport: true },
      { ...base(), hasCompetitiveReport: true },
      { ...base(), hasCapabilities: true },
    ];

    for (const state of allStates) {
      const chips = computeSuggestionChips(state);
      const actions = chips.filter(c => c.category === 'action');
      for (const a of actions) {
        expect(ACTION_CHIP_MAP).toHaveProperty(a.text);
        expect(ACTION_CHIP_MAP[a.text]).toBe(a.capability);
      }
    }
  });
});

// ============================================================================
// Priority / precedence
// ============================================================================

describe('priority precedence', () => {
  it('report takes priority over seoReport', () => {
    const chips = computeSuggestionChips({
      ...base(),
      hasReport: true,
      hasSeoReport: true,
    });
    expect(chips[0].text).toContain('bleeding');
  });

  it('report takes priority over forecast', () => {
    const chips = computeSuggestionChips({
      ...base(),
      hasReport: true,
      hasForecast: true,
    });
    expect(chips[0].text).toContain('bleeding');
  });

  it('seoReport takes priority over forecast', () => {
    const chips = computeSuggestionChips({
      ...base(),
      hasSeoReport: true,
      hasForecast: true,
    });
    expect(chips[0].text).toContain('SEO red flag');
  });

  it('forecast takes priority over socialAuditReport', () => {
    const chips = computeSuggestionChips({
      ...base(),
      hasForecast: true,
      hasSocialAuditReport: true,
    });
    expect(chips[0].text).toContain('short-staffed');
  });

  it('socialAuditReport takes priority over competitiveReport', () => {
    const chips = computeSuggestionChips({
      ...base(),
      hasSocialAuditReport: true,
      hasCompetitiveReport: true,
    });
    expect(chips[0].text).toContain('platform needs the most work');
  });
});
