/**
 * Unit tests for POST /api/chat
 *
 * Covers: missing/invalid request body, missing API key, successful
 * function-call handoff, graceful not-found fallback, and plain-text replies.
 * All external dependencies (Gemini SDK, LocatorAgent) are fully mocked.
 *
 * Note: vi.clearAllMocks() is used to preserve constructor mock implementations.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

// ── mock external deps before importing the route ─────────────────────────────
const mockSendMessage = vi.fn();
const mockStartChat = vi.fn();
const mockGetGenerativeModel = vi.fn();

vi.mock('@google/generative-ai', () => ({
  // Regular function: used with `new GoogleGenerativeAI(key)`
  GoogleGenerativeAI: vi.fn(function MockGenAI() {
    return { getGenerativeModel: mockGetGenerativeModel };
  }),
  SchemaType: { OBJECT: 'OBJECT', STRING: 'STRING' },
}));

vi.mock('@/agents/discovery/locator', () => ({
  LocatorAgent: { resolve: vi.fn() },
}));

import { POST } from '@/app/api/chat/route';
import { LocatorAgent } from '@/agents/discovery/locator';

// ── helpers ───────────────────────────────────────────────────────────────────

function makeRequest(body: unknown) {
  return new Request('http://localhost/api/chat', {
    method: 'POST',
    body: JSON.stringify(body),
    headers: { 'content-type': 'application/json' },
  }) as import('next/server').NextRequest;
}

function geminiRepliesWithText(text: string) {
  mockSendMessage.mockResolvedValue({
    response: {
      functionCalls: () => [],
      text: () => text,
    },
  });
}

function geminiCallsFunction(name: string, args: Record<string, unknown>) {
  mockSendMessage.mockResolvedValue({
    response: {
      functionCalls: () => [{ name, args }],
      text: () => '',
    },
  });
}

// ── env / mock reset ──────────────────────────────────────────────────────────

const ORIGINAL_KEY = process.env.GEMINI_API_KEY;

beforeEach(() => {
  vi.clearAllMocks();
  mockSendMessage.mockReset();
  mockStartChat.mockReset();
  mockGetGenerativeModel.mockReset();
  vi.mocked(LocatorAgent.resolve).mockReset();

  process.env.GEMINI_API_KEY = 'test-key';

  // Chain: getGenerativeModel(config) → { startChat }
  //        startChat(history) → { sendMessage }
  mockGetGenerativeModel.mockReturnValue({ startChat: mockStartChat });
  mockStartChat.mockReturnValue({ sendMessage: mockSendMessage });
});

afterEach(() => {
  process.env.GEMINI_API_KEY = ORIGINAL_KEY;
});

// ── tests ─────────────────────────────────────────────────────────────────────

describe('POST /api/chat', () => {
  // ── input validation ─────────────────────────────────────────────────────

  it('returns 400 when the messages field is missing entirely', async () => {
    const res = await POST(makeRequest({}));
    expect(res.status).toBe(400);
    const json = await res.json();
    expect(json.error).toBe('Invalid messages array');
  });

  it('returns 400 when messages is a string instead of an array', async () => {
    const res = await POST(makeRequest({ messages: 'hello' }));
    expect(res.status).toBe(400);
    const json = await res.json();
    expect(json.error).toBe('Invalid messages array');
  });

  it('returns 400 when messages is null', async () => {
    const res = await POST(makeRequest({ messages: null }));
    expect(res.status).toBe(400);
  });

  // ── API key guard ────────────────────────────────────────────────────────

  it('returns 500 when GEMINI_API_KEY is not set', async () => {
    delete process.env.GEMINI_API_KEY;
    const res = await POST(makeRequest({ messages: [{ role: 'user', text: 'hi' }] }));
    expect(res.status).toBe(500);
    const json = await res.json();
    expect(json.error).toMatch(/GEMINI_API_KEY/);
  });

  // ── function-call handoff ────────────────────────────────────────────────

  it('returns triggerCapabilityHandoff + locatedBusiness when LocatorAgent succeeds', async () => {
    const mockIdentity = {
      name: 'The Bosphorus',
      address: '111 Franklin Ave, Nutley, NJ',
      officialUrl: 'https://bosphorus.com',
      coordinates: { lat: 40.8218, lng: -74.1577 },
    };
    vi.mocked(LocatorAgent.resolve).mockResolvedValue(mockIdentity);
    geminiCallsFunction('locate_business', { query: 'The Bosphorus Nutley' });

    const res = await POST(makeRequest({ messages: [{ role: 'user', text: 'find The Bosphorus' }] }));

    expect(res.status).toBe(200);
    const json = await res.json();
    expect(json.triggerCapabilityHandoff).toBe(true);
    expect(json.locatedBusiness).toEqual(mockIdentity);
    expect(json.text).toContain('The Bosphorus');
  });

  it('calls LocatorAgent.resolve with the query from the function call args', async () => {
    vi.mocked(LocatorAgent.resolve).mockResolvedValue({
      name: 'X',
      officialUrl: 'https://x.com',
    });
    geminiCallsFunction('locate_business', { query: 'my special query' });

    await POST(makeRequest({ messages: [{ role: 'user', text: 'find X' }] }));

    expect(LocatorAgent.resolve).toHaveBeenCalledWith('my special query');
  });

  it('returns a graceful "couldn\'t locate" message when LocatorAgent throws', async () => {
    vi.mocked(LocatorAgent.resolve).mockRejectedValue(new Error('Gemini parse error'));
    geminiCallsFunction('locate_business', { query: 'Unknown Business XYZ' });

    const res = await POST(makeRequest({ messages: [{ role: 'user', text: 'find Unknown' }] }));

    expect(res.status).toBe(200);
    const json = await res.json();
    expect(json.text).toContain("couldn't locate");
    expect(json.triggerCapabilityHandoff).toBeUndefined();
    expect(json.locatedBusiness).toBeUndefined();
  });

  it('includes the original query in the not-found message', async () => {
    vi.mocked(LocatorAgent.resolve).mockRejectedValue(new Error('not found'));
    geminiCallsFunction('locate_business', { query: 'Pizzeria Bella Vista' });

    const res = await POST(makeRequest({ messages: [{ role: 'user', text: 'find Pizzeria' }] }));
    const json = await res.json();
    expect(json.text).toContain('Pizzeria Bella Vista');
  });

  // ── plain conversation replies ────────────────────────────────────────────

  it('returns a plain model message when Gemini does not call any function', async () => {
    geminiRepliesWithText('Hello! How can I assist you today?');

    const res = await POST(makeRequest({ messages: [{ role: 'user', text: 'hi' }] }));

    expect(res.status).toBe(200);
    const json = await res.json();
    expect(json.role).toBe('model');
    expect(json.text).toBe('Hello! How can I assist you today?');
    expect(json.triggerCapabilityHandoff).toBeUndefined();
  });

  it('returns 200 with an empty functionCalls array treated as plain reply', async () => {
    geminiRepliesWithText('I can help with that.');

    const res = await POST(makeRequest({ messages: [{ role: 'user', text: 'what can you do?' }] }));

    expect(res.status).toBe(200);
    const json = await res.json();
    expect(json.text).toBe('I can help with that.');
  });
});
