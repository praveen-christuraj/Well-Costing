/** Secondary Category — second-level classification linked to a Primary Category.

Each Secondary Category belongs to one Primary Category. Cost Categories pick
their parent from this level.
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
const entity = 'secondary-categories'

onMounted(() => {
  void references.load(['primary-categories'])
})

const columns = computed<GridColumn[]>(() => [
  { field: 'code', header: 'Sub category code', required: true, sortable: true, width: '170px', placeholder: 'e.g. RIG-OPS, CEM' },
  { field: 'name', header: 'Sub category name', required: true, sortable: true, width: '240px', placeholder: 'e.g. Rig Operations, Cementing' },
  { field: 'primary_category_id', header: 'Primary Category', type: 'select', options: references.primaryCategories.value, required: true, width: '220px' },
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
    description: item.description ?? '',
    is_active: item.is_active,
  }
}

function toPayload(row: EditableRow) {
  return {
    code: String(row.code ?? '').trim(),
    name: String(row.name ?? '').trim(),
    primary_category_id: row.primary_category_id || null,
    description: row.description || null,
    is_active: row.is_active !== false,
  }
}

const blankRow = () => ({ code: '', name: '', primary_category_id: '', description: '', is_active: true })
</script>

<template>
  <div class="library-page">
    <PageHeader
      title="Secondary Categories"
      description="Second-level classification linked to a Primary Category. Each sub category belongs to exactly one Primary — for example Drilling → Rig Operations, Services → Cementing."
    />
    <MasterDataNav active="secondary-categories" />

    <div class="uom-tip">
      <i class="pi pi-info-circle" aria-hidden="true" />
      <span>Configure Primary Categories first. Each Secondary Category must belong to a Primary Category chosen from the dropdown.</span>
    </div>

    <EnterpriseGrid
      title="Secondary categories"
      singular="secondary category"
      :columns="columns"
      :fetch-page="fetchPage"
      :to-row="toRow"
      :to-payload="toPayload"
      :blank-row="blankRow"
      :validate-rows="rows => api.validate(entity, rows as never)"
      :bulk-create="rows => api.bulkCreate(entity, rows as never)"
      :bulk-update="rows => api.bulkUpdate(entity, rows as never)"
      :remove-record="(id, hard) => (hard ? api.remove(entity, id) : api.deactivate(entity, id))"
      import-entity="secondary-categories"
      export-entity="secondary-categories"
      default-sort="code"
      search-placeholder="Search secondary categories…"
    />
  </div>
</template>
