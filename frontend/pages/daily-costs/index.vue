<script setup lang="ts">
/**
 * Daily Costs — the page the well team uses every day.
 *
 * The user picks the Rig, then its Well, then the cost date; the sheet for that
 * (rig, well, date) is loaded or started. Two daily cost types are entered
 * here — Services and Consumables — and the Tangibles block is filled in bulk
 * at well completion.
 *
 * Money is never calculated in the browser: the rows are posted (debounced) to
 * `/daily-cost/preview` and the totals shown are the pricing engine's, the same
 * engine that saves them. The charging basis and the unit rates come from the
 * service's configuration on the AFE cost estimation page, with an override
 * unit rate available everywhere a rate is captured.
 *
 * Common template: Import (XLSX/CSV), XLSX/CSV export, Print, edit, soft
 * delete → Deleted Entries tab → permanent delete, every action audit-logged.
 */
import { computed, onMounted, ref, watch } from 'vue'
import Button from 'primevue/button'
import DatePicker from 'primevue/datepicker'
import Message from 'primevue/message'
import Select from 'primevue/select'
import PageHeader from '~/components/design-system/PageHeader.vue'
import ImportDialog from '~/components/master-data/ImportDialog.vue'
import ConsumablesTable from '~/components/daily-cost/ConsumablesTable.vue'
import DailyCostPrintSheet from '~/components/daily-cost/DailyCostPrintSheet.vue'
import DaySummaryBar from '~/components/daily-cost/DaySummaryBar.vue'
import ServiceLinesTable from '~/components/daily-cost/ServiceLinesTable.vue'
import TangiblesTable from '~/components/daily-cost/TangiblesTable.vue'
import {
  decimalOf,
  formatDateLabel,
  formatMoney,
  formatQuantity,
  textOf,
  toDate,
  todayIso,
} from '~/utils/dailyCost'
import {
  CONSUMABLE_LABELS,
  type ConsumableCategory,
  type DailyCostContext,
  type DailyCostDay,
  type DailyCostEntry,
  type DailyCostPreview,
  type DailyCostSaveIn,
  type DrillBitOption,
  type MudChemicalOption,
  type ServiceOption,
  type TangibleOption,
} from '~/types/dailyCost'
import type { GridSelectOption } from '~/types/grid'

definePageMeta({ middleware: 'auth' })

const api = useApi()

const TAB_SERVICES = 0
const TAB_CONSUMABLES = 1
const TAB_TANGIBLES = 2
const TAB_DELETED = 3

const tabs = [
  { label: 'Services', icon: 'pi pi-cog' },
  { label: 'Consumables', icon: 'pi pi-box' },
  { label: 'Tangibles', icon: 'pi pi-inbox' },
  { label: 'Deleted Entries', icon: 'pi pi-trash' },
]

const activeTab = ref(0)
const dirty = ref(false)

function switchTab(index: number): void {
  if (index === activeTab.value) return
  if (!confirmDiscardUnsaved('Switch tab')) return
  activeTab.value = index
  if (index === TAB_DELETED) void loadDeleted()
}

// ---------------------------------------------------------------------------
// Context: rig → well → cost date
// ---------------------------------------------------------------------------

interface RigDropdown { id: number, rig_code: string, rig_name: string, display_name: string }
interface WellRecord {
  id: number
  rig_id: number
  well_code: string
  well_name: string
  status: string
  [key: string]: unknown
}

const rigs = ref<RigDropdown[]>([])
const wells = ref<WellRecord[]>([])
const services = ref<ServiceOption[]>([])
const chemicals = ref<MudChemicalOption[]>([])
const drillBits = ref<DrillBitOption[]>([])
const tangibles = ref<TangibleOption[]>([])
const lookupError = ref<string | null>(null)

const selectedRigId = ref<number | null>(null)
const selectedWellId = ref<number | null>(null)
const rigSelectorValue = ref<number | null>(null)
const wellSelectorValue = ref<number | null>(null)
const costDate = ref<Date>(new Date(`${todayIso()}T00:00:00`))
/** The date the API and the sheet work with (`YYYY-MM-DD`). */
const costDateIso = computed(() => todayIso(costDate.value))
const selectedAfeId = ref<number | null>(null)

const context = ref<DailyCostContext | null>(null)
const contextLoading = ref(false)
const day = ref<DailyCostDay | null>(null)
const dayLoading = ref(false)
const saving = ref(false)
const actionError = ref<string | null>(null)

const filteredWells = computed(() =>
  selectedRigId.value == null
    ? wells.value
    : wells.value.filter(well => well.rig_id === selectedRigId.value),
)
const wellOptions = computed(() =>
  filteredWells.value.map(well => ({ ...well, display: `${well.well_code} - ${well.well_name}` })),
)
const selectedWell = computed<WellRecord | null>(
  () => wells.value.find(well => well.id === selectedWellId.value) ?? null,
)
const selectedRig = computed<RigDropdown | null>(
  () => rigs.value.find(rig => rig.id === selectedRigId.value) ?? null,
)
const hasRigs = computed(() => rigs.value.length > 0)
const hasWellsForRig = computed(() => filteredWells.value.length > 0)

