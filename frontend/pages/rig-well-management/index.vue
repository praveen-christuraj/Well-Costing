<script setup lang="ts">
/**
 * Rig & Well Management — the foundation of every well-scoped transaction.
 *
 * Tabs:
 *   • Rig Management      — spreadsheet bulk entry (code/name/remarks)
 *   • Well Management     — spreadsheet bulk entry, rig + block dropdowns
 *   • Well Configuration  — searchable/filterable list with the Configure popup
 *   • Deleted Entries     — soft-deleted rigs & wells (restore / permanent delete)
 *
 * Every entry tab carries the common template: Import (XLSX/CSV), XLSX/CSV
 * export, Print, edit and soft delete. All actions are audit-logged server-side.
 */
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import Button from 'primevue/button'
import Message from 'primevue/message'
import Tag from 'primevue/tag'
import PageHeader from '~/components/design-system/PageHeader.vue'
import ExcelGrid from '~/components/master-data/ExcelGrid.vue'
import ImportDialog from '~/components/master-data/ImportDialog.vue'
import ConfigManagerDialog from '~/components/catalogue/ConfigManagerDialog.vue'
import WellConfigDialog from '~/components/rig-well/WellConfigDialog.vue'
import type { EditableGridRow, GridColumn, GridSelectOption } from '~/types/grid'
import { matchesAdvancedSearch } from '~/utils/search'

definePageMeta({ middleware: 'auth' })

const api = useApi()

const TAB_RIGS = 0
const TAB_WELLS = 1
const TAB_CONFIG = 2
const TAB_DELETED = 3

const tabs = [
  { label: 'Rig Management', icon: 'pi pi-truck' },
  { label: 'Well Management', icon: 'pi pi-globe' },
  { label: 'Well Configuration', icon: 'pi pi-sliders-h' },
  { label: 'Deleted Entries', icon: 'pi pi-trash' },
]

const activeTab = ref(0)
const tabDirty = ref(false)
const activeGrid = ref<InstanceType<typeof ExcelGrid> | null>(null)

function switchTab(index: number): void {
  if (index === activeTab.value) return
  if (tabDirty.value && !window.confirm('This tab has unsaved rows. Switch tab and discard the unsaved entries?')) return
  activeTab.value = index
  tabDirty.value = false
}

// ---------------------------------------------------------------------------
// Dropdowns shared across tabs
// ---------------------------------------------------------------------------

interface RigDropdown { id: number; rig_code: string; rig_name: string; display_name: string }
interface BlockConfig { id: number; value: string }

const rigDropdown = ref<RigDropdown[]>([])
const blockConfig = ref<BlockConfig[]>([])

const rigOptions = computed<GridSelectOption[]>(() =>
  rigDropdown.value.map(rig => ({ label: rig.display_name, value: rig.id })),
)
const blockOptions = computed<GridSelectOption[]>(() =>
  blockConfig.value.map(block => ({ label: block.value, value: block.value })),
)
const hasRigs = computed(() => rigDropdown.value.length > 0)

async function loadDropdowns(): Promise<void> {
  try {
    const [rigs, blocks] = await Promise.all([
      api.get<RigDropdown[]>('/rig-well/rigs/dropdown'),
      api.get<BlockConfig[]>('/catalogue/configs/block'),
    ])
    rigDropdown.value = rigs
    blockConfig.value = blocks
  }
  catch (error) {
    console.error('Failed to load dropdowns', error)
  }
}

onMounted(() => {
  void loadDropdowns()
})

// ---------------------------------------------------------------------------
// Rig Management
// ---------------------------------------------------------------------------

const rigColumns: GridColumn[] = [
  { field: 'code', header: 'Rig Code', required: true, width: '150px', placeholder: 'e.g. RIG001' },
  { field: 'name', header: 'Rig Name', required: true, width: '260px', placeholder: 'e.g. Drilling Rig Alpha' },
  { field: 'remarks', header: 'Remarks', placeholder: 'Optional remarks' },
]

function rigToRow(record: Record<string, unknown>): Record<string, unknown> {
  return {
    _id: record.id as number | null,
    code: record.rig_code,
    name: record.rig_name,
    remarks: (record.remarks as string | null) ?? '',
  }
}

