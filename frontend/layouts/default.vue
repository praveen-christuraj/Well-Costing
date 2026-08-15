<script setup lang="ts">
import AppHeader from '~/components/layout/AppHeader.vue'
import AppSidebar from '~/components/layout/AppSidebar.vue'
</script>

<template>
  <div class="app-shell">
    <AppHeader />
    <AppSidebar />
    <main class="app-main">
      <slot />
    </main>
  </div>
</template>
