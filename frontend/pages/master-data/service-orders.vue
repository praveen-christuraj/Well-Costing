/** Service order register linking vendors to the contracts that govern service rates. */
<script setup lang="ts">
import { computed, onMounted } from 'vue'
import EnterpriseGrid from '~/components/data-grid/EnterpriseGrid.vue'
import MasterDataNav from '~/components/master-data/MasterDataNav.vue'
import PageHeader from '~/components/design-system/PageHeader.vue'
import type { EditableRow, GridColumn, GridFilterDefinition } from '~/types/grid'
import type { PageResponse } from '~/types/masterData'
import { SERVICE_ORDER_STATUSES, type ServiceOrderRecord } from '~/types/procurement'

definePageMeta({ middleware: 'auth' })

const procurement = useProcurement()
const references = useReferenceOptions()
onMounted(() => {
  void references.load(['vendors', 'currencies'])
})

const columns = computed<GridColumn[]>(() => [
    { field: 'order_number', header: 'Service order no.', required: true, sortable: true, width: '180px', placeholder: 'SO-2026-0001' },
    { field: 'title', header: 'Title', required: true, sortable: true, width: '240px' },
    { field: 'vendor_id', header: 'Vendor', type: 'select', options: references.vendors.value, required: true, width: '220px' },
    { field: 'status', header: 'Status', type: 'select', options: SERVICE_ORDER_STATUSES, width: '160px', sortable: true },
    { field: 'valid_from', header: 'Valid from', type: 'date', required: true, sortable: true, width: '165px' },
    { field: 'valid_to', header: 'Valid to', type: 'date', sortable: true, width: '165px' },
    { field: 'contract_value', header: 'Contract value', type: 'number', numeric: true, width: '170px', suffixField: 'currency_code' },
    { field: 'currency_id', header: 'Currency', type: 'select', options: references.currencies.value, width: '160px' },
    { field: 'description', header: 'Notes', type: 'textarea', width: '200px' },
    { field: 'is_active', header: 'Active', type: 'checkbox', width: '110px' },
])

const filters = computed<GridFilterDefinition[]>(() => [
    { key: 'vendor_id', label: 'Vendor', type: 'select', options: references.vendors.value, width: '210px' },
    { key: 'status', label: 'Status', type: 'select', options: SERVICE_ORDER_STATUSES, width: '160px' },
    { key: 'valid_on', label: 'Valid on', type: 'date' },
])

function fetchPage(params: Record<string, unknown>): Promise<PageResponse<Record<string, unknown>>> {
  return procurement.serviceOrders.list(params as never) as unknown as Promise<PageResponse<Record<string, unknown>>>
}

function toRow(record: Record<string, unknown>) {
  const order = record as unknown as ServiceOrderRecord
  return {
    id: order.id,
    order_number: order.order_number,
    title: order.title,
    vendor_id: order.vendor_id,
    currency_id: order.currency_id ?? '',
    currency_code: order.currency_code ?? '',
    status: order.status,
    valid_from: order.valid_from,
    valid_to: order.valid_to ?? '',
    contract_value: order.contract_value === null ? null : Number(order.contract_value),
    description: order.description ?? '',
    is_active: order.is_active,
  }
}

function asDate(value: unknown): string | null {
  if (!value) return null
  if (value instanceof Date) {
    const offset = value.getTimezoneOffset() * 60000
    return new Date(value.getTime() - offset).toISOString().slice(0, 10)
  }
  return String(value)
}

function toPayload(row: EditableRow) {
  return {
    order_number: String(row.order_number ?? '').trim(),
    title: String(row.title ?? '').trim(),
    vendor_id: row.vendor_id,
    currency_id: row.currency_id || null,
    status: row.status || 'draft',
    valid_from: asDate(row.valid_from),
    valid_to: asDate(row.valid_to),
    contract_value: row.contract_value === null || row.contract_value === '' ? null : String(row.contract_value),
    description: row.description || null,
    is_active: row.is_active !== false,
  }
}

const blankRow = () => ({
  order_number: '',
  title: '',
  vendor_id: '',
  currency_id: '',
  status: 'draft',
  valid_from: '',
  valid_to: '',
  contract_value: null,
  description: '',
  is_active: true,
})
</script>

<template>
  <div class="library-page">
    <PageHeader
      title="Service Orders"
      description="Register the service orders and contracts each vendor works under. Service rates reference these orders so every AFE line traces back to a commercial agreement."
    />
    <MasterDataNav active="service-orders" />
    <EnterpriseGrid
      title="Service orders"
      singular="service order"
      :columns="columns"
      :filters="filters"
      :fetch-page="fetchPage"
      :to-row="toRow"
      :to-payload="toPayload"
      :blank-row="blankRow"
      :validate-rows="rows => procurement.serviceOrders.validate(rows)"
      :bulk-create="rows => procurement.serviceOrders.bulkCreate(rows)"
      :bulk-update="rows => procurement.serviceOrders.bulkUpdate(rows)"
      :remove-record="(id, hard) => procurement.serviceOrders.remove(id, hard)"
      import-entity="service-orders"
      default-sort="order_number"
      search-placeholder="Search by order number or title…"
    />
  </div>
</template>
