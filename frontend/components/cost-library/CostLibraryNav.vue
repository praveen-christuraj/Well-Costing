<script setup lang="ts">
import { costLibraryEntities } from '~/types/masterData'

const props = defineProps<{ active: string }>()
</script>

<template>
  <nav class="library-nav" aria-label="Cost library entities">
    <NuxtLink
      v-for="entity in costLibraryEntities"
      :key="entity.key"
      :to="`/cost-library/${entity.key}`"
      :class="['library-nav__item', { 'library-nav__item--active': props.active === entity.key }]"
    >
      {{ entity.label }}
    </NuxtLink>
    <NuxtLink
      to="/cost-library/import-history"
      :class="['library-nav__item', { 'library-nav__item--active': props.active === 'import-history' }]"
    >
      Import History
    </NuxtLink>
  </nav>
</template>
