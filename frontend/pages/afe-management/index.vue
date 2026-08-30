<script setup lang="ts">
/**
 * AFE Management — the backbone of the costing application.
 *
 * Tabs:
 *   • AFE                  — create the well-scoped AFE (rig → well → code/name/type)
 *   • AFE Cost Estimation  — configure Services / Consumables / Tangibles, price
 *                            them and move the AFE through draft → submitted → approved
 *   • Deleted Entries      — soft-deleted AFEs (restore / permanent delete)
 *
 * Every tab carries the common template: Import (XLSX/CSV), XLSX/CSV export,
 * Print, edit and soft delete, with every action audit-logged server-side.
 * The AFE tab shows the status but never changes it — that happens on the
 * AFE Cost Estimation tab.
 */
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import Button from 'primevue/button'
import Message from 'primevue/message'
import Tag from 'primevue/tag'
import PageHeader from '~/components/design-system/PageHeader.vue'
import ExcelGrid from '~/components/master-data/ExcelGrid.vue'
import ImportDialog from '~/components/master-data/ImportDialog.vue'
import AfeEstimateDialog from '~/components/afe/AfeEstimateDialog.vue'
import AfePrintSheet from '~/components/afe/AfePrintSheet.vue'
import type { EditableGridRow, GridColumn, GridSelectOption } from '~/types/grid'
import type {
  AfeEstimate,
  AfeRow,
  AfeType,
  ConsumableOption,
  ServiceOption,
  TangibleOption,
} from '~/types/afe'
import { matchesAdvancedSearch } from '~/utils/search'

definePageMeta({ middleware: 'auth' })

const api = useApi()

const TAB_AFE = 0
const TAB_ESTIMATION = 1
const TAB_DELETED = 2

const tabs = [
  { label: 'AFE', icon: 'pi pi-wallet' },
  { label: 'AFE Cost Estimation', icon: 'pi pi-calculator' },
  { label: 'Deleted Entries', icon: 'pi pi-trash' },
]

const activeTab = ref(0)
const tabDirty = ref(false)

function switchTab(index: number): void {
  if (index === activeTab.value) return
  if (tabDirty.value && !window.confirm('This tab has unsaved rows. Switch tab and discard the unsaved entries?')) return
  activeTab.value = index
  tabDirty.value = false
}

// ---------------------------------------------------------------------------
// Lookups owned by other pages
// ---------------------------------------------------------------------------

interface RigDropdown { id: number, rig_code: string, rig_name: string, display_name: string }
interface WellRecord { id: number, rig_id: number, well_code: string, well_name: string, config_status: string, section_count: number }

const rigs = ref<RigDropdown[]>([])
const wells = ref<WellRecord[]>([])
const serviceOptions = ref<ServiceOption[]>([])
const consumableOptions = ref<ConsumableOption[]>([])
const tangibleOptions = ref<TangibleOption[]>([])
const lookupError = ref<string | null>(null)

const rigOptions = computed<GridSelectOption[]>(() =>
  rigs.value.map(rig => ({ label: rig.display_name, value: rig.id })),
)
const afeTypeOptions: GridSelectOption[] = [
  { label: 'Drilling', value: 'Drilling' },
  { label: 'Completion', value: 'Completion' },
]
const hasRigs = computed(() => rigs.value.length > 0)
const hasWells = computed(() => wells.value.length > 0)

function wellOptionsFor(rigId: unknown): GridSelectOption[] {
  if (rigId == null || rigId === '') return []
  return wells.value
    .filter(well => well.rig_id === rigId)
    .map(well => ({ label: `${well.well_code} - ${well.well_name}`, value: well.id }))
}

