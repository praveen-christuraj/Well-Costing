<script setup lang="ts">
import { computed } from 'vue'
import PageHeader from '~/components/design-system/PageHeader.vue'
import CostLibraryNav from '~/components/cost-library/CostLibraryNav.vue'
import MasterDataGrid from '~/components/cost-library/MasterDataGrid.vue'
import RateGrid from '~/components/cost-library/RateGrid.vue'
import { costLibraryEntities } from '~/types/masterData'

definePageMeta({ middleware: 'auth' })

const route = useRoute()
const entityKey = computed(() => String(route.params.entity))
const entity = computed(() => costLibraryEntities.find(item => item.key === entityKey.value))

if (!entity.value) {
  throw createError({ statusCode: 404, statusMessage: 'Cost library entity not found' })
}
</script>

<template>
  <div v-if="entity" class="library-page">
    <PageHeader
      :title="entity.label"
      :description="`Maintain ${entity.label.toLowerCase()} through an auditable bulk grid or validated Excel import.`"
    />
    <CostLibraryNav :active="entity.key" />
    <RateGrid v-if="entity.key === 'rates'" />
    <MasterDataGrid
      v-else
      :entity="entity.key"
      :label="entity.label"
      :singular="entity.singular"
      :supports-symbol="entity.supportsSymbol ?? false"
    />
  </div>
</template>
