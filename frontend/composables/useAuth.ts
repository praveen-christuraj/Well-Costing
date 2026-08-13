import { storeToRefs } from 'pinia'
import { ApiClient } from '~/services/apiClient'
import { useAuthStore } from '~/stores/auth'
import type { AuthenticatedUser, LoginRequest, TokenResponse } from '~/types/auth'

export function useAuth() {
  const store = useAuthStore()
  const { user, initialized, isAuthenticated } = storeToRefs(store)
  const token = useAccessTokenCookie()
  const config = useRuntimeConfig()
  const api = new ApiClient(config.public.apiBase, () => token.value)

  async function login(credentials: LoginRequest): Promise<void> {
    const response = await api.post<TokenResponse>('/auth/login', {
      email: credentials.email,
      password: credentials.password,
    })
    token.value = response.access_token
    store.setUser(await api.get<AuthenticatedUser>('/auth/me'))
    store.markInitialized()
  }

  async function loadCurrentUser(): Promise<void> {
    if (!token.value) {
      store.setUser(null)
      store.markInitialized()
      return
    }
    try {
      store.setUser(await api.get<AuthenticatedUser>('/auth/me'))
    }
    catch {
      token.value = null
      store.setUser(null)
    }
    finally {
      store.markInitialized()
    }
  }

  function logout(): void {
    token.value = null
    store.setUser(null)
    store.markInitialized()
  }

  return { user, initialized, isAuthenticated, login, loadCurrentUser, logout }
}