const afeOptions = computed<GridSelectOption[]>(() =>
  (context.value?.afes ?? []).map(afe => ({
    label: `${afe.afe_code} - ${afe.afe_name}${afe.status ? ` (${afe.status})` : ''}`,
    value: afe.id,
  })),
)

const sections = computed(() => context.value?.well_configuration?.sections ?? [])
const subActivities = computed(() => context.value?.sub_activities ?? [])
const rateCard = computed(() => context.value?.rate_card ?? [])
const fuelRate = computed(() => context.value?.fuel_rate ?? '0')
const depthUnit = computed(() => context.value?.depth_unit ?? 'm')

const contextReady = computed(() => selectedWellId.value != null)

async function loadLookups(): Promise<void> {
  lookupError.value = null
  try {
    const [rigList, wellList, serviceList, chemicalList, bitList, tangibleList] = await Promise.all([
      api.get<RigDropdown[]>('/rig-well/rigs/dropdown'),
      api.get<WellRecord[]>('/rig-well/wells'),
      api.get<ServiceOption[]>('/catalogue/services'),
      api.get<MudChemicalOption[]>('/catalogue/mud-chemicals'),
      api.get<DrillBitOption[]>('/catalogue/drill-bits'),
      api.get<TangibleOption[]>('/catalogue/tangibles'),
    ])
    rigs.value = rigList
    wells.value = wellList
    services.value = serviceList
    chemicals.value = chemicalList
    drillBits.value = bitList
    tangibles.value = tangibleList
    if (selectedRigId.value != null && !rigs.value.some(rig => rig.id === selectedRigId.value)) {
      selectedRigId.value = null
      rigSelectorValue.value = null
      selectedWellId.value = null
      wellSelectorValue.value = null
    }
    if (selectedWellId.value != null && !filteredWells.value.some(well => well.id === selectedWellId.value)) {
      selectedWellId.value = null
      wellSelectorValue.value = null
    }
  }
  catch (caught: unknown) {
    lookupError.value = caught instanceof Error ? caught.message : 'Lookups could not be loaded'
  }
}

function confirmDiscardUnsaved(action: string): boolean {
  if (!dirty.value) return true
  return window.confirm(
    `This day has unsaved cost lines. ${action} and discard the unsaved entries?`,
  )
}

function onRigChange(value: number | null): void {
  if (value === selectedRigId.value) return
  if (!confirmDiscardUnsaved('Switch rig')) {
    rigSelectorValue.value = selectedRigId.value
    return
  }
  dirty.value = false
  selectedRigId.value = value
  rigSelectorValue.value = value
  selectedWellId.value = null
  wellSelectorValue.value = null
  context.value = null
  day.value = null
  clearRows()
}

function onWellChange(value: number | null): void {
  if (value === selectedWellId.value) return
  if (!confirmDiscardUnsaved('Switch well')) {
    wellSelectorValue.value = selectedWellId.value
    return
  }
  dirty.value = false
  selectedWellId.value = value
  wellSelectorValue.value = value
  clearRows()
}

function onDateChange(value: Date | Date[] | (Date | null)[] | null | undefined): void {
  const picked = toDate(value)
  if (picked == null) return
  if (todayIso(picked) === costDateIso.value) return
  if (!confirmDiscardUnsaved('Change the cost date')) return
  dirty.value = false
  costDate.value = picked
  clearRows()
}

function shiftDay(delta: number): void {
  if (!confirmDiscardUnsaved('Change the cost date')) return
  dirty.value = false
  const current = new Date(`${costDateIso.value}T00:00:00`)
  current.setDate(current.getDate() + delta)
  costDate.value = current
  clearRows()
}

async function onAfeChange(value: number | null): Promise<void> {
  selectedAfeId.value = value
  await loadContext()
  await loadDay()
}

// ---------------------------------------------------------------------------
// The sheet: context, saved day and the rows being edited
// ---------------------------------------------------------------------------

const serviceRows = ref<Record<string, unknown>[]>([])
const consumableRows = ref<Record<string, unknown>[]>([])
const tangibleRows = ref<Record<string, unknown>[]>([])

const preview = ref<DailyCostPreview | null>(null)
const previewing = ref(false)

const entry = computed<DailyCostEntry | null>(() => day.value?.entry ?? null)
const status = computed(() => entry.value?.status ?? null)
const isLocked = computed(() => status.value === 'submitted')

const serviceAmounts = computed(() => (preview.value?.services ?? []).map(line => line.amount))
const consumableAmounts = computed(() => (preview.value?.consumables ?? []).map(line => line.amount))
const tangibleAmounts = computed(() => (preview.value?.tangibles ?? []).map(line => line.amount))

