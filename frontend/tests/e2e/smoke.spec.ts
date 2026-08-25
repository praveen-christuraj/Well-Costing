import { expect, test } from '@playwright/test'

test('signed-out users are redirected to login from the dashboard route', async ({ page }) => {
  await page.goto('/')

  await expect(page).toHaveURL(/\/login/)
  await expect(page.getByRole('heading', { name: 'Sign in' })).toBeVisible()
  await expect(page.getByText('Use your well-costing account to manage Master Data, AFEs, estimates and Daily Cost.')).toBeVisible()
})