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
      description="Maintain cement additives — retarders, accelerators, extenders, and fluid loss control — with their unit of measure and unique material numbers. Their category comes from the Secondary Category of the classification."
    />
    <MasterDataNav active="cement-additives" />
    <CatalogueGrid
      entity="cement-additives"
      title="Cement additives"
      singular="cement additive"
      primary-category-code="CEMENT-ADDITIVES"
      identifier-label="Material number"
    />
  </div>
</template>