const serviceWarnings = computed(() => (preview.value?.services ?? []).map(line => line.warnings))
const consumableWarnings = computed(() => (preview.value?.consumables ?? []).map(line => line.warnings))
const tangibleWarnings = computed(() => (preview.value?.tangibles ?? []).map(line => line.warnings))

const summary = computed(() => preview.value?.summary ?? day.value?.summary ?? [])
const grandTotal = computed(() => preview.value?.grand_total ?? day.value?.grand_total ?? '0')
const warnings = computed(() => [
  ...(context.value?.warnings ?? []),
  ...(preview.value?.warnings ?? day.value?.warnings ?? []),
])

function clearRows(): void {
  serviceRows.value = []
  consumableRows.value = []
  tangibleRows.value = []
  preview.value = null
}

async function loadContext(): Promise<void> {
  if (selectedWellId.value == null) {
    context.value = null
    return
  }
  contextLoading.value = true
  actionError.value = null
  try {
    const query = selectedAfeId.value == null ? '' : `&afe_id=${selectedAfeId.value}`
    const loaded = await api.get<DailyCostContext>(
      `/daily-cost/context?well_id=${selectedWellId.value}${query}`,
    )
    context.value = loaded
    selectedAfeId.value = loaded.afe_id
  }
  catch (caught: unknown) {
    actionError.value = caught instanceof Error ? caught.message : 'The well context could not be loaded'
    context.value = null
  }
  finally {
    contextLoading.value = false
  }
}

function serviceToRow(line: DailyCostDay['services'][number]): Record<string, unknown> {
  return {
    _key: `svc-${line.id}`,
    service_id: line.service_id,
    charging_basis: line.charging_basis,
    charge_category: line.charge_category,
    afe_line_id: line.afe_line_id,
    section_id: line.section_id,
    phase_id: line.phase_id,
    sub_activity_id: line.sub_activity_id,
    quantity: formatQuantity(line.quantity),
    quantity_unit: line.quantity_unit,
    captured_rate: line.captured_rate,
    override_rate: line.override_rate == null ? '' : String(line.override_rate),
    remarks: line.remarks ?? '',
  }
}

function consumableToRow(line: DailyCostDay['consumables'][number]): Record<string, unknown> {
  return {
    _key: `cons-${line.id}`,
    category: line.category,
    item_id: line.item_id,
    item_code: line.item_code,
    item_name: line.item_name,
    quantity: formatQuantity(line.quantity),
    uom: line.uom ?? '',
    currency: line.currency ?? '',
    captured_rate: line.captured_rate,
    override_rate: line.override_rate == null ? '' : String(line.override_rate),
    manual_amount: line.manual_amount == null ? '' : String(line.manual_amount),
    section_id: line.section_id,
    phase_id: line.phase_id,
    sub_activity_id: line.sub_activity_id,
    remarks: line.remarks ?? '',
  }
}

function tangibleToRow(line: DailyCostDay['tangibles'][number]): Record<string, unknown> {
  return {
    _key: `tng-${line.id}`,
    tangible_id: line.tangible_id,
    quantity: formatQuantity(line.quantity),
    uom: line.uom ?? '',
    currency: line.currency ?? '',
    captured_rate: line.captured_rate,
    override_rate: line.override_rate == null ? '' : String(line.override_rate),
    remarks: line.remarks ?? '',
  }
}

async function loadDay(): Promise<void> {
  if (!contextReady.value) {
    day.value = null
    clearRows()
    return
  }
  dayLoading.value = true
  actionError.value = null
  try {
    const loaded = await api.get<DailyCostDay | null>(
      `/daily-cost/entries/for-date?well_id=${selectedWellId.value}&cost_date=${costDateIso.value}`,
    )
    day.value = loaded
    if (loaded) {
      serviceRows.value = loaded.services.map(serviceToRow)
      consumableRows.value = loaded.consumables.map(consumableToRow)
      tangibleRows.value = loaded.tangibles.map(tangibleToRow)
      selectedAfeId.value = loaded.entry.afe_id
    }
    else {
      clearRows()
    }
    dirty.value = false
    void requestPreview()
  }
  catch (caught: unknown) {
    actionError.value = caught instanceof Error ? caught.message : 'The day could not be loaded'
  }
  finally {
    dayLoading.value = false
  }
}

// ---------------------------------------------------------------------------
// Live pricing: the server prices the rows on screen (debounced)
// ---------------------------------------------------------------------------

