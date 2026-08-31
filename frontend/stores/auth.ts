import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import type { AuthenticatedUser } from '~/types/auth'

export const useAuthStore = defineStore('auth', () => {
  const user = ref<AuthenticatedUser | null>(null)
  const initialized = ref(false)
  /** Seconds until the current access token expires, when the login/refresh
   * response told us — drives the sliding-refresh cadence. Not persisted: a
   * reloaded page falls back to the default interval. */
  const tokenExpiresInSeconds = ref<number | null>(null)

  const isAuthenticated = computed(() => user.value !== null)

  function setUser(value: AuthenticatedUser | null): void {
    user.value = value
  }

  function markInitialized(): void {
    initialized.value = true
  }

  function setTokenExpiresIn(value: number | null): void {
    tokenExpiresInSeconds.value = value
  }

  return { user, initialized, isAuthenticated, tokenExpiresInSeconds, setUser, markInitialized, setTokenExpiresIn }
})