async function loadLookups(): Promise<void> {
  lookupError.value = null
  try {
    const [rigList, wellList, services, chemicals, bits, tangibles] = await Promise.all([
      api.get<RigDropdown[]>('/rig-well/rigs/dropdown'),
      api.get<WellRecord[]>('/rig-well/wells'),
      api.get<Record<string, any>[]>('/catalogue/services'),
      api.get<Record<string, any>[]>('/catalogue/mud-chemicals'),
      api.get<Record<string, any>[]>('/catalogue/drill-bits'),
      api.get<Record<string, any>[]>('/catalogue/tangibles'),
    ])
    rigs.value = rigList
    wells.value = wellList
    serviceOptions.value = services.map(service => ({
      id: service.id as number,
      service_code: String(service.service_code ?? ''),
      service_name: String(service.service_name ?? ''),
      provider_type: String(service.provider_type ?? ''),
      vendor_display: (service.vendor_display as string | null) ?? null,
    }))
    consumableOptions.value = [
      ...chemicals.map(item => ({
        id: item.id as number,
        code: String(item.chemical_code ?? ''),
        name: String(item.chemical_name ?? ''),
        rate: Number(item.current_rate ?? 0),
        uom: (item.uom as string | null) ?? null,
        currency: (item.currency as string | null) ?? null,
        kind: 'mud_chemical' as const,
        detail: `Mud Chemical · ${item.uom ?? '—'}`,
        manufacturer: (item.part_number as string | null) ?? null,
        description: (item.description as string | null) ?? null,
        category: (item.uom as string | null) ?? null,
      })),
      ...bits.map(item => ({
        id: item.id as number,
        code: String(item.bit_code ?? ''),
        name: String(item.bit_name ?? ''),
        rate: Number(item.final_cost ?? 0),
        uom: null,
        currency: (item.currency as string | null) ?? null,
        kind: 'drill_bit' as const,
        detail: `Drill Bit · ${item.bit_type ?? ''}`,
        manufacturer: (item.manufacturer as string | null) ?? null,
        description: (item.description as string | null) ?? null,
        itemType: (item.bit_type as string | null) ?? null,
        size: (item.size as string | null) ?? null,
        iadcCode: (item.iadc_code as string | null) ?? null,
        modelNo: (item.model_no as string | null) ?? null,
      })),
    ]
    tangibleOptions.value = tangibles.map(item => ({
      id: item.id as number,
      code: String(item.tangible_code ?? ''),
      name: String(item.tangible_name ?? ''),
      rate: Number(item.final_cost ?? 0),
      uom: (item.uom as string | null) ?? null,
      currency: (item.currency as string | null) ?? null,
      detail: `${item.tangible_scope ?? ''} · ${item.category ?? ''}`,
      manufacturer: (item.manufacturer as string | null) ?? null,
      description: (item.description as string | null) ?? null,
      category: (item.category as string | null) ?? null,
      subcategory: (item.subcategory as string | null) ?? null,
    }))
  }
  catch (caught: unknown) {
    lookupError.value = caught instanceof Error ? caught.message : 'Master data could not be loaded'
  }
}

// ---------------------------------------------------------------------------
// AFE tab (bulk entry grid)
// ---------------------------------------------------------------------------

const afeColumns = computed<GridColumn[]>(() => [
  {
    field: 'rig_id',
    header: 'Rig',
    type: 'select',
    options: rigOptions.value,
    required: true,
    width: '220px',
    noPaste: true,
    placeholder: 'Select rig',
    onCellChange: (row: EditableGridRow) => {
      // The well list depends on the rig: drop a well from the previous rig.
      if (!wellOptionsFor(row.rig_id).some(option => option.value === row.well_id)) row.well_id = null
    },
  },
  {
    field: 'well_id',
    header: 'Well',
    type: 'select',
    optionsFor: (row: Record<string, unknown>) => wellOptionsFor(row.rig_id),
    required: true,
    width: '230px',
    noPaste: true,
    placeholder: 'Select well',
  },
  { field: 'afe_code', header: 'AFE Code', required: true, width: '150px', placeholder: 'e.g. AFE-2026-001' },
  { field: 'afe_name', header: 'AFE Name', required: true, width: '240px', placeholder: 'e.g. Surface section drilling' },
  {
    field: 'afe_type',
    header: 'AFE Type',
    type: 'select',
    options: afeTypeOptions,
    required: true,
    width: '130px',
    noPaste: true,
    defaultValue: 'Drilling',
  },
  { field: 'status', header: 'Status', readonly: true, width: '95px' },
  { field: 'remarks', header: 'Remarks', width: '220px', placeholder: 'Optional remarks' },
])

