/**
 * Unit tests for LocatorAgent.resolve
 *
 * The Gemini SDK is fully mocked so no network calls are made.
 * Tests cover: missing API key, happy-path identity shape, URL normalisation,
 * markdown fence stripping, non-parseable Gemini output, and missing coordinates.
 *
 * Note: vi.clearAllMocks() preserves the constructor mock implementations
 * (which must be regular functions, not arrow functions).
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

// ── mock Gemini SDK ───────────────────────────────────────────────────────────
// Must be regular functions when used with `new`.

const mockGenerateContent = vi.fn();
const mockGetGenerativeModel = vi.fn();

vi.mock('@google/generative-ai', () => ({
  GoogleGenerativeAI: vi.fn(function MockGenAI() {
    return { getGenerativeModel: mockGetGenerativeModel };
  }),
}));

import { LocatorAgent } from '@/agents/discovery/locator';

// ── helpers ───────────────────────────────────────────────────────────────────

/** Configure the mock so Gemini responds with the given data. */
function geminiReturns(data: object | string) {
  const text = typeof data === 'string' ? data : JSON.stringify(data);
  mockGenerateContent.mockResolvedValue({
    response: { text: () => text },
  });
}

// ── env setup ─────────────────────────────────────────────────────────────────

const ORIGINAL_API_KEY = process.env.GEMINI_API_KEY;

beforeEach(() => {
  // clearAllMocks preserves constructor implementations; reset leaf mocks individually.
  vi.clearAllMocks();
  mockGenerateContent.mockReset();
  mockGetGenerativeModel.mockReset();
  // Chain: getGenerativeModel(config) → { generateContent }
  mockGetGenerativeModel.mockReturnValue({ generateContent: mockGenerateContent });
  process.env.GEMINI_API_KEY = 'test-api-key';
});

afterEach(() => {
  process.env.GEMINI_API_KEY = ORIGINAL_API_KEY;
});

// ── tests ─────────────────────────────────────────────────────────────────────

describe('LocatorAgent.resolve', () => {
  it('throws immediately when GEMINI_API_KEY is not set', async () => {
    delete process.env.GEMINI_API_KEY;
    await expect(LocatorAgent.resolve('The Bosphorus')).rejects.toThrow('Missing GEMINI_API_KEY');
  });

  it('returns a well-formed BaseIdentity on a valid Gemini response', async () => {
    geminiReturns({
      name: 'The Bosphorus',
      address: '111 Franklin Ave, Nutley, NJ 07110',
      officialUrl: 'https://bosphorus.com',
      lat: 40.8218,
      lng: -74.1577,
    });

    const result = await LocatorAgent.resolve('The Bosphorus Nutley NJ');

    expect(result.name).toBe('The Bosphorus');
    expect(result.address).toBe('111 Franklin Ave, Nutley, NJ 07110');
    expect(result.officialUrl).toBe('https://bosphorus.com');
    expect(result.coordinates).toEqual({ lat: 40.8218, lng: -74.1577 });
  });

  it('prepends "https://" when officialUrl has no protocol', async () => {
    geminiReturns({
      name: 'Tartine Bakery',
      address: '600 Guerrero St, San Francisco, CA',
      officialUrl: 'tartinebakery.com', // intentionally no protocol
      lat: 37.7617,
      lng: -122.4241,
    });

    const result = await LocatorAgent.resolve('Tartine Bakery SF');
    expect(result.officialUrl).toBe('https://tartinebakery.com');
  });

  it('does not double-prepend https:// when the URL already starts with https://', async () => {
    geminiReturns({
      name: 'Cafe X',
      address: '1 Main St',
      officialUrl: 'https://cafex.com',
      lat: 0,
      lng: 0,
    });

    const result = await LocatorAgent.resolve('Cafe X');
    expect(result.officialUrl).toBe('https://cafex.com');
  });

  it('strips ```json … ``` markdown fences before parsing', async () => {
    geminiReturns(
      '```json\n{"name":"Café Rome","address":"1 Via Roma","officialUrl":"https://cafe.it","lat":41.9,"lng":12.5}\n```',
    );

    const result = await LocatorAgent.resolve('Café Rome');
    expect(result.name).toBe('Café Rome');
    expect(result.officialUrl).toBe('https://cafe.it');
  });

  it('strips plain ``` fences before parsing', async () => {
    geminiReturns(
      '```\n{"name":"Bar Noir","address":"2 Rue Pigalle","officialUrl":"https://barnoir.fr","lat":48.88,"lng":2.33}\n```',
    );

    const result = await LocatorAgent.resolve('Bar Noir Paris');
    expect(result.name).toBe('Bar Noir');
  });

  it('throws a descriptive error when Gemini returns non-JSON text', async () => {
    geminiReturns("Sorry, I couldn't find that business.");

    await expect(LocatorAgent.resolve('nonexistent place xyz')).rejects.toThrow(
      'LocatorAgent failed to extract structured data from Gemini.',
    );
  });

  it('defaults lat and lng to 0 when Gemini omits coordinates', async () => {
    geminiReturns({
      name: 'Invisible Cafe',
      address: 'Unknown Street',
      officialUrl: 'https://invisible.com',
      // lat and lng intentionally omitted
    });

    const result = await LocatorAgent.resolve('Invisible Cafe');
    expect(result.coordinates).toEqual({ lat: 0, lng: 0 });
  });

  it('passes the original query verbatim to the Gemini prompt', async () => {
    geminiReturns({
      name: 'Test',
      address: 'Somewhere',
      officialUrl: 'https://test.com',
      lat: 0,
      lng: 0,
    });

    await LocatorAgent.resolve('my very specific query string 123');

    const [prompt] = mockGenerateContent.mock.calls[0];
    expect(prompt).toContain('my very specific query string 123');
  });
});