function rigToPayload(row: EditableGridRow): Record<string, unknown> {
  return {
    rig_code: String(row.code ?? '').trim(),
    rig_name: String(row.name ?? '').trim(),
    remarks: row.remarks ? String(row.remarks) : null,
  }
}

// ---------------------------------------------------------------------------
// Well Management
// ---------------------------------------------------------------------------

const wellColumns = computed<GridColumn[]>(() => [
  { field: 'rig_id', header: 'Rig', type: 'select', options: rigOptions.value, required: true, width: '230px', noPaste: true, placeholder: 'Select rig' },
  { field: 'well_code', header: 'Well Code', required: true, width: '130px', placeholder: 'e.g. WELL001' },
  { field: 'well_name', header: 'Well Name', required: true, width: '220px', placeholder: 'e.g. Exploratory 1' },
  { field: 'well_location', header: 'Well Location', required: true, width: '200px', placeholder: 'e.g. Block 12' },
  { field: 'block', header: 'Block', type: 'select', options: blockOptions.value, required: true, width: '150px', noPaste: true, placeholder: 'Select block' },
  { field: 'objective', header: 'Objective', required: true, width: '200px', placeholder: 'e.g. Appraisal' },
  { field: 'remarks', header: 'Remarks', width: '200px', placeholder: 'Optional remarks' },
])

function wellToRow(record: Record<string, unknown>): Record<string, unknown> {
  return {
    _id: record.id as number | null,
    rig_id: record.rig_id ?? null,
    well_code: record.well_code,
    well_name: record.well_name,
    well_location: record.well_location,
    block: record.block,
    objective: record.objective,
    remarks: (record.remarks as string | null) ?? '',
  }
}

function wellToPayload(row: EditableGridRow): Record<string, unknown> {
  return {
    rig_id: row.rig_id,
    well_code: String(row.well_code ?? '').trim(),
    well_name: String(row.well_name ?? '').trim(),
    well_location: String(row.well_location ?? '').trim(),
    block: String(row.block ?? '').trim(),
    objective: String(row.objective ?? '').trim(),
    remarks: row.remarks ? String(row.remarks) : null,
  }
}

// ---------------------------------------------------------------------------
// Import / Export / Print (Rigs + Wells)
// ---------------------------------------------------------------------------

const showImport = ref(false)
const showManageBlocks = ref(false)

const importTitle = computed(() =>
  activeTab.value === TAB_RIGS ? 'Bulk Import Rigs (CSV / XLSX)' : 'Bulk Import Wells (CSV / XLSX)',
)
const importEndpoint = computed(() =>
  activeTab.value === TAB_RIGS ? '/rig-well/rigs/import' : '/rig-well/wells/import',
)
const importTemplateEndpoint = computed(() =>
  activeTab.value === TAB_RIGS ? '/rig-well/rigs/import-template' : '/rig-well/wells/import-template',
)
const importTemplateFilename = computed(() =>
  activeTab.value === TAB_RIGS ? 'rigs_template.xlsx' : 'wells_template.xlsx',
)
const importHint = computed(() =>
  activeTab.value === TAB_RIGS
    ? 'Headers: rig_code, rig_name, remarks. Codes must be unique.'
    : 'Headers: rig_code, well_code, well_name, well_location, block, objective, remarks. Rigs must already exist.',
)

