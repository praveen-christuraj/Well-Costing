<script setup lang="ts">
/**
 * Master Data — intentionally empty.
 *
 * The restructure removed every master-data catalogue (primary/secondary/
 * tertiary categories, activities, cost codes, cost categories, units,
 * vendors, materials, services, tangibles, currencies, hole sections,
 * drilling phases, item prices, rate revisions, purchase orders and service
 * orders) together with their tables and API routes. This stub is the anchor
 * the rebuilt catalogues hang off.
 */
import EmptyState from '~/components/design-system/EmptyState.vue'
import PageHeader from '~/components/design-system/PageHeader.vue'

definePageMeta({ middleware: 'auth' })
</script>

<template>
  <div class="master-data-page">
    <PageHeader
      title="Master Data"
      description="Reference and catalogue data will be defined here."
    />
    <EmptyState
      title="No master data yet"
      description="The catalogues were cleared during the restructure. Add a catalogue module here when its data model is defined."
      icon="pi pi-book"
    />
  </div>
</template>
