import { test, expect } from '@playwright/test';

test.describe('Dashboard Module', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('http://localhost:5173');
    await page.click('text="Dashboard"');
  });

  test('should load the dashboard and display platform overview', async ({ page }) => {
    // Verify header updates
    await expect(page.locator('.app-header')).toContainText('Platform Overview');
    
    // Verify key metrics exist
    const content = page.locator('.app-content');
    await expect(content).toBeVisible();
    // Verify cards are loaded
    await expect(page.locator('.card').first()).toBeVisible();
  });
});
