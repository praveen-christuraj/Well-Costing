import { mount } from '@vue/test-utils'
import { ref } from 'vue'

describe('AppHeader', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    vi.clearAllMocks()
  })

  it('shows the signed-in user and logs out to the login page', async () => {
    vi.resetModules()
    const logout = vi.fn()
    const navigateTo = vi.fn().mockResolvedValue(undefined)

    vi.stubGlobal('useAuth', () => ({
      user: ref({
        id: 'user-1',
        email: 'admin@example.com',
        full_name: 'Admin User',
        is_active: true,
        created_at: '2026-08-13T00:00:00Z',
        updated_at: '2026-08-13T00:00:00Z',
      }),
      logout,
    }))
    vi.stubGlobal('navigateTo', navigateTo)

    const component = (await import('~/components/layout/AppHeader.vue')).default
    const wrapper = mount(component, {
      global: {
        stubs: {
          NuxtLink: { template: '<a><slot /></a>' },
        },
      },
    })

    expect(wrapper.text()).toContain('Admin User')
    expect(wrapper.get('.user-avatar').attributes('title')).toBe('Admin User')

    const buttons = wrapper.findAll('button')
    await buttons[buttons.length - 1]?.trigger('click')
    expect(logout).toHaveBeenCalledTimes(1)
    expect(navigateTo).toHaveBeenCalledWith('/login')
  })
})