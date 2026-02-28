import { test, expect } from '@playwright/test';

test('Phase 14: Foot Traffic App Parity Verification', async ({ page }) => {
    // 1. Boot Application
    console.log('Navigating to Hephae Hub...');
    await page.goto('http://localhost:3000');

    // 2. Clear onboarding email modal if it exists
    const isEmailWallVisible = await page.isVisible('text="Become a Margin Surgeon"');
    if (isEmailWallVisible) {
        console.log('Clearing Email Wall...');
        await page.fill('input[type="email"]', 'test-automation@hephae.co');
        await page.fill('input[type="text"]', 'E2E Testing LLC');
        await page.click('button:has-text("Get My Free Traffic & Margin Suite")');
    }

    // 3. Enter Business
    console.log('Searching for target business...');
    const input = page.locator('input[placeholder="Search for a business, restaurant, or location..."]');
    await input.fill('The Bosphorus Mediterranean Cuisine Nutley');
    await page.waitForTimeout(2000); // Wait for Places API
    await page.keyboard.press('ArrowDown');
    await page.keyboard.press('Enter');

    // 4. Wait for the standard Chat UI to appear
    console.log('Waiting for Discovery to finish...');
    await expect(page.locator('text="Bosphorus"')).toBeVisible({ timeout: 15000 });

    // 5. Click the "Forecast Foot Traffic" Capability
    console.log('Triggering the Traffic Forecaster...');
    await page.click('button:has-text("Forecast Foot Traffic")');

    // 6. Wait for Forecaster AI generation to complete and render the Dashboard
    console.log('Waiting for AI generation (up to 45s)...');
    await expect(page.locator('text="Hephae Traffic forecaster"')).toBeVisible({ timeout: 45000 });

    // 7. Click a Heatmap Slot to trigger the DetailPanel
    console.log('Clicking the Heatmap grid...');
    // Find the first interactive slot button and click it
    const firstSlot = page.locator('button.cursor-pointer').first();
    await firstSlot.click();

    // 8. Verify the Restored "DetailPanel" Modal appears
    console.log('Verifying the DetailPanel Modal restoration...');
    await expect(page.locator('text="AI Logic & Raw Factors"')).toBeVisible({ timeout: 5000 });
    await expect(page.locator('text="👨‍🍳 Staffing?"')).toBeVisible({ timeout: 5000 });
    await expect(page.locator('text="📢 Promo Idea?"')).toBeVisible({ timeout: 5000 });

    // 9. Verify the newly added "Close Forecast" button exists
    console.log('Verifying the universal Close Button...');
    const closeBtn = page.locator('button[title="Close Forecast"]');
    await expect(closeBtn).toBeVisible();

    console.log('✅ Phase 14 UI Parity Successful.');
});
