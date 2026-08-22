/** Primary Category — top-level configurable classification.

Replaces the hardcoded applies_to values. Each Primary Category becomes a
dropdown option on Secondary Categories, Cost Categories, and any place that
needs a top-level scope selector.
*/
<script setup lang="ts">
import EnterpriseGrid from '~/components/data-grid/EnterpriseGrid.vue'
import MasterDataNav from '~/components/master-data/MasterDataNav.vue'
import PageHeader from '~/components/design-system/PageHeader.vue'
import type { EditableRow, GridColumn } from '~/types/grid'
import type { MasterDataRecord, PageResponse } from '~/types/masterData'

definePageMeta({ middleware: 'auth' })

const api = useMasterData()
const entity = 'primary-categories'

const columns: GridColumn[] = [
  { field: 'code', header: 'Category code', required: true, sortable: true, width: '170px', placeholder: 'e.g. DRILL, SERV, TANG' },
  { field: 'name', header: 'Category name', required: true, sortable: true, width: '240px', placeholder: 'e.g. Drilling, Services, Tangibles' },
  { field: 'description', header: 'Description', type: 'textarea', width: '300px' },
  { field: 'is_active', header: 'Status', type: 'checkbox', width: '110px' },
]

function fetchPage(params: Record<string, unknown>): Promise<PageResponse<Record<string, unknown>>> {
  return api.listPage(entity, params as Record<string, string>) as unknown as Promise<PageResponse<Record<string, unknown>>>
}

function toRow(record: Record<string, unknown>) {
  const item = record as unknown as MasterDataRecord
  return {
    id: item.id,
    code: item.code,
    name: item.name,
    description: item.description ?? '',
    is_active: item.is_active,
  }
}

function toPayload(row: EditableRow) {
  return {
    code: String(row.code ?? '').trim(),
    name: String(row.name ?? '').trim(),
    description: row.description || null,
    is_active: row.is_active !== false,
  }
}

const blankRow = () => ({ code: '', name: '', description: '', is_active: true })
</script>

<template>
  <div class="library-page">
    <PageHeader
      title="Primary Categories"
      description="Top-level configurable classification for catalogue items and cost structures. Each Primary Category appears as a dropdown option on Secondary Categories and Cost Categories — configure these first."
    />
    <MasterDataNav active="primary-categories" />

    <div class="uom-tip">
      <i class="pi pi-info-circle" aria-hidden="true" />
      <span>Primary Categories are the foundation of the classification hierarchy. Create these first, then configure Secondary and Tertiary categories beneath them.</span>
    </div>

    <EnterpriseGrid
      title="Primary categories"
      singular="primary category"
      :columns="columns"
      :fetch-page="fetchPage"
      :to-row="toRow"
      :to-payload="toPayload"
      :blank-row="blankRow"
      :validate-rows="rows => api.validate(entity, rows as never)"
      :bulk-create="rows => api.bulkCreate(entity, rows as never)"
      :bulk-update="rows => api.bulkUpdate(entity, rows as never)"
      :remove-record="(id, hard) => (hard ? api.remove(entity, id) : api.deactivate(entity, id))"
      import-entity="primary-categories"
      export-entity="primary-categories"
      default-sort="code"
      search-placeholder="Search primary categories…"
    />
  </div>
</template>
