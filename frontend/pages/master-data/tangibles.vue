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
      description="Maintain drilling tangibles — bits, casings, centralisers, float shoes and collars, top and bottom plugs, wellheads, pup joints, pip tags, and threads. A tangible's category is its Secondary Category and its sub category its Tertiary Category, both taken from the classification in master data."
    />
    <MasterDataNav active="tangibles" />
    <CatalogueGrid
      entity="tangibles"
      title="Tangibles"
      singular="tangible"
      primary-category-code="TANGIBLES"
      identifier-label="Material number"
      show-equipment-detail
    />
  </div>
</template>
