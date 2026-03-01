/**
 * Unit tests for POST /api/send-report-email
 *
 * Covers: input validation (missing/invalid fields → 400),
 * successful send (200), and upstream failure (502).
 * The email utility is fully mocked.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';

const { mockSendReportEmail } = vi.hoisted(() => ({
  mockSendReportEmail: vi.fn(),
}));

vi.mock('@/lib/email', () => ({
  sendReportEmail: mockSendReportEmail,
}));

import { POST } from '@/app/api/send-report-email/route';

// ── helpers ──────────────────────────────────────────────────────────────────

function makeRequest(body: unknown) {
  return new Request('http://localhost/api/send-report-email', {
    method: 'POST',
    body: JSON.stringify(body),
    headers: { 'content-type': 'application/json' },
  }) as import('next/server').NextRequest;
}

beforeEach(() => {
  vi.clearAllMocks();
  mockSendReportEmail.mockReset();
});

// ── tests ────────────────────────────────────────────────────────────────────

describe('POST /api/send-report-email', () => {
  it('returns 400 when email is missing', async () => {
    const res = await POST(makeRequest({ reportUrl: 'https://x.com', reportType: 'margin', businessName: 'Test' }));
    expect(res.status).toBe(400);
  });

  it('returns 400 when email is invalid', async () => {
    const res = await POST(makeRequest({ email: 'notanemail', reportUrl: 'https://x.com', reportType: 'margin', businessName: 'Test' }));
    expect(res.status).toBe(400);
  });

  it('returns 400 when reportUrl is missing', async () => {
    const res = await POST(makeRequest({ email: 'a@b.com', reportType: 'margin', businessName: 'Test' }));
    expect(res.status).toBe(400);
  });

  it('returns 400 for invalid reportType', async () => {
    const res = await POST(makeRequest({ email: 'a@b.com', reportUrl: 'https://x.com', reportType: 'invalid', businessName: 'Test' }));
    expect(res.status).toBe(400);
  });

  it('returns 400 when businessName is missing', async () => {
    const res = await POST(makeRequest({ email: 'a@b.com', reportUrl: 'https://x.com', reportType: 'margin' }));
    expect(res.status).toBe(400);
  });

  it('returns 200 on successful send', async () => {
    mockSendReportEmail.mockResolvedValue({ success: true, id: 'email_abc' });

    const res = await POST(makeRequest({
      email: 'owner@biz.com',
      reportUrl: 'https://storage.googleapis.com/everything-hephae/test/margin-1.html',
      reportType: 'margin',
      businessName: 'Test Biz',
      summary: 'Leakage detected',
    }));

    expect(res.status).toBe(200);
    const json = await res.json();
    expect(json.success).toBe(true);
    expect(json.emailId).toBe('email_abc');
  });

  it('returns 502 when email sending fails', async () => {
    mockSendReportEmail.mockResolvedValue({ success: false, error: 'Rate limit exceeded' });

    const res = await POST(makeRequest({
      email: 'owner@biz.com',
      reportUrl: 'https://x.com/report.html',
      reportType: 'seo',
      businessName: 'Test',
    }));

    expect(res.status).toBe(502);
  });

  it('provides a default summary when none is given', async () => {
    mockSendReportEmail.mockResolvedValue({ success: true, id: 'x' });

    await POST(makeRequest({
      email: 'a@b.com',
      reportUrl: 'https://x.com',
      reportType: 'traffic',
      businessName: 'Biz',
    }));

    const callArgs = mockSendReportEmail.mock.calls[0][0];
    expect(callArgs.summary).toContain('Your report is ready');
  });

  it('passes correct options to sendReportEmail', async () => {
    mockSendReportEmail.mockResolvedValue({ success: true, id: 'y' });

    await POST(makeRequest({
      email: 'test@example.com',
      reportUrl: 'https://example.com/report.html',
      reportType: 'competitive',
      businessName: 'My Restaurant',
      summary: 'Custom summary here',
    }));

    expect(mockSendReportEmail).toHaveBeenCalledWith({
      to: 'test@example.com',
      reportUrl: 'https://example.com/report.html',
      reportType: 'competitive',
      businessName: 'My Restaurant',
      summary: 'Custom summary here',
    });
  });
});
