<script setup lang="ts">
/**
 * Consumables → Mud Chemicals tab. Bulk-entry grid over the mud-chemicals API:
 * auto-generated Chemical Code, optional Part Number, mandatory Name, UOM and
 * Currency dropdowns (from master data), Unit Rate + Effective Date. Previous
 * Rate is auto-detected from the last revision; rate changes append revisions
 * (rate revision history lives in its own tab).
 */
import { computed, ref } from 'vue'
import ExcelGrid from '~/components/master-data/ExcelGrid.vue'
import ImportDialog from '~/components/master-data/ImportDialog.vue'
import type { EditableGridRow, GridColumn, GridSelectOption } from '~/types/grid'

const api = useApi()

const grid = ref<InstanceType<typeof ExcelGrid> | null>(null)
const showImport = ref(false)

const uoms = ref<Record<string, unknown>[]>([])
const currencies = ref<Record<string, unknown>[]>([])

async function loadLookups(): Promise<void> {
  try {
    const [uomList, currencyList] = await Promise.all([
      api.get<Record<string, unknown>[]>('/master-data/uom'),
      api.get<Record<string, unknown>[]>('/master-data/currencies'),
    ])
    uoms.value = uomList
    currencies.value = currencyList
  }
  catch (error) {
    console.error('Failed to load UOM/currency lookups', error)
  }
}
void loadLookups()

const uomOptions = computed<GridSelectOption[]>(() =>
  uoms.value.map(u => ({
    label: String(u.unit_symbol ?? u.unit_code),
    value: String(u.unit_code),
  })),
)

const currencyOptions = computed<GridSelectOption[]>(() =>
  currencies.value.map(c => ({
    label: `${c.currency_code} (${c.currency_symbol})`,
    value: String(c.currency_code),
  })),
)

function money(row: Record<string, unknown>, field: string): string {
  const raw = String(row[field] ?? '')
  if (raw === '') return ''
  const n = Number(raw)
  return Number.isNaN(n) ? raw : n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

const columns = computed<GridColumn[]>(() => [
  { field: 'chemical_code', header: 'Chemical Code', width: '120px', readonly: true, placeholder: 'Auto' },
  { field: 'chemical_name', header: 'Chemical Name', required: true, width: '200px', placeholder: 'e.g. Bentonite' },
  { field: 'part_number', header: 'Part Number', width: '130px', placeholder: 'Optional' },
  { field: 'uom', header: 'UOM', type: 'select', options: uomOptions.value, width: '110px', noPaste: true },
  { field: 'unit_rate', header: 'Unit Rate', type: 'number', required: true, width: '120px', placeholder: '0.00' },
  { field: 'previous_rate', header: 'Previous Rate', width: '120px', compute: row => money(row, 'previous_rate') },
  { field: 'currency', header: 'Currency', type: 'select', options: currencyOptions.value, required: true, width: '120px', noPaste: true },
  { field: 'effective_date', header: 'Effective Date', type: 'date', required: true, width: '150px', noPaste: true, defaultValue: new Date().toISOString().slice(0, 10) },
  { field: 'description', header: 'Description', width: '220px', placeholder: 'Optional notes' },
])

function toRow(record: Record<string, unknown>): Record<string, unknown> {
  return {
    _id: record.id as number | null,
    chemical_code: record.chemical_code ?? '',
    chemical_name: record.chemical_name ?? '',
    part_number: (record.part_number as string | null) ?? '',
    uom: record.uom ?? null,
    unit_rate: record.current_rate != null ? String(record.current_rate) : '',
    previous_rate: record.previous_rate != null ? String(record.previous_rate) : '0',
    currency: record.currency ?? null,
    effective_date: record.effective_date ? String(record.effective_date).slice(0, 10) : '',
    description: (record.description as string | null) ?? '',
  }
}

function toPayload(row: EditableGridRow): Record<string, unknown> {
  return {
    chemical_name: String(row.chemical_name ?? '').trim(),
    part_number: row.part_number ? String(row.part_number).trim() : null,
    uom: row.uom ?? null,
    unit_rate: row.unit_rate !== '' ? Number(row.unit_rate) : null,
    currency: row.currency ?? null,
    effective_date: row.effective_date ? String(row.effective_date) : null,
    description: row.description ? String(row.description) : null,
  }
}

function exportCurrent(format: 'xlsx' | 'csv'): void {
  api.download(`/catalogue/mud-chemicals/export?format=${format}`).then((blob) => {
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `mud_chemicals_export.${format}`
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
      title="Consumables — Mud Chemicals"
      singular="mud chemical"
      :columns="columns"
      code-field="chemical_name"
      paste-hint="Code is auto-generated; UOM/Currency dropdowns and dates are excluded from paste — set them in the grid. Changing Unit Rate on a saved row records a rate revision."
      :load-records="() => api.get('/catalogue/mud-chemicals')"
      :to-row="toRow"
      :to-payload="toPayload"
      :create-record="(payload: Record<string, unknown>) => api.post('/catalogue/mud-chemicals', payload)"
      :update-record="(id: number, payload: Record<string, unknown>) => api.put(`/catalogue/mud-chemicals/${id}`, payload)"
      :delete-record="(id: number) => api.delete(`/catalogue/mud-chemicals/${id}`)"
    >
      <template #toolbar-extra>
        <Button label="Import" icon="pi pi-upload" size="small" severity="secondary" outlined @click="showImport = true" />
        <Button label="XLSX" icon="pi pi-file-excel" size="small" severity="success" outlined @click="exportCurrent('xlsx')" />
        <Button label="CSV" icon="pi pi-file" size="small" severity="secondary" outlined @click="exportCurrent('csv')" />
        <Button label="Print" icon="pi pi-print" size="small" severity="secondary" text @click="printTable" />
      </template>
    </ExcelGrid>

    <ImportDialog
      v-model:visible="showImport"
      title="Bulk Import Mud Chemicals (CSV / XLSX)"
      endpoint="/catalogue/mud-chemicals/import"
      hint="Headers: chemical_name, part_number (optional), uom, unit_rate, currency, effective_date (flexible: 2026-01-15 or 15/01/2026), description. Codes auto-generate; re-importing a name with a new rate appends a rate revision."
      template-endpoint="/catalogue/mud-chemicals/import-template"
      template-filename="mud_chemicals_template.xlsx"
      @committed="grid?.reload()"
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
