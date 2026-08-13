<script setup lang="ts">
withDefaults(defineProps<{
  title: string
  description?: string
  icon?: string
}>(), {
  description: 'There is no information to display yet.',
  icon: 'pi pi-inbox',
})
</script>

<template>
  <div class="state-panel empty-state">
    <span :class="[icon, 'state-panel__icon']" aria-hidden="true" />
    <h3>{{ title }}</h3>
    <p>{{ description }}</p>
    <div v-if="$slots.action" class="state-panel__action">
      <slot name="action" />
    </div>
  </div>
</template>
