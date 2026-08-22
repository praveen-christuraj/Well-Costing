/** Tertiary Category — third-level classification linked to a Secondary Category.

Auto-links to the Primary Category through its Secondary parent.
*/
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
const entity = 'tertiary-categories'

onMounted(() => {
  void references.load(['secondary-categories'])
})

const columns = computed<GridColumn[]>(() => [
  { field: 'code', header: 'Tertiary code', required: true, sortable: true, width: '170px', placeholder: 'e.g. HOIST, ROT' },
  { field: 'name', header: 'Tertiary name', required: true, sortable: true, width: '240px', placeholder: 'e.g. Hoisting, Rotating' },
  { field: 'secondary_category_id', header: 'Secondary Category', type: 'select', options: references.secondaryCategories.value, required: true, width: '240px' },
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
    secondary_category_id: item.secondary_category_id ?? '',
    description: item.description ?? '',
    is_active: item.is_active,
  }
}

function toPayload(row: EditableRow) {
  return {
    code: String(row.code ?? '').trim(),
    name: String(row.name ?? '').trim(),
    secondary_category_id: row.secondary_category_id || null,
    description: row.description || null,
    is_active: row.is_active !== false,
  }
}

const blankRow = () => ({ code: '', name: '', secondary_category_id: '', description: '', is_active: true })
</script>

<template>
  <div class="library-page">
    <PageHeader
      title="Tertiary Categories"
      description="Third-level classification linked to a Secondary Category. The Primary Category is auto-resolved through the Secondary parent — for example Drilling → Rig Operations → Hoisting."
    />
    <MasterDataNav active="tertiary-categories" />

    <div class="uom-tip">
      <i class="pi pi-info-circle" aria-hidden="true" />
      <span>Configure Primary and Secondary Categories first. Each Tertiary Category links to a Secondary Category, which auto-resolves the Primary.</span>
    </div>

    <EnterpriseGrid
      title="Tertiary categories"
      singular="tertiary category"
      :columns="columns"
      :fetch-page="fetchPage"
      :to-row="toRow"
      :to-payload="toPayload"
      :blank-row="blankRow"
      :validate-rows="rows => api.validate(entity, rows as never)"
      :bulk-create="rows => api.bulkCreate(entity, rows as never)"
      :bulk-update="rows => api.bulkUpdate(entity, rows as never)"
      :remove-record="(id, hard) => (hard ? api.remove(entity, id) : api.deactivate(entity, id))"
      import-entity="tertiary-categories"
      export-entity="tertiary-categories"
      default-sort="code"
      search-placeholder="Search tertiary categories…"
    />
  </div>
</template>