function exportCurrent(format: 'xlsx' | 'csv'): void {
  const base = activeTab.value === TAB_RIGS ? '/rig-well/rigs' : '/rig-well/wells'
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
// Well Configuration tab (list + configure)
// ---------------------------------------------------------------------------

interface WellRow {
  id: number
  rig_id: number
  well_code: string
  well_name: string
  well_location: string
  block: string
  objective: string
  status: string
  config_status: string
  depth_unit: string
  rig_code: string | null
  rig_name: string | null
  rig_display: string | null
  total_depth: string | number | null
  total_days: string | number | null
  section_count: number
  [key: string]: unknown
}

const wells = ref<WellRow[]>([])
const wellsLoading = ref(false)
const wellsError = ref<string | null>(null)

const configSearch = ref('')
const configRigFilter = ref<number | ''>('')
const configStatusFilter = ref('')
const configBlockFilter = ref('')

const configureTarget = ref<WellRow | null>(null)
const showConfigure = ref(false)

async function loadWells(): Promise<void> {
  wellsLoading.value = true
  wellsError.value = null
  try {
    wells.value = await api.get<WellRow[]>('/rig-well/wells')
  }
  catch (caught: unknown) {
    wellsError.value = caught instanceof Error ? caught.message : 'Wells could not be loaded'
    wells.value = []
  }
  finally {
    wellsLoading.value = false
  }
}

const filteredWells = computed(() => {
  return wells.value.filter((well) => {
    if (configRigFilter.value !== '' && well.rig_id !== configRigFilter.value) return false
    if (configStatusFilter.value === 'status' && well.status !== 'active') return false
    if (configStatusFilter.value === 'completed' && well.status !== 'completed') return false
    if (configStatusFilter.value === 'config-draft' && well.config_status !== 'draft') return false
    if (configStatusFilter.value === 'config-configured' && well.config_status !== 'configured') return false
    if (configBlockFilter.value && well.block !== configBlockFilter.value) return false
    if (!matchesAdvancedSearch(well, configSearch.value)) return false
    return true
  })
})

watch(activeTab, (tab) => {
  if (tab === TAB_CONFIG) void loadWells()
  if (tab === TAB_WELLS || tab === TAB_CONFIG) void loadDropdowns()
})

function openConfigure(well: WellRow): void {
  configureTarget.value = well
  showConfigure.value = true
}

function onConfigureChanged(): void {
  void loadWells()
}

function exportWells(format: 'xlsx' | 'csv'): void {
  api.download(`/rig-well/wells/export?format=${format}`).then((blob) => {
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `wells_export.${format}`
    a.click()
    window.URL.revokeObjectURL(url)
  }).catch((error: unknown) => {
    console.error('Export failed', error)
  })
}

function depthValue(value: string | number | null, unit: string): string {
  if (value == null || value === '') return '—'
  return `${Number(value)} ${unit === 'ft' ? 'ft' : 'm'}`
}

function daysValue(value: string | number | null): string {
  return value == null || value === '' ? '—' : Number(value).toFixed(2)
}

function depthLabel(well: WellRow): string {
  return depthValue(well.total_depth, well.depth_unit)
}

function daysLabel(well: WellRow): string {
  return daysValue(well.total_days)
}

// --- Row-wise print ---------------------------------------------------------
// The toolbar Print button prints the well list; the per-row Print button
// prints that one well's saved configuration (draft or configured). The
// configuration is fetched, swapped into the print-only sheet and the browser
// print dialog is opened; the sheet is cleared again when printing finishes so
// the next Print click goes back to the list.

interface PrintPhase {
  id: number
  phase_id: number
  phase_code: string | null
  phase_name: string | null
  days: string | number
  remarks: string | null
}

interface PrintSection {
  id: number
  section_id: number
  section_code: string | null
  section_name: string | null
  from_depth: string | number
  to_depth: string | number
  remarks: string | null
  total_days: string | number
  phases: PrintPhase[]
}

interface WellConfigurationSheet {
  well_id: number
  well_code: string
  well_name: string
  rig_code: string | null
  rig_name: string | null
  status: string
  config_status: string
  depth_unit: string
  total_depth: string | number | null
  total_days: string | number | null
  sections: PrintSection[]
}

const printSheet = ref<WellConfigurationSheet | null>(null)
// Id of the well whose configuration is being fetched, so only that row's
// button spins.
const printingWellId = ref<number | null>(null)

async function printWellConfiguration(well: WellRow): Promise<void> {
  printingWellId.value = well.id
  try {
    printSheet.value = await api.get<WellConfigurationSheet>(`/rig-well/wells/${well.id}/configuration`)
  }
  catch (caught: unknown) {
    printSheet.value = null
    window.alert(caught instanceof Error ? caught.message : 'Configuration could not be loaded for printing')
    return
  }
  finally {
    printingWellId.value = null
  }
  await nextTick()
  window.print()
}

function clearPrintSheet(): void {
  printSheet.value = null
}

onMounted(() => {
  window.addEventListener('afterprint', clearPrintSheet)
})

onBeforeUnmount(() => {
  window.removeEventListener('afterprint', clearPrintSheet)
})

// ---------------------------------------------------------------------------
// Deleted Entries tab
// ---------------------------------------------------------------------------

interface TrashItem {
  id: number
  kind: 'rig' | 'well'
  code: string
  name: string
  deleted_at: string | null
  [key: string]: unknown
}

const deletedRecords = ref<TrashItem[]>([])
const deletedLoading = ref(false)
const trashSearch = ref('')

const filteredTrash = computed(() =>
  deletedRecords.value.filter(item => matchesAdvancedSearch(item, trashSearch.value)),
)

async function loadAllDeleted(): Promise<void> {
  deletedLoading.value = true
  try {
    const [rigs, wellsRes] = await Promise.all([
      api.get<Record<string, any>[]>('/rig-well/rigs/deleted').catch(() => []),
      api.get<Record<string, any>[]>('/rig-well/wells/deleted').catch(() => []),
    ])
    const rigItems: TrashItem[] = rigs.map(r => ({
      id: r.id as number,
      kind: 'rig' as const,
      code: String(r.rig_code ?? ''),
      name: String(r.rig_name ?? ''),
      deleted_at: (r.deleted_at as string | null) ?? null,
    }))
    const wellItems: TrashItem[] = wellsRes.map(w => ({
      id: w.id as number,
      kind: 'well' as const,
      code: String(w.well_code ?? ''),
      name: `${String(w.well_name ?? '')} (${String(w.rig_display || w.rig_code || '')})`,
      deleted_at: (w.deleted_at as string | null) ?? null,
    }))
    deletedRecords.value = [...rigItems, ...wellItems].sort(
      (a, b) => new Date(b.deleted_at || 0).getTime() - new Date(a.deleted_at || 0).getTime(),
    )
  }
  catch (error) {
    console.error('Failed to load deleted entries', error)
  }
  finally {
    deletedLoading.value = false
  }
}

async function restoreRecord(item: TrashItem): Promise<void> {
  try {
    await api.post(`/rig-well/${item.kind}s/${item.id}/restore`, {})
    await Promise.all([loadAllDeleted(), loadDropdowns(), loadWells()])
  }
  catch (error: unknown) {
    window.alert(error instanceof Error ? error.message : 'Restore failed')
  }
}

async function permanentDelete(item: TrashItem): Promise<void> {
  if (!window.confirm('Permanently delete? This cannot be undone.')) return
  try {
    await api.delete(`/rig-well/${item.kind}s/${item.id}/permanent`)
    await loadAllDeleted()
  }
  catch (error: unknown) {
    window.alert(error instanceof Error ? error.message : 'Permanent delete failed')
  }
}

watch(activeTab, (tab) => {
  if (tab === TAB_DELETED) void loadAllDeleted()
})
</script>

<template>
  <div class="rig-well-page">
    <PageHeader
      class="no-print"
      title="Rig & Well Management"
      description="The foundation of every well-scoped transaction: create rigs first, then wells under each rig, then configure each well's sections, phases and days. Import (XLSX/CSV), export, print, soft delete and full audit logging on every tab."
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

    <!-- Rig Management -->
    <section v-if="activeTab === TAB_RIGS" class="grid-card">
      <ExcelGrid
        :ref="(el) => { if (el) activeGrid = el as InstanceType<typeof ExcelGrid> }"
        title="Rigs"
        singular="rig"
        :columns="rigColumns"
        code-field="code"
        :load-records="() => api.get('/rig-well/rigs')"
        :to-row="rigToRow"
        :to-payload="rigToPayload"
        :create-record="(payload: Record<string, unknown>) => api.post('/rig-well/rigs', payload)"
        :update-record="(id: number, payload: Record<string, unknown>) => api.put(`/rig-well/rigs/${id}`, payload)"
        :delete-record="(id: number) => api.delete(`/rig-well/rigs/${id}`)"
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

    <!-- Well Management -->
    <section v-else-if="activeTab === TAB_WELLS" class="grid-card">
      <Message v-if="!hasRigs" severity="warn" :closable="false" class="rig-warning no-print">
        No rigs have been created yet. Create at least one rig in the <strong>Rig Management</strong> tab first, then return here to create wells under it.
      </Message>

      <div class="well-toolbar no-print">
        <span class="well-toolbar__hint">Block is a user-configurable dropdown — manage its values or add wells below.</span>
        <Button label="Manage Blocks" icon="pi pi-list" size="small" severity="secondary" outlined @click="showManageBlocks = true" />
      </div>

      <ExcelGrid
        :ref="(el) => { if (el) activeGrid = el as InstanceType<typeof ExcelGrid> }"
        title="Wells"
        singular="well"
        :columns="wellColumns"
        code-field="well_code"
        paste-hint="The Rig and Block dropdowns are excluded from paste — set them in the grid afterwards."
        :load-records="() => api.get('/rig-well/wells')"
        :to-row="wellToRow"
        :to-payload="wellToPayload"
        :create-record="(payload: Record<string, unknown>) => api.post('/rig-well/wells', payload)"
        :update-record="(id: number, payload: Record<string, unknown>) => api.put(`/rig-well/wells/${id}`, payload)"
        :delete-record="(id: number) => api.delete(`/rig-well/wells/${id}`)"
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

    <!-- Well Configuration -->
    <section v-else-if="activeTab === TAB_CONFIG" class="grid-card">
      <div class="config-toolbar no-print">
        <div class="config-toolbar__filters">
          <div class="search">
            <i class="pi pi-search" />
            <input
              v-model="configSearch"
              type="search"
              placeholder="Search rig, well, location, block…"
              class="search__input"
            >
          </div>
          <select v-model="configRigFilter" class="filter-select">
            <option value="">All Rigs</option>
            <option v-for="rig in rigDropdown" :key="rig.id" :value="rig.id">{{ rig.display_name }}</option>
          </select>
          <select v-model="configStatusFilter" class="filter-select">
            <option value="">All Wells</option>
            <option value="status">Active</option>
            <option value="completed">Completed</option>
            <option value="config-draft">Config: Draft</option>
            <option value="config-configured">Config: Configured</option>
          </select>
          <select v-model="configBlockFilter" class="filter-select">
            <option value="">All Blocks</option>
            <option v-for="block in blockConfig" :key="block.id" :value="block.value">{{ block.value }}</option>
          </select>
          <span class="count">{{ filteredWells.length }} well(s)</span>
        </div>
        <div class="config-toolbar__actions">
          <Button label="Refresh" icon="pi pi-refresh" size="small" severity="secondary" outlined :loading="wellsLoading" @click="loadWells" />
          <Button label="XLSX" icon="pi pi-file-excel" size="small" severity="success" outlined @click="exportWells('xlsx')" />
          <Button label="CSV" icon="pi pi-file" size="small" severity="secondary" outlined @click="exportWells('csv')" />
          <Button label="Print" icon="pi pi-print" size="small" severity="secondary" text @click="printTable" />
        </div>
      </div>

      <p v-if="wellsError" class="error-copy no-print">{{ wellsError }}</p>

      <div class="table-scroll no-print">
        <table class="well-table">
          <thead>
            <tr>
              <th>Rig</th>
              <th>Well Code</th>
              <th>Well Name</th>
              <th>Location</th>
              <th>Block</th>
              <th>Status</th>
              <th>Configuration</th>
              <th>Total Depth</th>
              <th>Total Days</th>
              <th class="text-right">Actions</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="wellsLoading">
              <td colspan="10" class="empty-cell"><i class="pi pi-spin pi-spinner" /> Loading wells…</td>
            </tr>
            <tr v-else-if="filteredWells.length === 0">
              <td colspan="10" class="empty-cell">
                {{ wells.length ? 'No wells match the current filters.' : 'No wells yet — create them in the Well Management tab first.' }}
              </td>
            </tr>
            <tr v-for="well in filteredWells" :key="well.id">
              <td class="truncate" :title="well.rig_display ?? ''">{{ well.rig_display || '—' }}</td>
              <td class="mono">{{ well.well_code }}</td>
              <td class="truncate" :title="well.well_name">{{ well.well_name }}</td>
              <td class="truncate" :title="well.well_location">{{ well.well_location }}</td>
              <td>{{ well.block }}</td>
              <td>
                <Tag :severity="well.status === 'completed' ? 'danger' : 'success'" :value="well.status === 'completed' ? 'Completed' : 'Active'" />
              </td>
              <td>
                <Tag :severity="well.config_status === 'configured' ? 'success' : 'warn'" :value="well.config_status === 'configured' ? 'Configured' : 'Draft'" />
              </td>
              <td class="mono">{{ depthLabel(well) }}</td>
              <td class="mono">{{ daysLabel(well) }}</td>
              <td class="text-right config-actions">
                <Button label="Configure" icon="pi pi-sliders-h" size="small" severity="secondary" outlined @click="openConfigure(well)" />
                <Button
                  label="Print"
                  icon="pi pi-print"
                  size="small"
                  severity="secondary"
                  text
                  :loading="printingWellId === well.id"
                  :disabled="!well.section_count"
                  :title="well.section_count ? `Print the ${well.well_code} configuration` : 'No configuration saved for this well yet'"
                  @click="printWellConfiguration(well)"
                />
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <div v-if="!printSheet" class="print-sheet" aria-hidden="true">
        <header class="print-sheet__header">
          <p class="print-sheet__eyebrow">Drilling Costing</p>
          <h1>Well Configuration</h1>
          <p class="print-sheet__meta">{{ filteredWells.length }} well(s)</p>
        </header>
        <table class="print-sheet__table">
          <thead>
            <tr>
              <th>Rig</th>
              <th>Well Code</th>
              <th>Well Name</th>
              <th>Location</th>
              <th>Block</th>
              <th>Status</th>
              <th>Configuration</th>
              <th>Total Depth</th>
              <th>Total Days</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="well in filteredWells" :key="`print-${well.id}`">
              <td>{{ well.rig_display || '—' }}</td>
              <td>{{ well.well_code }}</td>
              <td>{{ well.well_name }}</td>
              <td>{{ well.well_location }}</td>
              <td>{{ well.block }}</td>
              <td>{{ well.status === 'completed' ? 'Completed' : 'Active' }}</td>
              <td>{{ well.config_status === 'configured' ? 'Configured' : 'Draft' }}</td>
              <td>{{ depthLabel(well) }}</td>
              <td>{{ daysLabel(well) }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Row-wise print: one well's sections → phases → days -->
      <div v-if="printSheet" class="print-sheet" aria-hidden="true">
        <header class="print-sheet__header">
          <p class="print-sheet__eyebrow">Drilling Costing</p>
          <h1>Well Configuration — {{ printSheet.well_code }}</h1>
          <p class="print-sheet__meta">
            {{ printSheet.rig_code || '—' }}{{ printSheet.rig_name ? ` — ${printSheet.rig_name}` : '' }}
            · {{ printSheet.well_name }}
            · {{ printSheet.status === 'completed' ? 'Completed' : 'Active' }}
            · {{ printSheet.config_status === 'configured' ? 'Configured' : 'Draft' }}
            · Total depth {{ depthValue(printSheet.total_depth, printSheet.depth_unit) }}
            · Total days {{ daysValue(printSheet.total_days) }}
            · Printed {{ new Date().toLocaleString() }}
          </p>
        </header>
        <table class="print-sheet__table">
          <thead>
            <tr>
              <th>#</th>
              <th>Hole Section</th>
              <th>From ({{ printSheet.depth_unit === 'ft' ? 'ft' : 'm' }})</th>
              <th>To ({{ printSheet.depth_unit === 'ft' ? 'ft' : 'm' }})</th>
              <th>Phase</th>
              <th>Days</th>
              <th>Remarks</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="!printSheet.sections.length">
              <td colspan="7" class="print-sheet__empty">No sections configured for this well.</td>
            </tr>
            <template v-for="(section, sIndex) in printSheet.sections" :key="`section-${section.id}`">
              <tr v-if="!section.phases.length">
                <td>{{ sIndex + 1 }}</td>
                <td>{{ section.section_code || '—' }}{{ section.section_name ? ` — ${section.section_name}` : '' }}</td>
                <td>{{ depthValue(section.from_depth, printSheet.depth_unit) }}</td>
                <td>{{ depthValue(section.to_depth, printSheet.depth_unit) }}</td>
                <td>—</td>
                <td>{{ daysValue(section.total_days) }}</td>
                <td>{{ section.remarks || '' }}</td>
              </tr>
              <tr v-for="(phase, pIndex) in section.phases" :key="`phase-${section.id}-${phase.id}`">
                <td>{{ pIndex === 0 ? sIndex + 1 : '' }}</td>
                <td>{{ pIndex === 0 ? `${section.section_code || '—'}${section.section_name ? ` — ${section.section_name}` : ''}` : '' }}</td>
                <td>{{ pIndex === 0 ? depthValue(section.from_depth, printSheet.depth_unit) : '' }}</td>
                <td>{{ pIndex === 0 ? depthValue(section.to_depth, printSheet.depth_unit) : '' }}</td>
                <td>{{ phase.phase_code || '—' }}{{ phase.phase_name ? ` — ${phase.phase_name}` : '' }}</td>
                <td>{{ daysValue(phase.days) }}</td>
                <td>{{ pIndex === 0 ? [section.remarks, phase.remarks].filter(Boolean).join(' · ') : (phase.remarks || '') }}</td>
              </tr>
            </template>
          </tbody>
          <tfoot v-if="printSheet.sections.length">
            <tr>
              <th colspan="3">Total — {{ printSheet.sections.length }} section(s)</th>
              <th>{{ depthValue(printSheet.total_depth, printSheet.depth_unit) }}</th>
              <th>Total days</th>
              <th>{{ daysValue(printSheet.total_days) }}</th>
              <th />
            </tr>
          </tfoot>
        </table>
      </div>
    </section>

    <!-- Deleted Entries -->
    <section v-else-if="activeTab === TAB_DELETED" class="grid-card">
      <div class="trash-head no-print">
        <h3 class="trash-title">Deleted Entries (Trash) — {{ deletedRecords.length }} items</h3>
        <div class="trash-head__right">
          <div class="trash-search">
            <i class="pi pi-search" />
            <input v-model="trashSearch" type="search" placeholder="Search trash…" class="trash-search__input">
          </div>
          <span class="trash-subtitle">Restore or permanently delete. All actions are audit-logged.</span>
        </div>
      </div>
      <div class="table-scroll">
        <table class="trash-table">
          <thead>
            <tr>
              <th>Type</th>
              <th>Code</th>
              <th>Name / Details</th>
              <th>Deleted At</th>
              <th class="text-right">Actions</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="deletedLoading">
              <td colspan="5" class="empty-cell"><i class="pi pi-spin pi-spinner" /> Loading deleted entries…</td>
            </tr>
            <tr v-else-if="filteredTrash.length === 0">
              <td colspan="5" class="empty-cell">No deleted entries.</td>
            </tr>
            <tr v-for="item in filteredTrash" :key="`${item.kind}-${item.id}`">
              <td><Tag :severity="item.kind === 'rig' ? 'info' : 'secondary'" :value="item.kind === 'rig' ? 'Rig' : 'Well'" /></td>
              <td class="mono">{{ item.code || '—' }}</td>
              <td class="truncate">{{ item.name || '—' }}</td>
              <td class="muted">{{ item.deleted_at ? new Date(item.deleted_at).toLocaleString() : '—' }}</td>
              <td class="text-right trash-actions">
                <Button label="Restore" size="small" severity="success" outlined @click="restoreRecord(item)" />
                <Button label="Delete" size="small" severity="danger" outlined @click="permanentDelete(item)" />
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <ImportDialog
      v-if="activeTab === TAB_RIGS || activeTab === TAB_WELLS"
      v-model:visible="showImport"
      :title="importTitle"
      :endpoint="importEndpoint"
      :hint="importHint"
      :template-endpoint="importTemplateEndpoint"
      :template-filename="importTemplateFilename"
      @committed="activeGrid?.reload(); loadDropdowns()"
    />

    <ConfigManagerDialog
      v-model:visible="showManageBlocks"
      config-type="block"
      title="Blocks"
      @changed="loadDropdowns()"
    />

    <WellConfigDialog
      v-model:visible="showConfigure"
      :well="configureTarget"
      @changed="onConfigureChanged"
    />
  </div>
</template>

<style scoped>
.rig-well-page {
  max-width: 1700px;
  margin: 0 auto;
}

/* The tab strip uses the shared underline tabs from assets/css/main.css —
   the same design as the Master Data page. Only the overflow behaviour is
   adjusted: these four are navigation tabs, so they sit side by side (and
   wrap on a narrow screen) instead of scrolling horizontally. */
.tabs {
  flex-wrap: wrap;
  overflow-x: visible;
}

.grid-card {
  background: var(--app-surface);
  border: 1px solid var(--app-border);
  border-radius: 12px;
  box-shadow: var(--app-shadow);
  padding: 1rem;
}

.rig-warning {
  margin: 0 0 0.75rem;
}

.well-toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 0.6rem;
  margin-bottom: 0.75rem;
}

.well-toolbar__hint {
  font-size: 0.75rem;
  color: var(--app-muted);
}

/* --- Well Configuration tab --- */
.config-toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  margin-bottom: 0.75rem;
}

