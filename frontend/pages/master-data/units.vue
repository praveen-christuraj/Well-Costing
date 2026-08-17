/** Unit of measure configuration — all UOMs available across the application. */
<script setup lang="ts">
import { computed } from 'vue'
import EnterpriseGrid from '~/components/data-grid/EnterpriseGrid.vue'
import MasterDataNav from '~/components/master-data/MasterDataNav.vue'
import PageHeader from '~/components/design-system/PageHeader.vue'
import type { EditableRow, GridColumn } from '~/types/grid'
import type { MasterDataRecord, PageResponse } from '~/types/masterData'

definePageMeta({ middleware: 'auth' })

const api = useMasterData()
const entity = 'units'

const columns: GridColumn[] = [
  {
    field: 'code',
    header: 'UOM code',
    required: true,
    sortable: true,
    width: '130px',
    placeholder: 'e.g. M, BBL, DAY',
  },
  {
    field: 'name',
    header: 'Full name',
    required: true,
    sortable: true,
    width: '220px',
    placeholder: 'e.g. Metre, Barrel, Day',
  },
  {
    field: 'symbol',
    header: 'Symbol',
    width: '110px',
    placeholder: 'e.g. m, bbl, d',
  },
  {
    field: 'description',
    header: 'Notes',
    type: 'textarea',
    width: '280px',
  },
  {
    field: 'is_active',
    header: 'Status',
    type: 'checkbox',
    width: '110px',
  },
]

function fetchPage(params: Record<string, unknown>): Promise<PageResponse<Record<string, unknown>>> {
  return api.listPage(entity, params as Record<string, string>) as unknown as Promise<PageResponse<Record<string, unknown>>>
}

function toRow(record: Record<string, unknown>) {
  const unit = record as unknown as MasterDataRecord
  return {
    id: unit.id,
    code: unit.code,
    name: unit.name,
    symbol: unit.symbol ?? '',
    description: unit.description ?? '',
    is_active: unit.is_active,
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

const blankRow = () => ({
  code: '',
  name: '',
  symbol: '',
  description: '',
  is_active: true,
})

const description = computed(
  () => 'Define every unit of measure used across the application — services, tangibles, mud chemicals, cement additives, rates, and item prices. Once saved here, the UOM appears in all dropdown lists.',
)
</script>

<template>
  <div class="library-page">
    <PageHeader title="Units of Measure (UOM)" :description="description" />
    <MasterDataNav active="units" />
    <div class="uom-tip">
      <i class="pi pi-info-circle" aria-hidden="true" />
      <span>Configure all UOMs here first. They will appear in the dropdowns across Services, Tangibles, Mud Chemicals, Cement Additives, Service Rates, and Item Prices.</span>
    </div>
    <EnterpriseGrid
      title="Units of measure"
      singular="unit"
      :columns="columns"
      :fetch-page="fetchPage"
      :to-row="toRow"
      :to-payload="toPayload"
      :blank-row="blankRow"
      :bulk-create="rows => api.bulkCreate(entity, rows as never)"
      :bulk-update="rows => api.bulkUpdate(entity, rows as never)"
      :remove-record="(id, hard) => (hard ? api.remove(entity, id) : api.deactivate(entity, id))"
      import-entity="units"
      export-entity="units"
      default-sort="code"
      search-placeholder="Search by code, name, or symbol…"
    />
  </div>
</template>
