<script setup lang="ts">
/**
 * Tangibles tab. Scope is fixed (Drilling / Completion / Others); Category,
 * Subcategory and Manufacturer are user-configurable dropdowns managed on the
 * page. Subcategories are dependents of the category: they are configured by
 * picking the category first, and each tangible row only offers the
 * subcategories that belong to its selected category. Final Cost = Unit Rate
 * as per PO × Cost Uplift %. Rate changes append revisions shown in the Rate
 * Revision History sub-tab.
 */
import { computed, ref } from 'vue'
import ConfigManagerDialog from '~/components/catalogue/ConfigManagerDialog.vue'
import ExcelGrid from '~/components/master-data/ExcelGrid.vue'
import ImportDialog from '~/components/master-data/ImportDialog.vue'
import type { EditableGridRow, GridColumn, GridSelectOption } from '~/types/grid'

interface SubcategoryOption {
  value: string
  /** Category the subcategory was configured under; null = legacy/unassigned. */
  category: string | null
}

const api = useApi()

const grid = ref<InstanceType<typeof ExcelGrid> | null>(null)
const showImport = ref(false)
const manage = ref<'' | 'category' | 'subcategory' | 'manufacturer'>('')

const currencies = ref<Record<string, unknown>[]>([])
const uoms = ref<Record<string, unknown>[]>([])
const categories = ref<string[]>([])
const subcategories = ref<SubcategoryOption[]>([])
const manufacturers = ref<string[]>([])

async function loadLookups(): Promise<void> {
  try {
    const [currencyList, uomList, opts] = await Promise.all([
      api.get<Record<string, unknown>[]>('/master-data/currencies'),
      api.get<Record<string, unknown>[]>('/master-data/uom'),
      api.get<{ categories: string[], subcategories: SubcategoryOption[], manufacturers: string[] }>('/catalogue/tangibles/dropdown-options'),
    ])
    currencies.value = currencyList
    uoms.value = uomList
    categories.value = opts.categories ?? []
    subcategories.value = (opts.subcategories ?? []).map(sub => (
      typeof sub === 'string' ? { value: sub, category: null } : sub
    ))
    manufacturers.value = opts.manufacturers ?? []
  }
  catch (error) {
    console.error('Failed to load tangible lookups', error)
  }
}
void loadLookups()

const scopeOptions: GridSelectOption[] = [
  { label: 'Drilling', value: 'Drilling' },
  { label: 'Completion', value: 'Completion' },
  { label: 'Others', value: 'Others' },
]

const currencyOptions = computed<GridSelectOption[]>(() =>
  currencies.value.map(c => ({ label: `${c.currency_code} (${c.currency_symbol})`, value: String(c.currency_code) })),
)
const uomOptions = computed<GridSelectOption[]>(() =>
  uoms.value.map(u => ({ label: String(u.unit_symbol ?? u.unit_code), value: String(u.unit_code) })),
)
const categoryOptions = computed<GridSelectOption[]>(() => categories.value.map(v => ({ label: v, value: v })))
const manufacturerOptions = computed<GridSelectOption[]>(() => manufacturers.value.map(v => ({ label: v, value: v })))

/** Subcategories that belong to a category (legacy unassigned values stay available everywhere). */
function subcategoriesFor(category: unknown): GridSelectOption[] {
  return subcategories.value
    .filter(sub => sub.category == null || sub.category === category)
    .map(sub => ({ label: sub.value, value: sub.value }))
}

function subcategoryOptionsFor(row: Record<string, unknown>): GridSelectOption[] {
  return subcategoriesFor(row.category)
}

/** Changing the category invalidates a subcategory that belongs elsewhere. */
function handleCategoryChange(row: EditableGridRow): void {
  if (row.subcategory == null || row.subcategory === '') return
  const allowed = subcategoriesFor(row.category).some(option => option.value === row.subcategory)
  if (!allowed) row.subcategory = null
}

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
  { field: 'tangible_code', header: 'Tangible Code', width: '120px', readonly: true, placeholder: 'Auto' },
  { field: 'tangible_name', header: 'Tangible Name', required: true, width: '160px', placeholder: 'e.g. Casing 9-5/8"' },
  { field: 'tangible_scope', header: 'Scope', type: 'select', options: scopeOptions, required: true, width: '125px', noPaste: true, defaultValue: 'Drilling' },
  { field: 'category', header: 'Category', type: 'select', options: categoryOptions.value, required: true, width: '140px', noPaste: true, placeholder: 'Manage ↓', onCellChange: handleCategoryChange },
  { field: 'subcategory', header: 'Subcategory', type: 'select', optionsFor: subcategoryOptionsFor, required: true, width: '150px', noPaste: true, placeholder: 'Pick category first' },
  { field: 'manufacturer', header: 'Manufacturer', type: 'select', options: manufacturerOptions.value, required: true, width: '150px', noPaste: true, placeholder: 'Manage ↓' },
  { field: 'po_number', header: 'PO Number', width: '115px', placeholder: 'Optional' },
  { field: 'uom', header: 'UOM', type: 'select', options: uomOptions.value, width: '90px', noPaste: true },
  { field: 'unit_rate_po', header: 'Rate as per PO', type: 'number', required: true, width: '125px', placeholder: '0.00' },
  { field: 'cost_uplift', header: 'Uplift %', type: 'number', required: true, width: '90px', defaultValue: '100' },
  { field: 'final_cost', header: 'Final Cost', width: '120px', compute: calcFinal },
  { field: 'previous_final_cost', header: 'Prev. Cost', width: '110px', compute: row => money(row, 'previous_final_cost') },
  { field: 'currency', header: 'Currency', type: 'select', options: currencyOptions.value, required: true, width: '100px', noPaste: true },
  { field: 'description', header: 'Description', width: '150px', placeholder: 'Optional' },
  { field: 'remarks', header: 'Remarks', width: '140px', placeholder: 'Optional' },
])

