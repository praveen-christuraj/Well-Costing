<script setup lang="ts">
/**
 * Master Data Management — excel-type bulk entry UI.
 *
 * No form/dialog data entry: every tab renders an always-editable spreadsheet
 * grid (multiple rows, inline cells, paste from Excel) with a single bulk
 * "Save All" commit. Import (CSV/XLSX upload), export, print, soft delete and
 * the deleted-entries trash remain available.
 */
import { computed, onMounted, ref, watch } from 'vue'
import PageHeader from '~/components/design-system/PageHeader.vue'
import ExcelGrid from '~/components/master-data/ExcelGrid.vue'
import ImportDialog from '~/components/master-data/ImportDialog.vue'
import type { EditableGridRow, GridColumn, GridSelectOption } from '~/types/grid'

definePageMeta({ middleware: 'auth' })

const api = useApi()

interface ModuleDef {
  key: string
  label: string
  fullLabel: string
  codeField: string
  nameField: string
  symbolField: string | null
}

// Tabs: 0-4 generic modules, 5 vendors, 6 PO/SO, 7 deleted entries
const modules: ModuleDef[] = [
  { key: 'uom', label: 'UOM', fullLabel: 'Unit of Measurements (UOM)', codeField: 'unit_code', nameField: 'unit_name', symbolField: 'unit_symbol' },
  { key: 'currencies', label: 'Currency', fullLabel: 'Currencies', codeField: 'currency_code', nameField: 'currency_name', symbolField: 'currency_symbol' },
  { key: 'phases', label: 'Phases', fullLabel: 'Phases', codeField: 'phase_code', nameField: 'phase_name', symbolField: null },
  { key: 'activities', label: 'Activities', fullLabel: 'Activities', codeField: 'activity_code', nameField: 'activity_name', symbolField: null },
  { key: 'hole-sections', label: 'Hole Sections', fullLabel: 'Hole Sections', codeField: 'section_code', nameField: 'section_name', symbolField: null },
]

const TAB_VENDORS = 5
const TAB_PO = 6
const TAB_DELETED = 7

const tabs = [
  ...modules.map(mod => ({ label: mod.label, icon: 'pi pi-table' })),
  { label: 'Vendors/Suppliers', icon: 'pi pi-truck' },
  { label: 'PO/SO Orders', icon: 'pi pi-file-edit' },
  { label: 'Deleted Entries', icon: 'pi pi-trash' },
]

const activeTab = ref(0)
const tabDirty = ref(false)
const activeGrid = ref<InstanceType<typeof ExcelGrid> | null>(null)

const currentModule = computed<ModuleDef | null>(() => modules[activeTab.value] ?? null)

function switchTab(index: number): void {
  if (index === activeTab.value) return
  if (tabDirty.value && !window.confirm('This tab has unsaved rows. Switch tab and discard the unsaved entries?')) return
  activeTab.value = index
  tabDirty.value = false
}

// ---------------------------------------------------------------------------
// Generic modules (UOM, Currencies, Phases, Activities, Hole Sections)
// ---------------------------------------------------------------------------

function genericColumns(mod: ModuleDef): GridColumn[] {
  const cols: GridColumn[] = [
    { field: 'code', header: 'Code', required: true, width: '150px', placeholder: 'Unique code' },
    { field: 'name', header: 'Name', required: true, width: '260px', placeholder: 'Descriptive name' },
  ]
  if (mod.symbolField) {
    cols.push({ field: 'symbol', header: 'Symbol', width: '110px', placeholder: 'e.g. $' })
  }
  cols.push({ field: 'description', header: 'Description', placeholder: 'Optional notes' })
  return cols
}

function genericToRow(mod: ModuleDef) {
  return (record: Record<string, unknown>): Record<string, unknown> => ({
    _id: record.id as number | null,
    code: record[mod.codeField],
    name: record[mod.nameField],
    symbol: mod.symbolField ? record[mod.symbolField] ?? '' : '',
    description: (record.description as string | null) ?? '',
  })
}

function genericToPayload(mod: ModuleDef) {
  return (row: EditableGridRow): Record<string, unknown> => {
    const payload: Record<string, unknown> = {
      [mod.codeField]: String(row.code ?? '').trim(),
      [mod.nameField]: String(row.name ?? '').trim(),
      description: row.description ? String(row.description) : null,
    }
    if (mod.symbolField) {
      const symbol = String(row.symbol ?? '').trim()
      payload[mod.symbolField] = symbol || String(row.code ?? '').trim() || null
    }
    return payload
  }
}

