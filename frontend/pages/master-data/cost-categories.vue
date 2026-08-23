/**
 * Cost category register.
 *
 * A cost category is classified by the same hierarchy as everything else: its
 * parent is a Primary Category and its second level a Secondary Category, both
 * read from the classification in master data. The old free-form parent (another
 * cost category) is gone, as are the separate service / item-category lists.
 */
<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import EnterpriseGrid from '~/components/data-grid/EnterpriseGrid.vue'
import MasterDataNav from '~/components/master-data/MasterDataNav.vue'
import PageHeader from '~/components/design-system/PageHeader.vue'
import type { EditableRow, GridColumn, GridSelectOption } from '~/types/grid'
import type { MasterDataRecord, PageResponse } from '~/types/masterData'
import { SLOT } from '~/types/reference'

definePageMeta({ middleware: 'auth' })

const api = useMasterData()
const references = useReferenceOptions()
const entity = 'cost-categories'

const primaryOptions = ref<GridSelectOption[]>([])
const secondaryOptions = ref<GridSelectOption[]>([])

onMounted(async () => {
  primaryOptions.value = (await references.slot(SLOT.costCategoryPrimary))
    .map(option => ({ label: option.label, value: option.value }))
  secondaryOptions.value = (await references.slot(SLOT.costCategorySecondary))
    .map(option => ({ label: option.label, value: option.value }))
})

const columns = computed<GridColumn[]>(() => [
  { field: 'code', header: 'Category code', required: true, sortable: true, width: '170px', placeholder: 'e.g. DRILL, SERV, TANG' },
  { field: 'name', header: 'Category name', required: true, sortable: true, width: '230px', placeholder: 'e.g. Drilling, Services' },
  { field: 'primary_category_id', header: 'Parent (Primary Category)', type: 'select', options: primaryOptions.value, width: '230px' },
  { field: 'secondary_category_id', header: 'Secondary Category', type: 'select', options: secondaryOptions.value, width: '240px' },
  { field: 'description', header: 'Description', type: 'textarea', width: '280px' },
  { field: 'is_active', header: 'Status', type: 'checkbox', width: '110px' },
])

function fetchPage(params: Record<string, unknown>): Promise<PageResponse<Record<string, unknown>>> {
  return api.listPage(entity, params as Record<string, string>) as unknown as Promise<PageResponse<Record<string, unknown>>>
}

function toRow(record: Record<string, unknown>) {
  const item = record as unknown as MasterDataRecord
  return {
    id: item.id,
    code: item.code,
    name: item.name,
    primary_category_id: item.primary_category_id ?? '',
    secondary_category_id: item.secondary_category_id ?? '',
    description: item.description ?? '',
    is_active: item.is_active,
  }
}

function toPayload(row: EditableRow) {
  return {
    code: String(row.code ?? '').trim(),
    name: String(row.name ?? '').trim(),
    // The parent is derived from the secondary category when one is chosen, so
    // the two levels can never disagree.
    primary_category_id: row.primary_category_id || null,
    secondary_category_id: row.secondary_category_id || null,
    description: row.description || null,
    is_active: row.is_active !== false,
  }
}

const blankRow = () => ({ code: '', name: '', primary_category_id: '', secondary_category_id: '', description: '', is_active: true })

const description = computed(
  () => 'Group cost codes under the categories used in reporting and costing. Each cost category takes its parent from the Primary Category and its second level from the Secondary Category of the classification, so costing and catalogue data roll up the same way.',
)
</script>

<template>
  <div class="library-page">
    <PageHeader title="Cost Categories" :description="description" />
    <MasterDataNav active="cost-categories" />
    <div class="uom-tip">
      <i class="pi pi-info-circle" aria-hidden="true" />
      <span>Create your Primary and Secondary Categories first — a cost category is filed under them. Every Cost Code you define next must belong to one of these cost categories.</span>
    </div>
    <EnterpriseGrid
      title="Cost categories"
      singular="cost category"
      :columns="columns"
      :fetch-page="fetchPage"
      :to-row="toRow"
      :to-payload="toPayload"
      :blank-row="blankRow"
      :validate-rows="rows => api.validate(entity, rows as never)"
      :bulk-create="rows => api.bulkCreate(entity, rows as never)"
      :bulk-update="rows => api.bulkUpdate(entity, rows as never)"
      :remove-record="(id, hard) => (hard ? api.remove(entity, id) : api.deactivate(entity, id))"
      import-entity="cost-categories"
      export-entity="cost-categories"
      default-sort="code"
      search-placeholder="Search by category code or name…"
    />
  </div>
</template>
