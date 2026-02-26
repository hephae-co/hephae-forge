import { chromium } from 'playwright';
import { BaseIdentity, EnrichedProfile } from './types';

export class ProfilerAgent {
    static async profile(identity: BaseIdentity): Promise<EnrichedProfile> {
        let browser;
        try {
            console.log(`[ProfilerAgent] Profiling ${identity.name} at ${identity.officialUrl}...`);
            browser = await chromium.launch();
            const context = await browser.newContext({ ignoreHTTPSErrors: true });
            const page = await context.newPage();

            // Initial load - give it up to 30 seconds
            await page.goto(identity.officialUrl, { waitUntil: 'domcontentloaded', timeout: 30000 });

            // Extract Colors
            const colors = await page.evaluate<{ primary: string, secondary: string }>(`(() => {
                const getBg = (el) => window.getComputedStyle(el).backgroundColor;
                const bodyBg = getBg(document.body);
                const header = document.querySelector('header, nav, .navbar');
                const headerBg = header ? getBg(header) : 'rgb(0,0,0)';

                const rgbToHex = (rgb) => {
                    const result = rgb.match(/\\d+/g);
                    if (!result || result.length < 3) return "#000000";
                    return "#" + ((1 << 24) + (parseInt(result[0]) << 16) + (parseInt(result[1]) << 8) + (parseInt(result[2]))).toString(16).slice(1);
                };

                return {
                    primary: rgbToHex(headerBg !== 'rgba(0, 0, 0, 0)' ? headerBg : bodyBg),
                    secondary: rgbToHex(bodyBg)
                };
            })()`);

            // Extract Logo
            const logoUrl = await page.evaluate<string | undefined>(`(() => {
                const img = document.querySelector('img[src*="logo"], header img');
                return img ? img.src : undefined;
            })()`);

            // Determine Persona
            const persona = await page.evaluate<string>(`(() => {
                const text = document.body.innerText.toLowerCase();
                if (text.includes("est.") || text.includes("family owned") || text.includes("since 19")) return "Old School Jersey Diner";
                if (text.includes("artisanal") || text.includes("organic") || text.includes("brew")) return "Modern Cafe";
                return "Classic Neighborhood Spot";
            })()`);

            // Crawl Menu
            let menuScreenshotBase64: string | undefined;
            try {
                console.log("[ProfilerAgent] Looking for menu link...");
                const menuHref = await page.evaluate<string | null>(`(() => {
                    const anchors = Array.from(document.querySelectorAll('a'));
                    const menuLink = anchors.find(a =>
                        (a.innerText && a.innerText.toLowerCase().includes('menu')) ||
                        (a.href && a.href.toLowerCase().includes('menu'))
                    );
                    return menuLink ? menuLink.href : null;
                })()`);

                if (menuHref) {
                    console.log("[ProfilerAgent] Found menu link:", menuHref);
                    // Handle relative links properly
                    let finalMenuUrl = menuHref;
                    if (menuHref.startsWith('/')) {
                        const baseUrl = new URL(identity.officialUrl);
                        finalMenuUrl = `${baseUrl.origin}${menuHref}`;
                    }
                    await page.goto(finalMenuUrl, { waitUntil: 'domcontentloaded', timeout: 20000 });
                } else {
                    console.log("[ProfilerAgent] No menu link found, assuming homepage is the menu.");
                }

                await page.waitForTimeout(2000);
                const buffer = await page.screenshot({ fullPage: true, type: 'jpeg', quality: 60 });
                menuScreenshotBase64 = buffer.toString('base64');
                console.log("[ProfilerAgent] Menu screenshot captured.");

            } catch (err) {
                console.warn("[ProfilerAgent] Menu discovery failed:", err);
            }

            return {
                ...identity,
                primaryColor: colors.primary,
                secondaryColor: colors.secondary,
                logoUrl,
                persona,
                menuScreenshotBase64
            };

        } catch (error: any) {
            console.error("[ProfilerAgent] Failed:", error);
            return {
                ...identity, // Always return base state even on failure
                primaryColor: "#1e3a8a",
                secondaryColor: "#ffffff",
                persona: "Classic Neighborhood Spot",
                _debugError: error.message || error.toString()
            };
        } finally {
            if (browser) await browser.close();
        }
    }
}
