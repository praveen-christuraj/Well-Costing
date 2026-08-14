/** Cement additive catalogue with unit of measure and vendor material numbers. */
<script setup lang="ts">
import CatalogueGrid from '~/components/master-data/CatalogueGrid.vue'
import MasterDataNav from '~/components/master-data/MasterDataNav.vue'
import PageHeader from '~/components/design-system/PageHeader.vue'

definePageMeta({ middleware: 'auth' })
</script>

<template>
  <div class="library-page">
    <PageHeader
      title="Cement Additives"
      description="Maintain cement additives — retarders, accelerators, extenders, and fluid loss control — with their unit of measure and unique material numbers."
    />
    <MasterDataNav active="cement-additives" />
    <CatalogueGrid
      entity="cement-additives"
      title="Cement additives"
      singular="cement additive"
      category-scope="cement_additive"
      identifier-label="Material number"
    />
  </div>
</template>
