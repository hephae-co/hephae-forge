/**
 * Unit tests for src/lib/email.ts
 *
 * Covers: HTML template generation (structure, escaping, per-type accents)
 * and sendReportEmail (happy path, API error, network error).
 * The Resend SDK is fully mocked.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';

// ── mock Resend SDK ──────────────────────────────────────────────────────────

const mockSend = vi.fn();

vi.mock('resend', () => ({
  Resend: vi.fn(function MockResend() {
    return { emails: { send: mockSend } };
  }),
}));

import { buildReportEmailHtml, sendReportEmail, type SendReportEmailOptions } from '@/lib/email';

// ── helpers ──────────────────────────────────────────────────────────────────

const VALID_OPTS: SendReportEmailOptions = {
  to: 'owner@restaurant.com',
  businessName: 'Bosphorus Nutley',
  reportType: 'margin',
  reportUrl: 'https://storage.googleapis.com/everything-hephae/bosphorus-nutley/margin-123.html',
  summary: '$847 profit leakage detected. Score: 72/100',
};

beforeEach(() => {
  vi.clearAllMocks();
  mockSend.mockReset();
  process.env.RESEND_API_KEY = 'test_re_key';
});

// ── buildReportEmailHtml ─────────────────────────────────────────────────────

describe('buildReportEmailHtml', () => {
  it('returns a complete HTML document', () => {
    const html = buildReportEmailHtml(VALID_OPTS);
    expect(html).toContain('<!DOCTYPE html>');
    expect(html).toContain('</html>');
  });

  it('includes the business name', () => {
    const html = buildReportEmailHtml(VALID_OPTS);
    expect(html).toContain('Bosphorus Nutley');
  });

  it('includes the report URL as a clickable link', () => {
    const html = buildReportEmailHtml(VALID_OPTS);
    expect(html).toContain(VALID_OPTS.reportUrl);
    expect(html).toContain('View Full Report');
  });

  it('includes the summary text', () => {
    const html = buildReportEmailHtml(VALID_OPTS);
    expect(html).toContain('$847 profit leakage detected');
  });

  it('uses the correct report type label for margin', () => {
    const html = buildReportEmailHtml(VALID_OPTS);
    expect(html).toContain('Margin Surgery Report');
  });

  it('uses the dark theme background', () => {
    const html = buildReportEmailHtml(VALID_OPTS);
    expect(html).toContain('#0f172a');
  });

  it('escapes HTML special characters in business name', () => {
    const opts = { ...VALID_OPTS, businessName: '<script>alert("xss")</script>' };
    const html = buildReportEmailHtml(opts);
    expect(html).not.toContain('<script>');
    expect(html).toContain('&lt;script&gt;');
  });

  it('renders different accent colors for each report type', () => {
    const seoHtml = buildReportEmailHtml({ ...VALID_OPTS, reportType: 'seo' });
    const trafficHtml = buildReportEmailHtml({ ...VALID_OPTS, reportType: 'traffic' });
    expect(seoHtml).toContain('#a78bfa');
    expect(trafficHtml).toContain('#4ade80');
  });

  it('renders correct tagline per report type', () => {
    const html = buildReportEmailHtml({ ...VALID_OPTS, reportType: 'competitive' });
    expect(html).toContain('Know thy rivals');
  });
});

// ── sendReportEmail ──────────────────────────────────────────────────────────

describe('sendReportEmail', () => {
  it('sends email via Resend with correct parameters', async () => {
    mockSend.mockResolvedValue({ data: { id: 'email_123' }, error: null });

    const result = await sendReportEmail(VALID_OPTS);

    expect(result.success).toBe(true);
    expect(result.id).toBe('email_123');
    expect(mockSend).toHaveBeenCalledTimes(1);

    const callArgs = mockSend.mock.calls[0][0];
    expect(callArgs.from).toContain('chris@hephae.co');
    expect(callArgs.to).toEqual(['owner@restaurant.com']);
    expect(callArgs.subject).toContain('Bosphorus Nutley');
    expect(callArgs.html).toContain('<!DOCTYPE html>');
  });

  it('returns error when Resend API returns an error object', async () => {
    mockSend.mockResolvedValue({ data: null, error: { message: 'Invalid API key' } });

    const result = await sendReportEmail(VALID_OPTS);

    expect(result.success).toBe(false);
    expect(result.error).toBe('Invalid API key');
  });

  it('catches thrown exceptions and returns failure gracefully', async () => {
    mockSend.mockRejectedValue(new Error('Network timeout'));

    const result = await sendReportEmail(VALID_OPTS);

    expect(result.success).toBe(false);
    expect(result.error).toBe('Network timeout');
  });

  it('subject line includes the report type label', async () => {
    mockSend.mockResolvedValue({ data: { id: 'x' }, error: null });
    await sendReportEmail({ ...VALID_OPTS, reportType: 'seo' });

    const subject = mockSend.mock.calls[0][0].subject;
    expect(subject).toContain('SEO Deep Audit');
  });
});