function genericCreate(mod: ModuleDef) {
  return (payload: Record<string, unknown>) => api.post(`/master-data/${mod.key}`, payload)
}

function genericUpdate(mod: ModuleDef) {
  return (id: number, payload: Record<string, unknown>) => api.put(`/master-data/${mod.key}/${id}`, payload)
}

function genericDelete(mod: ModuleDef) {
  return (id: number) => api.delete(`/master-data/${mod.key}/${id}`)
}

function genericLoad(mod: ModuleDef) {
  return () => api.get<Record<string, unknown>[]>(`/master-data/${mod.key}`)
}

// ---------------------------------------------------------------------------
// Vendors / Suppliers
// ---------------------------------------------------------------------------

const vendorColumns: GridColumn[] = [
  { field: 'code', header: 'Vendor Code', required: true, width: '150px', placeholder: 'e.g. VEND001' },
  { field: 'name', header: 'Vendor/Supplier Name', required: true, width: '280px', placeholder: 'e.g. Acme Drilling Services' },
  { field: 'contact', header: 'Contact', width: '220px', placeholder: 'Phone / email / address' },
  { field: 'description', header: 'Description', placeholder: 'Optional notes' },
]

function vendorToRow(record: Record<string, unknown>): Record<string, unknown> {
  return {
    _id: record.id as number | null,
    code: record.vendor_code,
    name: record.vendor_name,
    contact: (record.contact as string | null) ?? '',
    description: (record.description as string | null) ?? '',
  }
}

function vendorToPayload(row: EditableGridRow): Record<string, unknown> {
  return {
    vendor_code: String(row.code ?? '').trim(),
    vendor_name: String(row.name ?? '').trim(),
    contact: row.contact ? String(row.contact) : null,
    description: row.description ? String(row.description) : null,
  }
}

// ---------------------------------------------------------------------------
// Purchase Orders / Service Orders
// ---------------------------------------------------------------------------

const poTypeOptions: GridSelectOption[] = [
  { label: 'PO', value: 'PO' },
  { label: 'SO', value: 'SO' },
  { label: 'Callout', value: 'Callout' },
  { label: 'Others', value: 'Others' },
]

const vendorsDropdown = ref<Record<string, unknown>[]>([])
const poTypeFilter = ref('')

const vendorOptions = computed<GridSelectOption[]>(() =>
  vendorsDropdown.value.map(vendor => ({
    label: String(vendor.display_name ?? `${vendor.vendor_code} — ${vendor.vendor_name}`),
    value: vendor.id as number,
  })),
)

const poColumns = computed<GridColumn[]>(() => [
  { field: 'po_type', header: 'Type', type: 'select', options: poTypeOptions, required: true, width: '125px', noPaste: true, defaultValue: 'PO' },
  { field: 'vendor_id', header: 'Vendor/Supplier', type: 'select', options: vendorOptions.value, required: true, width: '230px', noPaste: true, placeholder: 'Select vendor' },
  { field: 'po_so_number', header: 'PO/SO Number', required: true, width: '165px', placeholder: 'e.g. PO-2024-001' },
  { field: 'effective_date', header: 'Effective Date', type: 'date', width: '150px', noPaste: true },
  { field: 'value', header: 'Value', type: 'number', width: '130px', placeholder: 'e.g. 50000.00' },
  { field: 'is_amendment', header: 'Amend?', type: 'checkbox', width: '85px' },
  { field: 'amendment_number', header: 'Amend №', type: 'number', width: '100px', placeholder: '1-200' },
  { field: 'remarks', header: 'Remarks', width: '240px', placeholder: 'Optional remarks' },
  { field: 'attachment', header: 'Copy', type: 'slot', width: '110px' },
])

function poToRow(record: Record<string, unknown>): Record<string, unknown> {
  return {
    _id: record.id as number | null,
    po_type: record.po_type ?? 'PO',
    vendor_id: record.vendor_id ?? null,
    po_so_number: record.po_so_number ?? '',
    effective_date: record.effective_date ? String(record.effective_date).slice(0, 10) : '',
    value: record.value != null ? String(record.value) : '',
    is_amendment: !!record.is_amendment,
    amendment_number: record.amendment_number != null ? String(record.amendment_number) : '',
    remarks: (record.remarks as string | null) ?? '',
    attachment_original_name: record.attachment_original_name ?? null,
  }
}

