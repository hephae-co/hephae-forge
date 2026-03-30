import { Page, Route } from '@playwright/test';
import * as fs from 'fs';
import * as path from 'path';

const FIXTURES_DIR = path.join(__dirname, '../fixtures');

function loadFixture(name: string) {
  return JSON.parse(fs.readFileSync(path.join(FIXTURES_DIR, name), 'utf-8'));
}

export interface MockApiOptions {
  zipCode?: '07110' | '10001';
  /** Provide a custom overview response to override the fixture */
  overviewOverride?: object;
  /** If true, simulate all capability routes returning 200 with fixture data */
  mockCapabilities?: boolean;
  /** Simulate the user as logged in (Firebase token check) */
  mockAuth?: boolean;
}

/**
 * Set up all API route mocks for a mocked test run.
 * Call BEFORE page.goto('/').
 */
export async function setupMockApi(page: Page, opts: MockApiOptions = {}) {
  const { zipCode = '07110', overviewOverride, mockCapabilities = true, mockAuth = false } = opts;
  const isUltralocal = zipCode === '07110';

  const zipcodeFixture = isUltralocal
    ? loadFixture('validate-zipcode-ultralocal.json')
    : loadFixture('validate-zipcode-national.json');

  const overviewFixture = overviewOverride ?? (
    isUltralocal
      ? loadFixture('overview-ultralocal.json')
      : loadFixture('overview-national.json')
  );

  // Intercept zipcode validation
  await page.route('**/api/places/validate-zipcode**', async (route: Route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(zipcodeFixture),
    });
  });

  // Intercept overview
  await page.route('**/api/overview', async (route: Route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(overviewFixture),
    });
  });

  // Intercept save (non-critical — just ack)
  await page.route('**/api/b/save', async (route: Route) => {
    await route.fulfill({ status: 200, body: JSON.stringify({ ok: true }) });
  });

  // Intercept track
  await page.route('**/api/track', async (route: Route) => {
    await route.fulfill({ status: 200, body: JSON.stringify({ ok: true }) });
  });

  // Intercept feedback
  await page.route('**/api/feedback', async (route: Route) => {
    await route.fulfill({ status: 200, body: JSON.stringify({ ok: true }) });
  });

  if (mockCapabilities) {
    // SEO capability
    await page.route('**/api/capabilities/seo', async (route: Route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(loadFixture('seo.json')),
      });
    });

    // Traffic / foot traffic capability
    await page.route('**/api/capabilities/traffic', async (route: Route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(loadFixture('traffic.json')),
      });
    });

    // Margin (uses /api/analyze)
    await page.route('**/api/analyze', async (route: Route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(loadFixture('margin.json')),
      });
    });

    // Competitive
    await page.route('**/api/capabilities/competitive', async (route: Route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(loadFixture('competitive.json')),
      });
    });
  }

  if (mockAuth) {
    // Mock Firebase identity token endpoint (used by useApiClient)
    await page.route('**/identitytoolkit.googleapis.com/**', async (route: Route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          idToken: 'mock-firebase-token',
          email: 'test@hephae.co',
          localId: 'mock-uid-123',
        }),
      });
    });
  }
}

/**
 * Wait for the overview call to complete and the dashboard to render.
 * Use after triggerPlaceSelect().
 */
export async function waitForOverview(page: Page) {
  await page.waitForResponse('**/api/overview', { timeout: 10_000 });
}

/**
 * Wait for a specific capability response.
 */
export async function waitForCapability(page: Page, cap: 'seo' | 'traffic' | 'analyze' | 'competitive') {
  const urlMap: Record<string, string> = {
    seo: '**/api/capabilities/seo',
    traffic: '**/api/capabilities/traffic',
    analyze: '**/api/analyze',
    competitive: '**/api/capabilities/competitive',
  };
  await page.waitForResponse(urlMap[cap], { timeout: 15_000 });
}
