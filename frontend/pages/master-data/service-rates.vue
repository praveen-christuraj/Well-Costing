/**
 * Service rate cards. Each row holds the equipment and personnel operating/standby, mobilisation, demobilisation, and
 * other rates side by side, optionally scoped to a configured hole section.
 */
<script setup lang="ts">
import { computed, onMounted } from 'vue'
import EnterpriseGrid from '~/components/data-grid/EnterpriseGrid.vue'
import MasterDataNav from '~/components/master-data/MasterDataNav.vue'
import PageHeader from '~/components/design-system/PageHeader.vue'
import type { EditableRow, GridColumn, GridFilterDefinition } from '~/types/grid'
import type { PageResponse } from '~/types/masterData'
import { SERVICE_RATE_BASES, type ServiceRateRecord } from '~/types/procurement'

definePageMeta({ middleware: 'auth' })

const procurement = useProcurement()
const references = useReferenceOptions()

onMounted(() => {
  void references.load(['vendors', 'currencies', 'units', 'services', 'hole-sections'])
})

const columns = computed<GridColumn[]>(() => [
    { field: 'service_id', header: 'Service', type: 'select', options: references.services.value, required: true, width: '230px' },
    { field: 'vendor_id', header: 'Vendor', type: 'select', options: references.vendors.value, required: true, width: '210px' },
    { field: 'rate_basis', header: 'Rate basis', type: 'select', options: SERVICE_RATE_BASES, required: true, width: '155px' },
    { field: 'hole_section_id', header: 'Hole section', type: 'select', options: references.holeSections.value, width: '180px', placeholder: 'All sections' },
    { field: 'operating_rate', header: 'Operating', type: 'number', numeric: true, sortable: true, width: '150px' },
    { field: 'standby_rate', header: 'Standby', type: 'number', numeric: true, width: '145px' },
    { field: 'mobilisation_rate', header: 'Mobilisation', type: 'number', numeric: true, width: '150px' },
    { field: 'demobilisation_rate', header: 'Demobilisation', type: 'number', numeric: true, width: '160px' },
    { field: 'personnel_operating_rate', header: 'Personnel operating', type: 'number', numeric: true, width: '180px' },
    { field: 'personnel_standby_rate', header: 'Personnel standby', type: 'number', numeric: true, width: '175px' },
    { field: 'other_rate', header: 'Others', type: 'number', numeric: true, width: '140px' },
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
    { key: 'rate_basis', label: 'Rate basis', type: 'select', options: SERVICE_RATE_BASES, width: '160px' },
    { key: 'hole_section_id', label: 'Hole section', type: 'select', options: references.holeSections.value, width: '180px' },
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
    rate_basis: rate.rate_basis,
    hole_section_id: rate.hole_section_id ?? '',
    operating_rate: Number(rate.operating_rate),
    standby_rate: Number(rate.standby_rate),
    mobilisation_rate: Number(rate.mobilisation_rate),
    demobilisation_rate: Number(rate.demobilisation_rate),
    personnel_operating_rate: Number(rate.personnel_operating_rate),
    personnel_standby_rate: Number(rate.personnel_standby_rate),
    other_rate: Number(rate.other_rate),
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
    rate_basis: row.rate_basis || 'daily',
    hole_section_id: row.hole_section_id || null,
    operating_rate: money(row.operating_rate),
    standby_rate: money(row.standby_rate),
    mobilisation_rate: money(row.mobilisation_rate),
    demobilisation_rate: money(row.demobilisation_rate),
    personnel_operating_rate: money(row.personnel_operating_rate),
    personnel_standby_rate: money(row.personnel_standby_rate),
    other_rate: money(row.other_rate),
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
  rate_basis: 'daily',
  hole_section_id: '',
  operating_rate: 0,
  standby_rate: 0,
  mobilisation_rate: 0,
  demobilisation_rate: 0,
  personnel_operating_rate: 0,
  personnel_standby_rate: 0,
  other_rate: 0,
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
      description="Configure daily, per-service, per-section, or fixed service rates for AFE planning and daily actual-cost tracking. Capture equipment, personnel, mobilisation, demobilisation, and other charges on one auditable rate card."
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
      import-entity="service-rates"
      export-entity="service-rates"
      default-sort="effective_from"
      default-sort-order="desc"
      search-placeholder="Search by service code or name…"
    />
  </div>
</template>