function poToPayload(row: EditableGridRow): Record<string, unknown> {
  const value = String(row.value ?? '').trim()
  const amendment = String(row.amendment_number ?? '').trim()
  return {
    po_type: row.po_type,
    vendor_id: row.vendor_id,
    po_so_number: String(row.po_so_number ?? '').trim(),
    effective_date: row.effective_date ? String(row.effective_date) : null,
    value: value !== '' ? Number(value) : null,
    is_amendment: !!row.is_amendment,
    amendment_number: amendment !== '' ? Number(amendment) : null,
    remarks: row.remarks ? String(row.remarks) : null,
  }
}

function poLoad(): Promise<Record<string, unknown>[]> {
  return api.get<Record<string, unknown>[]>('/master-data/purchase-orders').then(records =>
    poTypeFilter.value ? records.filter(record => record.po_type === poTypeFilter.value) : records,
  )
}

async function loadVendorsDropdown(): Promise<void> {
  try {
    vendorsDropdown.value = await api.get<Record<string, unknown>[]>('/master-data/vendors/dropdown')
  }
  catch (error) {
    console.error('Failed to load vendors dropdown', error)
  }
}

watch(poTypeFilter, () => activeGrid.value?.reload())

// --- Attachments (kept as dialogs: they are file operations, not data entry) ---

const showBulkAttachDialog = ref(false)
const bulkAttachFiles = ref<FileList | null>(null)
const bulkAttachResult = ref<{ uploaded_count: number, error_count: number, errors?: string[] } | null>(null)
const bulkAttachUploading = ref(false)

const showAttachDialog = ref(false)
const attachTarget = ref<{ id: number | null, po_so_number: string } | null>(null)
const attachFile = ref<File | null>(null)
const attachUploading = ref(false)
const attachError = ref<string | null>(null)

function openAttachmentUpload(row: EditableGridRow): void {
  attachTarget.value = { id: row._id, po_so_number: String(row.po_so_number ?? '') }
  attachFile.value = null
  attachError.value = null
  showAttachDialog.value = true
}

function handleAttachSelect(event: Event): void {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  if (file.size > 15 * 1024 * 1024) {
    attachError.value = 'File size exceeds 15 MB'
    return
  }
  attachError.value = null
  attachFile.value = file
}

async function executeAttachUpload(): Promise<void> {
  if (!attachFile.value || !attachTarget.value?.id) return
  attachUploading.value = true
  attachError.value = null
  const fd = new FormData()
  fd.append('file', attachFile.value)
  try {
    await api.postForm(`/master-data/purchase-orders/${attachTarget.value.id}/attachment`, fd)
    showAttachDialog.value = false
    await activeGrid.value?.reload()
  }
  catch (caught: unknown) {
    attachError.value = caught instanceof Error ? caught.message : 'Attachment upload failed'
  }
  finally {
    attachUploading.value = false
  }
}

function handleBulkAttachSelect(event: Event): void {
  bulkAttachFiles.value = (event.target as HTMLInputElement).files
}

async function executeBulkAttach(): Promise<void> {
  if (!bulkAttachFiles.value || bulkAttachFiles.value.length === 0) return
  bulkAttachUploading.value = true
  bulkAttachResult.value = null
  const fd = new FormData()
  for (let i = 0; i < bulkAttachFiles.value.length; i++) {
    const file = bulkAttachFiles.value.item(i)
    if (file) fd.append('files', file)
  }
  try {
    bulkAttachResult.value = await api.postForm<typeof bulkAttachResult.value>('/master-data/purchase-orders/attachments/bulk', fd)
    await activeGrid.value?.reload()
  }
  catch (caught: unknown) {
    console.error('Bulk attachment upload failed', caught)
  }
  finally {
    bulkAttachUploading.value = false
  }
}

async function downloadPOAttachment(row: Record<string, unknown>): Promise<void> {
  try {
    const blob = await api.download(`/master-data/purchase-orders/${row._id}/attachment`)
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = String(row.attachment_original_name || `attachment_${row.po_so_number}`)
    a.click()
    window.URL.revokeObjectURL(url)
  }
  catch (caught: unknown) {
    console.error('Attachment download failed', caught)
  }
}

