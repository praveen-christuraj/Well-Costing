<script setup lang="ts">
import { computed } from 'vue'
import Button from 'primevue/button'

const { user, logout } = useAuth()

defineEmits<{
  toggleSidebar: []
}>()

const userInitials = computed(() => {
  const source = user.value?.full_name?.trim() || user.value?.email?.trim() || 'DC'
  const parts = source.split(/\s+/).filter(Boolean)
  return parts.slice(0, 2).map(part => part[0]?.toUpperCase() ?? '').join('') || 'DC'
})

async function handleLogout(): Promise<void> {
  logout()
  await navigateTo('/login')
}
</script>

<template>
  <header class="app-header">
    <div class="app-header__identity">
      <Button
        class="app-header__menu"
        icon="pi pi-bars"
        text
        rounded
        aria-label="Toggle navigation"
        @click="$emit('toggleSidebar')"
      />
      <div class="app-mark" aria-hidden="true">
        DC
      </div>
      <div>
        <strong>Drilling Costing</strong>
        <span>Cost control workspace</span>
      </div>
    </div>
    <div class="app-header__meta">
      <span class="environment-chip">
        <i class="pi pi-shield" /> Foundation
      </span>
      <div v-if="user" class="app-header__account">
        <div class="app-header__user-text">
          <strong>{{ user.full_name }}</strong>
          <span>{{ user.email }}</span>
        </div>
        <div class="user-avatar" :title="user.full_name">
          {{ userInitials }}
        </div>
        <Button
          label="Logout"
          icon="pi pi-sign-out"
          text
          severity="secondary"
          class="app-header__logout"
          @click="handleLogout"
        />
      </div>
      <NuxtLink v-else to="/login" class="app-header__signin-link">Sign in</NuxtLink>
    </div>
  </header>
</template>