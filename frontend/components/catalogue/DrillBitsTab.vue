<script setup lang="ts">
/**
 * Consumables → Drill Bits tab. Bit Type and Manufacturer are user-configurable
 * dropdowns (Manage buttons on the toolbar). Final Cost is auto-calculated as
 * Unit Rate as per PO × Cost Uplift %. Rate changes on saved rows append
 * revisions to the rate history tab.
 */
import { computed, ref } from 'vue'
import ConfigManagerDialog from '~/components/catalogue/ConfigManagerDialog.vue'
import ExcelGrid from '~/components/master-data/ExcelGrid.vue'
import ImportDialog from '~/components/master-data/ImportDialog.vue'
import type { EditableGridRow, GridColumn, GridSelectOption } from '~/types/grid'

const api = useApi()

const grid = ref<InstanceType<typeof ExcelGrid> | null>(null)
const showImport = ref(false)
const showTypeManager = ref(false)
const showManufacturerManager = ref(false)

const currencies = ref<Record<string, unknown>[]>([])
const bitTypes = ref<string[]>([])
const manufacturers = ref<string[]>([])

async function loadLookups(): Promise<void> {
  try {
    const [currencyList, opts] = await Promise.all([
      api.get<Record<string, unknown>[]>('/master-data/currencies'),
      api.get<{ bit_types: string[], manufacturers: string[] }>('/catalogue/drill-bits/dropdown-options'),
    ])
    currencies.value = currencyList
    bitTypes.value = opts.bit_types ?? []
    manufacturers.value = opts.manufacturers ?? []
  }
  catch (error) {
    console.error('Failed to load drill bit lookups', error)
  }
}
void loadLookups()

const currencyOptions = computed<GridSelectOption[]>(() =>
  currencies.value.map(c => ({
    label: `${c.currency_code} (${c.currency_symbol})`,
    value: String(c.currency_code),
  })),
)

const bitTypeOptions = computed<GridSelectOption[]>(() => bitTypes.value.map(t => ({ label: t, value: t })))
const manufacturerOptions = computed<GridSelectOption[]>(() => manufacturers.value.map(m => ({ label: m, value: m })))

