/** Effective-dated purchase prices for tangibles, mud chemicals, and cement additives. */
<script setup lang="ts">
import { computed, onMounted } from 'vue'
import EnterpriseGrid from '~/components/data-grid/EnterpriseGrid.vue'
import MasterDataNav from '~/components/master-data/MasterDataNav.vue'
import PageHeader from '~/components/design-system/PageHeader.vue'
import type { EditableRow, GridColumn, GridFilterDefinition } from '~/types/grid'
import type { PageResponse } from '~/types/masterData'
import type { ItemPriceRecord } from '~/types/procurement'

definePageMeta({ middleware: 'auth' })

const procurement = useProcurement()
const references = useReferenceOptions()
const itemTypeOptions = [
  { label: 'Tangible', value: 'tangible' },
  { label: 'Mud chemical', value: 'mud_chemical' },
  { label: 'Cement additive', value: 'cement_additive' },
  { label: 'Material', value: 'material' },
]

onMounted(() => {
  void references.load(['vendors', 'currencies', 'units', 'purchase-orders', 'catalogue'])
})

const columns = computed<GridColumn[]>(() => [
    { field: 'item_id', header: 'Item', type: 'select', options: references.catalogueItems.value, required: true, width: '260px' },
    { field: 'item_type', header: 'Type', readonly: true, width: '145px', display: row => itemTypeOptions.find(option => option.value === row.item_type)?.label ?? '—' },
    { field: 'vendor_id', header: 'Vendor', type: 'select', options: references.vendors.value, required: true, width: '210px' },
    { field: 'purchase_order_id', header: 'Purchase order', type: 'select', options: references.purchaseOrders.value, width: '225px' },
    { field: 'unit_price', header: 'Unit price', type: 'number', numeric: true, required: true, sortable: true, width: '160px' },
    { field: 'currency_id', header: 'Currency', type: 'select', options: references.currencies.value, required: true, width: '155px' },
    { field: 'unit_id', header: 'UOM', type: 'select', options: references.units.value, required: true, width: '150px' },
    { field: 'effective_from', header: 'Effective from', type: 'date', required: true, sortable: true, width: '170px' },
    { field: 'effective_to', header: 'Effective to', type: 'date', sortable: true, width: '165px' },
    { field: 'description', header: 'Notes', type: 'textarea', width: '190px' },
    { field: 'is_active', header: 'Active', type: 'checkbox', width: '110px' },
])

const filters = computed<GridFilterDefinition[]>(() => [
    { key: 'item_type', label: 'Item type', type: 'select', options: itemTypeOptions, width: '175px' },
    { key: 'vendor_id', label: 'Vendor', type: 'select', options: references.vendors.value, width: '205px' },
    { key: 'purchase_order_id', label: 'Purchase order', type: 'select', options: references.purchaseOrders.value, width: '215px' },
    { key: 'effective_on', label: 'Effective on', type: 'date' },
])

function fetchPage(params: Record<string, unknown>): Promise<PageResponse<Record<string, unknown>>> {
  return procurement.itemPrices.list(params as never) as unknown as Promise<PageResponse<Record<string, unknown>>>
}

function toRow(record: Record<string, unknown>) {
  const price = record as unknown as ItemPriceRecord
  return {
    id: price.id,
    item_id: price.item_id,
    item_type: price.item_type ?? '',
    vendor_id: price.vendor_id,
    purchase_order_id: price.purchase_order_id ?? '',
    unit_price: Number(price.unit_price),
    currency_id: price.currency_id,
    unit_id: price.unit_id,
    effective_from: price.effective_from,
    effective_to: price.effective_to ?? '',
    description: price.description ?? '',
    is_active: price.is_active,
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
    item_id: row.item_id,
    vendor_id: row.vendor_id,
    purchase_order_id: row.purchase_order_id || null,
    unit_price: row.unit_price === null || row.unit_price === '' ? '0' : String(row.unit_price),
    currency_id: row.currency_id,
    unit_id: row.unit_id,
    effective_from: asDate(row.effective_from),
    effective_to: asDate(row.effective_to),
    description: row.description || null,
    is_active: row.is_active !== false,
  }
}

const blankRow = () => ({
  item_id: '',
  item_type: '',
  vendor_id: '',
  purchase_order_id: '',
  unit_price: 0,
  currency_id: '',
  unit_id: '',
  effective_from: '',
  effective_to: '',
  description: '',
  is_active: true,
})
</script>

<template>
  <div class="library-page">
    <PageHeader
      title="Item Prices"
      description="Maintain effective-dated purchase prices for tangibles, mud chemicals, and cement additives, each linked to its vendor and purchase order so AFE tangible and consumable costs stay traceable."
    />
    <MasterDataNav active="item-prices" />
    <EnterpriseGrid
      title="Item prices"
      singular="item price"
      :columns="columns"
      :filters="filters"
      :fetch-page="fetchPage"
      :to-row="toRow"
      :to-payload="toPayload"
      :blank-row="blankRow"
      :validate-rows="rows => procurement.itemPrices.validate(rows)"
      :bulk-create="rows => procurement.itemPrices.bulkCreate(rows)"
      :bulk-update="rows => procurement.itemPrices.bulkUpdate(rows)"
      :remove-record="(id, hard) => procurement.itemPrices.remove(id, hard)"
      import-entity="item-prices"
      export-entity="item-prices"
      default-sort="effective_from"
      default-sort-order="desc"
      search-placeholder="Search by item code, name, or material number…"
    />
  </div>
</template>
