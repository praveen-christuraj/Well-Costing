import { expect, test } from '@playwright/test'

test('signed-out users are redirected to login from the dashboard route', async ({ page }) => {
  await page.goto('/')

  await expect(page).toHaveURL(/\/login/)
  await expect(page.getByRole('heading', { name: 'Sign in' })).toBeVisible()
  await expect(page.getByText('Use your drilling costing account to manage the cost library and enterprise setup.')).toBeVisible()
})