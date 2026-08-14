/** Service catalogue used for AFE service lines. */
<script setup lang="ts">
import CatalogueGrid from '~/components/master-data/CatalogueGrid.vue'
import MasterDataNav from '~/components/master-data/MasterDataNav.vue'
import PageHeader from '~/components/design-system/PageHeader.vue'

definePageMeta({ middleware: 'auth' })
</script>

<template>
  <div class="library-page">
    <PageHeader
      title="Services"
      description="Maintain every well service used during drilling and completion — directional, cementing, logging, surveys, and support services. Rates for each service are held on the Service Rates page."
    />
    <MasterDataNav active="services" />
    <CatalogueGrid
      entity="services"
      title="Services"
      singular="service"
      category-scope="service"
      identifier-label="Reference number"
    />
  </div>
</template>
