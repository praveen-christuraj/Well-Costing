/** Mud chemical catalogue with unit of measure and vendor material numbers. */
<script setup lang="ts">
import CatalogueGrid from '~/components/master-data/CatalogueGrid.vue'
import MasterDataNav from '~/components/master-data/MasterDataNav.vue'
import PageHeader from '~/components/design-system/PageHeader.vue'

definePageMeta({ middleware: 'auth' })
</script>

<template>
  <div class="library-page">
    <PageHeader
      title="Mud Chemicals"
      description="Maintain drilling fluid chemicals with their unit of measure and unique material numbers. Prices per vendor are held on the Item Prices page."
    />
    <MasterDataNav active="mud-chemicals" />
    <CatalogueGrid
      entity="mud-chemicals"
      title="Mud chemicals"
      singular="mud chemical"
      category-scope="mud_chemical"
      identifier-label="Material number"
    />
  </div>
</template>
