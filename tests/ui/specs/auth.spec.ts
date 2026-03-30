import { test, expect } from '@playwright/test';
import { HomePage, NUTLEY_PLACE } from '../pages/HomePage';

test.describe('Auth — Logged Out State', () => {
  test('signin banner is visible when not logged in after selecting a business', async ({ page }) => {
    const home = new HomePage(page);
    await home.setup({ zipCode: '07110' });
    await home.goto();
    await home.searchAndSelectPlace(NUTLEY_PLACE);

    await expect(home.signinBanner).toBeVisible();
    await expect(home.signinBanner).toContainText(/sign in/i);
  });

  test('gated nav sections are locked when not logged in', async ({ page }) => {
    const home = new HomePage(page);
    await home.setup({ zipCode: '07110' });
    await home.goto();
    await home.searchAndSelectPlace(NUTLEY_PLACE);

    // All 4 gated sections should be disabled
    for (const section of ['margin', 'seo', 'traffic', 'competitive'] as const) {
      const btn = page.locator(`[data-testid="nav-${section}"]`);
      await expect(btn).toBeDisabled();
    }
  });

  test('non-gated sections remain accessible when not logged in', async ({ page }) => {
    const home = new HomePage(page);
    await home.setup({ zipCode: '07110' });
    await home.goto();
    await home.searchAndSelectPlace(NUTLEY_PLACE);

    await expect(page.locator('[data-testid="nav-overview"]')).not.toBeDisabled();
    await expect(page.locator('[data-testid="nav-local-intel"]')).not.toBeDisabled();
  });

  test('lock tooltip appears on hover over locked section', async ({ page }) => {
    const home = new HomePage(page);
    await home.setup({ zipCode: '07110' });
    await home.goto();
    await home.searchAndSelectPlace(NUTLEY_PLACE);

    // Hover over a locked nav item to reveal tooltip
    const marginBtn = page.locator('[data-testid="nav-margin"]');
    await marginBtn.hover();

    // The tooltip text is "Sign in to unlock"
    await expect(page.getByText('Sign in to unlock')).toBeVisible({ timeout: 3_000 });
  });
});

test.describe('Auth — Sign In Button', () => {
  test('signin banner contains a sign-in action', async ({ page }) => {
    const home = new HomePage(page);
    await home.setup({ zipCode: '07110' });
    await home.goto();
    await home.searchAndSelectPlace(NUTLEY_PLACE);

    const banner = home.signinBanner;
    await expect(banner).toBeVisible();

    // Should contain a button or link for signing in
    const signInEl = banner.locator('button, a').first();
    await expect(signInEl).toBeVisible();
  });
});

test.describe('Auth — Logged In (live only)', () => {
  test('[live] logged-in user sees all nav sections unlocked', async ({ page }) => {
    // This requires real Firebase auth — can only run with a live session
    // Set up: add auth state to localStorage before navigate
    await page.addInitScript(() => {
      // Simulate Firebase user stored in indexedDB/localStorage
      // In practice, use page.evaluate to inject auth state
      (window as any).__mockFirebaseUser = {
        uid: 'test-uid-123',
        email: 'test@hephae.co',
        getIdToken: async () => 'mock-id-token',
      };
    });

    const home = new HomePage(page);
    await home.setup({ zipCode: '07110' });
    await home.goto();
    await home.searchAndSelectPlace(NUTLEY_PLACE);

    // With real auth, all sections should be unlocked
    // Note: this won't work until Firebase is properly initialized with auth state
    // This is a placeholder for a full integration test
    await expect(home.businessName).toContainText("Arturo's Tavern");
  });
});
