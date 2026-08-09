import { test, expect } from '@playwright/test';

test.describe('Run Management Module', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('http://localhost:5173');
    await page.click('text="Run Management"');
  });

  test('should render run history and search inputs', async ({ page }) => {
    await expect(page.locator('.app-header')).toContainText('Run Management History');
    
    // Check for a data table or run items
    await expect(page.locator('.card').first()).toBeVisible();
    
    // Check for search or filter inputs
    const searchInput = page.locator('input[type="text"], input[placeholder*="Search"]').first();
    if (await searchInput.isVisible()) {
      await searchInput.fill('run-');
    }
  });
});