function afeToRow(record: Record<string, unknown>): Record<string, unknown> {
  const status = String(record.status ?? 'draft')
  const statusLabels: Record<string, string> = { draft: 'Draft', submitted: 'Submitted', approved: 'Approved' }
  return {
    _id: record.id as number | null,
    rig_id: record.rig_id ?? null,
    well_id: record.well_id ?? null,
    afe_code: record.afe_code,
    afe_name: record.afe_name,
    afe_type: record.afe_type,
    status: statusLabels[status] ?? status,
    remarks: (record.remarks as string | null) ?? '',
  }
}

function afeToPayload(row: EditableGridRow): Record<string, unknown> {
  return {
    rig_id: row.rig_id,
    well_id: row.well_id,
    afe_code: String(row.afe_code ?? '').trim(),
    afe_name: String(row.afe_name ?? '').trim(),
    afe_type: (row.afe_type as AfeType) ?? 'Drilling',
    remarks: row.remarks ? String(row.remarks) : null,
  }
}

// ---------------------------------------------------------------------------
// Import / Export / Print
// ---------------------------------------------------------------------------

const showImport = ref(false)

function exportAfes(format: 'xlsx' | 'csv'): void {
  api.download(`/afe/afes/export?format=${format}`).then((blob) => {
    const url = window.URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = `afe_list.${format}`
    anchor.click()
    window.URL.revokeObjectURL(url)
  }).catch((error: unknown) => {
    console.error('Export failed', error)
  })
}

function exportEstimates(format: 'xlsx' | 'csv'): void {
  const target = printEstimateTarget.value?.afe.id
  const path = target ? `/afe/estimates/${target}/export?format=${format}` : `/afe/estimates/export?format=${format}`
  api.download(path).then((blob) => {
    const url = window.URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = target ? `afe_estimate.${format}` : `afe_cost_estimates.${format}`
    anchor.click()
    window.URL.revokeObjectURL(url)
  }).catch((error: unknown) => {
    console.error('Export failed', error)
  })
}

function printPage(): void {
  window.print()
}

// ---------------------------------------------------------------------------
// AFE Cost Estimation tab
// ---------------------------------------------------------------------------

const estimateRows = ref<AfeRow[]>([])
const estimatesLoading = ref(false)
const estimatesError = ref<string | null>(null)
const estimateSearch = ref('')
const statusFilter = ref('')
const typeFilter = ref('')
const rigFilter = ref<number | ''>('')

const filteredEstimates = computed(() =>
  estimateRows.value.filter((row) => {
    if (statusFilter.value && row.status !== statusFilter.value) return false
    if (typeFilter.value && row.afe_type !== typeFilter.value) return false
    if (rigFilter.value !== '' && row.rig_id !== rigFilter.value) return false
    return matchesAdvancedSearch(row, estimateSearch.value)
  }),
)

async function loadEstimates(): Promise<void> {
  estimatesLoading.value = true
  estimatesError.value = null
  try {
    estimateRows.value = await api.get<AfeRow[]>('/afe/estimates')
  }
  catch (caught: unknown) {
    estimatesError.value = caught instanceof Error ? caught.message : 'The AFE list could not be loaded'
    estimateRows.value = []
  }
  finally {
    estimatesLoading.value = false
  }
}

const estimateTarget = ref<number | null>(null)
const showEstimate = ref(false)
const loadingEstimateId = ref<number | null>(null)

function openEstimate(row: AfeRow): void {
  estimateTarget.value = row.id
  showEstimate.value = true
}

function onEstimateChanged(): void {
  void loadEstimates()
}

