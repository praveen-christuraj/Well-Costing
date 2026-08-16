/** Manage currency codes used across service orders, purchase orders, and pricing. */
<script setup lang="ts">
import EnterpriseGrid from '~/components/data-grid/EnterpriseGrid.vue'
import MasterDataNav from '~/components/master-data/MasterDataNav.vue'
import PageHeader from '~/components/design-system/PageHeader.vue'
import type { EditableRow, GridColumn, GridFilterDefinition } from '~/types/grid'
import type { MasterDataRecord, PageResponse } from '~/types/masterData'

definePageMeta({ middleware: 'auth' })

const api = useMasterData()
const entity = 'currencies'

const columns: GridColumn[] = [
  { field: 'code', header: 'Currency code', required: true, sortable: true, width: '170px', placeholder: 'USD' },
  { field: 'name', header: 'Currency name', required: true, sortable: true, width: '230px', placeholder: 'US Dollar' },
  { field: 'symbol', header: 'Symbol', width: '130px', placeholder: '$' },
  { field: 'description', header: 'Description', type: 'textarea', width: '280px' },
  { field: 'is_active', header: 'Status', type: 'checkbox', width: '110px' },
]

const filters: GridFilterDefinition[] = []

function fetchPage(params: Record<string, unknown>): Promise<PageResponse<Record<string, unknown>>> {
  return api.listPage(entity, params as Record<string, string>) as unknown as Promise<PageResponse<Record<string, unknown>>>
}

function toRow(record: Record<string, unknown>) {
  const item = record as unknown as MasterDataRecord
  return {
    id: item.id,
    code: item.code,
    name: item.name,
    symbol: item.symbol ?? '',
    description: item.description ?? '',
    is_active: item.is_active,
  }
}

function toPayload(row: EditableRow) {
  return {
    code: String(row.code ?? '').trim().toUpperCase(),
    name: String(row.name ?? '').trim(),
    symbol: row.symbol || null,
    description: row.description || null,
    is_active: row.is_active !== false,
  }
}

const blankRow = () => ({ code: '', name: '', symbol: '', description: '', is_active: true })
</script>

<template>
  <div class="library-page">
    <PageHeader
      title="Currencies"
      description="Maintain the list of active currencies. Currencies appear in the dropdown for service orders, purchase orders, service rates, and item prices."
    />
    <MasterDataNav active="currencies" />
    <EnterpriseGrid
      title="Currencies"
      singular="currency"
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
      import-entity="currencies"
      default-sort="code"
      search-placeholder="Search currencies…"
    />
  </div>
</template>