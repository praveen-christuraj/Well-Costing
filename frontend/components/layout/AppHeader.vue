<script setup lang="ts">
import Button from 'primevue/button'

defineEmits<{
  toggleSidebar: []
}>()
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
      <div class="user-avatar" title="Authentication UI arrives in a later phase">
        CE
      </div>
    </div>
  </header>
</template>
