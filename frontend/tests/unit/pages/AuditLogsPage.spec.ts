import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'

const sampleLogs = [
  {
    id: 1,
    timestamp: '2026-08-27T10:00:00Z',
    user_email: 'engineer@example.com',
    action: 'LOGIN',
    module: 'Authentication',
    entity_code: 'engineer@example.com',
    details: 'Successful sign-in for engineer@example.com',
    ip_address: '127.0.0.1',
  },
  {
    id: 2,
    timestamp: '2026-08-27T10:01:00Z',
    user_email: 'engineer@example.com',
    action: 'CREATE',
    module: 'Currency',
    entity_code: 'USD',
    details: 'Created Currency record USD',
    ip_address: '127.0.0.1',
  },
]

async function mountPage() {
  vi.resetModules()
  const api = {
    get: vi.fn().mockResolvedValue(sampleLogs),
    download: vi.fn().mockResolvedValue(new Blob()),
  }
  vi.stubGlobal('definePageMeta', vi.fn())
  vi.stubGlobal('useApi', () => api)

  const component = (await import('~/pages/audit-logs/index.vue')).default
  const wrapper = mount(component, { attachTo: document.body })
  await flushPromises()
  return { wrapper, api }
}

describe('Audit log page', () => {
  it('renders the current shell and loaded logs', async () => {
    const { wrapper, api } = await mountPage()
    expect(api.get).toHaveBeenCalled()
    expect(wrapper.text()).toContain('System Audit Log')
    expect(wrapper.text()).toContain('engineer@example.com')
    expect(wrapper.text()).toContain('LOGIN')
    expect(wrapper.text()).toContain('Currency')
    expect(wrapper.find('.grid-card').exists()).toBe(true)
    expect(wrapper.find('.print-sheet').text()).toContain('System Audit Log')
    expect(wrapper.find('.print-sheet').text()).toContain('LOGIN')
  })

  it('searches across every log field, not only the entity code', async () => {
    const { wrapper } = await mountPage()
    const input = wrapper.get('.search__input')
    await input.setValue('currency')
    await flushPromises()
    expect(wrapper.find('.audit-table').text()).toContain('USD')
    expect(wrapper.find('.audit-table').text()).not.toContain('LOGIN')
  })
})
