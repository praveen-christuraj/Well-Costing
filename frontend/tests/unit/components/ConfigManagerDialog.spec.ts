import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'
import ConfigManagerDialog from '~/components/catalogue/ConfigManagerDialog.vue'

/**
 * The manage-dropdown dialog used by Drill Bits (type/manufacturer) and
 * Tangibles (category/subcategory/manufacturer). Non-parented lists must be
 * addable without picking a parent — that was a no-op previously.
 *
 * PrimeVue Dialog teleports to document.body, so assertions query the body.
 */

type ApiMock = Record<'get' | 'post' | 'put' | 'delete', ReturnType<typeof vi.fn>>

function makeApi(overrides: Partial<ApiMock> = {}): ApiMock {
  return {
    get: vi.fn().mockResolvedValue([]),
    post: vi.fn().mockResolvedValue({ id: 11, value: 'PDC' }),
    put: vi.fn().mockResolvedValue({}),
    delete: vi.fn().mockResolvedValue(undefined),
    ...overrides,
  }
}

function mountDialog(api: ApiMock, props: Record<string, unknown> = {}) {
  vi.stubGlobal('useApi', () => api)
  return mount(ConfigManagerDialog, {
    attachTo: document.body,
    props: {
      visible: true,
      configType: 'bit_type',
      title: 'Drill Bit Types',
      ...props,
    },
  })
}

function bodyFind(selector: string): HTMLElement | null {
  return document.body.querySelector(selector)
}

afterEach(() => {
  document.body.innerHTML = ''
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('ConfigManagerDialog', () => {
  it('adds a value to a non-parented list (bit types / manufacturers / categories)', async () => {
    const api = makeApi()
    const wrapper = mountDialog(api)
    await flushPromises()
    const input = bodyFind('[data-testid="config-single-input"]')?.querySelector('input')
      ?? (bodyFind('[data-testid="config-single-input"]') as HTMLInputElement | null)
    expect(input).toBeTruthy()
    if (input && 'value' in input) {
      input.value = 'PDC'
      input.dispatchEvent(new Event('input', { bubbles: true }))
    }
    await flushPromises()
    ;(bodyFind('[data-testid="config-add-single"]') as HTMLButtonElement).click()
    await flushPromises()
    expect(api.post).toHaveBeenCalledWith('/catalogue/configs/bit_type', { value: 'PDC' })
    wrapper.unmount()
  })

  it('bulk-adds values without requiring a parent on non-parented lists', async () => {
    const api = makeApi()
    const wrapper = mountDialog(api, { configType: 'bit_manufacturer', title: 'Drill Bit Manufacturers' })
    await flushPromises()
    const textarea = document.body.querySelector('textarea') as HTMLTextAreaElement
    expect(textarea).toBeTruthy()
    textarea.value = 'Hughes\nSmith'
    textarea.dispatchEvent(new Event('input', { bubbles: true }))
    await flushPromises()
    ;(bodyFind('[data-testid="config-bulk-add"]') as HTMLButtonElement).click()
    await flushPromises()
    expect(api.post).toHaveBeenCalledWith('/catalogue/configs/bit_manufacturer/bulk', {
      values: ['Hughes', 'Smith'],
    })
    wrapper.unmount()
  })

  it('hides add controls for a parented list until a parent is chosen', async () => {
    const api = makeApi()
    const wrapper = mountDialog(api, {
      configType: 'tangible_subcategory',
      title: 'Tangible Subcategories',
      parentConfigType: 'tangible_category',
      parentLabel: 'Category',
    })
    await flushPromises()
    expect(bodyFind('[data-testid="config-add-single"]')).toBeNull()
    expect(document.body.textContent).toContain('Configure a category first')
    expect(api.post).not.toHaveBeenCalled()
    wrapper.unmount()
  })
})
