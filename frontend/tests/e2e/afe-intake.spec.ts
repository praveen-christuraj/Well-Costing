import { expect, test } from '@playwright/test'

const enabled = process.env.E2E_FULL_STACK === '1'

test('creates an AFE and bulk-pastes a validated line', async ({ page, request }) => {
  test.skip(!enabled, 'Full-stack backend is required')
  const email = process.env.E2E_EMAIL ?? ''
  const password = process.env.E2E_PASSWORD ?? ''
  const suffix = String(Date.now())
  const unitCode = `D-${suffix}`
  const categoryCode = `CAT-${suffix}`
  const costCode = `CC-${suffix}`
  const serviceCode = `SVC-${suffix}`
  const login = await request.post('/api/v1/auth/login', { data: { email, password } })
  const token = (await login.json()).access_token as string
  const headers = { Authorization: `Bearer ${token}` }
  const create = async (path: string, data: Record<string, unknown>) => {
    const response = await request.post(path, { data, headers })
    expect(response.ok(), await response.text()).toBe(true)
    return response.json()
  }
  const unit = await create('/api/v1/master-data/units', { code: unitCode, name: 'Day P3' })
  const category = await create('/api/v1/master-data/cost-categories', { code: categoryCode, name: 'Phase 3 services' })
  const code = await create('/api/v1/master-data/cost-codes', { code: costCode, name: 'Phase 3 code', cost_category_id: category.id })
  await create('/api/v1/master-data/services', { code: serviceCode, name: 'Phase 3 service', cost_category_id: category.id, cost_code_id: code.id, default_unit_id: unit.id })
  const currency = await create('/api/v1/master-data/currencies', { code: `X${suffix.slice(-2)}`, name: 'Phase 5 test currency' })
  const sectionCode = `S-${suffix.slice(-6)}`
  await create('/api/v1/master-data/hole-sections', { code: sectionCode, name: '17-1/2 inch hole' })

  await page.goto('/login')
  await page.getByLabel('Email').fill(email)
  await page.getByLabel('Password').fill(password)
  await page.getByRole('button', { name: 'Sign in' }).click()
  await expect(page).toHaveURL(/dashboard/)
  await page.goto('/afe')
  await page.waitForLoadState('networkidle')

  // The Projects tab is the default.
  await page.getByRole('button', { name: 'Add project' }).click()
  const projectDialog = page.getByRole('dialog', { name: 'Add project' })
  await projectDialog.getByLabel('Code').fill(`PRJ-${suffix}`)
  await projectDialog.getByLabel('Name').fill('Phase 3 project')
  await projectDialog.getByRole('button', { name: 'Create project' }).click()
  await expect(projectDialog).toBeHidden()
  // The well dialog defaults its project from the reloaded list, so wait for it.
  await expect(page.getByRole('cell', { name: `PRJ-${suffix}`, exact: true })).toBeVisible()

  await page.getByRole('tab', { name: 'Wells' }).click()
  await page.getByRole('button', { name: 'Add well' }).click()
  const wellDialog = page.getByRole('dialog', { name: 'Add well' })
  await wellDialog.getByLabel('Code').fill(`WELL-${suffix}`)
  await wellDialog.getByLabel('Name').fill('Phase 3 well')
  await wellDialog.getByRole('button', { name: 'Create well' }).click()
  await expect(wellDialog).toBeHidden()
  await expect(page.getByRole('cell', { name: `WELL-${suffix}`, exact: true })).toBeVisible()

  await page.getByRole('button', { name: 'New AFE' }).first().click()
  const afeDialog = page.getByRole('dialog', { name: 'New AFE' })
  await afeDialog.getByLabel('AFE code').fill(`AFE-${suffix}`)
  await afeDialog.getByLabel('Title').fill('Phase 3 AFE')
  await afeDialog.getByRole('button', { name: 'Create and open' }).click()
  await expect(afeDialog).toBeHidden()

  await page.getByRole('button', { name: 'Paste' }).click()
  await page.getByRole('dialog', { name: 'Paste AFE lines' }).getByRole('textbox').fill(
    `${serviceCode}\tservice\t${costCode}\t2\t${unitCode}\t${sectionCode}\t5`,
  )
  await page.getByRole('button', { name: 'Apply rows' }).click()
  await page.getByRole('button', { name: /Save 1/ }).click()
  await expect(page.getByText('1 rows saved.')).toBeVisible()
  await page.getByRole('button', { name: 'Submit' }).click()
  await expect(page.getByText('submitted', { exact: true }).first()).toBeVisible()

  const afeResponse = await request.get('/api/v1/afes?page=1&page_size=500&status=submitted', { headers })
  const afePage = await afeResponse.json() as { items: { id: string, code: string }[] }
  const afe = afePage.items.find(item => item.code === `AFE-${suffix}`)
  expect(afe).toBeTruthy()
  const estimate = await create('/api/v1/estimates/from-afe', {
    afe_id: afe?.id,
    code: `EST-${suffix}`,
    title: 'Phase 5 blocked calculation',
    currency_id: currency.id,
  })
  await page.goto(`/cost-builder/${estimate.id}`)
  await expect(page.getByText('No calculated breakdown')).toBeVisible()
  await page.getByRole('button', { name: 'Recalculate' }).click()
  await expect(page.getByText('Estimate calculation is blocked pending confirmed business rules')).toBeVisible()
  await expect(page.getByText('blocked', { exact: true }).first()).toBeVisible()
  await expect(page.getByText('Pending business rules (7)')).toBeVisible()
  await expect(page.getByText('Workflow profile pending')).toBeVisible()
  await expect(page.getByText('Pending workflow policy (6)')).toBeVisible()

  const blockedTransition = await request.post(`/api/v1/estimates/${estimate.id}/workflow/transitions`, {
    data: { version_id: estimate.versions[0].id, action_key: 'submit_for_review' },
    headers,
  })
  expect(blockedTransition.status()).toBe(422)
  expect((await blockedTransition.json()).error.code).toBe('workflow_profile_pending')
  await page.reload()
  await expect(page.getByText('submit_for_review')).toBeVisible()

  await page.getByRole('textbox', { name: 'Add review note' }).fill('Phase 6 review trace from the full-stack regression.')
  await page.getByRole('button', { name: 'Add review note' }).click()
  await expect(page.getByText('Phase 6 review trace from the full-stack regression.')).toBeVisible()

  await expect(page.getByText('AFE policy pending')).toBeVisible()
  await expect(page.getByText('No AFE issued')).toBeVisible()
  await expect(page.getByText('Pending AFE policy (6)')).toBeVisible()
  await page.getByRole('button', { name: 'Create baseline AFE snapshot' }).click()
  await expect(page.getByText('Baseline AFE creation is blocked pending an approved eligibility and snapshot policy')).toBeVisible()
  await expect(page.getByText('Explicit baseline request')).toBeVisible()

  const staged = await request.post('/api/v1/cost-control/batches/validate', {
    data: {
      estimate_version_id: estimate.versions[0].id,
      cost_state: 'forecast',
      rows: [{
        transaction_date: '2026-08-13', source_document_type: 'field_ticket',
        source_document_reference: `FT-${suffix}`, external_transaction_id: `EXT-${suffix}`,
        cost_code: costCode, description: 'Phase 8 staged forecast', quantity: '1',
        unit_code: unitCode, currency_code: currency.code, amount: '250.0000', correction_kind: 'original',
      }],
    },
    headers,
  })
  expect(staged.ok(), await staged.text()).toBe(true)
  const stagedBatch = await staged.json()
  const blockedPost = await request.post(`/api/v1/cost-control/batches/${stagedBatch.id}/post`, { headers })
  expect(blockedPost.status()).toBe(422)
  expect((await blockedPost.json()).error.code).toBe('cost_state_policy_pending')

  await page.goto('/cost-control')
  await expect(page.getByRole('heading', { name: 'Cost control staging' })).toBeVisible()
  await expect(page.getByText('pending-all-cost-states')).toBeVisible()
  await expect(page.getByRole('cell', { name: 'forecast' })).toBeVisible()
  await expect(page.getByRole('cell', { name: 'blocked' })).toBeVisible()

  await page.goto('/reports')
  await expect(page.getByRole('heading', { name: 'Cost-state reporting' })).toBeVisible()
  await expect(page.getByText('pending-shared-cost-reporting')).toBeVisible()
  await expect(page.getByText('Financial metrics pending')).toBeVisible()
  await expect(page.getByText('Pending reporting metrics (6)')).toBeVisible()
  const reportDownload = page.waitForEvent('download')
  await page.getByRole('button', { name: 'Export Excel' }).click()
  expect((await reportDownload).suggestedFilename()).toBe('cost-overview.xlsx')

  await page.goto('/assurance')
  await expect(page.getByRole('heading', { name: 'Framework assurance' })).toBeVisible()
  await expect(page.getByText('framework_ready')).toBeVisible()
  await expect(page.getByText('0 violations').first()).toBeVisible()
  await expect(page.getByText('numeric reconciliation')).toBeVisible()

  const configuredType = await request.post('/api/v1/enterprise-config/node-types', {
    data: { code: `ORG-${suffix}`, name: 'E2E Organization Level', level_order: 10 }, headers,
  })
  expect(configuredType.ok(), await configuredType.text()).toBe(true)
  await page.goto('/administration/enterprise')
  await expect(page.getByRole('heading', { name: 'Enterprise well-costing model' })).toBeVisible()
  await expect(page.locator('article').filter({ hasText: 'Node types' }).getByText('1', { exact: true })).toBeVisible()
})