function payload(): Record<string, unknown> {
  const body: DailyCostSaveIn = {
    services: serviceRows.value.map(row => ({
      service_id: row.service_id as number | null,
      charging_basis: (row.charging_basis as never) ?? null,
      charge_category: textOf(row, 'charge_category') || null,
      afe_line_id: (row.afe_line_id as number | null) ?? null,
      section_id: (row.section_id as number | null) ?? null,
      phase_id: (row.phase_id as number | null) ?? null,
      sub_activity_id: (row.sub_activity_id as number | null) ?? null,
      quantity: decimalOf(row, 'quantity') ?? '0',
      quantity_unit: (row.quantity_unit as 'days' | 'hours') ?? 'hours',
      captured_rate: decimalOf(row, 'captured_rate'),
      override_rate: decimalOf(row, 'override_rate'),
      remarks: textOf(row, 'remarks') || null,
    })),
    consumables: consumableRows.value.map(row => ({
      category: (row.category as ConsumableCategory) ?? 'mud_chemical',
      item_id: (row.item_id as number | null) ?? null,
      item_code: textOf(row, 'item_code') || null,
      item_name: textOf(row, 'item_name') || null,
      quantity: decimalOf(row, 'quantity') ?? '0',
      uom: textOf(row, 'uom') || null,
      currency: textOf(row, 'currency') || null,
      captured_rate: decimalOf(row, 'captured_rate'),
      override_rate: decimalOf(row, 'override_rate'),
      manual_amount: decimalOf(row, 'manual_amount'),
      section_id: (row.section_id as number | null) ?? null,
      phase_id: (row.phase_id as number | null) ?? null,
      sub_activity_id: (row.sub_activity_id as number | null) ?? null,
      remarks: textOf(row, 'remarks') || null,
    })),
    tangibles: tangibleRows.value.map(row => ({
      tangible_id: row.tangible_id as number | null,
      quantity: decimalOf(row, 'quantity') ?? '1',
      uom: textOf(row, 'uom') || null,
      currency: textOf(row, 'currency') || null,
      captured_rate: decimalOf(row, 'captured_rate'),
      override_rate: decimalOf(row, 'override_rate'),
      remarks: textOf(row, 'remarks') || null,
    })),
    remarks: day.value?.entry.remarks ?? null,
  }
  return { ...body }
}

let previewTimer: ReturnType<typeof setTimeout> | null = null
let previewController: AbortController | null = null

/** Queue a pricing request; a stale in-flight one is cancelled. */
function requestPreview(): void {
  if (previewTimer) clearTimeout(previewTimer)
  previewTimer = setTimeout(() => { void runPreview() }, 600)
}

async function runPreview(): Promise<void> {
  if (!contextReady.value) return
  if (
    serviceRows.value.length === 0
    && consumableRows.value.length === 0
    && tangibleRows.value.length === 0
  ) {
    preview.value = null
    return
  }
  previewController?.abort()
  previewController = new AbortController()
  previewing.value = true
  try {
    preview.value = await api.post<DailyCostPreview>('/daily-cost/preview', {
      well_id: selectedWellId.value,
      afe_id: selectedAfeId.value,
      ...payload(),
    })
  }
  catch (caught: unknown) {
    // An aborted superseded request is normal; anything else is worth showing.
    if (caught instanceof Error && caught.name !== 'AbortError') {
      actionError.value = caught.message
    }
  }
  finally {
    previewing.value = false
  }
}

function onRowsChanged(): void {
  dirty.value = true
  requestPreview()
}

// ---------------------------------------------------------------------------
// Save / submit / reopen / delete
// ---------------------------------------------------------------------------

async function ensureEntry(): Promise<DailyCostEntry | null> {
  if (entry.value) return entry.value
  if (selectedWellId.value == null) return null
  const created = await api.post<DailyCostDay>('/daily-cost/entries', {
    well_id: selectedWellId.value,
    cost_date: costDateIso.value,
    afe_id: selectedAfeId.value,
  })
  day.value = created
  return created.entry
}

async function saveDay(): Promise<DailyCostDay | null> {
  if (!contextReady.value) return null
  saving.value = true
  actionError.value = null
  try {
    const target = await ensureEntry()
    if (!target) return null
    const saved = await api.put<DailyCostDay>(`/daily-cost/entries/${target.id}`, payload())
    day.value = saved
    dirty.value = false
    await loadDeleted()
    return saved
  }
  catch (caught: unknown) {
    actionError.value = caught instanceof Error ? caught.message : 'The day could not be saved'
    return null
  }
  finally {
    saving.value = false
  }
}

async function submitDay(): Promise<void> {
  const saved = await saveDay()
  if (!saved) return
  if (
    saved.services.length === 0
    && saved.consumables.length === 0
    && saved.tangibles.length === 0
  ) {
    actionError.value = 'Enter at least one service, consumable or tangible before submitting the day.'
    return
  }
  saving.value = true
  try {
    await api.post<DailyCostEntry>(`/daily-cost/entries/${saved.entry.id}/status`, {
      action: 'submit',
    })
    await loadDay()
    await loadDeleted()
  }
  catch (caught: unknown) {
    actionError.value = caught instanceof Error ? caught.message : 'The day could not be submitted'
  }
  finally {
    saving.value = false
  }
}

