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
      description="Maintain every well service used during drilling and completion — directional, cementing, logging, surveys, and support services — and classify how each one is charged: daily rate, per section, per service, or a fixed rate. The amount itself is always agreed per well on the well's rate book."
    />
    <MasterDataNav active="services" />
    <CatalogueGrid
      entity="services"
      title="Services"
      singular="service"
      category-scope="service"
      identifier-label="Reference number"
      show-rate-basis
    />
  </div>
</template>
