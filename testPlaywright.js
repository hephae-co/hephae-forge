const { chromium } = require('playwright');

async function test() {
    console.log("Launching browser...");
    const browser = await chromium.launch();
    const context = await browser.newContext();
    const page = await context.newPage();

    console.log("Navigating to app...");
    await page.goto('http://localhost:3000', { waitUntil: 'networkidle' });

    console.log("Locating the initial search input...");
    const inputs = await page.locator('input[type="text"]');
    if (await inputs.count() > 0) {
        await inputs.first().fill('Bosphorus in Nutley');
        await page.keyboard.press('Enter');
    } else {
        const textareas = await page.locator('textarea');
        if (await textareas.count() > 0) {
            await textareas.first().fill('Bosphorus in Nutley');
            await page.keyboard.press('Enter');
        }
    }

    console.log("Waiting dynamically up to 3m for business resolution and capability buttons...");

    try {
        const button = page.locator('button', { hasText: 'Run SEO Deep Audit' }).first();
        await button.waitFor({ state: 'visible', timeout: 180000 });

        console.log("Looking for 'Run SEO Deep Audit' button...");
        await button.click();

        console.log("Waiting for Email Wall to appear...");
        const emailInput = page.locator('input[type="email"], input[placeholder="Enter your email address..."]').first();
        await emailInput.waitFor({ state: 'visible', timeout: 10000 });
        await emailInput.fill('test@example.com');
        await page.keyboard.press('Enter');

        console.log("Email submitted! Waiting 90s for ADK Agent to finish...");

        // SEO agent requires 1-2 Google Searches and a Pro generation.
        const header = page.locator('h2', { hasText: 'SEO Infrastructure Assessment' }).first();
        await header.waitFor({ state: 'visible', timeout: 90000 });

        // Wait another 3s for animations
        await page.waitForTimeout(3000);

        await page.screenshot({ path: 'seo_integration_success.png', fullPage: true });
        console.log("Screenshot saved.");
    } catch (e) {
        console.log("Failed to find capability button or execute agent. Snapshotting state.");
        await page.screenshot({ path: 'seo_integration_fail.png', fullPage: true });
    }

    await browser.close();
}

test();
