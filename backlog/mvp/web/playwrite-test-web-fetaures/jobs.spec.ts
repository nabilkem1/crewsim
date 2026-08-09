import { test, expect } from '@playwright/test';

test.describe('Jobs Queue Module', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('http://localhost:5173');
    await page.click('text="Runs & Jobs"');
  });

  test('should render the active job queue', async ({ page }) => {
    await expect(page.locator('.app-header')).toContainText('Job Execution Queue');
    
    // Wait for jobs container
    await expect(page.locator('.card, .job-item').first()).toBeVisible();
  });
});
