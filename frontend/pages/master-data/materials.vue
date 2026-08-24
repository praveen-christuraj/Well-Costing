<script setup lang="ts">
/** User-defined consumables/materials. Items are classified first and then
 * become available to AFE scope and Daily Cost consumption entry. */
import CatalogueGrid from '~/components/master-data/CatalogueGrid.vue'
import MasterDataNav from '~/components/master-data/MasterDataNav.vue'
import PageHeader from '~/components/design-system/PageHeader.vue'

definePageMeta({ middleware: 'auth' })
</script>

<template>
  <div class="library-page">
    <PageHeader
      title="Consumable Materials"
      description="Create consumables with the names used by your operation. Classify each item under Primary, Secondary, and Tertiary Categories; classified items can then be linked to an AFE and entered in Daily Cost consumption."
    />
    <MasterDataNav active="materials" />
    <CatalogueGrid
      entity="materials"
      title="Consumable Materials"
      singular="consumable material"
      identifier-label="Material number"
      show-rate-basis
    />
  </div>
</template>
