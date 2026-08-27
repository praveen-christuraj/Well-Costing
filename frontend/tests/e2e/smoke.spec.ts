import { expect, test } from '@playwright/test'

test('signed-out users are redirected to login from the landing route', async ({ page }) => {
  await page.goto('/')

  await expect(page).toHaveURL(/\/login/)
  await expect(page.getByRole('heading', { name: 'Sign in' })).toBeVisible()
  await expect(page.getByText('Use your well-costing account to open the workspace.')).toBeVisible()
})
