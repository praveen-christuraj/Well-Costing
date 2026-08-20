/** Tangible catalogue: bits, casings, centralisers, shoes, collars, plugs, wellheads. */
<script setup lang="ts">
import CatalogueGrid from '~/components/master-data/CatalogueGrid.vue'
import MasterDataNav from '~/components/master-data/MasterDataNav.vue'
import PageHeader from '~/components/design-system/PageHeader.vue'

definePageMeta({ middleware: 'auth' })
</script>

<template>
  <div class="library-page">
    <PageHeader
      title="Tangibles"
      description="Maintain drilling tangibles — bits, casings, centralisers, float shoes and collars, top and bottom plugs, wellheads, pup joints, pip tags, and threads — with their category, sub category, unit, and material numbers."
    />
    <MasterDataNav active="tangibles" />
    <CatalogueGrid
      entity="tangibles"
      title="Tangibles"
      singular="tangible"
      category-scope="tangible"
      identifier-label="Material number"
      show-equipment-detail
      show-sub-category
    />
  </div>
</template>
