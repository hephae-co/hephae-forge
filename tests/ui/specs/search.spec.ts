import { test, expect } from '@playwright/test';
import { HomePage, NUTLEY_PLACE, NYC_PLACE } from '../pages/HomePage';

test.describe('Search & Business Selection', () => {
  test('landing page renders the search autocomplete', async ({ page }) => {
    const home = new HomePage(page);
    await home.setup();
    await home.goto();

    // The autocomplete container should be present
    await expect(home.searchContainer).toBeVisible({ timeout: 8_000 });
  });

  test('selecting a business in an ultralocal zip shows the dashboard', async ({ page }) => {
    const home = new HomePage(page);
    await home.setup({ zipCode: '07110' });
    await home.goto();

    await home.searchAndSelectPlace(NUTLEY_PLACE);

    // Business name appears in header
    await expect(home.businessName).toContainText("Arturo's Tavern");

    // Sidebar is visible with nav items
    await expect(page.locator('[data-testid="nav-overview"]')).toBeVisible();
    await expect(page.locator('[data-testid="nav-local-intel"]')).toBeVisible();
  });

  test('selecting a business in a non-ultralocal zip shows the dashboard', async ({ page }) => {
    const home = new HomePage(page);
    await home.setup({ zipCode: '10001' });
    await home.goto();

    await home.searchAndSelectPlace(NYC_PLACE);

    await expect(home.businessName).toContainText("Joe's Pizza NYC");
  });

  test('ultralocal zip shows "Live" badge in Local Intel section', async ({ page }) => {
    const home = new HomePage(page);
    await home.setup({ zipCode: '07110' });
    await home.goto();

    await home.searchAndSelectPlace(NUTLEY_PLACE);
    await home.navigateTo('local-intel');

    await expect(home.ultralocalBadge).toBeVisible();
    await expect(home.ultralocalBadge).toHaveText('Live');
  });

  test('non-ultralocal zip does NOT show "Live" badge', async ({ page }) => {
    const home = new HomePage(page);
    await home.setup({ zipCode: '10001' });
    await home.goto();

    await home.searchAndSelectPlace(NYC_PLACE);
    await home.navigateTo('local-intel');

    await expect(home.ultralocalBadge).not.toBeVisible();
  });

  test('non-ultralocal zip shows national coverage CTA banner', async ({ page }) => {
    const home = new HomePage(page);
    await home.setup({ zipCode: '10001' });
    await home.goto();

    await home.searchAndSelectPlace(NYC_PLACE);
    await home.navigateTo('local-intel');

    await expect(home.nationalCoverageBanner).toBeVisible();
    await expect(home.nationalCoverageBanner).toContainText('national benchmarks');
  });

  test('ultralocal zip does NOT show national coverage CTA banner', async ({ page }) => {
    const home = new HomePage(page);
    await home.setup({ zipCode: '07110' });
    await home.goto();

    await home.searchAndSelectPlace(NUTLEY_PLACE);
    await home.navigateTo('local-intel');

    await expect(home.nationalCoverageBanner).not.toBeVisible();
  });

  test('URL changes to /b/{slug} after selecting a business [live]', async ({ page }) => {
    // This test runs against real localhost — requires API to be up
    const home = new HomePage(page);
    await home.setup({ zipCode: '07110' });
    await home.goto();

    await home.searchAndSelectPlace(NUTLEY_PLACE);

    // URL should update to /b/arturos-tavern-nutley-nj or similar
    await expect(page).toHaveURL(/\/b\/.+/, { timeout: 8_000 });
  });
});
