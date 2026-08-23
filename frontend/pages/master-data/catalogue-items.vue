/**
 * Catalogue Items — the single register for everything that carries a rate.
 *
 * Services, tangibles, consumables, materials, and equipment all live here.
 * What an item *is* comes from its classification: Primary Category places it
 * (Services, Tangibles, …), the Secondary Category is its category, and the
 * Tertiary Category its sub category. There are no separate item-category or
 * item-sub-category lists any more.
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
      title="Catalogue Items"
      description="Every rate-bearing item in one register — services, tangibles, mud chemicals, cement additives, materials, and equipment. Classify each item with the Primary, Secondary, and Tertiary categories from the classification; the type field only says which kind of item it is."
    />
    <MasterDataNav active="catalogue-items" />
    <div class="uom-tip">
      <i class="pi pi-info-circle" aria-hidden="true" />
      <span>
        Set up Primary, Secondary, and Tertiary Categories first. Every catalogue item is filed
        against them, and the AFE, cost builder, and daily cost pickers all read the same
        classification.
      </span>
    </div>
    <CatalogueGrid
      entity="catalog-items"
      title="Catalogue items"
      singular="catalogue item"
      identifier-label="Material / reference number"
      show-item-type
      show-rate-basis
      show-equipment-detail
    />
  </div>
</template>