const statusMeta: Record<string, { label: string, severity: 'secondary' | 'warn' | 'success' }> = {
  draft: { label: 'Draft', severity: 'secondary' },
  submitted: { label: 'Submitted', severity: 'warn' },
  approved: { label: 'Approved', severity: 'success' },
}

function statusOf(row: AfeRow): { label: string, severity: 'secondary' | 'warn' | 'success' } {
  return statusMeta[row.status] ?? { label: row.status, severity: 'secondary' }
}

function money(value: string | number | null | undefined): string {
  if (value == null || value === '') return '0.00'
  const numeric = Number(value)
  return Number.isFinite(numeric)
    ? numeric.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
    : String(value)
}

// --- Print -----------------------------------------------------------------
// The toolbar Print button prints the AFE list; the per-row Print button (and
// the dialog) print one complete AFE — well configuration plus the three cost
// groups. The single-AFE sheet replaces the list sheet while printing.

const printEstimateTarget = ref<AfeEstimate | null>(null)
const printEstimateStamp = ref('')

async function printAfe(row: AfeRow): Promise<void> {
  loadingEstimateId.value = row.id
  try {
    printEstimateTarget.value = await api.get<AfeEstimate>(`/afe/estimates/${row.id}`)
    printEstimateStamp.value = new Date().toLocaleString()
  }
  catch (caught: unknown) {
    printEstimateTarget.value = null
    window.alert(caught instanceof Error ? caught.message : 'The AFE could not be loaded for printing')
    return
  }
  finally {
    loadingEstimateId.value = null
  }
  await nextTick()
  window.print()
}

async function printFromDialog(estimate: AfeEstimate): Promise<void> {
  printEstimateTarget.value = estimate
  printEstimateStamp.value = new Date().toLocaleString()
  await nextTick()
}

function clearPrintSheet(): void {
  printEstimateTarget.value = null
}

onMounted(() => {
  void loadLookups()
  window.addEventListener('afterprint', clearPrintSheet)
})

onBeforeUnmount(() => {
  window.removeEventListener('afterprint', clearPrintSheet)
})

watch(activeTab, (tab) => {
  if (tab === TAB_ESTIMATION) {
    void loadEstimates()
    void loadLookups()
  }
  if (tab === TAB_DELETED) void loadDeleted()
})

// ---------------------------------------------------------------------------
// Deleted Entries tab
// ---------------------------------------------------------------------------

const deletedRecords = ref<AfeRow[]>([])
const deletedLoading = ref(false)
const trashSearch = ref('')

const filteredTrash = computed(() =>
  deletedRecords.value.filter(item => matchesAdvancedSearch(item, trashSearch.value)),
)

async function loadDeleted(): Promise<void> {
  deletedLoading.value = true
  try {
    deletedRecords.value = await api.get<AfeRow[]>('/afe/afes/deleted')
  }
  catch (error) {
    console.error('Failed to load deleted entries', error)
  }
  finally {
    deletedLoading.value = false
  }
}

async function restoreRecord(item: AfeRow): Promise<void> {
  try {
    await api.post(`/afe/afes/${item.id}/restore`, {})
    await Promise.all([loadDeleted(), loadEstimates()])
  }
  catch (error: unknown) {
    window.alert(error instanceof Error ? error.message : 'Restore failed')
  }
}

async function permanentDelete(item: AfeRow): Promise<void> {
  if (!window.confirm(`Permanently delete AFE ${item.afe_code} and all of its estimate lines? This cannot be undone.`)) return
  try {
    await api.delete(`/afe/afes/${item.id}/permanent`)
    await loadDeleted()
  }
  catch (error: unknown) {
    window.alert(error instanceof Error ? error.message : 'Permanent delete failed')
  }
}
</script>