async function reopenDay(): Promise<void> {
  if (!entry.value) return
  saving.value = true
  actionError.value = null
  try {
    await api.post<DailyCostEntry>(`/daily-cost/entries/${entry.value.id}/status`, {
      action: 'reopen',
    })
    await loadDay()
  }
  catch (caught: unknown) {
    actionError.value = caught instanceof Error ? caught.message : 'The day could not be reopened'
  }
  finally {
    saving.value = false
  }
}

// ---------------------------------------------------------------------------
// Import / export / print
// ---------------------------------------------------------------------------

const showImport = ref(false)
const importEndpoint = computed(
  () => `/daily-cost/entries/import?well_id=${selectedWellId.value ?? ''}&cost_date=${costDateIso.value}`,
)

function exportEntries(format: 'xlsx' | 'csv'): void {
  if (selectedWellId.value == null) return
  api
    .download(`/daily-cost/entries/export?format=${format}&well_id=${selectedWellId.value}`)
    .then((blob) => {
      triggerDownload(blob, `daily_costs_${selectedWell.value?.well_code ?? 'export'}.${format}`)
    })
    .catch((error: unknown) => {
      actionError.value = error instanceof Error ? error.message : 'Export failed'
    })
}

function exportDay(format: 'xlsx' | 'csv'): void {
  if (!entry.value) return
  api
    .download(`/daily-cost/entries/${entry.value.id}/export?format=${format}`)
    .then((blob) => {
      triggerDownload(blob, `${entry.value?.daily_cost_code ?? 'daily_cost'}.${format}`)
    })
    .catch((error: unknown) => {
      actionError.value = error instanceof Error ? error.message : 'Export failed'
    })
}

function triggerDownload(blob: Blob, filename: string): void {
  const url = window.URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  anchor.click()
  window.URL.revokeObjectURL(url)
}

function printPage(): void {
  window.print()
}

// ---------------------------------------------------------------------------
// Deleted Entries tab
// ---------------------------------------------------------------------------

const deletedEntries = ref<DailyCostEntry[]>([])
const deletedLoading = ref(false)

async function loadDeleted(): Promise<void> {
  if (selectedWellId.value == null) {
    deletedEntries.value = []
    return
  }
  deletedLoading.value = true
  try {
    deletedEntries.value = await api.get<DailyCostEntry[]>(
      `/daily-cost/entries/deleted?well_id=${selectedWellId.value}`,
    )
  }
  catch (caught: unknown) {
    actionError.value = caught instanceof Error ? caught.message : 'Deleted entries could not load'
  }
  finally {
    deletedLoading.value = false
  }
}

async function restoreEntry(item: DailyCostEntry): Promise<void> {
  try {
    await api.post(`/daily-cost/entries/${item.id}/restore`, {})
    await loadDeleted()
    if (item.cost_date === costDateIso.value) await loadDay()
  }
  catch (caught: unknown) {
    actionError.value = caught instanceof Error ? caught.message : 'Restore failed'
  }
}

async function permanentDelete(item: DailyCostEntry): Promise<void> {
  if (!window.confirm(`Permanently delete daily cost ${item.daily_cost_code}? This cannot be undone.`)) {
    return
  }
  try {
    await api.delete(`/daily-cost/entries/${item.id}/permanent`)
    await loadDeleted()
  }
  catch (caught: unknown) {
    actionError.value = caught instanceof Error ? caught.message : 'Permanent delete failed'
  }
}

async function deleteCurrentDay(): Promise<void> {
  if (!entry.value) return
  if (!window.confirm(`Delete the daily cost for ${formatDateLabel(entry.value.cost_date)}? It moves to Deleted Entries.`)) {
    return
  }
  try {
    await api.delete(`/daily-cost/entries/${entry.value.id}`)
    await loadDay()
    await loadDeleted()
  }
  catch (caught: unknown) {
    actionError.value = caught instanceof Error ? caught.message : 'Delete failed'
  }
}

// ---------------------------------------------------------------------------
// Wiring
// ---------------------------------------------------------------------------

const printDay = computed<DailyCostDay | null>(() => day.value)
const printSubtitle = computed(() => {
  if (!selectedRig.value || !selectedWell.value) return ''
  return (
    `Rig: ${selectedRig.value.display_name} · Well: ${selectedWell.value.well_code} - `
    + `${selectedWell.value.well_name} · Cost date: ${formatDateLabel(costDateIso.value)}`
  )
})

onMounted(() => {
  void loadLookups()
})

watch([selectedWellId, costDateIso], async ([wellId]) => {
  if (wellId == null) {
    context.value = null
    day.value = null
    clearRows()
    return
  }
  await loadContext()
  await loadDay()
  if (activeTab.value === TAB_DELETED) await loadDeleted()
})

watch(activeTab, (tab) => {
  if (tab === TAB_DELETED) void loadDeleted()
})
</script>

