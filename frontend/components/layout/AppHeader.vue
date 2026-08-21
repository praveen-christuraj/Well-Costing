<script setup lang="ts">
/**
 * Topbar, modelled on the PrimeVue Sakai shell: menu toggle and brand on the
 * left; dark-mode switch, theme configurator, and the signed-in account on the
 * right.
 */
import { computed, ref } from 'vue'
import Button from 'primevue/button'
import AppConfigurator from '~/components/layout/AppConfigurator.vue'
import { useLayout } from '~/composables/useLayout'

const { user, logout } = useAuth()
const { toggleMenu, toggleDarkMode, isDarkTheme, layoutState } = useLayout()
const configuratorRef = ref<HTMLElement | null>(null)

const userInitials = computed(() => {
  const source = user.value?.full_name?.trim() || user.value?.email?.trim() || 'DC'
  const parts = source.split(/\s+/).filter(Boolean)
  return parts.slice(0, 2).map(part => part[0]?.toUpperCase() ?? '').join('') || 'DC'
})

function toggleConfigurator(): void {
  layoutState.configSidebarVisible = !layoutState.configSidebarVisible
}

async function handleLogout(): Promise<void> {
  logout()
  await navigateTo('/login')
}
</script>

<template>
  <header class="layout-topbar">
    <div class="layout-topbar-logo-container">
      <button
        type="button"
        class="layout-menu-button layout-topbar-action"
        aria-label="Toggle navigation"
        @click="toggleMenu"
      >
        <i class="pi pi-bars" aria-hidden="true" />
      </button>
      <NuxtLink to="/dashboard" class="layout-topbar-logo">
        <span class="app-mark" aria-hidden="true">DC</span>
        <span>Drilling Costing</span>
      </NuxtLink>
    </div>

    <div class="layout-topbar-actions">
      <button
        type="button"
        class="layout-topbar-action"
        :aria-label="isDarkTheme ? 'Switch to light theme' : 'Switch to dark theme'"
        @click="toggleDarkMode"
      >
        <i :class="['pi', isDarkTheme ? 'pi-moon' : 'pi-sun']" aria-hidden="true" />
      </button>

      <div ref="configuratorRef" class="layout-config-menu">
        <button
          type="button"
          class="layout-topbar-action layout-topbar-action-highlight"
          aria-label="Theme configurator"
          :aria-expanded="layoutState.configSidebarVisible"
          @click="toggleConfigurator"
        >
          <i class="pi pi-palette" aria-hidden="true" />
        </button>
        <AppConfigurator v-if="layoutState.configSidebarVisible" />
      </div>

      <div v-if="user" class="layout-topbar-account">
        <span class="user-avatar" :title="user.full_name ?? ''">{{ userInitials }}</span>
        <span class="layout-topbar-username">{{ user.full_name }}</span>
        <Button
          icon="pi pi-sign-out"
          text
          rounded
          severity="secondary"
          aria-label="Logout"
          @click="handleLogout"
        />
      </div>
      <NuxtLink v-else to="/login" class="layout-topbar-signin">Sign in</NuxtLink>
    </div>
  </header>
</template>
