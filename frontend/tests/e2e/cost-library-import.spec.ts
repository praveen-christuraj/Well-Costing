import { fileURLToPath } from 'node:url'
import { expect, test } from '@playwright/test'

const fullStackEnabled = process.env.E2E_FULL_STACK === '1'

test('imports a validated vendor workbook into the cost library', async ({ page, request }) => {
  test.skip(!fullStackEnabled, 'Full-stack credentials and backend are required')

  const email = process.env.E2E_EMAIL ?? ''
  const password = process.env.E2E_PASSWORD ?? ''
  const loginResponse = await request.post('/api/v1/auth/login', { data: { email, password } })
  const token = (await loginResponse.json()).access_token as string
  const existing = await request.get('/api/v1/master-data/vendors?page=1&page_size=500', {
    headers: { Authorization: `Bearer ${token}` },
  })
  for (const vendor of (await existing.json()).items as Array<{ id: string, code: string }>) {
    if (['VEND-001', 'VEND-002'].includes(vendor.code)) {
      await request.delete(`/api/v1/master-data/vendors/${vendor.id}`, {
        headers: { Authorization: `Bearer ${token}` },
      })
    }
  }

  await page.goto('/login')
  await page.getByLabel('Email').fill(process.env.E2E_EMAIL ?? '')
  await page.getByLabel('Password').fill(process.env.E2E_PASSWORD ?? '')
  await page.getByRole('button', { name: 'Sign in' }).click()
  await expect(page).toHaveURL(/master-data\/vendors/)

  await page.goto('/cost-library/vendors')
  await expect(page.getByRole('heading', { name: 'Vendors' })).toBeVisible()
  await page.waitForLoadState('networkidle')
  await page.getByRole('button', { name: 'Import' }).click()
  await expect(page.getByRole('dialog')).toBeVisible()

  const workbook = fileURLToPath(
    new URL('../../../test_data/excel/vendors-valid.xlsx', import.meta.url),
  )
  await page.getByTestId('import-file').setInputFiles(workbook)
  await page.getByRole('button', { name: 'Preview and validate' }).click()
  await expect(page.getByText('All rows passed structural and reference validation.')).toBeVisible()
  await expect(page.getByText('2', { exact: true }).first()).toBeVisible()

  await page.getByRole('button', { name: 'Commit import' }).click()
  await expect(page.getByText('2 rows imported successfully.')).toBeVisible()
  await expect(page.locator('input[value="Alpha Drilling Services"]')).toBeVisible()
})
