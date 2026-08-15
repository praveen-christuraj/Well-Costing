<script setup lang="ts">
import { computed } from 'vue'
import Button from 'primevue/button'

const { user, logout } = useAuth()

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
    <div class="app-header__left">
      <div class="app-mark" aria-hidden="true">DC</div>
      <span class="app-header__brand">Drilling Costing</span>
    </div>
    <div class="app-header__right">
      <div v-if="user" class="app-header__account">
        <div class="user-avatar" :title="user.full_name ?? ''">{{ userInitials }}</div>
        <span class="app-header__username">{{ user.full_name }}</span>
        <Button
          icon="pi pi-sign-out"
          text
          rounded
          severity="secondary"
          aria-label="Logout"
          class="app-header__logout"
          @click="handleLogout"
        />
      </div>
      <NuxtLink v-else to="/login" class="app-header__signin-link">Sign in</NuxtLink>
    </div>
  </header>
</template>