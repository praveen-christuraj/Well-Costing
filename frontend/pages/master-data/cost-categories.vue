/** Cost category register — the top level of the cost classification hierarchy. */
<script setup lang="ts">
import { computed, onMounted } from 'vue'
import EnterpriseGrid from '~/components/data-grid/EnterpriseGrid.vue'
import MasterDataNav from '~/components/master-data/MasterDataNav.vue'
import PageHeader from '~/components/design-system/PageHeader.vue'
import type { EditableRow, GridColumn } from '~/types/grid'
import type { MasterDataRecord, PageResponse } from '~/types/masterData'

definePageMeta({ middleware: 'auth' })

const api = useMasterData()
const references = useReferenceOptions()
const entity = 'cost-categories'

onMounted(() => {
  void references.load(['cost-categories'])
})

const columns = computed<GridColumn[]>(() => [
  { field: 'code', header: 'Category code', required: true, sortable: true, width: '170px', placeholder: 'e.g. DRILL, SERV, TANG' },
  { field: 'name', header: 'Category name', required: true, sortable: true, width: '230px', placeholder: 'e.g. Drilling, Services' },
  { field: 'parent_id', header: 'Parent category', type: 'select', options: references.costCategories.value, width: '210px' },
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
    parent_id: item.parent_id ?? '',
    description: item.description ?? '',
    is_active: item.is_active,
  }
}

function toPayload(row: EditableRow) {
  return {
    code: String(row.code ?? '').trim(),
    name: String(row.name ?? '').trim(),
    parent_id: row.parent_id || null,
    description: row.description || null,
    is_active: row.is_active !== false,
  }
}

const blankRow = () => ({ code: '', name: '', parent_id: '', description: '', is_active: true })

const description = computed(
  () => 'Group cost codes under the categories used in reporting and costing — Drilling, Services, Tangibles, Consumables, and so on. Cost codes belong to a category; categories keep the code list organised and summarise neatly.',
)
</script>

<template>
  <div class="library-page">
    <PageHeader title="Cost Categories" :description="description" />
    <MasterDataNav active="cost-categories" />
    <div class="uom-tip">
      <i class="pi pi-info-circle" aria-hidden="true" />
      <span>Create your cost categories first. Every Cost Code you define next must belong to one of these categories, so plan the grouping before you start adding codes.</span>
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