function calcFinal(row: Record<string, unknown>): string {
  const rate = Number(row.unit_rate_po ?? 0) || 0
  const uplift = row.cost_uplift === '' || row.cost_uplift == null ? 100 : Number(row.cost_uplift)
  if (!Number.isFinite(rate) || !Number.isFinite(uplift)) return ''
  return (rate * uplift / 100).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function money(row: Record<string, unknown>, field: string): string {
  const raw = String(row[field] ?? '')
  if (raw === '') return ''
  const n = Number(raw)
  return Number.isNaN(n) ? raw : n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

const columns = computed<GridColumn[]>(() => [
  { field: 'bit_code', header: 'Bit Code', width: '110px', readonly: true, placeholder: 'Auto' },
  { field: 'bit_name', header: 'Bit Name', required: true, width: '150px', placeholder: 'e.g. PDC Drill Bit' },
  { field: 'bit_type', header: 'Bit Type', type: 'select', options: bitTypeOptions.value, required: true, width: '130px', noPaste: true, placeholder: 'Manage ↓' },
  { field: 'model_no', header: 'Model No', required: true, width: '120px' },
  { field: 'size', header: 'Size', required: true, width: '100px', placeholder: 'e.g. 12 1/4' },
  { field: 'manufacturer', header: 'Manufacturer', type: 'select', options: manufacturerOptions.value, required: true, width: '150px', noPaste: true, placeholder: 'Manage ↓' },
  { field: 'po_number', header: 'PO Number', width: '120px', placeholder: 'Optional' },
  { field: 'serial_number', header: 'Serial No', width: '120px', placeholder: 'Optional' },
  { field: 'unit_rate_po', header: 'Rate as per PO', type: 'number', required: true, width: '125px', placeholder: '0.00' },
  { field: 'cost_uplift', header: 'Uplift %', type: 'number', required: true, width: '95px', defaultValue: '100' },
  { field: 'final_cost', header: 'Final Cost', width: '125px', compute: calcFinal },
  { field: 'previous_final_cost', header: 'Prev. Cost', width: '115px', compute: row => money(row, 'previous_final_cost') },
  { field: 'currency', header: 'Currency', type: 'select', options: currencyOptions.value, required: true, width: '105px', noPaste: true },
  { field: 'description', header: 'Description', width: '160px', placeholder: 'Optional' },
  { field: 'remarks', header: 'Remarks', width: '150px', placeholder: 'Optional' },
])

function toRow(record: Record<string, unknown>): Record<string, unknown> {
  return {
    _id: record.id as number | null,
    bit_code: record.bit_code ?? '',
    bit_name: record.bit_name ?? '',
    bit_type: record.bit_type ?? null,
    model_no: record.model_no ?? '',
    size: record.size ?? '',
    manufacturer: record.manufacturer ?? null,
    po_number: (record.po_number as string | null) ?? '',
    serial_number: (record.serial_number as string | null) ?? '',
    unit_rate_po: record.unit_rate_po != null ? String(record.unit_rate_po) : '',
    cost_uplift: record.cost_uplift != null ? String(record.cost_uplift) : '100',
    final_cost: record.final_cost != null ? String(record.final_cost) : '',
    previous_final_cost: record.previous_final_cost != null ? String(record.previous_final_cost) : '',
    currency: record.currency ?? null,
    description: (record.description as string | null) ?? '',
    remarks: (record.remarks as string | null) ?? '',
  }
}

function toPayload(row: EditableGridRow): Record<string, unknown> {
  return {
    bit_name: String(row.bit_name ?? '').trim(),
    bit_type: row.bit_type ?? null,
    model_no: String(row.model_no ?? '').trim(),
    size: String(row.size ?? '').trim(),
    manufacturer: row.manufacturer ?? null,
    po_number: row.po_number ? String(row.po_number).trim() : null,
    serial_number: row.serial_number ? String(row.serial_number).trim() : null,
    unit_rate_po: row.unit_rate_po !== '' ? Number(row.unit_rate_po) : null,
    cost_uplift: row.cost_uplift !== '' ? Number(row.cost_uplift) : 100,
    currency: row.currency ?? null,
    description: row.description ? String(row.description) : null,
    remarks: row.remarks ? String(row.remarks) : null,
  }
}

async function reloadLookupsThenGrid(): Promise<void> {
  await loadLookups()
  await grid.value?.reload()
}

function exportCurrent(format: 'xlsx' | 'csv'): void {
  api.download(`/catalogue/drill-bits/export?format=${format}`).then((blob) => {
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `drill_bits_export.${format}`
    a.click()
    window.URL.revokeObjectURL(url)
  }).catch((error: unknown) => console.error('Export failed', error))
}

function printTable(): void {
  window.print()
}

defineExpose({
  reload: () => grid.value?.reload(),
})
</script>

<template>
  <div class="tab-panel">
    <ExcelGrid
      ref="grid"
      title="Consumables — Drill Bits"
      singular="drill bit"
      :columns="columns"
      code-field="bit_name"
      paste-hint="Code and Final Cost are auto; Bit Type/Manufacturer/Currency dropdowns are excluded from paste. New Bit Types or Manufacturers can be added with the Manage buttons."
      :load-records="() => api.get('/catalogue/drill-bits')"
      :to-row="toRow"
      :to-payload="toPayload"
      :create-record="(payload: Record<string, unknown>) => api.post('/catalogue/drill-bits', payload)"
      :update-record="(id: number, payload: Record<string, unknown>) => api.put(`/catalogue/drill-bits/${id}`, payload)"
      :delete-record="(id: number) => api.delete(`/catalogue/drill-bits/${id}`)"
    >
      <template #toolbar-extra>
        <Button label="Manage Types" icon="pi pi-cog" size="small" severity="info" text @click="showTypeManager = true" />
        <Button label="Manage Makes" icon="pi pi-cog" size="small" severity="info" text @click="showManufacturerManager = true" />
        <Button label="Import" icon="pi pi-upload" size="small" severity="secondary" outlined @click="showImport = true" />
        <Button label="XLSX" icon="pi pi-file-excel" size="small" severity="success" outlined @click="exportCurrent('xlsx')" />
        <Button label="CSV" icon="pi pi-file" size="small" severity="secondary" outlined @click="exportCurrent('csv')" />
        <Button label="Print" icon="pi pi-print" size="small" severity="secondary" text @click="printTable" />
      </template>
    </ExcelGrid>

    <ImportDialog
      v-model:visible="showImport"
      title="Bulk Import Drill Bits (CSV / XLSX)"
      endpoint="/catalogue/drill-bits/import"
      hint="Headers: bit_name, bit_type (new types auto-created), model_no, size, manufacturer (new makes auto-created), po_number, serial_number, unit_rate_po, cost_uplift (default 100), currency, effective_date (flexible), description, remarks. Codes auto-generate; re-importing name+model+size with a new rate appends a revision."
      :template="{
        filename: 'drill_bits_template.csv',
        csv: 'bit_name,bit_type,model_no,size,manufacturer,po_number,serial_number,unit_rate_po,cost_uplift,currency,effective_date,description,remarks\nPDC Drill Bit,PDC,M-500,12 1/4,Schlumberger,PO-2026-01,SN-001,45000,110,USD,2026-01-20,Polycrystalline diamond compact,First batch\n',
      }"
      @committed="reloadLookupsThenGrid()"
    />

    <ConfigManagerDialog
      v-model:visible="showTypeManager"
      config-type="bit_type"
      title="Drill Bit Types"
      @changed="reloadLookupsThenGrid()"
    />
    <ConfigManagerDialog
      v-model:visible="showManufacturerManager"
      config-type="bit_manufacturer"
      title="Drill Bit Manufacturers"
      @changed="reloadLookupsThenGrid()"
    />
  </div>
</template>

<style scoped>
.tab-panel {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}
</style>
