<script setup lang="ts">
import Button from 'primevue/button'

withDefaults(defineProps<{
  title?: string
  message: string
  retryLabel?: string
}>(), {
  title: 'Something went wrong',
  retryLabel: 'Try again',
})

const emit = defineEmits<{
  retry: []
}>()
</script>

<template>
  <div class="state-panel error-state" role="alert">
    <span class="pi pi-exclamation-triangle state-panel__icon" aria-hidden="true" />
    <h3>{{ title }}</h3>
    <p>{{ message }}</p>
    <Button
      v-if="$attrs.onRetry"
      :label="retryLabel"
      icon="pi pi-refresh"
      severity="danger"
      outlined
      @click="emit('retry')"
    />
  </div>
</template>