<template>
  <div class="daily-page">
    <PageHeader
      class="no-print"
      title="Daily Costs"
      description="Record the cost incurred on a rig's well for one date. Services and consumables are entered daily and priced by the cost engine — the charging basis and unit rates come from the service's configuration on the AFE cost estimation page, and tangibles are entered in bulk at well completion from the Master Data list. Save the day as a draft, then submit it to feed the daily costs incurred report."
    />

    <!-- Rig → well → cost date -->
    <section class="context-card no-print">
      <div class="context-fields">
        <label class="context-field">
          <span class="context-label">Rig</span>
          <Select
            :model-value="rigSelectorValue"
            :options="rigs"
            option-label="display_name"
            option-value="id"
            placeholder="Select rig"
            filter
            size="small"
            class="context-select"
            :disabled="!hasRigs"
            @update:model-value="onRigChange"
          />
        </label>
        <label class="context-field">
          <span class="context-label">Well</span>
          <Select
            :model-value="wellSelectorValue"
            :options="wellOptions"
            option-label="display"
            option-value="id"
            placeholder="Select well"
            filter
            size="small"
            class="context-select"
            :disabled="selectedRigId == null || !hasWellsForRig"
            @update:model-value="onWellChange"
          />
        </label>
        <label class="context-field">
          <span class="context-label">Cost Date</span>
          <span class="date-row">
            <Button
              icon="pi pi-chevron-left"
              size="small"
              severity="secondary"
              text
              aria-label="Previous day"
              :disabled="selectedWellId == null"
              @click="shiftDay(-1)"
            />
            <DatePicker
              :model-value="costDate"
              date-format="dd-mm-yy"
              :show-icon="true"
              size="small"
              class="context-date"
              :disabled="selectedWellId == null"
              @update:model-value="onDateChange"
            />
            <Button
              icon="pi pi-chevron-right"
              size="small"
              severity="secondary"
              text
              aria-label="Next day"
              :disabled="selectedWellId == null"
              @click="shiftDay(1)"
            />
          </span>
        </label>
        <label class="context-field">
          <span class="context-label">AFE (rate card)</span>
          <Select
            :model-value="selectedAfeId"
            :options="afeOptions"
            option-label="label"
            option-value="value"
            placeholder="Well's AFE"
            show-clear
            size="small"
            class="context-select"
            :disabled="selectedWellId == null || afeOptions.length === 0"
            @update:model-value="onAfeChange"
          />
        </label>
        <div v-if="selectedRig && selectedWell && context" class="context-summary">
          <i class="pi pi-check-circle" />
          <span>
            Daily cost for
            <strong>{{ context.well_code }} - {{ context.well_name }}</strong>
            under <strong>{{ selectedRig.display_name }}</strong> on
            <strong>{{ formatDateLabel(costDateIso) }}</strong>
            <template v-if="context.well_configuration">
              · total depth {{ formatQuantity(context.well_configuration.total_depth) }}
              {{ context.depth_unit }} · planned
              {{ formatQuantity(context.well_configuration.total_days) }} days
            </template>
          </span>
        </div>
      </div>

      <Message v-if="!hasRigs" severity="warn" :closable="false" class="context-message">
        No rigs yet — create a rig in Rig &amp; Well Management first, then return here.
      </Message>
      <Message
        v-else-if="selectedRigId != null && !hasWellsForRig"
        severity="warn"
        :closable="false"
        class="context-message"
      >
        No wells under this rig yet — create the wells in Rig &amp; Well Management first.
      </Message>
      <Message v-else-if="selectedWellId == null" severity="info" :closable="false" class="context-message">
        Select the rig, its well and the cost date to open that day's cost sheet.
      </Message>
    </section>

    <Message v-if="lookupError" severity="warn" :closable="false" class="no-print">{{ lookupError }}</Message>
    <Message v-if="actionError" severity="error" :closable="false" class="no-print" @close="actionError = null">
      {{ actionError }}
    </Message>

    <template v-if="contextReady && context">
      <div class="toolbar no-print">
        <div class="toolbar__tabs">
          <button
            v-for="(tab, index) in tabs"
            :key="tab.label"
            class="toolbar__tab"
            :class="{ 'toolbar__tab--active': activeTab === index, 'toolbar__tab--danger': index === TAB_DELETED }"
            @click="switchTab(index)"
          >
            <i :class="tab.icon" />
            {{ tab.label }}
            <span v-if="index === TAB_SERVICES && serviceRows.length" class="toolbar__count">{{ serviceRows.length }}</span>
            <span v-if="index === TAB_CONSUMABLES && consumableRows.length" class="toolbar__count">{{ consumableRows.length }}</span>
            <span v-if="index === TAB_TANGIBLES && tangibleRows.length" class="toolbar__count">{{ tangibleRows.length }}</span>
          </button>
        </div>
        <div class="toolbar__actions">
          <span v-if="previewing" class="toolbar__busy"><i class="pi pi-spin pi-spinner" /> Pricing…</span>
          <Button
            v-if="entry"
            label="Delete day"
            icon="pi pi-trash"
            size="small"
            severity="danger"
            text
            :disabled="isLocked"
            @click="deleteCurrentDay"
          />
          <Button
            v-if="entry"
            label="This day"
            icon="pi pi-file"
            size="small"
            severity="secondary"
            outlined
            @click="exportDay('csv')"
          />
          <Button label="Import" icon="pi pi-upload" size="small" severity="secondary" outlined @click="showImport = true" />
          <Button label="XLSX" icon="pi pi-file-excel" size="small" severity="success" outlined @click="exportEntries('xlsx')" />
          <Button label="CSV" icon="pi pi-file" size="small" severity="secondary" outlined @click="exportEntries('csv')" />
          <Button label="Print" icon="pi pi-print" size="small" severity="secondary" text @click="printPage" />
        </div>
      </div>

      <DaySummaryBar
        class="no-print"
        :summary="summary"
        :grand-total="grandTotal"
        :status="status"
        :warnings="warnings"
        :reconciliation-status="entry?.reconciliation_status ?? 'pending'"
        :afe-estimated="context.afe_estimated_total"
        :actual-to-date="null"
        :saving="saving"
        :dirty="dirty"
        :disabled="isLocked"
        @save="saveDay"
        @submit="submitDay"
        @reopen="reopenDay"
      />

      <Message v-if="isLocked" severity="success" :closable="false" class="no-print">
        This day is submitted — it is counted in the daily costs incurred report. Reopen it as a
        draft to make a correction.
      </Message>

      <section v-if="activeTab === TAB_SERVICES" class="block-card">
        <ServiceLinesTable
          v-model:rows="serviceRows"
          :rate-card="rateCard"
          :services="services"
          :sections="sections"
          :sub-activities="subActivities"
          :amounts="serviceAmounts"
          :line-warnings="serviceWarnings"
          :disabled="isLocked"
          @change="onRowsChanged"
        />
      </section>

      <section v-else-if="activeTab === TAB_CONSUMABLES" class="block-card">
        <ConsumablesTable
          v-model:rows="consumableRows"
          :chemicals="chemicals"
          :drill-bits="drillBits"
          :sections="sections"
          :sub-activities="subActivities"
          :fuel-rate="fuelRate"
          :amounts="consumableAmounts"
          :line-warnings="consumableWarnings"
          :disabled="isLocked"
          @change="onRowsChanged"
        />
      </section>

      <section v-else-if="activeTab === TAB_TANGIBLES" class="block-card">
        <TangiblesTable
          v-model:rows="tangibleRows"
          :tangibles="tangibles"
          :amounts="tangibleAmounts"
          :line-warnings="tangibleWarnings"
          :disabled="isLocked"
          @change="onRowsChanged"
        />
      </section>

      <section v-else-if="activeTab === TAB_DELETED" class="block-card">
        <div class="trash-head no-print">
          <h3 class="trash-title">
            Deleted Entries (Trash) — {{ deletedEntries.length }} day(s)
          </h3>
          <span class="trash-subtitle">Restore or permanently delete. All actions are audit-logged.</span>
        </div>
        <div class="table-scroll">
          <table class="trash-table">
            <thead>
              <tr>
                <th>Daily Cost Code</th>
                <th>Cost Date</th>
                <th>Status</th>
                <th class="num">Services</th>
                <th class="num">Consumables</th>
                <th class="num">Tangibles</th>
                <th class="num">Total</th>
                <th>Deleted At</th>
                <th class="text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              <tr v-if="deletedLoading">
                <td colspan="9" class="empty-cell"><i class="pi pi-spin pi-spinner" /> Loading deleted entries…</td>
              </tr>
              <tr v-else-if="deletedEntries.length === 0">
                <td colspan="9" class="empty-cell">No deleted daily costs for this well.</td>
              </tr>
              <tr v-for="item in deletedEntries" :key="item.id">
                <td class="mono">{{ item.daily_cost_code }}</td>
                <td>{{ formatDateLabel(item.cost_date) }}</td>
                <td>{{ item.status === 'submitted' ? 'Submitted' : 'Draft' }}</td>
                <td class="num">{{ formatMoney(item.service_total) }}</td>
                <td class="num">{{ formatMoney(item.consumable_total) }}</td>
                <td class="num">{{ formatMoney(item.tangible_total) }}</td>
                <td class="num mono"><strong>{{ formatMoney(item.total_cost) }}</strong></td>
                <td class="muted">{{ item.deleted_at ? new Date(item.deleted_at).toLocaleString() : '—' }}</td>
                <td class="text-right">
                  <Button label="Restore" size="small" severity="success" outlined @click="restoreEntry(item)" />
                  <Button label="Delete" size="small" severity="danger" outlined class="ml-1" @click="permanentDelete(item)" />
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <p class="print-subtitle no-print">{{ printSubtitle }}</p>
    </template>

    <ImportDialog
      v-if="selectedWellId != null"
      v-model:visible="showImport"
      title="Bulk Import Daily Costs (CSV / XLSX)"
      :endpoint="importEndpoint"
      template-endpoint="/daily-cost/entries/import-template"
      template-filename="daily_costs_template.xlsx"
      hint="Headers: cost_date, rig_code, well_code, cost_group (Service / Consumable / Tangible), category, item_code, section_code, phase_code, sub_activity_code, quantity, quantity_unit, override_rate, remarks. Dates accept dd/mm/yyyy, dd-mm-yyyy, yyyy-mm-dd and similar; codes are matched by code or name; each row is added to that day's sheet and priced by the cost engine. The selected well and date pre-fill blank columns."
      @committed="loadDay()"
    />

    <DailyCostPrintSheet
      v-if="printDay"
      :day="printDay"
      :rig-display="selectedRig?.display_name ?? ''"
      :well-display="selectedWell ? `${selectedWell.well_code} - ${selectedWell.well_name}` : ''"
      :printed-at="new Date().toLocaleString()"
    />
    <p v-else class="print-only print-empty">
      Nothing to print — open a day with cost lines first. Depth unit: {{ depthUnit }}.
      Consumable categories: {{ Object.values(CONSUMABLE_LABELS).join(', ') }}.
    </p>
  </div>
