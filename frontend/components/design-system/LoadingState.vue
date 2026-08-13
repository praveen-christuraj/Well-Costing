<script setup lang="ts">
import ProgressSpinner from 'primevue/progressspinner'

withDefaults(defineProps<{
  message?: string
}>(), {
  message: 'Loading…',
})
</script>

<template>
  <div class="state-panel" role="status" aria-live="polite">
    <ProgressSpinner class="state-panel__spinner" stroke-width="4" />
    <p>{{ message }}</p>
  </div>
</template>
