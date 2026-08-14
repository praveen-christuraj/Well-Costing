/**
 * Service rate cards. Each row holds the operating, standby, mobilisation, and
 * demobilisation rates side by side, optionally scoped to a hole section.
 */
<script setup lang="ts">
import { computed, onMounted } from 'vue'
import EnterpriseGrid from '~/components/data-grid/EnterpriseGrid.vue'
import MasterDataNav from '~/components/master-data/MasterDataNav.vue'
import PageHeader from '~/components/design-system/PageHeader.vue'
import type { EditableRow, GridColumn, GridFilterDefinition } from '~/types/grid'
import type { PageResponse } from '~/types/masterData'
import { HOLE_SECTIONS, type ServiceRateRecord } from '~/types/procurement'

definePageMeta({ middleware: 'auth' })

const procurement = useProcurement()
const references = useReferenceOptions()
const sectionOptions = HOLE_SECTIONS.map(section => ({ label: section, value: section }))

onMounted(() => {
  void references.load(['vendors', 'currencies', 'units', 'services', 'service-orders'])
})

const columns = computed<GridColumn[]>(() => [
    { field: 'service_id', header: 'Service', type: 'select', options: references.services.value, required: true, width: '230px' },
    { field: 'vendor_id', header: 'Vendor', type: 'select', options: references.vendors.value, required: true, width: '210px' },
    { field: 'service_order_id', header: 'Service order', type: 'select', options: references.serviceOrders.value, width: '215px' },
    { field: 'hole_section', header: 'Hole section', type: 'select', options: sectionOptions, width: '155px', placeholder: 'All sections' },
    { field: 'operating_rate', header: 'Operating', type: 'number', numeric: true, sortable: true, width: '150px' },
    { field: 'standby_rate', header: 'Standby', type: 'number', numeric: true, width: '145px' },
    { field: 'mobilisation_rate', header: 'Mobilisation', type: 'number', numeric: true, width: '150px' },
    { field: 'demobilisation_rate', header: 'Demobilisation', type: 'number', numeric: true, width: '160px' },
    { field: 'currency_id', header: 'Currency', type: 'select', options: references.currencies.value, required: true, width: '155px' },
    { field: 'unit_id', header: 'Per unit', type: 'select', options: references.units.value, required: true, width: '150px' },
    { field: 'effective_from', header: 'Effective from', type: 'date', required: true, sortable: true, width: '170px' },
    { field: 'effective_to', header: 'Effective to', type: 'date', sortable: true, width: '165px' },
    { field: 'description', header: 'Notes', type: 'textarea', width: '190px' },
    { field: 'is_active', header: 'Active', type: 'checkbox', width: '110px' },
])

const filters = computed<GridFilterDefinition[]>(() => [
    { key: 'service_id', label: 'Service', type: 'select', options: references.services.value, width: '215px' },
    { key: 'vendor_id', label: 'Vendor', type: 'select', options: references.vendors.value, width: '205px' },
    { key: 'service_order_id', label: 'Service order', type: 'select', options: references.serviceOrders.value, width: '215px' },
    { key: 'hole_section', label: 'Hole section', type: 'select', options: sectionOptions, width: '150px' },
    { key: 'effective_on', label: 'Effective on', type: 'date' },
])

function fetchPage(params: Record<string, unknown>): Promise<PageResponse<Record<string, unknown>>> {
  return procurement.serviceRates.list(params as never) as unknown as Promise<PageResponse<Record<string, unknown>>>
}

function toRow(record: Record<string, unknown>) {
  const rate = record as unknown as ServiceRateRecord
  return {
    id: rate.id,
    service_id: rate.service_id,
    vendor_id: rate.vendor_id,
    service_order_id: rate.service_order_id ?? '',
    hole_section: rate.hole_section ?? '',
    operating_rate: Number(rate.operating_rate),
    standby_rate: Number(rate.standby_rate),
    mobilisation_rate: Number(rate.mobilisation_rate),
    demobilisation_rate: Number(rate.demobilisation_rate),
    currency_id: rate.currency_id,
    unit_id: rate.unit_id,
    effective_from: rate.effective_from,
    effective_to: rate.effective_to ?? '',
    description: rate.description ?? '',
    is_active: rate.is_active,
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

function money(value: unknown): string {
  return value === null || value === undefined || value === '' ? '0' : String(value)
}

function toPayload(row: EditableRow) {
  return {
    service_id: row.service_id,
    vendor_id: row.vendor_id,
    service_order_id: row.service_order_id || null,
    hole_section: row.hole_section || null,
    operating_rate: money(row.operating_rate),
    standby_rate: money(row.standby_rate),
    mobilisation_rate: money(row.mobilisation_rate),
    demobilisation_rate: money(row.demobilisation_rate),
    currency_id: row.currency_id,
    unit_id: row.unit_id,
    effective_from: asDate(row.effective_from),
    effective_to: asDate(row.effective_to),
    description: row.description || null,
    is_active: row.is_active !== false,
  }
}

const blankRow = () => ({
  service_id: '',
  vendor_id: '',
  service_order_id: '',
  hole_section: '',
  operating_rate: 0,
  standby_rate: 0,
  mobilisation_rate: 0,
  demobilisation_rate: 0,
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
      title="Service Rates"
      description="Hold operating, standby, mobilisation, and demobilisation rates for each service and vendor on a single row. Add a hole section to capture section-wise rates, and use effective dates to keep rate history auditable."
    />
    <MasterDataNav active="service-rates" />
    <EnterpriseGrid
      title="Service rates"
      singular="service rate"
      :columns="columns"
      :filters="filters"
      :fetch-page="fetchPage"
      :to-row="toRow"
      :to-payload="toPayload"
      :blank-row="blankRow"
      :validate-rows="rows => procurement.serviceRates.validate(rows)"
      :bulk-create="rows => procurement.serviceRates.bulkCreate(rows)"
      :bulk-update="rows => procurement.serviceRates.bulkUpdate(rows)"
      :remove-record="(id, hard) => procurement.serviceRates.remove(id, hard)"
      default-sort="effective_from"
      default-sort-order="desc"
      search-placeholder="Search by service code or name…"
    />
  </div>
</template>
