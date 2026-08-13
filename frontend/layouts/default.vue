<script setup lang="ts">
import { ref } from 'vue'
import AppHeader from '~/components/layout/AppHeader.vue'
import AppSidebar from '~/components/layout/AppSidebar.vue'

const sidebarOpen = ref(false)
</script>

<template>
  <div class="app-shell" :class="{ 'app-shell--sidebar-open': sidebarOpen }">
    <AppHeader @toggle-sidebar="sidebarOpen = !sidebarOpen" />
    <AppSidebar />
    <button
      v-if="sidebarOpen"
      type="button"
      class="sidebar-backdrop"
      aria-label="Close navigation"
      @click="sidebarOpen = false"
    />
    <main class="app-main">
      <slot />
    </main>
  </div>
</template>
