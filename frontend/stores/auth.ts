import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import type { AuthenticatedUser } from '~/types/auth'

export const useAuthStore = defineStore('auth', () => {
  const user = ref<AuthenticatedUser | null>(null)
  const initialized = ref(false)

  const isAuthenticated = computed(() => user.value !== null)

  function setUser(value: AuthenticatedUser | null): void {
    user.value = value
  }

  function markInitialized(): void {
    initialized.value = true
  }

  return { user, initialized, isAuthenticated, setUser, markInitialized }
})
