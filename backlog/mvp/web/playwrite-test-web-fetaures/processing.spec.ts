import { test, expect } from '@playwright/test';

test.describe('Processing Module', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('http://localhost:5173');
    await page.click('text="Processing"');
  });

  test('should display single and batch simulation launch forms', async ({ page }) => {
    await expect(page.locator('.app-header')).toContainText('Simulation Processing');
    
    // Verify scenario input or run button exists
    const simulateBtn = page.locator('.btn:has-text("Simulate"), button:has-text("Run")').first();
    await expect(simulateBtn).toBeVisible();
  });
});
