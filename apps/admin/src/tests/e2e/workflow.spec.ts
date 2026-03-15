import { test, expect } from '@playwright/test';

test.describe('Hephae Admin Workflow Lifecycle', () => {
    const MOCK_WORKFLOW_ID = 'wf_12345';
    const MOCK_BUSINESS_SLUG = 'test-pizzeria-1';

    test.beforeEach(async ({ page }) => {
        // Initial workflows list
        await page.route('/api/workflows', async route => {
            if (route.request().method() === 'GET') {
                await route.fulfill({ json: [] });
            } else if (route.request().method() === 'POST') {
                await route.fulfill({ json: { workflowId: MOCK_WORKFLOW_ID } });
            }
        });
    });

    test('should complete full DISCOVERY -> APPROVAL -> COMPLETED lifecycle', async ({ page }) => {
        await page.goto('http://localhost:3000');

        // 1. Launch a new workflow
        await page.fill('input[placeholder="07110"]', '07110');
        await page.selectOption('select', 'Pizza Shops');
        
        // Mock the GET workflow call for the "discovery" phase
        await page.route(`/api/workflows/${MOCK_WORKFLOW_ID}`, async route => {
            await route.fulfill({
                json: {
                    id: MOCK_WORKFLOW_ID,
                    phase: 'discovery',
                    zipCode: '07110',
                    businessType: 'Pizza Shops',
                    progress: {
                        totalBusinesses: 5,
                        analysisComplete: 0,
                        qualityPassed: 0,
                        outreachComplete: 0
                    },
                    businesses: [
                        { slug: MOCK_BUSINESS_SLUG, name: 'Test Pizzeria', address: '123 Main St', phase: 'pending', capabilitiesCompleted: [], capabilitiesFailed: [], evaluations: {} }
                    ]
                }
            });
        });

        await page.click('[data-testid="launch-button"]');

        // 2. Verify DISCOVERY phase UI
        const stepper = page.locator('[data-testid="phase-stepper"]');
        await expect(stepper).toHaveAttribute('data-phase', 'discovery');
        await expect(page.locator('[data-testid="counter-discovered"]')).toContainText('5');

        // 3. Transition to APPROVAL phase (mocking new data)
        await page.route(`/api/workflows/${MOCK_WORKFLOW_ID}`, async route => {
            await route.fulfill({
                json: {
                    id: MOCK_WORKFLOW_ID,
                    phase: 'approval',
                    zipCode: '07110',
                    businessType: 'Pizza Shops',
                    progress: {
                        totalBusinesses: 5,
                        analysisComplete: 5,
                        qualityPassed: 4,
                        outreachComplete: 0
                    },
                    businesses: [
                        { 
                            slug: MOCK_BUSINESS_SLUG, 
                            name: 'Test Pizzeria', 
                            address: '123 Main St', 
                            phase: 'evaluation_done', 
                            qualityPassed: true,
                            capabilitiesCompleted: ['seo', 'traffic'], 
                            capabilitiesFailed: [], 
                            evaluations: {
                                'seo': { score: 85, isHallucinated: false }
                            } 
                        }
                    ]
                }
            });
        });

        // The UI should update (polling or manual trigger in mock-world)
        // In real app, SSE or polling would trigger this. Here we wait for the mock to be picked up.
        await expect(stepper).toHaveAttribute('data-phase', 'approval', { timeout: 10000 });
        
        // 4. Verify Approval UI elements
        const bizCard = page.locator(`[data-testid="business-card-${MOCK_BUSINESS_SLUG}"]`);
        await expect(bizCard).toBeVisible();
        await expect(bizCard.locator('button .lucide-thumbs-up')).toBeVisible();

        // 5. Submit Approval
        await page.route(`/api/workflows/${MOCK_WORKFLOW_ID}/approve`, async route => {
            await route.fulfill({ json: { success: true } });
        });
        
        await bizCard.locator('button .lucide-thumbs-up').click();
        
        // Mock transition to COMPLETED after approval
        await page.route(`/api/workflows/${MOCK_WORKFLOW_ID}`, async route => {
            await route.fulfill({
                json: {
                    id: MOCK_WORKFLOW_ID,
                    phase: 'completed',
                    zipCode: '07110',
                    businessType: 'Pizza Shops',
                    progress: {
                        totalBusinesses: 5,
                        analysisComplete: 5,
                        qualityPassed: 4,
                        outreachComplete: 1
                    },
                    businesses: [
                        { slug: MOCK_BUSINESS_SLUG, name: 'Test Pizzeria', address: '123 Main St', phase: 'outreach_done', capabilitiesCompleted: ['seo'], capabilitiesFailed: [], evaluations: {} }
                    ]
                }
            });
        });

        await page.click('button:has-text("Submit Approvals")');
        
        await expect(page.getByText(/Pipeline complete/i)).toBeVisible();
        await expect(stepper).toHaveAttribute('data-phase', 'completed');
    });
});