function toRow(record: Record<string, unknown>): Record<string, unknown> {
  return {
    _id: record.id as number | null,
    tangible_code: record.tangible_code ?? '',
    tangible_name: record.tangible_name ?? '',
    tangible_scope: record.tangible_scope ?? 'Drilling',
    category: record.category ?? null,
    subcategory: record.subcategory ?? null,
    manufacturer: record.manufacturer ?? null,
    po_number: (record.po_number as string | null) ?? '',
    uom: record.uom ?? null,
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
    tangible_name: String(row.tangible_name ?? '').trim(),
    tangible_scope: row.tangible_scope ?? 'Drilling',
    category: row.category ?? null,
    subcategory: row.subcategory ?? null,
    manufacturer: row.manufacturer ?? null,
    po_number: row.po_number ? String(row.po_number).trim() : null,
    uom: row.uom ?? null,
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
  api.download(`/catalogue/tangibles/export?format=${format}`).then((blob) => {
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `tangibles_export.${format}`
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
      title="Tangibles"
      singular="tangible"
      :columns="columns"
      code-field="tangible_name"
      paste-hint="Code and Final Cost are auto; Scope/Category/Subcategory/Manufacturer/UOM/Currency dropdowns are excluded from paste. New dropdown values can be added with the Manage buttons."
      :load-records="() => api.get('/catalogue/tangibles')"
      :to-row="toRow"
      :to-payload="toPayload"
      :create-record="(payload: Record<string, unknown>) => api.post('/catalogue/tangibles', payload)"
      :update-record="(id: number, payload: Record<string, unknown>) => api.put(`/catalogue/tangibles/${id}`, payload)"
      :delete-record="(id: number) => api.delete(`/catalogue/tangibles/${id}`)"
    >
      <template #toolbar-extra>
        <Button label="Categories" icon="pi pi-cog" size="small" severity="info" text @click="manage = 'category'" />
        <Button label="Subcategories" icon="pi pi-cog" size="small" severity="info" text @click="manage = 'subcategory'" />
        <Button label="Makes" icon="pi pi-cog" size="small" severity="info" text @click="manage = 'manufacturer'" />
        <Button label="Import" icon="pi pi-upload" size="small" severity="secondary" outlined @click="showImport = true" />
        <Button label="XLSX" icon="pi pi-file-excel" size="small" severity="success" outlined @click="exportCurrent('xlsx')" />
        <Button label="CSV" icon="pi pi-file" size="small" severity="secondary" outlined @click="exportCurrent('csv')" />
        <Button label="Print" icon="pi pi-print" size="small" severity="secondary" text @click="printTable" />
      </template>
    </ExcelGrid>

    <ImportDialog
      v-model:visible="showImport"
      title="Bulk Import Tangibles (CSV / XLSX)"
      endpoint="/catalogue/tangibles/import"
      hint="Headers: tangible_name, tangible_scope (Drilling/Completion/Others), category, subcategory, manufacturer (new values auto-created), po_number, uom, unit_rate_po, cost_uplift (default 100), currency, effective_date (flexible), description, remarks. Each subcategory is linked to the row's category — unknown subcategories are created under it. Codes auto-generate; re-importing a name with a new rate appends a revision."
      template-endpoint="/catalogue/tangibles/import-template"
      template-filename="tangibles_template.xlsx"
      @committed="reloadLookupsThenGrid()"
    />

    <ConfigManagerDialog
      :visible="manage === 'category'"
      config-type="tangible_category"
      title="Tangible Categories"
      @update:visible="(v: boolean) => { if (!v) manage = '' }"
      @changed="reloadLookupsThenGrid()"
    />
    <ConfigManagerDialog
      :visible="manage === 'subcategory'"
      config-type="tangible_subcategory"
      title="Tangible Subcategories"
      parent-config-type="tangible_category"
      parent-label="Category"
      @update:visible="(v: boolean) => { if (!v) manage = '' }"
      @changed="reloadLookupsThenGrid()"
    />
    <ConfigManagerDialog
      :visible="manage === 'manufacturer'"
      config-type="tangible_manufacturer"
      title="Tangible Manufacturers"
      @update:visible="(v: boolean) => { if (!v) manage = '' }"
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
