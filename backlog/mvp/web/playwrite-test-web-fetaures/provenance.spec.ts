import { test, expect } from '@playwright/test';

test.describe('Comparison & Provenance Module', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('http://localhost:5173');
    await page.click('a[aria-label="Navigate to Comparison and Provenance"]');
  });

  test('should render the provenance dashboard with diff capabilities', async ({ page }) => {
    await expect(page.locator('.app-header')).toContainText('Run Comparison & Provenance');
    
    // Ensure the side-by-side components load
    await expect(page.locator('.card').first()).toBeVisible();
  });
});
