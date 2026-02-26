import { chromium } from 'playwright';

export async function generateSocialCard(
    businessName: string,
    totalLeakage: number,
    topItem: string
): Promise<Buffer> {
    // In a real implementation, we would spin up a browser, render a local HTML string, and screenshot it.
    // For this MVP, we will try to do exactly that using a data URI or a quick local page render.

    const html = `
    <html>
      <body style="width: 600px; height: 400px; margin: 0; background: linear-gradient(135deg, #1e3a8a 0%, #3b82f6 100%); display: flex; align-items: center; justify-content: center; font-family: sans-serif; color: white;">
        <div style="text-align: center; padding: 40px; border: 4px solid white; border-radius: 20px;">
          <h2 style="margin: 0; font-size: 24px; opacity: 0.9;">THE MENU SURGEON REPORT</h2>
          <h1 style="font-size: 48px; margin: 20px 0;">${businessName}</h1>
          <div style="font-size: 64px; font-weight: bold; margin-bottom: 10px;">$${totalLeakage.toLocaleString()}</div>
          <p style="font-size: 24px; margin: 0;">Potential Annual Profit Recovered</p>
          <div style="margin-top: 30px; padding: 10px 20px; background: rgba(255,255,255,0.2); border-radius: 50px;">
            Top Fix: ${topItem}
          </div>
        </div>
      </body>
    </html>
  `;

    const browser = await chromium.launch();
    try {
        const page = await browser.newPage();
        await page.setViewportSize({ width: 600, height: 400 });
        await page.setContent(html);
        const buffer = await page.screenshot({ type: 'png' });
        return buffer;
    } finally {
        await browser.close();
    }
}
