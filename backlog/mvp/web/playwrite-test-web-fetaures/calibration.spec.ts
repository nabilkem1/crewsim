import { test, expect } from '@playwright/test';

test.describe('Calibration Module', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('http://localhost:5173');
    await page.click('text="Calibration"');
  });

  test('should allow running a calibration job', async ({ page }) => {
    await expect(page.locator('.app-header')).toContainText('Calibration Pipeline');
    
    // Look for a run/execute button
    const runBtn = page.locator('button:has-text("Run Statistical Fitting")').first();
    await expect(runBtn).toBeVisible();
  });
});