<template>
  <div class="afe-page">
    <PageHeader
      class="no-print"
      title="AFE Management"
      description="The backbone of the costing application: create well-scoped AFEs, then configure their Services, Consumables and Tangibles. Sections and phases always come from the well configuration, rates come from Master Data, and the estimate compiles the three cost groups into the final AFE cost. Import (XLSX/CSV), export, print, soft delete and full audit logging on every tab."
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

    <Message v-if="lookupError" severity="warn" :closable="false" class="no-print">{{ lookupError }}</Message>

    <!-- AFE -->
    <section v-if="activeTab === TAB_AFE" class="grid-card">
      <Message v-if="!hasRigs || !hasWells" severity="warn" :closable="false" class="no-print">
        {{ !hasRigs
          ? 'No rigs yet — create a rig in Rig & Well Management first.'
          : 'No wells yet — create the wells under their rigs in Rig & Well Management, then return here.' }}
      </Message>

      <ExcelGrid
        title="AFEs"
        singular="AFE"
        :columns="afeColumns"
        code-field="afe_code"
        paste-hint="The Rig, Well and AFE Type dropdowns are excluded from paste — set them in the grid afterwards."
        :load-records="() => api.get('/afe/afes')"
        :to-row="afeToRow"
        :to-payload="afeToPayload"
        :create-record="(payload: Record<string, unknown>) => api.post('/afe/afes', payload)"
        :update-record="(id: number, payload: Record<string, unknown>) => api.put(`/afe/afes/${id}`, payload)"
        :delete-record="(id: number) => api.delete(`/afe/afes/${id}`)"
        @dirty="tabDirty = $event"
      >
        <template #toolbar-extra>
          <Button label="Import" icon="pi pi-upload" size="small" severity="secondary" outlined @click="showImport = true" />
          <Button label="XLSX" icon="pi pi-file-excel" size="small" severity="success" outlined @click="exportAfes('xlsx')" />
          <Button label="CSV" icon="pi pi-file" size="small" severity="secondary" outlined @click="exportAfes('csv')" />
          <Button label="Print" icon="pi pi-print" size="small" severity="secondary" text @click="printPage" />
        </template>
      </ExcelGrid>
    </section>

    <!-- AFE Cost Estimation -->
    <section v-else-if="activeTab === TAB_ESTIMATION" class="grid-card">
      <div class="afe-toolbar no-print">
        <div class="afe-toolbar__filters">
          <div class="search">
            <i class="pi pi-search" />
            <input
              v-model="estimateSearch"
              type="search"
              placeholder="Search AFE code, name, rig, well…"
              class="search__input"
            >
          </div>
          <select v-model="statusFilter" class="filter-select">
            <option value="">All Statuses</option>
            <option value="draft">Draft</option>
            <option value="submitted">Submitted</option>
            <option value="approved">Approved</option>
          </select>
          <select v-model="typeFilter" class="filter-select">
            <option value="">All Types</option>
            <option value="Drilling">Drilling</option>
            <option value="Completion">Completion</option>
          </select>
          <select v-model="rigFilter" class="filter-select">
            <option value="">All Rigs</option>
            <option v-for="rig in rigs" :key="rig.id" :value="rig.id">{{ rig.display_name }}</option>
          </select>
          <span class="count">{{ filteredEstimates.length }} AFE(s)</span>
        </div>
        <div class="afe-toolbar__actions">
          <Button label="Refresh" icon="pi pi-refresh" size="small" severity="secondary" outlined :loading="estimatesLoading" @click="loadEstimates" />
          <Button label="XLSX" icon="pi pi-file-excel" size="small" severity="success" outlined @click="exportEstimates('xlsx')" />
          <Button label="CSV" icon="pi pi-file" size="small" severity="secondary" outlined @click="exportEstimates('csv')" />
          <Button label="Print" icon="pi pi-print" size="small" severity="secondary" text @click="printPage" />
        </div>
      </div>

      <p v-if="estimatesError" class="error-copy no-print">{{ estimatesError }}</p>

      <div class="table-scroll no-print">
        <table class="afe-table">
          <thead>
            <tr>
              <th>AFE Code</th>
              <th>AFE Name</th>
              <th>Type</th>
              <th>Rig</th>
              <th>Well</th>
              <th>Status</th>
              <th class="text-right">S / C / T</th>
              <th class="text-right">Estimate</th>
              <th class="text-right">Actions</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="estimatesLoading">
              <td colspan="9" class="empty-cell"><i class="pi pi-spin pi-spinner" /> Loading AFEs…</td>
            </tr>
            <tr v-else-if="filteredEstimates.length === 0">
              <td colspan="9" class="empty-cell">
                {{ estimateRows.length ? 'No AFEs match the current filters.' : 'No AFEs yet — create them in the AFE tab first.' }}
              </td>
            </tr>
            <tr v-for="row in filteredEstimates" :key="row.id">
              <td class="mono">{{ row.afe_code }}</td>
              <td class="truncate" :title="row.afe_name">{{ row.afe_name }}</td>
              <td>{{ row.afe_type }}</td>
              <td class="truncate" :title="row.rig_display ?? ''">{{ row.rig_display || '—' }}</td>
              <td class="truncate" :title="row.well_display ?? ''">{{ row.well_display || '—' }}</td>
              <td><Tag :severity="statusOf(row).severity" :value="statusOf(row).label" /></td>
              <td class="mono text-right">{{ row.service_count }} / {{ row.consumable_count }} / {{ row.tangible_count }}</td>
              <td class="mono text-right">{{ money(row.estimated_total) }}</td>
              <td class="text-right afe-actions">
                <Button label="Cost Estimate" icon="pi pi-calculator" size="small" severity="secondary" outlined @click="openEstimate(row)" />
                <Button
                  label="Print"
                  icon="pi pi-print"
                  size="small"
                  severity="secondary"
                  text
                  :loading="loadingEstimateId === row.id"
                  @click="printAfe(row)"
                />
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Print: the AFE list, unless one AFE is being printed -->
      <div v-if="!printEstimateTarget" class="print-sheet" aria-hidden="true">
        <header class="print-sheet__header">
          <p class="print-sheet__eyebrow">Drilling Costing</p>
          <h1>AFE Cost Estimation</h1>
          <p class="print-sheet__meta">{{ filteredEstimates.length }} AFE(s)</p>
        </header>
        <table class="print-sheet__table">
          <thead>
            <tr>
              <th>AFE Code</th>
              <th>AFE Name</th>
              <th>Type</th>
              <th>Rig</th>
              <th>Well</th>
              <th>Status</th>
              <th>Services</th>
              <th>Consumables</th>
              <th>Tangibles</th>
              <th>Estimate</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in filteredEstimates" :key="`print-${row.id}`">
              <td>{{ row.afe_code }}</td>
              <td>{{ row.afe_name }}</td>
              <td>{{ row.afe_type }}</td>
              <td>{{ row.rig_display || '—' }}</td>
              <td>{{ row.well_display || '—' }}</td>
              <td>{{ statusOf(row).label }}</td>
              <td>{{ row.service_count }}</td>
              <td>{{ row.consumable_count }}</td>
              <td>{{ row.tangible_count }}</td>
              <td>{{ money(row.estimated_total) }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <AfePrintSheet v-else :estimate="printEstimateTarget" :printed-at="printEstimateStamp" />
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
              <th>AFE Code</th>
              <th>AFE Name</th>
              <th>Type</th>
              <th>Rig</th>
              <th>Well</th>
              <th>Deleted At</th>
              <th class="text-right">Actions</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="deletedLoading">
              <td colspan="7" class="empty-cell"><i class="pi pi-spin pi-spinner" /> Loading deleted entries…</td>
            </tr>
            <tr v-else-if="filteredTrash.length === 0">
              <td colspan="7" class="empty-cell">No deleted entries.</td>
            </tr>
            <tr v-for="item in filteredTrash" :key="item.id">
              <td class="mono">{{ item.afe_code }}</td>
              <td class="truncate">{{ item.afe_name }}</td>
              <td>{{ item.afe_type }}</td>
              <td class="truncate">{{ item.rig_display || '—' }}</td>
              <td class="truncate">{{ item.well_display || '—' }}</td>
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
      v-model:visible="showImport"
      title="Bulk Import AFEs (CSV / XLSX)"
      endpoint="/afe/afes/import"
      template-endpoint="/afe/afes/import-template"
      template-filename="afe_template.xlsx"
      hint="Headers: rig_code, well_code, afe_code, afe_name, afe_type, remarks. Rigs and wells must already exist, the well must belong to that rig, and afe_code must be unique."
      @committed="loadEstimates"
    />

    <AfeEstimateDialog
      v-model:visible="showEstimate"
      :afe-id="estimateTarget"
      :services="serviceOptions"
      :consumables="consumableOptions"
      :tangibles="tangibleOptions"
      @changed="onEstimateChanged"
      @print="printFromDialog"
    />
  </div>
</template>

<style scoped>
  .afe-page {
    display: grid;
    gap: 14px;
  }

  .afe-toolbar {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
    margin-bottom: 10px;
  }

  .afe-toolbar__filters,
  .afe-toolbar__actions {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 8px;
  }

  .search {
    position: relative;
    min-width: 240px;
  }

  .search i {
    position: absolute;
    top: 50%;
    left: 10px;
    z-index: 2;
    color: var(--app-muted);
    transform: translateY(-50%);
  }

  .search__input {
    width: 100%;
    padding: 6px 10px 6px 30px;
    border: 1px solid var(--app-border);
    border-radius: 8px;
    background: var(--app-surface);
    color: var(--app-ink);
    font-size: .8rem;
  }

  .filter-select {
    padding: 6px 8px;
    border: 1px solid var(--app-border);
    border-radius: 8px;
    background: var(--app-surface);
    color: var(--app-ink);
    font-size: .78rem;
  }

  .count {
    color: var(--app-muted);
    font-size: .74rem;
    font-variant-numeric: tabular-nums;
  }

  .table-scroll {
    overflow: auto;
    max-height: 62vh;
    border: 1px solid var(--app-border);
    border-radius: 10px;
  }

  .afe-table,
  .trash-table {
    width: 100%;
    border-collapse: collapse;
    font-size: .78rem;
  }

  .afe-table thead th,
  .trash-table thead th {
    position: sticky;
    top: 0;
    z-index: 1;
    padding: 6px 8px;
    background: var(--app-bg);
    color: var(--app-ink);
    font-size: .68rem;
    font-weight: 750;
    letter-spacing: .04em;
    text-transform: uppercase;
    text-align: left;
    white-space: nowrap;
    border-bottom: 1px solid var(--app-border);
  }

  .afe-table tbody td,
  .trash-table tbody td {
    padding: 5px 8px;
    border-bottom: 1px solid var(--app-border);
    vertical-align: middle;
  }

  .afe-table tbody tr:hover td,
  .trash-table tbody tr:hover td {
    background: color-mix(in srgb, var(--app-bg) 60%, transparent);
  }

  .truncate {
    max-width: 220px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .mono {
    font-variant-numeric: tabular-nums;
  }

  .muted {
    color: var(--app-muted);
  }

  .text-right {
    text-align: right;
  }

  .empty-cell {
    padding: 22px 10px;
    color: var(--app-muted);
    text-align: center;
  }

  .afe-actions {
    display: flex;
    justify-content: flex-end;
    gap: 4px;
    white-space: nowrap;
  }

  .trash-head {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
    margin-bottom: 10px;
  }

  .trash-title {
    margin: 0;
    font-size: .9rem;
  }

  .trash-head__right {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 10px;
  }

  .trash-subtitle {
    color: var(--app-muted);
    font-size: .72rem;
  }

  .trash-search {
    position: relative;
  }

  .trash-search i {
    position: absolute;
    top: 50%;
    left: 10px;
    color: var(--app-muted);
    transform: translateY(-50%);
  }

  .trash-search__input {
    padding: 6px 10px 6px 30px;
    border: 1px solid var(--app-border);
    border-radius: 8px;
    background: var(--app-surface);
    color: var(--app-ink);
    font-size: .78rem;
  }

  .trash-actions {
    display: flex;
    justify-content: flex-end;
    gap: 4px;
  }
</style>
