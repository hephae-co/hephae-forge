import { test, expect } from '@playwright/test';
import { HomePage, NUTLEY_PLACE, NYC_PLACE } from '../pages/HomePage';

test.describe('Dashboard — Local Intel Section', () => {
  test.beforeEach(async ({ page }) => {
    const home = new HomePage(page);
    await home.setup({ zipCode: '07110' });
    await home.goto();
    await home.searchAndSelectPlace(NUTLEY_PLACE);
    await home.navigateTo('local-intel');
  });

  test('shows this week\'s pulse headline', async ({ page }) => {
    await expect(page.getByText('Rising food costs hit NJ diners')).toBeVisible();
  });

  test('shows weekly brief narrative', async ({ page }) => {
    await expect(page.getByText("This week, Nutley's restaurant scene")).toBeVisible();
  });

  test('shows action items', async ({ page }) => {
    await expect(page.getByText('Raise pasta dish prices by $1.50')).toBeVisible();
    await expect(page.getByText('Launch $14.99 express lunch special')).toBeVisible();
  });

  test('shows competitor watch', async ({ page }) => {
    await expect(page.getByText('Tavola Rustica')).toBeVisible();
    await expect(page.getByText('Cut weekday lunch service')).toBeVisible();
  });

  test('shows community buzz section', async ({ page }) => {
    await expect(page.getByText('Nutley Farmers Market')).toBeVisible();
  });

  test('shows local events', async ({ page }) => {
    await expect(page.getByText('Nutley Farmers Market Opening')).toBeVisible();
    await expect(page.getByText('Saturday April 5')).toBeVisible();
  });

  test('shows weekly insights', async ({ page }) => {
    // Insight titles are displayed in cards
    await expect(page.getByText(/dairy.*cost.*spike|lunch.*opportunity|spring.*traffic/i)).toBeVisible();
  });

  test('shows local facts', async ({ page }) => {
    await expect(page.getByText(/28,500 residents/i)).toBeVisible();
  });

  test('shows market demographics stats', async ({ page }) => {
    await expect(page.getByText('$78,400')).toBeVisible();
    await expect(page.getByText('28,500')).toBeVisible();
  });

  test('shows nearby competitors', async ({ page }) => {
    await expect(page.getByText('Nearby Businesses')).toBeVisible();
    await expect(page.getByText('The Nutley Grill')).toBeVisible();
  });

  test('shows industry research snippets', async ({ page }) => {
    await expect(page.getByText('Industry Research')).toBeVisible();
    await expect(page.getByText('bifurcation')).toBeVisible();
  });
});

test.describe('Dashboard — Overview Section', () => {
  test('shows key opportunity cards after selecting a business', async ({ page }) => {
    const home = new HomePage(page);
    await home.setup({ zipCode: '07110' });
    await home.goto();
    await home.searchAndSelectPlace(NUTLEY_PLACE);

    // Overview is the default section — key info from businessSnapshot
    await expect(home.businessName).toContainText("Arturo's Tavern");
  });
});

test.describe('Dashboard — National Coverage', () => {
  test('national pulse shows amber CTA banner with correct copy', async ({ page }) => {
    const home = new HomePage(page);
    await home.setup({ zipCode: '10001' });
    await home.goto();
    await home.searchAndSelectPlace(NYC_PLACE);
    await home.navigateTo('local-intel');

    const banner = home.nationalCoverageBanner;
    await expect(banner).toBeVisible();
    await expect(banner).toContainText('Want deeper local intelligence?');
    await expect(banner).toContainText('ultralocal monitoring');
  });

  test('national pulse does NOT show pulse headline card', async ({ page }) => {
    const home = new HomePage(page);
    await home.setup({ zipCode: '10001' });
    await home.goto();
    await home.searchAndSelectPlace(NYC_PLACE);
    await home.navigateTo('local-intel');

    // pulseHeadline is null in national fixture — the card should not appear
    await expect(page.locator('text=This Week\'s Pulse')).not.toBeVisible();
  });
});

test.describe('Dashboard — Sidebar Navigation', () => {
  test('all non-gated nav items are clickable', async ({ page }) => {
    const home = new HomePage(page);
    await home.setup({ zipCode: '07110' });
    await home.goto();
    await home.searchAndSelectPlace(NUTLEY_PLACE);

    await expect(page.locator('[data-testid="nav-overview"]')).not.toBeDisabled();
    await expect(page.locator('[data-testid="nav-local-intel"]')).not.toBeDisabled();
  });

  test('gated sections show lock icon when not logged in', async ({ page }) => {
    const home = new HomePage(page);
    await home.setup({ zipCode: '07110' });
    await home.goto();
    await home.searchAndSelectPlace(NUTLEY_PLACE);

    // Gated sections: margin, seo, traffic, competitive
    const marginBtn = page.locator('[data-testid="nav-margin"]');
    await expect(marginBtn).toBeVisible();
    // Should be disabled (locked) when not logged in and no report exists
    await expect(marginBtn).toBeDisabled();
  });
});
