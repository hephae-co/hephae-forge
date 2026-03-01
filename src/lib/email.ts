import { Resend } from 'resend';

// ---------------------------------------------------------------------------
// Singleton Resend client
// ---------------------------------------------------------------------------

let resendClient: Resend | null = null;

function getResendClient(): Resend {
  if (!resendClient) {
    const apiKey = process.env.RESEND_API_KEY;
    if (!apiKey) throw new Error('[Email] RESEND_API_KEY is not set');
    resendClient = new Resend(apiKey);
  }
  return resendClient;
}

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type EmailReportType = 'profile' | 'margin' | 'traffic' | 'seo' | 'competitive';

export interface SendReportEmailOptions {
  to: string;
  businessName: string;
  reportType: EmailReportType;
  reportUrl: string;
  summary: string;
}

// ---------------------------------------------------------------------------
// Report type metadata
// ---------------------------------------------------------------------------

const REPORT_META: Record<EmailReportType, { label: string; accent: string; tagline: string }> = {
  profile:     { label: 'Business Profile',      accent: '#818cf8', tagline: 'Your digital identity, decoded.' },
  margin:      { label: 'Margin Surgery Report',  accent: '#f87171', tagline: 'We found the invisible bleed in your margins.' },
  traffic:     { label: 'Foot Traffic Forecast',  accent: '#4ade80', tagline: 'Your 3-day traffic crystal ball is ready.' },
  seo:         { label: 'SEO Deep Audit',         accent: '#a78bfa', tagline: 'Your search visibility, dissected.' },
  competitive: { label: 'Competitive Strategy',   accent: '#fb923c', tagline: 'Know thy rivals. Then outmaneuver them.' },
};

// ---------------------------------------------------------------------------
// HTML email template
// ---------------------------------------------------------------------------

export function buildReportEmailHtml(opts: SendReportEmailOptions): string {
  const meta = REPORT_META[opts.reportType] || REPORT_META.profile;

  const esc = (s: string) =>
    s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');

  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>${esc(meta.label)} - ${esc(opts.businessName)}</title>
</head>
<body style="margin:0;padding:0;background-color:#0f172a;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color:#0f172a;">
    <tr>
      <td align="center" style="padding:40px 20px;">
        <table role="presentation" width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;">

          <!-- HEADER -->
          <tr>
            <td style="background:linear-gradient(135deg,#4f46e5 0%,#7c3aed 100%);border-radius:16px 16px 0 0;padding:32px 40px;text-align:center;">
              <div style="font-size:24px;font-weight:800;color:#ffffff;margin-bottom:4px;">Hephae</div>
              <div style="font-size:13px;color:rgba(255,255,255,0.7);">Surgical Intelligence for Local Businesses</div>
            </td>
          </tr>

          <!-- BODY -->
          <tr>
            <td style="background:rgba(255,255,255,0.03);border-left:1px solid rgba(255,255,255,0.08);border-right:1px solid rgba(255,255,255,0.08);padding:40px;">

              <!-- Report badge -->
              <div style="text-align:center;margin-bottom:24px;">
                <span style="display:inline-block;background:${meta.accent}22;color:${meta.accent};border:1px solid ${meta.accent}44;padding:6px 16px;border-radius:999px;font-size:12px;font-weight:700;letter-spacing:0.05em;text-transform:uppercase;">${esc(meta.label)}</span>
              </div>

              <!-- Business name -->
              <div style="text-align:center;margin-bottom:8px;">
                <span style="font-size:22px;font-weight:800;color:#e2e8f0;">${esc(opts.businessName)}</span>
              </div>

              <!-- Tagline -->
              <div style="text-align:center;margin-bottom:28px;">
                <span style="font-size:14px;color:${meta.accent};font-style:italic;">${esc(meta.tagline)}</span>
              </div>

              <!-- Summary card -->
              <div style="background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);border-radius:12px;padding:20px 24px;margin-bottom:32px;">
                <div style="font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:0.08em;color:rgba(226,232,240,0.5);margin-bottom:10px;">Key Findings</div>
                <div style="font-size:15px;color:#e2e8f0;line-height:1.65;">${esc(opts.summary)}</div>
              </div>

              <!-- CTA Button -->
              <div style="text-align:center;margin-bottom:16px;">
                <a href="${esc(opts.reportUrl)}" target="_blank" style="display:inline-block;background:linear-gradient(135deg,#4f46e5 0%,#7c3aed 100%);color:#ffffff;font-weight:700;font-size:16px;padding:14px 40px;border-radius:12px;text-decoration:none;">
                  View Full Report &rarr;
                </a>
              </div>

              <div style="text-align:center;font-size:12px;color:rgba(226,232,240,0.35);margin-top:8px;">
                This report is hosted securely and accessible anytime.
              </div>
            </td>
          </tr>

          <!-- FOOTER -->
          <tr>
            <td style="background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.06);border-top:none;border-radius:0 0 16px 16px;padding:24px 40px;text-align:center;">
              <div style="font-size:12px;color:rgba(226,232,240,0.3);line-height:1.6;">
                Powered by <a href="https://hephae.co" style="color:#818cf8;text-decoration:none;">Hephae</a><br/>
                Surgical intelligence, delivered.
              </div>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>`;
}

// ---------------------------------------------------------------------------
// Send report email
// ---------------------------------------------------------------------------

export async function sendReportEmail(
  opts: SendReportEmailOptions,
): Promise<{ success: boolean; id?: string; error?: string }> {
  try {
    const resend = getResendClient();
    const meta = REPORT_META[opts.reportType] || REPORT_META.profile;

    const { data, error } = await resend.emails.send({
      from: 'Chris from Hephae <chris@hephae.co>',
      to: [opts.to],
      subject: `${meta.label} Ready: ${opts.businessName}`,
      html: buildReportEmailHtml(opts),
    });

    if (error) {
      console.error('[Email] Resend API error:', error);
      return { success: false, error: error.message };
    }

    console.log(`[Email] Sent ${opts.reportType} report email to ${opts.to} (id: ${data?.id})`);
    return { success: true, id: data?.id };
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : String(err);
    console.error('[Email] Failed to send report email:', message);
    return { success: false, error: message };
  }
}
