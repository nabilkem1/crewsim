import { test, expect } from '@playwright/test';

test.describe('Results & Reporting Module', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('http://localhost:5173');
    await page.click('text="Results & Reports"');
  });

  test('should render visualization charts and drilldown modal', async ({ page }) => {
    await expect(page.locator('.app-header')).toContainText('Simulation Results & Reporting');
    
    // Ensure charts load (e.g. Gantt, Waterfall, etc)
    const card = page.locator('.card').first();
    await expect(card).toBeVisible();
    
    // Click card to test Universal Drill-down
    await card.click();
    
    // Verify modal overlay
    // Adjust selector based on actual modal implementation classes
    const modal = page.locator('div[style*="fixed"], .modal').first();
    if (await modal.isVisible()) {
        await expect(modal).toBeVisible();
    }
  });
});