// ---------------------------------------------------------------------------
// Import / Export / Print
// ---------------------------------------------------------------------------

const showImport = ref(false)

const importTitle = computed(() => {
  if (activeTab.value === TAB_VENDORS) return 'Bulk Import Vendors/Suppliers (CSV / XLSX)'
  if (activeTab.value === TAB_PO) return 'Bulk Import PO/SO (CSV / XLSX)'
  return `Bulk Import ${currentModule.value?.fullLabel ?? ''} (CSV / XLSX)`
})

const importEndpoint = computed(() => {
  if (activeTab.value === TAB_VENDORS) return '/master-data/vendors/import'
  if (activeTab.value === TAB_PO) return '/master-data/purchase-orders/import'
  return `/master-data/${currentModule.value?.key ?? 'uom'}/import`
})

const importHint = computed(() => {
  if (activeTab.value === TAB_VENDORS) return 'Headers: vendor_code, vendor_name, contact, description.'
  if (activeTab.value === TAB_PO) return 'Headers: po_type, vendor_code, po_so_number, effective_date (flexible formats), value, is_amendment (Yes/No), amendment_number (1-200), remarks.'
  return 'Headers: code, name, symbol (if applicable), description. Flexible date parsing supported.'
})

const importTemplate = computed<{ filename: string, csv: string } | undefined>(() => {
  if (activeTab.value === TAB_VENDORS) {
    return {
      filename: 'vendors_template.csv',
      csv: 'vendor_code,vendor_name,contact,description\nVEND001,Acme Drilling Services,+1-555-0100,Primary drilling contractor\nVEND002,Baker Tools Inc,baker@example.com,Tool supplier\n',
    }
  }
  if (activeTab.value === TAB_PO) {
    return {
      filename: 'purchase_orders_template.csv',
      csv: 'po_type,vendor_code,po_so_number,effective_date,value,is_amendment,amendment_number,remarks\nPO,VEND001,PO-2024-001,2024-01-15,50000,No,,Initial purchase order\nSO,VEND002,SO-2024-002,15/01/2024,75000.50,No,,Service order for maintenance\nPO,VEND001,PO-2024-001,2024-02-01,55000,Yes,1,Amendment for additional work\n',
    }
  }
  const mod = currentModule.value
  if (!mod) return undefined
  const headers = mod.symbolField
    ? `${mod.codeField},${mod.nameField},${mod.symbolField},description\n`
    : `${mod.codeField},${mod.nameField},description\n`
  const sample = mod.symbolField
    ? 'CODE1,Sample Name,SYM,Sample description\n'
    : 'CODE1,Sample Name,Sample description\n'
  return { filename: `${mod.key}_template.csv`, csv: headers + sample }
})

