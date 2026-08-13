import { expect, test } from '@playwright/test'

test('foundation dashboard renders and degrades safely without business modules', async ({ page }) => {
  await page.goto('/')

  await expect(page.getByRole('heading', { name: 'Foundation dashboard' })).toBeVisible()
  await expect(page.getByText('Drilling Costing', { exact: true }).first()).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Business modules' })).toBeVisible()
  await expect(page.getByText('Coming in Phase 2')).toBeVisible()
  await expect(page.getByText('Coming in Phase 3')).toBeVisible()
})
