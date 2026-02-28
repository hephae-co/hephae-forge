/**
 * Unit tests for callMarketTruthTool (mcpClient.ts)
 *
 * These tests mock the MCP SDK entirely so no external stdio process is needed.
 * They verify JSON parsing, raw-text fallback, content passthrough, singleton
 * reuse, and client reset on error.
 *
 * Note: vi.fn() implementations used as constructors (called with `new`) must
 * be regular functions, not arrow functions. vi.clearAllMocks() is used instead
 * of vi.resetAllMocks() so those constructor implementations are preserved.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';

// ── mock the MCP SDK ──────────────────────────────────────────────────────────
// vi.mock is hoisted above imports, so these mocks are in place before
// mcpClient.ts is evaluated.

const mockCallTool = vi.fn();
const mockConnect = vi.fn();

vi.mock('@modelcontextprotocol/sdk/client/index.js', () => ({
  // Must be a regular function: arrow functions cannot be used with `new`.
  Client: vi.fn(function MockClient() {
    return { connect: mockConnect, callTool: mockCallTool };
  }),
}));

vi.mock('@modelcontextprotocol/sdk/client/stdio.js', () => ({
  StdioClientTransport: vi.fn(function MockTransport() { return {}; }),
}));

// Import the module under test AFTER mock declarations (hoisting ensures order).
import { callMarketTruthTool } from '@/agents/mcpClient';

// ── reset singleton + mocks before every test ─────────────────────────────────
beforeEach(() => {
  // clearAllMocks clears call history but preserves constructor implementations.
  vi.clearAllMocks();
  // Individually reset the leaf mocks so stale return values don't bleed across tests.
  mockCallTool.mockReset();
  mockConnect.mockReset();
  // Reset the singleton so each test starts with a fresh client creation.
  const g = global as typeof globalThis & { _mcpClient?: unknown; _mcpTransport?: unknown };
  g._mcpClient = undefined;
  g._mcpTransport = undefined;
  // Default connect to succeed unless a test overrides it.
  mockConnect.mockResolvedValue(undefined);
});

// ── tests ─────────────────────────────────────────────────────────────────────

describe('callMarketTruthTool', () => {
  it('parses and returns JSON when the tool returns text content', async () => {
    const payload = { prices: [{ item: 'Eggs', price: 3.5 }] };
    mockCallTool.mockResolvedValue({
      content: [{ type: 'text', text: JSON.stringify(payload) }],
    });

    const result = await callMarketTruthTool('get_usda_wholesale_prices', { category: 'Eggs' });

    expect(result).toEqual(payload);
    expect(mockCallTool).toHaveBeenCalledWith({
      name: 'get_usda_wholesale_prices',
      arguments: { category: 'Eggs' },
    });
  });

  it('returns the raw text string when the tool response is not valid JSON', async () => {
    mockCallTool.mockResolvedValue({
      content: [{ type: 'text', text: 'Server unavailable — try again later.' }],
    });

    const result = await callMarketTruthTool('get_bls_cpi_data');
    expect(result).toBe('Server unavailable — try again later.');
  });

  it('returns the content array directly when the content type is not "text"', async () => {
    const content = [{ type: 'blob', data: 'base64data' }];
    mockCallTool.mockResolvedValue({ content });

    const result = await callMarketTruthTool('get_fred_economic_indicators');
    expect(result).toEqual(content);
  });

  it('parses only the first item when content has multiple text entries', async () => {
    // branch: content[0].type === "text" → parse content[0].text
    mockCallTool.mockResolvedValue({
      content: [{ type: 'text', text: '{}' }, { type: 'text', text: '{}' }],
    });
    const result = await callMarketTruthTool('get_bls_cpi_data');
    expect(result).toEqual({});
  });

  it('resets the singleton client and rethrows when the tool call fails', async () => {
    mockCallTool.mockRejectedValue(new Error('stdio process exited'));

    await expect(callMarketTruthTool('get_usda_wholesale_prices')).rejects.toThrow(
      'stdio process exited',
    );

    const g = global as typeof globalThis & { _mcpClient?: unknown; _mcpTransport?: unknown };
    expect(g._mcpClient).toBeUndefined();
    expect(g._mcpTransport).toBeUndefined();
  });

  it('reuses the singleton client across subsequent calls (connect called once)', async () => {
    mockCallTool
      .mockResolvedValueOnce({ content: [{ type: 'text', text: '"first"' }] })
      .mockResolvedValueOnce({ content: [{ type: 'text', text: '"second"' }] });

    const r1 = await callMarketTruthTool('get_bls_cpi_data');
    const r2 = await callMarketTruthTool('get_bls_cpi_data');

    expect(r1).toBe('first');
    expect(r2).toBe('second');
    // The client was constructed once → connect is called exactly once.
    expect(mockConnect).toHaveBeenCalledTimes(1);
  });

  it('creates a new client after a previous call failed (reconnect on next request)', async () => {
    // First call fails → client is reset.
    mockCallTool.mockRejectedValueOnce(new Error('lost'));
    await expect(callMarketTruthTool('get_bls_cpi_data')).rejects.toThrow();

    // Second call succeeds → a new client must be created.
    mockCallTool.mockResolvedValueOnce({ content: [{ type: 'text', text: '"ok"' }] });
    const result = await callMarketTruthTool('get_bls_cpi_data');

    expect(result).toBe('ok');
    // connect was called once before the failure, and again after reconnect.
    expect(mockConnect).toHaveBeenCalledTimes(2);
  });

  it('passes an empty arguments object by default when no args are provided', async () => {
    mockCallTool.mockResolvedValue({ content: [{ type: 'text', text: '{}' }] });

    await callMarketTruthTool('get_fred_economic_indicators');

    expect(mockCallTool).toHaveBeenCalledWith({
      name: 'get_fred_economic_indicators',
      arguments: {},
    });
  });
});
