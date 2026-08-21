<script setup lang="ts">
/** A single headline figure, after the Sakai stats widget. */
defineProps<{
  label: string
  value: string | number
  icon: string
  hint?: string
  tone?: 'teal' | 'blue' | 'amber' | 'violet'
}>()
</script>

<template>
  <article class="stat-card">
    <div class="stat-card__body">
      <span class="stat-card__label">{{ label }}</span>
      <strong class="stat-card__value">{{ value }}</strong>
      <small v-if="hint" class="stat-card__hint">{{ hint }}</small>
    </div>
    <span :class="['stat-card__icon', `stat-card__icon--${tone ?? 'teal'}`]">
      <i :class="icon" aria-hidden="true" />
    </span>
  </article>
</template>
