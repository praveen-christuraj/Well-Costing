/**
 * Services — the rate-bearing service register.
 *
 * Rig, cementing, logging, directional, and other service items live here.
 * Each service is classified with the Primary → Secondary → Tertiary
 * hierarchy from the classification pages; the AFE picks services from this
 * register and the AFE Cost Estimates page prices them per well.
 */
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
      description="Maintain the service register — rig, cementing, logging, directional drilling, mud engineering, and other contracted services. Classify each service with the Primary, Secondary, and Tertiary categories; the AFE builds its scope from this register and the AFE Cost Estimates page prices it per well."
    />
    <MasterDataNav active="services" />
    <CatalogueGrid
      entity="services"
      title="Services"
      singular="service"
      identifier-label="Service / contract reference"
      show-rate-basis
    />
  </div>
</template>