.config-toolbar__filters,
.config-toolbar__actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.4rem;
}

.filter-select,
.search__input {
  height: 2rem;
  font-size: 0.78rem;
  border: 1px solid var(--app-border);
  border-radius: 6px;
  background: var(--app-surface);
  color: var(--app-ink);
  padding: 0 0.5rem;
}

.search {
  position: relative;
  display: flex;
  align-items: center;
}

.search .pi-search {
  position: absolute;
  left: 0.55rem;
  color: var(--app-muted);
  font-size: 0.75rem;
  pointer-events: none;
}

.search__input {
  padding-left: 1.7rem;
  width: 16rem;
  border-radius: 999px;
  background: var(--app-glass, var(--app-surface));
  border-color: var(--app-glass-border, var(--app-border));
}

.count {
  font-size: 0.72rem;
  color: var(--app-muted);
}

.error-copy {
  color: #e11d48;
}

.table-scroll {
  overflow: auto;
  max-height: 65vh;
  border: 1px solid var(--app-border);
  border-radius: 8px;
}

.well-table,
.trash-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.78rem;
  text-align: left;
}

.well-table th,
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
  white-space: nowrap;
}

.well-table td,
.trash-table td {
  padding: 0.45rem 0.6rem;
  border-bottom: 1px solid var(--app-border);
  vertical-align: top;
}

.mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
}

.muted {
  color: var(--app-muted);
  font-size: 0.72rem;
}

.truncate {
  max-width: 260px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.empty-cell {
  padding: 1.5rem !important;
  text-align: center;
  color: var(--app-muted);
}

.config-actions,
.trash-actions {
  white-space: nowrap;
}

.text-right {
  text-align: right;
}

/* --- Trash --- */
.trash-head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
  margin-bottom: 0.75rem;
}

.trash-head__right {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  flex-wrap: wrap;
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

.trash-search {
  position: relative;
  display: flex;
  align-items: center;
}

.trash-search .pi-search {
  position: absolute;
  left: 0.55rem;
  color: var(--app-muted);
  font-size: 0.72rem;
  pointer-events: none;
}

.trash-search__input {
  height: 1.9rem;
  font-size: 0.75rem;
  border: 1px solid var(--app-glass-border, var(--app-border));
  border-radius: 999px;
  background: var(--app-glass, var(--app-surface));
  color: var(--app-ink);
  padding: 0 0.5rem 0 1.6rem;
  width: 16rem;
}

.print-sheet {
  display: none;
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

  .print-sheet {
    display: block;
  }
}
</style>
