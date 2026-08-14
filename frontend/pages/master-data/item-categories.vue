/** Catalogue sub-classification: bits, casings, shoes and collars, wellheads, and so on. */
<script setup lang="ts">
import EnterpriseGrid from '~/components/data-grid/EnterpriseGrid.vue'
import MasterDataNav from '~/components/master-data/MasterDataNav.vue'
import PageHeader from '~/components/design-system/PageHeader.vue'
import type { EditableRow, GridColumn, GridFilterDefinition } from '~/types/grid'
import type { MasterDataRecord, PageResponse } from '~/types/masterData'
import { ITEM_CATEGORY_SCOPES } from '~/types/procurement'

definePageMeta({ middleware: 'auth' })

const api = useMasterData()
const entity = 'item-categories'

const columns: GridColumn[] = [
  { field: 'code', header: 'Category code', required: true, sortable: true, width: '170px', placeholder: 'BITS' },
  { field: 'name', header: 'Category name', required: true, sortable: true, width: '230px', placeholder: 'Drill Bits' },
  { field: 'applies_to', header: 'Applies to', type: 'select', options: ITEM_CATEGORY_SCOPES, required: true, width: '170px' },
  { field: 'description', header: 'Description', type: 'textarea', width: '280px' },
  { field: 'is_active', header: 'Status', type: 'checkbox', width: '110px' },
]

const filters: GridFilterDefinition[] = [
  { key: 'applies_to', label: 'Applies to', type: 'select', options: ITEM_CATEGORY_SCOPES },
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
    applies_to: item.applies_to ?? 'tangible',
    description: item.description ?? '',
    is_active: item.is_active,
  }
}

function toPayload(row: EditableRow) {
  return {
    code: String(row.code ?? '').trim(),
    name: String(row.name ?? '').trim(),
    applies_to: row.applies_to || 'tangible',
    description: row.description || null,
    is_active: row.is_active !== false,
  }
}

const blankRow = () => ({ code: '', name: '', applies_to: 'tangible', description: '', is_active: true })
</script>

<template>
  <div class="library-page">
    <PageHeader
      title="Item Categories"
      description="Group catalogue items into the classifications used on the AFE — bits, casings, centralisers, float shoes and collars, plugs, wellheads, pup joints, and consumable groups."
    />
    <MasterDataNav active="item-categories" />
    <EnterpriseGrid
      title="Item categories"
      singular="item category"
      :columns="columns"
      :filters="filters"
      :fetch-page="fetchPage"
      :to-row="toRow"
      :to-payload="toPayload"
      :blank-row="blankRow"
      :validate-rows="rows => api.validate(entity, rows as never)"
      :bulk-create="rows => api.bulkCreate(entity, rows as never)"
      :bulk-update="rows => api.bulkUpdate(entity, rows as never)"
      :remove-record="(id, hard) => (hard ? api.remove(entity, id) : api.deactivate(entity, id))"
      default-sort="code"
      search-placeholder="Search categories…"
    />
  </div>
</template>
