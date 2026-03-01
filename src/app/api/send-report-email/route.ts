import { NextRequest, NextResponse } from 'next/server';
import { sendReportEmail, type EmailReportType } from '@/lib/email';

const VALID_REPORT_TYPES: EmailReportType[] = ['profile', 'margin', 'traffic', 'seo', 'competitive'];

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const { email, reportUrl, reportType, businessName, summary } = body;

    if (!email || !email.includes('@')) {
      return NextResponse.json({ error: 'Valid email is required.' }, { status: 400 });
    }
    if (!reportUrl) {
      return NextResponse.json({ error: 'reportUrl is required.' }, { status: 400 });
    }
    if (!reportType || !VALID_REPORT_TYPES.includes(reportType)) {
      return NextResponse.json(
        { error: `reportType must be one of: ${VALID_REPORT_TYPES.join(', ')}` },
        { status: 400 },
      );
    }
    if (!businessName) {
      return NextResponse.json({ error: 'businessName is required.' }, { status: 400 });
    }

    const result = await sendReportEmail({
      to: email,
      businessName,
      reportType,
      reportUrl,
      summary: summary || 'Your report is ready. Click below to view the full analysis.',
    });

    if (!result.success) {
      return NextResponse.json({ error: result.error || 'Failed to send email.' }, { status: 502 });
    }

    return NextResponse.json({ success: true, emailId: result.id });
  } catch (error: unknown) {
    console.error('[API/SendReportEmail] Failed:', error);
    return NextResponse.json({ error: 'Internal Server Error' }, { status: 500 });
  }
}