function exportCurrent(format: 'xlsx' | 'csv'): void {
  const endpoints: Record<number, string> = {
    [TAB_VENDORS]: '/master-data/vendors',
    [TAB_PO]: '/master-data/purchase-orders',
  }
  const base = activeTab.value <= TAB_PO
    ? endpoints[activeTab.value] ?? `/master-data/${currentModule.value?.key ?? 'uom'}`
    : null
  if (!base) return
  api.download(`${base}/export?format=${format}`).then((blob) => {
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${base.split('/').pop()}_export.${format}`
    a.click()
    window.URL.revokeObjectURL(url)
  }).catch((error: unknown) => {
    console.error('Export failed', error)
  })
}

function printTable(): void {
  window.print()
}

// ---------------------------------------------------------------------------
// Deleted entries (trash)
// ---------------------------------------------------------------------------

const deletedRecords = ref<Record<string, any>[]>([])
const deletedLoading = ref(false)

async function loadAllDeleted(): Promise<void> {
  deletedLoading.value = true
  try {
    const genericPromises = modules.map(async (mod) => {
      try {
        const res = await api.get<Record<string, any>[]>(`/master-data/${mod.key}/deleted`)
        return res.map(r => ({
          ...r,
          moduleKey: mod.key,
          moduleName: mod.fullLabel,
          code: r[mod.codeField],
          name: r[mod.nameField],
        }))
      }
      catch {
        return []
      }
    })
    const vendorDeleted = api.get<Record<string, any>[]>('/master-data/vendors/deleted')
      .then(res => res.map(r => ({ ...r, moduleKey: 'vendors', moduleName: 'Vendors/Suppliers', code: r.vendor_code, name: r.vendor_name })))
      .catch(() => [])
    const poDeleted = api.get<Record<string, any>[]>('/master-data/purchase-orders/deleted')
      .then(res => res.map(r => ({ ...r, moduleKey: 'purchase-orders', moduleName: 'Purchase/Service Orders', code: r.po_so_number, name: `${r.po_type} — ${r.vendor_display || r.vendor_code || ''}` })))
      .catch(() => [])
    const results = await Promise.all([...genericPromises, vendorDeleted, poDeleted])
    deletedRecords.value = (results.flat() as Record<string, any>[])
      .sort((a, b) => new Date(b.deleted_at || 0).getTime() - new Date(a.deleted_at || 0).getTime())
  }
  catch (error) {
    console.error('Failed to load deleted entries', error)
  }
  finally {
    deletedLoading.value = false
  }
}

async function restoreRecord(item: Record<string, any>): Promise<void> {
  try {
    await api.post(`/master-data/${item.moduleKey}/${item.id}/restore`, {})
    await loadAllDeleted()
  }
  catch (error: unknown) {
    window.alert(error instanceof Error ? error.message : 'Restore failed')
  }
}

async function permanentDelete(item: Record<string, any>): Promise<void> {
  if (!window.confirm('Permanently delete? This cannot be undone.')) return
  try {
    await api.delete(`/master-data/${item.moduleKey}/${item.id}/permanent`)
    await loadAllDeleted()
  }
  catch (error: unknown) {
    window.alert(error instanceof Error ? error.message : 'Permanent delete failed')
  }
}

watch(activeTab, (tab) => {
  if (tab === TAB_DELETED) void loadAllDeleted()
  if (tab === TAB_PO) void loadVendorsDropdown()
})

onMounted(() => {
  void loadVendorsDropdown()
})
</script>

<template>
  <div class="master-data-page">
    <PageHeader
      class="no-print"
      title="Master Data Configuration"
      description="Spreadsheet-style bulk entry: type directly into the grid, add a single row or paste multiple rows, then Save All in one go. UOM, Currencies, Phases, Activities, Hole Sections, Vendors/Suppliers and PO/SO Orders — with Import/Export, Print, Soft Delete and Audit."
    />

    <div class="tabs no-print">
      <button
        v-for="(tab, index) in tabs"
        :key="tab.label"
        class="tabs__item"
        :class="{ 'tabs__item--active': activeTab === index, 'tabs__item--danger': index === TAB_DELETED }"
        @click="switchTab(index)"
      >
        <i :class="tab.icon" />
        {{ tab.label }}
      </button>
    </div>

    <!-- Generic modules -->
    <section v-if="currentModule" class="grid-card">
      <ExcelGrid
        :ref="(el) => { if (el) activeGrid = el as InstanceType<typeof ExcelGrid> }"
        :key="currentModule.key"
        :title="currentModule.fullLabel"
        :singular="currentModule.label.toLowerCase()"
        :columns="genericColumns(currentModule)"
        code-field="code"
        :load-records="genericLoad(currentModule)"
        :to-row="genericToRow(currentModule)"
        :to-payload="genericToPayload(currentModule)"
        :create-record="genericCreate(currentModule)"
        :update-record="genericUpdate(currentModule)"
        :delete-record="genericDelete(currentModule)"
        @dirty="tabDirty = $event"
      >
        <template #toolbar-extra>
          <Button label="Import" icon="pi pi-upload" size="small" severity="secondary" outlined @click="showImport = true" />
          <Button label="XLSX" icon="pi pi-file-excel" size="small" severity="success" outlined @click="exportCurrent('xlsx')" />
          <Button label="CSV" icon="pi pi-file" size="small" severity="secondary" outlined @click="exportCurrent('csv')" />
          <Button label="Print" icon="pi pi-print" size="small" severity="secondary" text @click="printTable" />
        </template>
      </ExcelGrid>
    </section>

    <!-- Vendors / Suppliers -->
    <section v-else-if="activeTab === TAB_VENDORS" class="grid-card">
      <ExcelGrid
        :ref="(el) => { if (el) activeGrid = el as InstanceType<typeof ExcelGrid> }"
        title="Vendors/Suppliers"
        singular="vendor"
        :columns="vendorColumns"
        code-field="code"
        :load-records="() => api.get('/master-data/vendors')"
        :to-row="vendorToRow"
        :to-payload="vendorToPayload"
        :create-record="(payload: Record<string, unknown>) => api.post('/master-data/vendors', payload)"
        :update-record="(id: number, payload: Record<string, unknown>) => api.put(`/master-data/vendors/${id}`, payload)"
        :delete-record="(id: number) => api.delete(`/master-data/vendors/${id}`)"
        @dirty="tabDirty = $event"
      >
        <template #toolbar-extra>
          <Button label="Import" icon="pi pi-upload" size="small" severity="secondary" outlined @click="showImport = true" />
          <Button label="XLSX" icon="pi pi-file-excel" size="small" severity="success" outlined @click="exportCurrent('xlsx')" />
          <Button label="CSV" icon="pi pi-file" size="small" severity="secondary" outlined @click="exportCurrent('csv')" />
          <Button label="Print" icon="pi pi-print" size="small" severity="secondary" text @click="printTable" />
        </template>
      </ExcelGrid>
    </section>

    <!-- Purchase Orders / Service Orders -->
    <section v-else-if="activeTab === TAB_PO" class="grid-card">
      <ExcelGrid
        :ref="(el) => { if (el) activeGrid = el as InstanceType<typeof ExcelGrid> }"
        title="Purchase Orders / Service Orders"
        singular="PO/SO"
        :columns="poColumns"
        code-field="po_so_number"
        paste-hint="Type, vendor, date and amendment flag are excluded from paste — set them in the grid afterwards."
        :load-records="poLoad"
        :to-row="poToRow"
        :to-payload="poToPayload"
        :create-record="(payload: Record<string, unknown>) => api.post('/master-data/purchase-orders', payload)"
        :update-record="(id: number, payload: Record<string, unknown>) => api.put(`/master-data/purchase-orders/${id}`, payload)"
        :delete-record="(id: number) => api.delete(`/master-data/purchase-orders/${id}`)"
        :print-subtitle="poTypeFilter ? `Type filter: ${poTypeFilter}` : 'All types'"
        @dirty="tabDirty = $event"
      >
        <template #toolbar-extra>
          <select v-model="poTypeFilter" class="filter-select">
            <option value="">All Types</option>
            <option value="PO">PO</option>
            <option value="SO">SO</option>
            <option value="Callout">Callout</option>
            <option value="Others">Others</option>
          </select>
          <Button label="Import" icon="pi pi-upload" size="small" severity="secondary" outlined @click="showImport = true" />
          <Button label="Bulk Attach" icon="pi pi-paperclip" size="small" severity="secondary" outlined @click="showBulkAttachDialog = true" />
          <Button label="XLSX" icon="pi pi-file-excel" size="small" severity="success" outlined @click="exportCurrent('xlsx')" />
          <Button label="CSV" icon="pi pi-file" size="small" severity="secondary" outlined @click="exportCurrent('csv')" />
          <Button label="Print" icon="pi pi-print" size="small" severity="secondary" text @click="printTable" />
        </template>
        <template #cell-attachment="{ data }">
          <button
            v-if="data.attachment_original_name"
            class="attach-link"
            :title="`Download ${data.attachment_original_name}`"
            @click="downloadPOAttachment(data)"
          >
            <i class="pi pi-paperclip" />
            {{ String(data.attachment_original_name).length > 10 ? `${String(data.attachment_original_name).slice(0, 10)}…` : data.attachment_original_name }}
          </button>
          <span v-else class="attach-none">—</span>
        </template>
        <template #row-actions="{ data }">
          <button
            class="icon-btn"
            :disabled="data._id == null"
            :title="data._id == null ? 'Save the row first, then upload its copy' : 'Upload copy (PDF, DOCX, XLSX, images < 15 MB)'"
            @click="data._id != null && openAttachmentUpload(data)"
          >
            <i class="pi pi-upload" />
          </button>
        </template>
      </ExcelGrid>

      <p class="bulk-attach-hint no-print">
        <strong>Bulk attachments:</strong> name files as <code>PO_NUMBER.pdf</code> or
        <code>PO_NUMBER__AMENDMENT.pdf</code> (e.g. <code>PO-2024-001.pdf</code>,
        <code>PO-2024-001__1.pdf</code>) — the system matches them by PO/SO number automatically.
      </p>
    </section>

    <!-- Deleted entries -->
    <section v-else class="grid-card">
      <div class="flex items-center justify-between mb-3">
        <h3 class="trash-title">
          Deleted Entries (Trash) — {{ deletedRecords.length }} items
        </h3>
        <span class="trash-subtitle">Restore or permanently delete. All actions are audit-logged.</span>
      </div>
      <div class="table-scroll">
        <table class="trash-table">
          <thead>
            <tr>
              <th>Module</th>
              <th>Code / Number</th>
              <th>Name / Details</th>
              <th>Deleted At</th>
              <th class="text-right">Actions</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="deletedLoading">
              <td colspan="5" class="empty-cell"><i class="pi pi-spin pi-spinner" /> Loading deleted entries…</td>
            </tr>
            <tr v-else-if="deletedRecords.length === 0">
              <td colspan="5" class="empty-cell">No deleted entries.</td>
            </tr>
            <tr v-for="item in deletedRecords" :key="`${item.moduleKey}-${item.id}`">
              <td class="trash-module">{{ item.moduleName }}</td>
              <td class="mono">{{ item.code || '—' }}</td>
              <td class="truncate">{{ item.name || item.description || item.remarks || '—' }}</td>
              <td class="muted">{{ item.deleted_at ? new Date(item.deleted_at).toLocaleString() : '—' }}</td>
              <td class="text-right">
                <Button label="Restore" size="small" severity="success" outlined @click="restoreRecord(item)" />
                <Button label="Delete" size="small" severity="danger" outlined class="ml-2" @click="permanentDelete(item)" />
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <ImportDialog
      v-model:visible="showImport"
      :title="importTitle"
      :endpoint="importEndpoint"
      :hint="importHint"
      :template="importTemplate"
      @committed="activeGrid?.reload()"
    />

    <Dialog v-model:visible="showAttachDialog" modal :header="`Upload Copy — ${attachTarget?.po_so_number ?? ''}`" :style="{ width: '30rem' }">
      <div class="attach-form">
        <p class="attach-form__hint">
          Allowed: pdf, docx, doc, xlsx, csv, xls, jpg, jpeg, png — max 15 MB.
        </p>
        <input
          type="file"
          accept=".pdf,.docx,.doc,.xlsx,.xls,.csv,.jpg,.jpeg,.png"
          class="attach-form__file"
          @change="handleAttachSelect"
        >
        <div v-if="attachFile" class="attach-form__selected">
          Selected: <strong>{{ attachFile.name }}</strong> ({{ (attachFile.size / 1024 / 1024).toFixed(2) }} MB)
        </div>
        <div v-if="attachError" class="attach-form__error">{{ attachError }}</div>
      </div>
      <template #footer>
        <Button label="Cancel" severity="secondary" text size="small" @click="showAttachDialog = false" />
        <Button label="Upload" icon="pi pi-upload" size="small" :disabled="!attachFile" :loading="attachUploading" @click="executeAttachUpload" />
      </template>
    </Dialog>

    <Dialog v-model:visible="showBulkAttachDialog" modal header="Bulk Upload Copies for PO/SO" :style="{ width: '34rem' }">
      <div class="attach-form">
        <p class="attach-form__hint">
          Name files as <code>PO_NUMBER.pdf</code> or <code>PO_NUMBER__AMENDMENT.pdf</code> to auto-match.
          Allowed: pdf, docx, doc, xlsx, csv, xls, jpg, jpeg, png — max 15 MB each.
        </p>
        <input type="file" multiple accept=".pdf,.docx,.doc,.xlsx,.xls,.csv,.jpg,.jpeg,.png" class="attach-form__file" @change="handleBulkAttachSelect">
        <div v-if="bulkAttachUploading" class="muted"><i class="pi pi-spin pi-spinner" /> Uploading…</div>
        <div v-if="bulkAttachResult" class="attach-form__result">
          <div>Uploaded: {{ bulkAttachResult.uploaded_count }}</div>
          <div v-if="bulkAttachResult.error_count" class="attach-form__error">
            Errors: {{ bulkAttachResult.error_count }}
            <ul>
              <li v-for="(item, index) in bulkAttachResult.errors || []" :key="index">{{ item }}</li>
            </ul>
          </div>
        </div>
      </div>
      <template #footer>
        <Button label="Close" severity="secondary" text size="small" @click="showBulkAttachDialog = false" />
        <Button label="Upload All" icon="pi pi-upload" size="small" :disabled="!bulkAttachFiles?.length" :loading="bulkAttachUploading" @click="executeBulkAttach" />
      </template>
    </Dialog>
  </div>
</template>

<style scoped>
.master-data-page {
  max-width: 1600px;
  margin: 0 auto;
}

.tabs {
  display: flex;
  gap: 0.25rem;
  border-bottom: 1px solid var(--app-border);
  margin-bottom: 1rem;
  overflow-x: auto;
}

.tabs__item {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.6rem 1rem;
  border: none;
  border-bottom: 2px solid transparent;
  background: transparent;
  color: var(--app-muted);
  font-size: 0.8rem;
  font-weight: 500;
  white-space: nowrap;
  cursor: pointer;
}

.tabs__item:hover {
  color: var(--app-ink);
}

.tabs__item--active {
  color: var(--app-teal);
  border-bottom-color: var(--app-teal);
  font-weight: 600;
}

.tabs__item--danger {
  color: #e11d48;
}

.tabs__item--danger.tabs__item--active {
  border-bottom-color: #e11d48;
  font-weight: 600;
}

.grid-card {
  background: var(--app-surface);
  border: 1px solid var(--app-border);
  border-radius: 12px;
  box-shadow: var(--app-shadow);
  padding: 1rem;
}

.filter-select {
  height: 2rem;
  font-size: 0.78rem;
  border: 1px solid var(--app-border);
  border-radius: 6px;
  background: var(--app-surface);
  color: var(--app-ink);
  padding: 0 0.5rem;
}

.icon-btn {
  border: none;
  background: transparent;
  color: var(--app-muted);
  cursor: pointer;
  padding: 0.3rem;
  border-radius: 4px;
  font-size: 0.75rem;
  line-height: 1;
}

.icon-btn:hover:not(:disabled) {
  background: var(--app-bg);
  color: var(--p-primary-color);
}

.icon-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.attach-link {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  border: none;
  background: transparent;
  color: var(--p-primary-color);
  font-size: 0.72rem;
  cursor: pointer;
  padding: 0.15rem 0.25rem;
}

.attach-link:hover {
  text-decoration: underline;
}

.attach-none {
  color: var(--app-muted);
}

.bulk-attach-hint {
  margin: 0.75rem 0 0;
  padding: 0.5rem 0.75rem;
  background: rgb(59 130 246 / 8%);
  border-radius: 8px;
  font-size: 0.75rem;
  color: #1d4ed8;
}

.trash-title {
  margin: 0;
  font-size: 0.9rem;
  font-weight: 600;
}

.trash-subtitle {
  font-size: 0.72rem;
  color: var(--app-muted);
}

.table-scroll {
  overflow: auto;
  max-height: 65vh;
  border: 1px solid var(--app-border);
  border-radius: 8px;
}

.trash-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.78rem;
  text-align: left;
}

.trash-table th {
  position: sticky;
  top: 0;
  background: var(--app-bg);
  font-size: 0.68rem;
  text-transform: uppercase;
  letter-spacing: 0.03em;
  color: var(--app-muted);
  padding: 0.55rem 0.6rem;
  border-bottom: 1px solid var(--app-border);
}

.trash-table td {
  padding: 0.45rem 0.6rem;
  border-bottom: 1px solid var(--app-border);
  vertical-align: top;
}

.trash-module {
  color: var(--app-teal);
  font-weight: 600;
  font-size: 0.72rem;
}

.mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
}

.muted {
  color: var(--app-muted);
  font-size: 0.72rem;
}

.truncate {
  max-width: 320px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.empty-cell {
  padding: 1.5rem !important;
  text-align: center;
  color: var(--app-muted);
}

.attach-form {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  font-size: 0.82rem;
}

.attach-form__hint {
  margin: 0;
  color: var(--app-muted);
}

.attach-form__file {
  font-size: 0.8rem;
}

.attach-form__selected {
  color: var(--app-muted);
}

.attach-form__error {
  color: #e11d48;
}

.attach-form__result {
  background: var(--app-bg);
  border-radius: 8px;
  padding: 0.6rem 0.75rem;
}

@media print {
  .no-print {
    display: none !important;
  }

  .grid-card {
    border: none;
    box-shadow: none;
    padding: 0;
  }

  .table-scroll {
    overflow: visible;
    max-height: none;
    border: none;
  }
}
</style>
