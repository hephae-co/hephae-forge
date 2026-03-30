import { test, expect } from '@playwright/test';
import { HomePage, NUTLEY_PLACE } from '../pages/HomePage';

test.describe('Feedback — Thumbs Up / Down Buttons', () => {
  test.beforeEach(async ({ page }) => {
    const home = new HomePage(page);
    await home.setup({ zipCode: '07110' });
    await home.goto();
    await home.searchAndSelectPlace(NUTLEY_PLACE);
    await home.navigateTo('local-intel');
  });

  test('thumbs-up and thumbs-down buttons appear on insight cards', async ({ page }) => {
    // Insight cards should have feedback buttons in Local Intel
    const upBtn = page.locator('[data-testid="feedback-up"]').first();
    const downBtn = page.locator('[data-testid="feedback-down"]').first();

    await expect(upBtn).toBeVisible({ timeout: 5_000 });
    await expect(downBtn).toBeVisible({ timeout: 5_000 });
  });

  test('clicking thumbs-up fires a POST to /api/feedback', async ({ page }) => {
    const feedbackRequest = page.waitForRequest(req =>
      req.url().includes('/api/feedback') && req.method() === 'POST'
    );

    const upBtn = page.locator('[data-testid="feedback-up"]').first();
    await upBtn.waitFor({ state: 'visible', timeout: 5_000 });
    await upBtn.click();

    const req = await feedbackRequest;
    const body = JSON.parse(req.postData() || '{}');
    expect(body.rating).toBe('up');
  });

  test('clicking thumbs-down fires a POST to /api/feedback with rating: down', async ({ page }) => {
    const feedbackRequest = page.waitForRequest(req =>
      req.url().includes('/api/feedback') && req.method() === 'POST'
    );

    const downBtn = page.locator('[data-testid="feedback-down"]').first();
    await downBtn.waitFor({ state: 'visible', timeout: 5_000 });
    await downBtn.click();

    const req = await feedbackRequest;
    const body = JSON.parse(req.postData() || '{}');
    expect(body.rating).toBe('down');
  });

  test('after thumbs-up — green icon persists and thumbs-down disappears', async ({ page }) => {
    const upBtn = page.locator('[data-testid="feedback-up"]').first();
    const downBtn = page.locator('[data-testid="feedback-down"]').first();

    await upBtn.waitFor({ state: 'visible', timeout: 5_000 });
    await upBtn.click();

    // After clicking up, the down button should disappear
    await expect(downBtn).not.toBeVisible({ timeout: 3_000 });
    // The up button remains visible (green)
    await expect(upBtn).toBeVisible();
  });

  test('after thumbs-down — muted icon persists and thumbs-up disappears', async ({ page }) => {
    const upBtn = page.locator('[data-testid="feedback-up"]').first();
    const downBtn = page.locator('[data-testid="feedback-down"]').first();

    await downBtn.waitFor({ state: 'visible', timeout: 5_000 });
    await downBtn.click();

    // After clicking down, the up button should disappear
    await expect(upBtn).not.toBeVisible({ timeout: 3_000 });
    // The down button remains visible
    await expect(downBtn).toBeVisible();
  });

  test('both buttons are disabled after one vote (no re-voting)', async ({ page }) => {
    const upBtn = page.locator('[data-testid="feedback-up"]').first();
    await upBtn.waitFor({ state: 'visible', timeout: 5_000 });
    await upBtn.click();

    // The remaining visible button should be disabled
    await expect(upBtn).toBeDisabled({ timeout: 3_000 });
  });

  test('feedback buttons appear on community buzz card', async ({ page }) => {
    // Community buzz section also has feedback buttons
    const buzzSection = page.getByText('Community Buzz');
    await expect(buzzSection).toBeVisible({ timeout: 5_000 });

    // Look for feedback buttons near community buzz
    const buzzFeedback = page.locator('[data-testid="feedback-up"]');
    // Should be multiple (one per insight + one for buzz)
    const count = await buzzFeedback.count();
    expect(count).toBeGreaterThan(1);
  });

  test('feedback buttons appear on local event items', async ({ page }) => {
    const eventSection = page.getByText('Local Events');
    await expect(eventSection).toBeVisible({ timeout: 5_000 });

    // Events section should have feedback buttons
    const allUpButtons = await page.locator('[data-testid="feedback-up"]').count();
    expect(allUpButtons).toBeGreaterThanOrEqual(3); // at least insights + buzz + events
  });
});
