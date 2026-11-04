import { test, expect } from '@playwright/test';

test.describe('Configuration Module', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('http://localhost:5173');
    await page.click('text="Configuration"');
  });

  test('should load the configuration schema tree', async ({ page }) => {
    await expect(page.locator('.app-header')).toContainText('Configuration Management');
    await expect(page.locator('.app-content')).toBeVisible();
    
    // Check if the tree or cards representing config sections load
    await expect(page.locator('.config-dashboard-container').first()).toBeVisible();
  });
});
