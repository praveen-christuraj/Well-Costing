import { flushPromises, mount } from '@vue/test-utils'
import { ref } from 'vue'
import { NormalizedApiError } from '~/types/api'

describe('Login page', () => {
  async function mountPage(options?: {
    redirect?: string
    loginImpl?: ReturnType<typeof vi.fn>
    initialized?: boolean
    authenticated?: boolean
  }) {
    vi.resetModules()

    const navigateTo = vi.fn().mockResolvedValue(undefined)
    const login = options?.loginImpl ?? vi.fn().mockResolvedValue(undefined)
    const loadCurrentUser = vi.fn().mockResolvedValue(undefined)

    vi.stubGlobal('definePageMeta', vi.fn())
    vi.stubGlobal('useRoute', () => ({ query: options?.redirect ? { redirect: options.redirect } : {} }))
    vi.stubGlobal('navigateTo', navigateTo)
    vi.stubGlobal('useAuth', () => ({
      login,
      loadCurrentUser,
      initialized: ref(options?.initialized ?? true),
      isAuthenticated: ref(options?.authenticated ?? false),
    }))

    const component = (await import('~/pages/login.vue')).default
    const wrapper = mount(component, {
      global: {
        stubs: {
          NuxtLink: { template: '<a><slot /></a>' },
        },
      },
    })

    return { wrapper, login, loadCurrentUser, navigateTo }
  }

  afterEach(() => {
    vi.unstubAllGlobals()
    vi.clearAllMocks()
  })

  it('normalizes the email and respects the redirect query after sign in', async () => {
    const { wrapper, login, navigateTo } = await mountPage({ redirect: '/reports' })

    await wrapper.get('input[type="email"]').setValue(' ADMIN@example.com ')
    await wrapper.get('input[type="password"]').setValue('LocalAdminPass2026!')
    await wrapper.get('form').trigger('submit.prevent')
    await flushPromises()

    expect(wrapper.text()).toContain('Sign in to continue to your requested page.')
    expect(login).toHaveBeenCalledWith({
      email: 'admin@example.com',
      password: 'LocalAdminPass2026!',
    })
    expect(navigateTo).toHaveBeenCalledWith('/reports')
  })

  it('shows a deployment-friendly error when the sign-in service is unavailable', async () => {
    const loginImpl = vi.fn().mockRejectedValue(new NormalizedApiError({
      code: 'network_error',
      message: 'Request failed',
      details: null,
    }))
    const { wrapper } = await mountPage({ loginImpl })

    await wrapper.get('input[type="email"]').setValue('admin@example.com')
    await wrapper.get('input[type="password"]').setValue('LocalAdminPass2026!')
    await wrapper.get('form').trigger('submit.prevent')
    await flushPromises()

    expect(wrapper.text()).toContain('Unable to reach the sign-in service. Check the backend deployment and try again.')
  })
})