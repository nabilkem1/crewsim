import { test, expect } from '@playwright/test';

test.describe('Cascade Analytics Module', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('http://localhost:5173');
    await page.click('text="Cascade Analytics"');
  });

  test('should render cascade summaries and policy comparisons', async ({ page }) => {
    await expect(page.locator('.app-header')).toContainText('Deep Cascade Analytics');
    
    // Check that the analytical grids loaded
    await expect(page.locator('.card').first()).toBeVisible();
  });
});
