/**
 * Unit tests for POST /api/capabilities/seo
 *
 * Covers: missing officialUrl → 400, successful report passthrough (200),
 * and graceful handling when the agent returns unparseable output.
 * The ADK Runner, SeoAuditorAgent, and marketing orchestrator are all mocked.
 *
 * Note: vi.clearAllMocks() preserves the constructor mock implementations
 * (which must be regular functions, not arrow functions).
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';

// ── mock ADK and agents ───────────────────────────────────────────────────────

const mockRunAsync = vi.fn();
const mockCreateSession = vi.fn();
const mockGetSession = vi.fn();

vi.mock('@google/adk', () => ({
  // Regular functions: these are called with `new` in the route.
  Runner: vi.fn(function MockRunner() { return { runAsync: mockRunAsync }; }),
  InMemorySessionService: vi.fn(function MockSession() {
    return { createSession: mockCreateSession, getSession: mockGetSession };
  }),
}));

vi.mock('@/agents/seo-auditor/seoAuditor', () => ({
  SeoAuditorAgent: {},
}));

vi.mock('@/agents/marketing-swarm/orchestrator', () => ({
  generateAndDraftMarketingContent: vi.fn(function() { return Promise.resolve(); }),
}));

import { POST } from '@/app/api/capabilities/seo/route';

// ── helpers ───────────────────────────────────────────────────────────────────

function makeRequest(body: unknown) {
  return new Request('http://localhost/api/capabilities/seo', {
    method: 'POST',
    body: JSON.stringify(body),
    headers: { 'content-type': 'application/json' },
  }) as import('next/server').NextRequest;
}

// Generator that yields nothing (empty agent run — no model output).
async function* emptyStream() {}

beforeEach(() => {
  vi.clearAllMocks();
  mockRunAsync.mockReset();
  mockCreateSession.mockReset();
  mockGetSession.mockReset();

  // Safe defaults for each test.
  mockRunAsync.mockImplementation(emptyStream);
  mockCreateSession.mockResolvedValue(undefined);
  mockGetSession.mockResolvedValue({ state: {} });
});

// ── tests ─────────────────────────────────────────────────────────────────────

describe('POST /api/capabilities/seo', () => {
  // ── input validation ─────────────────────────────────────────────────────

  it('returns 400 when identity has no officialUrl', async () => {
    const res = await POST(makeRequest({ identity: { name: 'Test Business' } }));
    expect(res.status).toBe(400);
    const json = await res.json();
    expect(json.error).toMatch(/No URL/i);
  });

  it('returns 400 when identity.officialUrl is an empty string', async () => {
    const res = await POST(makeRequest({ identity: { name: 'Test', officialUrl: '' } }));
    expect(res.status).toBe(400);
  });

  // ── successful run ────────────────────────────────────────────────────────

  it('returns 200 with session state when agent produces no direct text output', async () => {
    mockGetSession.mockResolvedValue({
      state: { overallScore: 72, summary: 'Decent SEO baseline.', sections: [] },
    });

    const res = await POST(
      makeRequest({ identity: { name: 'Test Biz', officialUrl: 'https://testbiz.com' } }),
    );

    expect(res.status).toBe(200);
    const json = await res.json();
    expect(json.overallScore).toBe(72);
    expect(json.url).toBe('https://testbiz.com');
  });

  it('always attaches the target URL from the identity to the report', async () => {
    mockGetSession.mockResolvedValue({ state: { overallScore: 55 } });

    const res = await POST(
      makeRequest({ identity: { name: 'Biz', officialUrl: 'https://mybiz.io' } }),
    );

    const json = await res.json();
    expect(json.url).toBe('https://mybiz.io');
  });

  it('parses direct JSON model output when the agent emits an agentMessage event', async () => {
    const report = {
      overallScore: 88,
      summary: 'Strong technical foundation.',
      sections: [{ id: 'technical', title: 'Technical SEO', score: 90, recommendations: [] }],
    };

    async function* streamWithReport() {
      yield {
        type: 'agentMessage',
        message: { role: 'model', parts: [{ text: JSON.stringify(report) }] },
      };
    }
    mockRunAsync.mockImplementation(streamWithReport);
    mockGetSession.mockResolvedValue({ state: {} });

    const res = await POST(
      makeRequest({ identity: { name: 'Biz', officialUrl: 'https://biz.com' } }),
    );

    expect(res.status).toBe(200);
    const json = await res.json();
    expect(json.overallScore).toBe(88);
    expect(json.sections).toHaveLength(1);
  });

  it('falls back to session state when agent text output is not valid JSON', async () => {
    async function* streamWithBadJson() {
      yield {
        type: 'agentMessage',
        message: { role: 'model', parts: [{ text: 'Analysis complete. Score is great!' }] },
      };
    }
    mockRunAsync.mockImplementation(streamWithBadJson);
    mockGetSession.mockResolvedValue({ state: { overallScore: 60 } });

    const res = await POST(
      makeRequest({ identity: { name: 'Biz', officialUrl: 'https://biz.com' } }),
    );

    expect(res.status).toBe(200);
    const json = await res.json();
    expect(json.overallScore).toBe(60);
  });

  it('strips ```json … ``` markdown fences from agent text output before parsing', async () => {
    const report = { overallScore: 77, sections: [] };

    async function* streamWithFencedJson() {
      yield {
        type: 'agentMessage',
        message: {
          role: 'model',
          parts: [{ text: `\`\`\`json\n${JSON.stringify(report)}\n\`\`\`` }],
        },
      };
    }
    mockRunAsync.mockImplementation(streamWithFencedJson);
    mockGetSession.mockResolvedValue({ state: {} });

    const res = await POST(
      makeRequest({ identity: { name: 'Biz', officialUrl: 'https://biz.com' } }),
    );

    const json = await res.json();
    expect(json.overallScore).toBe(77);
  });
});
