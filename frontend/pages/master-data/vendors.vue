/** Vendor register covering both third-party and in-house providers. */
<script setup lang="ts">
import { computed } from 'vue'
import EnterpriseGrid from '~/components/data-grid/EnterpriseGrid.vue'
import MasterDataNav from '~/components/master-data/MasterDataNav.vue'
import PageHeader from '~/components/design-system/PageHeader.vue'
import type { EditableRow, GridColumn, GridFilterDefinition } from '~/types/grid'
import type { MasterDataRecord, PageResponse } from '~/types/masterData'
import { VENDOR_TYPES } from '~/types/procurement'

definePageMeta({ middleware: 'auth' })

const api = useMasterData()
const entity = 'vendors'

const columns: GridColumn[] = [
  { field: 'code', header: 'Vendor code', required: true, sortable: true, width: '150px', placeholder: 'SLB' },
  { field: 'name', header: 'Vendor name', required: true, sortable: true, width: '220px' },
  { field: 'vendor_type', header: 'Type', type: 'select', options: VENDOR_TYPES, required: true, width: '150px' },
  { field: 'contact_person', header: 'Contact person', width: '170px' },
  { field: 'email', header: 'Email', width: '200px' },
  { field: 'phone', header: 'Phone', width: '150px' },
  { field: 'country', header: 'Country', width: '140px' },
  { field: 'description', header: 'Notes', type: 'textarea', width: '200px' },
  { field: 'is_active', header: 'Status', type: 'checkbox', width: '110px' },
]

const filters: GridFilterDefinition[] = [
  { key: 'vendor_type', label: 'Vendor type', type: 'select', options: VENDOR_TYPES },
]

function fetchPage(params: Record<string, unknown>): Promise<PageResponse<Record<string, unknown>>> {
  return api.listPage(entity, params as Record<string, string>) as unknown as Promise<PageResponse<Record<string, unknown>>>
}

function toRow(record: Record<string, unknown>) {
  const vendor = record as unknown as MasterDataRecord
  return {
    id: vendor.id,
    code: vendor.code,
    name: vendor.name,
    vendor_type: vendor.vendor_type ?? 'third_party',
    contact_person: vendor.contact_person ?? '',
    email: vendor.email ?? '',
    phone: vendor.phone ?? '',
    country: vendor.country ?? '',
    description: vendor.description ?? '',
    is_active: vendor.is_active,
  }
}

function toPayload(row: EditableRow) {
  return {
    code: String(row.code ?? '').trim(),
    name: String(row.name ?? '').trim(),
    vendor_type: row.vendor_type || 'third_party',
    contact_person: row.contact_person || null,
    email: row.email || null,
    phone: row.phone || null,
    country: row.country || null,
    description: row.description || null,
    is_active: row.is_active !== false,
  }
}

const blankRow = () => ({
  code: '',
  name: '',
  vendor_type: 'third_party',
  contact_person: '',
  email: '',
  phone: '',
  country: '',
  description: '',
  is_active: true,
})

const description = computed(
  () => 'Maintain every service and material provider, classified as third-party or in-house, with the contacts used across service orders, purchase orders, and rates.',
)

async function exportWorkbook(): Promise<void> {
  const blob = await api.export(entity)
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = 'vendors-export.xlsx'
  anchor.click()
  URL.revokeObjectURL(url)
}
</script>

<template>
  <div class="library-page">
    <PageHeader title="Vendors" :description="description" />
    <MasterDataNav active="vendors" />
    <EnterpriseGrid
      title="Vendors"
      singular="vendor"
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
      :on-export="exportWorkbook"
      import-entity="vendors"
      default-sort="code"
      search-placeholder="Search by vendor code or name…"
    />
  </div>
</template>
