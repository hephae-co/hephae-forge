import { Page, Locator, expect } from '@playwright/test';
import { mockGoogleMaps, triggerPlaceSelect } from '../helpers/mockGoogleMaps';
import { setupMockApi, waitForOverview, MockApiOptions } from '../helpers/mockApi';

export interface PlaceData {
  name: string;
  address: string;
  zipCode: string | null;
  lat?: number;
  lng?: number;
  phone?: string;
  rating?: number;
}

export const NUTLEY_PLACE: PlaceData = {
  name: "Arturo's Tavern",
  address: '128 Washington Ave, Nutley, NJ 07110',
  zipCode: '07110',
  lat: 40.8182,
  lng: -74.1588,
  phone: '+19737515535',
  rating: 4.5,
};

export const NYC_PLACE: PlaceData = {
  name: "Joe's Pizza NYC",
  address: '7 Carmine St, New York, NY 10014',
  zipCode: '10001',
  lat: 40.7303,
  lng: -74.0023,
  rating: 4.3,
};

export class HomePage {
  readonly page: Page;

  // Landing elements
  readonly searchContainer: Locator;

  // Dashboard elements
  readonly businessName: Locator;
  readonly nationalCoverageBanner: Locator;
  readonly signinBanner: Locator;
  readonly ultralocalBadge: Locator;

  // Sidebar
  readonly sidebarSearch: Locator;

  constructor(page: Page) {
    this.page = page;
    this.searchContainer = page.locator('[data-testid="places-autocomplete"]');
    this.businessName = page.locator('[data-testid="business-name"]');
    this.nationalCoverageBanner = page.locator('[data-testid="national-coverage-banner"]');
    this.signinBanner = page.locator('[data-testid="signin-banner"]');
    this.ultralocalBadge = page.locator('[data-testid="ultralocal-badge"]');
    this.sidebarSearch = page.locator('[data-testid="sidebar-search"]');
  }

  async setup(opts?: MockApiOptions) {
    await mockGoogleMaps(this.page);
    if (opts !== undefined) {
      await setupMockApi(this.page, opts);
    }
  }

  async goto() {
    await this.page.goto('/');
  }

  async searchAndSelectPlace(place: PlaceData) {
    await triggerPlaceSelect(this.page, place);
    await waitForOverview(this.page);
    // Wait for business name to appear in the dashboard
    await expect(this.businessName).toContainText(place.name, { timeout: 10_000 });
  }

  /** Navigate to a dashboard section via the sidebar */
  async navigateTo(section: 'overview' | 'local-intel' | 'margin' | 'seo' | 'traffic' | 'competitive') {
    await this.page.locator(`[data-testid="nav-${section}"]`).click();
    await this.page.waitForTimeout(300); // small debounce for state update
  }

  /** Click the "Run Analysis" button on a locked/empty capability section */
  async clickRunCapability() {
    const btn = this.page.locator('[data-testid="run-capability"]').first();
    await btn.waitFor({ state: 'visible', timeout: 5_000 });
    await btn.click();
  }

  async isOnDashboard() {
    return this.businessName.isVisible();
  }
}
