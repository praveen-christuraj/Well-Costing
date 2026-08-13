<script setup lang="ts">
import { computed } from 'vue'
import Tag from 'primevue/tag'

type StatusTone = 'success' | 'warning' | 'danger' | 'info' | 'secondary'

const props = withDefaults(defineProps<{
  label: string
  tone?: StatusTone
  icon?: string
}>(), {
  tone: 'secondary',
  icon: '',
})

const severity = computed(() => props.tone)
</script>

<template>
  <Tag
    class="status-badge"
    :value="label"
    :severity="severity"
    :icon="icon"
    rounded
  />
</template>
