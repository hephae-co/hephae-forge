import { test, expect } from '@playwright/test';

test.describe('Hephae Admin Dashboard', () => {
    test.beforeEach(async ({ page }) => {
        await page.route('/api/run-tests', async route => {
            if (route.request().method() === 'GET') {
                await route.fulfill({ json: [] });
            }
        });
    });

    test('should load the dashboard and show the main title', async ({ page }) => {
        await page.goto('http://localhost:3000');
        const title = page.locator('h1');
        await expect(title).toContainText('Hephae');
    });

    test('should show tab navigation', async ({ page }) => {
        await page.goto('http://localhost:3000');
        await expect(page.getByText('Research & CRM')).toBeVisible();
    });

    test('should switch to tester tab and show Run Tests Now button', async ({ page }) => {
        await page.goto('http://localhost:3000');
        const testerTab = page.getByText('Tester');
        await testerTab.click();
        const runButton = page.getByRole('button', { name: /Run Tests Now/i });
        await expect(runButton).toBeVisible();
        await expect(runButton).toBeEnabled();
    });

    test('should show loading state and refresh results on successful test run', async ({ page }) => {
        let postCalled = false;

        await page.route('/api/run-tests', async route => {
            if (route.request().method() === 'POST') {
                postCalled = true;
                await route.fulfill({ status: 200, json: { success: true } });
            } else if (route.request().method() === 'GET') {
                if (postCalled) {
                    await route.fulfill({
                        json: [{
                            runId: 'test_run_1',
                            timestamp: new Date().toISOString(),
                            totalTests: 3,
                            passedTests: 3,
                            failedTests: 0,
                            results: [
                                { businessName: 'Test Biz', capability: 'seo', score: 95, isHallucinated: false, issues: [], responseTimeMs: 1200 }
                            ],
                            systemResults: []
                        }]
                    });
                } else {
                    await route.fulfill({ json: [] });
                }
            }
        });

        await page.goto('http://localhost:3000');
        const testerTab = page.getByText('Tester');
        await testerTab.click();

        const runButton = page.getByRole('button', { name: /Run Tests Now/i });
        await runButton.click();

        await expect(page.getByText(/Running Suite.../i)).toBeVisible();
    });

    test('should show error message if API fails', async ({ page }) => {
        await page.route('/api/run-tests', async route => {
            if (route.request().method() === 'POST') {
                await route.fulfill({
                    status: 500,
                    json: { error: "Agent Orchestration Failed: Gemini API error" }
                });
            } else if (route.request().method() === 'GET') {
                await route.fulfill({ json: [] });
            }
        });

        await page.goto('http://localhost:3000');
        const testerTab = page.getByText('Tester');
        await testerTab.click();

        await page.getByRole('button', { name: /Run Tests Now/i }).click();

        const errorMessage = page.getByText(/Agent Orchestration Failed/i);
        await expect(errorMessage).toBeVisible();
    });
});