</template>

<style scoped>
  .daily-page {
    display: grid;
    gap: 12px;
  }

  .context-card,
  .block-card {
    background: var(--app-surface);
    border: 1px solid var(--app-border);
    border-radius: 12px;
    box-shadow: var(--app-shadow);
    padding: 12px 14px;
  }

  .context-fields {
    display: flex;
    flex-wrap: wrap;
    gap: 12px 18px;
    align-items: flex-end;
  }

  .context-field {
    display: grid;
    gap: 3px;
    min-width: 190px;
  }

  .context-label {
    font-size: 0.68rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--app-text-muted, #6b7480);
    font-weight: 600;
  }

  .context-select {
    width: 100%;
  }

  .date-row {
    display: flex;
    align-items: center;
    gap: 2px;
  }

  .context-date {
    width: 150px;
  }

  .context-summary {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 0.76rem;
    color: var(--app-text, #1c2430);
    padding-bottom: 4px;
  }

  .context-message {
    margin-top: 10px;
  }

  .toolbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    flex-wrap: wrap;
  }

  .toolbar__tabs {
    display: flex;
    gap: 4px;
    flex-wrap: wrap;
  }

  .toolbar__tab {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    border: 1px solid var(--app-border, #e3e7ee);
    background: var(--app-surface, #fff);
    border-radius: 999px;
    padding: 5px 12px;
    font-size: 0.78rem;
    cursor: pointer;
    color: var(--app-text-muted, #4b5563);
  }

  .toolbar__tab--active {
    background: var(--app-primary, #1d4ed8);
    border-color: var(--app-primary, #1d4ed8);
    color: #fff;
  }

  .toolbar__tab--danger.toolbar__tab--active {
    background: #b91c1c;
    border-color: #b91c1c;
  }

  .toolbar__count {
    background: rgb(255 255 255 / 25%);
    border-radius: 999px;
    padding: 0 6px;
    font-size: 0.68rem;
  }

  .toolbar__actions {
    display: flex;
    align-items: center;
    gap: 6px;
    flex-wrap: wrap;
  }

  .toolbar__busy {
    font-size: 0.72rem;
    color: var(--app-text-muted, #6b7480);
    display: inline-flex;
    align-items: center;
    gap: 5px;
  }

  .trash-head {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: 12px;
    flex-wrap: wrap;
    margin-bottom: 8px;
  }

  .trash-title {
    margin: 0;
    font-size: 0.9rem;
    font-weight: 650;
  }

  .trash-subtitle {
    font-size: 0.72rem;
    color: var(--app-text-muted, #6b7480);
  }

  .table-scroll {
    overflow-x: auto;
  }

  .trash-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.76rem;
  }

  .trash-table th,
  .trash-table td {
    border-bottom: 1px solid var(--app-border-soft, #eef1f6);
    padding: 5px 8px;
    text-align: left;
    white-space: nowrap;
  }

  .trash-table th {
    background: var(--app-surface-muted, #f7f9fc);
    color: var(--app-text-muted, #5b6472);
    font-weight: 600;
  }

  .num {
    text-align: right;
    font-variant-numeric: tabular-nums;
  }

  .text-right {
    text-align: right;
  }

  .mono {
    font-family: var(--app-font-mono, ui-monospace, monospace);
  }

  .muted {
    color: var(--app-text-muted, #8a929e);
  }

  .empty-cell {
    text-align: center;
    color: var(--app-text-muted, #7c8593);
    padding: 16px !important;
  }

  .ml-1 {
    margin-left: 4px;
  }

  .print-subtitle {
    margin: 0;
    font-size: 0.7rem;
    color: var(--app-text-muted, #8a929e);
  }

  .print-only {
    display: none;
  }

  @media print {
    .print-only {
      display: block;
      font-size: 9px;
    }

    .print-empty {
      color: #555;
    }
  }
</style>
