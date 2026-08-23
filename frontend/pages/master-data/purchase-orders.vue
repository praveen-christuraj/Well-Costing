/** Purchase order register covering tangibles and consumables procurement. */
<script setup lang="ts">
import { computed, onMounted } from 'vue'
import EnterpriseGrid from '~/components/data-grid/EnterpriseGrid.vue'
import MasterDataNav from '~/components/master-data/MasterDataNav.vue'
import PageHeader from '~/components/design-system/PageHeader.vue'
import type { EditableRow, GridColumn, GridFilterDefinition } from '~/types/grid'
import type { PageResponse } from '~/types/masterData'
import { PURCHASE_ORDER_STATUSES, type PurchaseOrderRecord } from '~/types/procurement'

definePageMeta({ middleware: 'auth' })

const procurement = useProcurement()
const references = useReferenceOptions()
onMounted(() => {
  void references.load(['vendors', 'currencies'])
})

const columns = computed<GridColumn[]>(() => [
    { field: 'order_number', header: 'Purchase order no.', required: true, sortable: true, width: '185px', placeholder: 'PO-2026-0101' },
    { field: 'title', header: 'Title', required: true, sortable: true, width: '240px' },
    { field: 'vendor_id', header: 'Vendor', type: 'select', options: references.vendors.value, required: true, width: '220px' },
    { field: 'status', header: 'Status', type: 'select', options: PURCHASE_ORDER_STATUSES, width: '180px', sortable: true },
    { field: 'order_date', header: 'Order date', type: 'date', required: true, sortable: true, width: '165px' },
    { field: 'expected_delivery_date', header: 'Expected delivery', type: 'date', width: '175px' },
    { field: 'order_value', header: 'Order value', type: 'number', numeric: true, width: '165px', suffixField: 'currency_code' },
    { field: 'currency_id', header: 'Currency', type: 'select', options: references.currencies.value, width: '160px' },
    { field: 'description', header: 'Notes', type: 'textarea', width: '200px' },
    { field: 'is_active', header: 'Active', type: 'checkbox', width: '110px' },
])

const filters = computed<GridFilterDefinition[]>(() => [
    { key: 'vendor_id', label: 'Vendor', type: 'select', options: references.vendors.value, width: '210px' },
    { key: 'status', label: 'Status', type: 'select', options: PURCHASE_ORDER_STATUSES, width: '180px' },
])

function fetchPage(params: Record<string, unknown>): Promise<PageResponse<Record<string, unknown>>> {
  return procurement.purchaseOrders.list(params as never) as unknown as Promise<PageResponse<Record<string, unknown>>>
}

function toRow(record: Record<string, unknown>) {
  const order = record as unknown as PurchaseOrderRecord
  return {
    id: order.id,
    order_number: order.order_number,
    title: order.title,
    vendor_id: order.vendor_id,
    currency_id: order.currency_id ?? '',
    currency_code: order.currency_code ?? '',
    status: order.status,
    order_date: order.order_date,
    expected_delivery_date: order.expected_delivery_date ?? '',
    order_value: order.order_value === null ? null : Number(order.order_value),
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
    order_date: asDate(row.order_date),
    expected_delivery_date: asDate(row.expected_delivery_date),
    order_value: row.order_value === null || row.order_value === '' ? null : String(row.order_value),
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
  order_date: '',
  expected_delivery_date: '',
  order_value: null,
  description: '',
  is_active: true,
})
</script>

<template>
  <div class="library-page">
    <PageHeader
      title="Purchase Orders"
      description="Register the purchase orders used to procure tangibles and consumables. These are held for reference only — a rate may quote an order for traceability, but no catalogue item has to be linked to one."
    />
    <MasterDataNav active="purchase-orders" />
    <EnterpriseGrid
      title="Purchase orders"
      singular="purchase order"
      :columns="columns"
      :filters="filters"
      :fetch-page="fetchPage"
      :to-row="toRow"
      :to-payload="toPayload"
      :blank-row="blankRow"
      :validate-rows="rows => procurement.purchaseOrders.validate(rows)"
      :bulk-create="rows => procurement.purchaseOrders.bulkCreate(rows)"
      :bulk-update="rows => procurement.purchaseOrders.bulkUpdate(rows)"
      :remove-record="(id, hard) => procurement.purchaseOrders.remove(id, hard)"
      import-entity="purchase-orders"
      export-entity="purchase-orders"
      default-sort="order_number"
      search-placeholder="Search by order number or title…"
    />
  </div>
</template>
