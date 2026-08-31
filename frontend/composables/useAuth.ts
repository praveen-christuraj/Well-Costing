import { storeToRefs } from 'pinia'
import { ApiClient } from '~/services/apiClient'
import { NormalizedApiError } from '~/types/api'
import { useAuthStore } from '~/stores/auth'
import type { AuthenticatedUser, LoginRequest, TokenResponse } from '~/types/auth'

/**
 * Fallback refresh cadence when the login response's expiry is unknown (e.g.
 * the session cookie survived a page reload). Half the default 60-minute
 * token lifetime, so one missed refresh still leaves a full interval of slack.
 */
const DEFAULT_REFRESH_INTERVAL_MS = 30 * 60 * 1000

/** The server rejected the credentials/token themselves — not a blip. */
function isAuthRejection(error: unknown): boolean {
  return error instanceof NormalizedApiError && (error.status === 401 || error.status === 403)
}

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
    store.setTokenExpiresIn(response.expires_in)
    store.setUser(await api.get<AuthenticatedUser>('/auth/me'))
    store.markInitialized()
  }

  async function fetchCurrentUser(): Promise<AuthenticatedUser> {
    return await api.get<AuthenticatedUser>('/auth/me')
  }

  async function loadCurrentUser(): Promise<void> {
    if (!token.value) {
      store.setUser(null)
      store.markInitialized()
      return
    }
    try {
      store.setUser(await fetchCurrentUser())
    }
    catch (caught: unknown) {
      // Only an explicit rejection from the server means the session is really
      // gone. A transient failure (API busy, proxy timeout, offline) used to
      // wipe the cookie and force a re-login mid-work — retry once after a
      // beat, and if it still fails without a verdict, leave the token alone.
      if (isAuthRejection(caught)) {
        token.value = null
        store.setUser(null)
      }
      else {
        try {
          await new Promise(resolve => setTimeout(resolve, 500))
          store.setUser(await fetchCurrentUser())
        }
        catch (retry: unknown) {
          if (isAuthRejection(retry)) token.value = null
          store.setUser(null)
        }
      }
    }
    finally {
      store.markInitialized()
    }
  }

  /**
   * Slide the access token's expiry forward while the app is open.
   *
   * Tokens live 60 minutes and used to expire underneath a long data-entry
   * session ("Invalid or expired access token" while saving). A still-valid
   * token buys a fresh one well before it lapses, so an active user is never
   * interrupted; an idle/closed tab simply logs back in as before.
   */
  async function refreshSession(): Promise<boolean> {
    if (!token.value) return false
    try {
      const response = await api.post<TokenResponse>('/auth/refresh', {})
      token.value = response.access_token
      store.setTokenExpiresIn(response.expires_in)
      return true
    }
    catch (caught: unknown) {
      if (isAuthRejection(caught)) {
        token.value = null
        store.setUser(null)
      }
      // Transient failures keep the current token; the next tick retries.
      return false
    }
  }

  let refreshTimer: ReturnType<typeof setInterval> | undefined

  function startSessionKeepAlive(): void {
    if (refreshTimer) return
    const knownExpiryMs = store.tokenExpiresInSeconds
      ? Math.floor((store.tokenExpiresInSeconds / 2) * 1000)
      : null
    const intervalMs = Math.max(60_000, knownExpiryMs ?? DEFAULT_REFRESH_INTERVAL_MS)
    refreshTimer = setInterval(() => {
      if (!token.value) return
      void refreshSession()
    }, intervalMs)
  }

  function stopSessionKeepAlive(): void {
    if (refreshTimer) clearInterval(refreshTimer)
    refreshTimer = undefined
  }

  function logout(): void {
    stopSessionKeepAlive()
    token.value = null
    store.setUser(null)
    store.setTokenExpiresIn(null)
    store.markInitialized()
  }

  return {
    user,
    initialized,
    isAuthenticated,
    login,
    loadCurrentUser,
    refreshSession,
    startSessionKeepAlive,
    stopSessionKeepAlive,
    logout,
  }
}
