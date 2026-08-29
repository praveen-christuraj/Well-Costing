<script setup lang="ts">
/**
 * AFE Cost Estimation — configure the Services, Consumables and Tangibles of one
 * AFE and move it through draft → submitted → approved.
 *
 * The three cost groups are separate sections, and everything the user picks
 * comes from the pages that own the data: services and tangibles from Master
 * Data, consumables from the Mud Chemicals / Drill Bits lists, and every
 * section/phase from the well's own configuration. Money is never calculated
 * here — the totals come from the backend engine (live through the debounced
 * preview, permanently on Save).
 */
import { computed, nextTick, ref, watch } from 'vue'
import Button from 'primevue/button'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Dialog from 'primevue/dialog'
import InputText from 'primevue/inputtext'
import Message from 'primevue/message'
import Select from 'primevue/select'
import Tag from 'primevue/tag'
import {
  CHARGE_CATEGORIES,
  CHARGING_BASES,
  DAY_BASED_CATEGORIES,
  ONE_TIME_CATEGORIES,
  type AfeEstimate,
  type ChargingBasis,
  type ConsumableOption,
  type ConsumableLineRow,
  type EstimatePayload,
  type LineEstimate,
  type QuantityUnit,
  type ServiceLineRow,
  type ServiceOption,
  type TangibleLineRow,
  type TangibleOption,
} from '~/types/afe'

const props = defineProps<{
  visible: boolean
  afeId: number | null
  services: ServiceOption[]
  consumables: ConsumableOption[]
  tangibles: TangibleOption[]
}>()

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void
  (e: 'changed'): void
  (e: 'print', estimate: AfeEstimate): void
}>()

const api = useApi()

const SUB_SERVICES = 0
const SUB_CONSUMABLES = 1
const SUB_TANGIBLES = 2
const SUB_SUMMARY = 3

const subTabs = [
  { label: 'Services', icon: 'pi pi-cog' },
  { label: 'Consumables', icon: 'pi pi-flask' },
  { label: 'Tangibles', icon: 'pi pi-box' },
  { label: 'Summary', icon: 'pi pi-chart-bar' },
]

const visibleModel = computed({
  get: () => props.visible,
  set: value => emit('update:visible', value),
})

const activeSub = ref(SUB_SERVICES)
const loading = ref(false)
const saving = ref(false)
const error = ref<string | null>(null)
const notice = ref<string | null>(null)
const estimate = ref<AfeEstimate | null>(null)
const expandedRows = ref<Record<string, boolean>>({})
const printedAt = ref('')

let previewTimer: ReturnType<typeof setTimeout> | undefined
let uid = 0
function nextKey(): string {
  uid += 1
  return `k${uid}`
}

// ---------------------------------------------------------------------------
// Local row models
// ---------------------------------------------------------------------------

interface ChargeRow {
  category: string
  quantity: string
  quantity_unit: QuantityUnit
}

interface SectionRateRow {
  section_id: number | null
  phase_id: number | null
  amount: string
}

interface LocalService {
  _key: string
  service_id: number
  service_code: string
  service_name: string
  provider_type: string
  charging_basis: ChargingBasis
  section_id: number | null
  phase_id: number | null
  per_service_amount: string
  effective_date: string | null
  remarks: string
  rates: Record<string, string>
  charge_lines: ChargeRow[]
  section_rates: SectionRateRow[]
}

interface LocalConsumable {
  _key: string
  item_kind: 'mud_chemical' | 'drill_bit'
  item_id: number
  item_code: string
  item_name: string
  quantity: string
  captured_rate: string
  override_rate: string
  uom: string
  currency: string
  section_id: number | null
  phase_id: number | null
  remarks: string
}

interface LocalTangible {
  _key: string
  tangible_id: number
  tangible_code: string
  tangible_name: string
  quantity: string
  captured_rate: string
  override_rate: string
  uom: string
  currency: string
  remarks: string
}

const serviceRows = ref<LocalService[]>([])
const consumableRows = ref<LocalConsumable[]>([])
const tangibleRows = ref<LocalTangible[]>([])

const preview = ref<{
  services: LineEstimate[]
  consumables: LineEstimate[]
  tangibles: LineEstimate[]
  summary: { group: string, amount: string | number, line_count: number }[]
  by_section: { section_id: number | null, section_label: string, planned_days: string | number, amount: string | number }[]
  grand_total: string | number
  warnings: string[]
} | null>(null)

const isDraft = computed(() => (estimate.value?.afe.status ?? 'draft') === 'draft')
const statusLabel = computed(() => {
  const map: Record<string, string> = { draft: 'Draft', submitted: 'Submitted', approved: 'Approved' }
  return map[estimate.value?.afe.status ?? 'draft'] ?? 'Draft'
})
const statusSeverity = computed(() => {
  const status = estimate.value?.afe.status ?? 'draft'
  if (status === 'approved') return 'success'
  return status === 'submitted' ? 'warn' : 'secondary'
})

function money(value: string | number | null | undefined): string {
  if (value == null || value === '') return '0.00'
  const numeric = Number(value)
  return Number.isFinite(numeric)
    ? numeric.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
    : String(value)
}

function num(value: string | number | null): string {
  if (value == null || value === '') return '—'
  return String(Number(value))
}

// ---------------------------------------------------------------------------
// Well configuration drives every section / phase dropdown
// ---------------------------------------------------------------------------

const sectionOptions = computed(() =>
  (estimate.value?.well_configuration?.sections ?? []).map(section => ({
    label: `${section.section_code ?? ''}${section.section_name ? ` — ${section.section_name}` : ''}`,
    value: section.section_id,
  })),
)

function phaseOptionsFor(sectionId: number | null): { label: string, value: number }[] {
  const sections = estimate.value?.well_configuration?.sections ?? []
  const source = sectionId == null ? sections : sections.filter(section => section.section_id === sectionId)
  const seen = new Map<number, string>()
  for (const section of source) {
    for (const phase of section.phases) {
      if (!seen.has(phase.phase_id)) {
        seen.set(phase.phase_id, `${phase.phase_code ?? ''}${phase.phase_name ? ` — ${phase.phase_name}` : ''}`)
      }
    }
  }
  return [...seen.entries()].map(([value, label]) => ({ label, value }))
}

const hasConfiguration = computed(() => (estimate.value?.well_configuration?.sections.length ?? 0) > 0)

// ---------------------------------------------------------------------------
// Loading
// ---------------------------------------------------------------------------

function toLocalService(line: ServiceLineRow): LocalService {
  const rates: Record<string, string> = {}
  for (const category of CHARGE_CATEGORIES) rates[category] = ''
  for (const rate of line.rates) rates[rate.category] = String(rate.unit_rate)
  return {
    _key: nextKey(),
    service_id: line.service_id,
    service_code: line.service_code ?? '',
    service_name: line.service_name ?? '',
    provider_type: line.provider_type ?? '',
    charging_basis: line.charging_basis,
    section_id: line.section_id,
    phase_id: line.phase_id,
    per_service_amount: String(line.per_service_amount ?? '0'),
    effective_date: line.effective_date,
    remarks: line.remarks ?? '',
    rates,
    charge_lines: line.charge_lines.map(row => ({
      category: row.category,
      quantity: String(row.quantity),
      quantity_unit: row.quantity_unit,
    })),
    section_rates: line.section_rates.map(row => ({
      section_id: row.section_id,
      phase_id: row.phase_id,
      amount: String(row.amount),
    })),
  }
}

function toLocalConsumable(line: ConsumableLineRow): LocalConsumable {
  return {
    _key: nextKey(),
    item_kind: line.item_kind,
    item_id: line.item_id,
    item_code: line.item_code,
    item_name: line.item_name,
    quantity: String(line.quantity),
    captured_rate: String(line.captured_rate),
    override_rate: line.override_rate == null ? '' : String(line.override_rate),
    uom: line.uom ?? '',
    currency: line.currency ?? '',
    section_id: line.section_id,
    phase_id: line.phase_id,
    remarks: line.remarks ?? '',
  }
}

function toLocalTangible(line: TangibleLineRow): LocalTangible {
  return {
    _key: nextKey(),
    tangible_id: line.tangible_id,
    tangible_code: line.tangible_code ?? '',
    tangible_name: line.tangible_name ?? '',
    quantity: String(line.quantity),
    captured_rate: String(line.captured_rate),
    override_rate: line.override_rate == null ? '' : String(line.override_rate),
    uom: line.uom ?? '',
    currency: line.currency ?? '',
    remarks: line.remarks ?? '',
  }
}

async function load(): Promise<void> {
  if (props.afeId == null) return
  loading.value = true
  error.value = null
  notice.value = null
  try {
    const data = await api.get<AfeEstimate>(`/afe/estimates/${props.afeId}`)
    estimate.value = data
    serviceRows.value = data.services.map(toLocalService)
    consumableRows.value = data.consumables.map(toLocalConsumable)
    tangibleRows.value = data.tangibles.map(toLocalTangible)
    preview.value = {
      services: data.services.map(line => line.estimate),
      consumables: data.consumables.map(line => line.estimate),
      tangibles: data.tangibles.map(line => line.estimate),
      summary: data.summary,
      by_section: data.by_section,
      grand_total: data.grand_total,
      warnings: data.warnings,
    }
    expandedRows.value = {}
  }
  catch (caught: unknown) {
    error.value = caught instanceof Error ? caught.message : 'The cost estimate could not be loaded'
  }
  finally {
    loading.value = false
  }
}

watch(
  () => [props.visible, props.afeId] as const,
  ([open]) => {
    if (open) {
      activeSub.value = SUB_SERVICES
      void load()
    }
  },
  // The dialog can be mounted already open; do not wait for a change to load.
  { immediate: true },
)

// ---------------------------------------------------------------------------
// Payload + live preview
// ---------------------------------------------------------------------------

function buildPayload(): EstimatePayload {
  return {
    services: serviceRows.value.map(row => ({
      service_id: row.service_id,
      charging_basis: row.charging_basis,
      section_id: row.section_id,
      phase_id: row.phase_id,
      per_service_amount: row.per_service_amount || '0',
      effective_date: row.effective_date || null,
      remarks: row.remarks || null,
      rates: CHARGE_CATEGORIES
        .filter(category => String(row.rates[category] ?? '').trim() !== '')
        .map(category => ({ category, unit_rate: row.rates[category] ?? '0' })),
      charge_lines: row.charge_lines
        .filter(line => String(line.quantity).trim() !== '' && Number(line.quantity) > 0)
        .map(line => ({
          category: line.category,
          quantity: line.quantity,
          quantity_unit: line.quantity_unit,
        })),
      section_rates: row.section_rates
        .filter(entry => entry.section_id != null)
        .map(entry => ({
          section_id: entry.section_id as number,
          phase_id: entry.phase_id,
          amount: entry.amount || '0',
        })),
    })),
    consumables: consumableRows.value.map(row => ({
      item_kind: row.item_kind,
      item_id: row.item_id,
      quantity: row.quantity || '0',
      captured_rate: row.captured_rate || '0',
      override_rate: row.override_rate.trim() === '' ? null : row.override_rate,
      uom: row.uom || null,
      currency: row.currency || null,
      section_id: row.section_id,
      phase_id: row.phase_id,
      remarks: row.remarks || null,
    })),
    tangibles: tangibleRows.value.map(row => ({
      tangible_id: row.tangible_id,
      quantity: row.quantity || '0',
      captured_rate: row.captured_rate || '0',
      override_rate: row.override_rate.trim() === '' ? null : row.override_rate,
      uom: row.uom || null,
      currency: row.currency || null,
      remarks: row.remarks || null,
    })),
  }
}

async function refreshPreview(): Promise<void> {
  if (props.afeId == null || !isDraft.value) return
  try {
    preview.value = await api.post(`/afe/estimates/${props.afeId}/preview`, buildPayload())
  }
  catch (caught: unknown) {
    // A preview failure is not fatal: the message explains what to fix.
    error.value = caught instanceof Error ? caught.message : null
  }
}

function schedulePreview(): void {
  if (!isDraft.value) return
  if (previewTimer) clearTimeout(previewTimer)
  previewTimer = setTimeout(() => { void refreshPreview() }, 350)
}

watch([serviceRows, consumableRows, tangibleRows], schedulePreview, { deep: true })

function lineEstimate(group: 'services' | 'consumables' | 'tangibles', index: number): LineEstimate | null {
  return preview.value?.[group][index] ?? null
}

function lineAmount(group: 'services' | 'consumables' | 'tangibles', index: number): string {
  return money(lineEstimate(group, index)?.amount ?? 0)
}

// ---------------------------------------------------------------------------
// Pickers
// ---------------------------------------------------------------------------

const picker = ref<null | 'service' | 'consumable' | 'tangible'>(null)
const pickerSearch = ref('')
const pickerSelection = ref<number[]>([])

const pickerRows = computed(() => {
  const query = pickerSearch.value.trim().toLowerCase()
  const matches = (text: string): boolean => !query || text.toLowerCase().includes(query)
  if (picker.value === 'service') {
    return props.services
      .filter(service => matches(`${service.service_code} ${service.service_name} ${service.provider_type}`))
      .map(service => ({
        id: service.id,
        code: service.service_code,
        name: service.service_name,
        detail: service.provider_type,
        extra: '',
      }))
  }
  return props.tangibles
    .filter(item => matches(`${item.code} ${item.name} ${item.detail}`))
    .map(item => ({ id: item.id, code: item.code, name: item.name, detail: item.detail, extra: `Rate ${money(item.rate)}` }))
})

const pickerVisible = computed({
  get: () => picker.value !== null,
  set: (value: boolean) => {
    if (!value) picker.value = null
  },
})

const pickerTitle = computed(() => {
  if (picker.value === 'service') return 'Add services'
  return 'Add tangibles'
})

function openPicker(kind: 'service' | 'tangible'): void {
  picker.value = kind
  pickerSearch.value = ''
  pickerSelection.value = []
}

function addPicked(): void {
  if (picker.value === 'service') {
    for (const id of pickerSelection.value) {
      const service = props.services.find(item => item.id === id)
      if (!service) continue
      if (serviceRows.value.some(row => row.service_id === id && row.section_id == null && row.phase_id == null)) continue
      const rates: Record<string, string> = {}
      for (const category of CHARGE_CATEGORIES) rates[category] = ''
      serviceRows.value.push({
        _key: nextKey(),
        service_id: service.id,
        service_code: service.service_code,
        service_name: service.service_name,
        provider_type: service.provider_type,
        charging_basis: 'Daily Rate',
        section_id: null,
        phase_id: null,
        per_service_amount: '0',
        effective_date: null,
        remarks: '',
        rates,
        charge_lines: [],
        section_rates: [],
      })
    }
  }
  else {
    for (const id of pickerSelection.value) {
      const item = props.tangibles.find(candidate => candidate.id === id)
      if (!item) continue
      if (tangibleRows.value.some(row => row.tangible_id === id)) continue
      tangibleRows.value.push({
        _key: nextKey(),
        tangible_id: item.id,
        tangible_code: item.code,
        tangible_name: item.name,
        quantity: '1',
        captured_rate: String(item.rate),
        override_rate: '',
        uom: item.uom ?? '',
        currency: item.currency ?? '',
        remarks: '',
      })
    }
  }
  picker.value = null
  pickerSelection.value = []
  schedulePreview()
}

function addConsumable(): void {
  consumableRows.value.push({
    _key: nextKey(),
    item_kind: 'mud_chemical',
    item_id: null,
    item_code: 'LUMPSUM',
    item_name: 'Mud Chemicals',
    quantity: '1',
    captured_rate: '0',
    override_rate: '',
    uom: '',
    currency: '',
    section_id: null,
    phase_id: null,
    remarks: '',
  })
  schedulePreview()
}

function onConsumableKindChange(row: LocalConsumable): void {
  if (row.item_kind === 'drill_bit') {
    row.item_id = null
    row.item_code = ''
    row.item_name = ''
    row.quantity = '1'
    row.captured_rate = '0'
    row.override_rate = ''
  } else {
    row.item_id = null
    const kindMap: Record<string, string> = {
      'mud_chemical': 'Mud Chemicals',
      'cement_additive': 'Cement Additives',
      'fuel': 'Fuel'
    }
    row.item_name = kindMap[row.item_kind] || 'Mud Chemicals'
    row.item_code = 'LUMPSUM'
    row.quantity = '1'
    row.captured_rate = '0'
  }
  schedulePreview()
}

function onDrillBitSelect(row: LocalConsumable, itemId: number): void {
  const item = props.consumables.find(candidate => candidate.id === itemId && candidate.kind === 'drill_bit')
  if (item) {
    row.item_id = item.id
    row.item_code = item.code
    row.item_name = item.name
    row.captured_rate = String(item.rate)
    row.uom = item.uom ?? ''
    row.currency = item.currency ?? ''
  }
  schedulePreview()
}

function removeService(row: LocalService): void {
  serviceRows.value = serviceRows.value.filter(item => item._key !== row._key)
}

function removeConsumable(row: LocalConsumable): void {
  consumableRows.value = consumableRows.value.filter(item => item._key !== row._key)
}

function removeTangible(row: LocalTangible): void {
  tangibleRows.value = tangibleRows.value.filter(item => item._key !== row._key)
}

function addChargeLine(row: LocalService): void {
  row.charge_lines.push({ category: 'Standby', quantity: '1', quantity_unit: 'days' })
}

function removeChargeLine(row: LocalService, index: number): void {
  row.charge_lines.splice(index, 1)
}

function addSectionRate(row: LocalService): void {
  row.section_rates.push({
    section_id: sectionOptions.value[0]?.value ?? null,
    phase_id: null,
    amount: '0',
  })
}

function removeSectionRate(row: LocalService, index: number): void {
  row.section_rates.splice(index, 1)
}

function onBasisChange(row: LocalService): void {
  if (row.charging_basis === 'Daily Rate' && !row.charge_lines.length) {
    // Keep the day-based categories ready; the well's planned days still drive Operation.
    row.charge_lines = []
  }
  if (row.charging_basis === 'Per Section Rate' && !row.section_rates.length) addSectionRate(row)
  schedulePreview()
}

function onScopeChange(row: LocalService | LocalConsumable): void {
  const options = phaseOptionsFor(row.section_id)
  if (row.phase_id != null && !options.some(option => option.value === row.phase_id)) row.phase_id = null
  schedulePreview()
}

// ---------------------------------------------------------------------------
// Save / status / print
// ---------------------------------------------------------------------------

async function save(): Promise<void> {
  if (props.afeId == null) return
  saving.value = true
  error.value = null
  notice.value = null
  try {
    estimate.value = await api.put<AfeEstimate>(`/afe/estimates/${props.afeId}`, buildPayload())
    await load()
    notice.value = 'Cost estimate saved and recalculated.'
    emit('changed')
  }
  catch (caught: unknown) {
    error.value = caught instanceof Error ? caught.message : 'The cost estimate could not be saved'
  }
  finally {
    saving.value = false
  }
}

async function changeStatus(action: 'submit' | 'approve' | 'reopen'): Promise<void> {
  if (props.afeId == null) return
  const prompt = {
    submit: 'Remarks for submitting this AFE:',
    approve: 'Remarks for approving this AFE:',
    reopen: 'Remarks for reopening this AFE as draft:',
  }[action]
  const remarks = window.prompt(prompt, '')
  if (remarks == null) return
  if (!remarks.trim()) {
    error.value = 'Remarks are required for a status change.'
    return
  }
  saving.value = true
  error.value = null
  try {
    await api.post(`/afe/estimates/${props.afeId}/status`, { action, remarks })
    await load()
    notice.value = 'Status updated.'
    emit('changed')
  }
  catch (caught: unknown) {
    error.value = caught instanceof Error ? caught.message : 'The status could not be changed'
  }
  finally {
    saving.value = false
  }
}

async function printEstimate(): Promise<void> {
  if (!estimate.value) return
  printedAt.value = new Date().toLocaleString()
  emit('print', { ...estimate.value, grand_total: preview.value?.grand_total ?? estimate.value.grand_total })
  await nextTick()
  window.print()
}

const grandTotal = computed(() => money(preview.value?.grand_total ?? estimate.value?.grand_total ?? 0))
const summaryRows = computed(() => preview.value?.summary ?? estimate.value?.summary ?? [])
const rollupRows = computed(() => preview.value?.by_section ?? estimate.value?.by_section ?? [])
const warningList = computed(() => preview.value?.warnings ?? estimate.value?.warnings ?? [])
const basisOptions = CHARGING_BASES.map(basis => ({ label: basis, value: basis }))
const dayCategoryOptions = DAY_BASED_CATEGORIES.map(category => ({ label: category, value: category }))
const unitOptions = [
  { label: 'Days', value: 'days' },
  { label: 'Hours (0-24)', value: 'hours' },
]
const oneTimeCategories = [...ONE_TIME_CATEGORIES]
</script>

<template>
  <Dialog
    v-model:visible="visibleModel"
    :header="`${estimate?.afe.afe_code ?? 'AFE'} — Cost Estimation`"
    modal
    maximizable
    :style="{ width: '1200px' }"
    :breakpoints="{ '1400px': '96vw' }"
    data-testid="afe-estimate-dialog"
  >
    <div class="afe-est">
      <div class="afe-est__head">
        <div class="afe-est__id">
          <strong>{{ estimate?.afe.afe_name }}</strong>
          <Tag :severity="statusSeverity" :value="statusLabel" />
          <span class="afe-est__meta">
            {{ estimate?.afe.afe_type }} · {{ estimate?.afe.rig_display || '—' }} · {{ estimate?.afe.well_display || '—' }}
          </span>
        </div>
        <div class="afe-est__total">
          <span class="afe-est__total-label">AFE cost estimate</span>
          <strong class="afe-est__total-value">{{ grandTotal }}</strong>
        </div>
      </div>

      <Message v-if="error" severity="error" :closable="false" class="afe-est__msg">{{ error }}</Message>
      <Message v-else-if="notice" severity="success" :closable="false" class="afe-est__msg">{{ notice }}</Message>
      <Message v-if="!hasConfiguration" severity="warn" :closable="false" class="afe-est__msg">
        This well has no configuration yet. Configure its sections, phases and planned days in
        <strong>Rig &amp; Well Management → Well Configuration</strong> so the day-based estimates can be calculated.
      </Message>

      <div class="subtabs">
        <button
          v-for="(tab, index) in subTabs"
          :key="tab.label"
          class="subtabs__item"
          :class="{ 'subtabs__item--active': activeSub === index }"
          @click="activeSub = index"
        >
          <i :class="tab.icon" /> {{ tab.label }}
          <span v-if="index === SUB_SERVICES" class="afe-est__count">{{ serviceRows.length }}</span>
          <span v-else-if="index === SUB_CONSUMABLES" class="afe-est__count">{{ consumableRows.length }}</span>
          <span v-else-if="index === SUB_TANGIBLES" class="afe-est__count">{{ tangibleRows.length }}</span>
        </button>
      </div>

      <!-- Services -->
      <section v-if="activeSub === SUB_SERVICES" class="afe-est__panel">
        <div class="afe-est__actions">
          <Button label="Add service" icon="pi pi-plus" size="small" severity="secondary" outlined :disabled="!isDraft" @click="openPicker('service')" />
          <span class="afe-est__hint">
            Daily Rate = planned days × Operation rate + one-time Mobilization / Demobilization / Fixed Charge.
            Per Section Rate = a constant amount per section (optionally per phase). Per Service Rate = one price for the service.
          </span>
        </div>

        <DataTable
          v-model:expanded-rows="expandedRows"
          :value="serviceRows"
          data-key="_key"
          size="small"
          scrollable
          scroll-height="46vh"
          class="afe-est__table"
        >
          <Column :expander="true" header-style="width: 2.4rem" />
          <Column field="service_name" header="Service" header-style="width: 210px">
            <template #body="{ data }">
              <div class="afe-est__cell-strong">{{ data.service_name }}</div>
              <div class="afe-est__cell-sub">{{ data.service_code }} · {{ data.provider_type }}</div>
            </template>
          </Column>
          <Column header="Charging Basis" header-style="width: 160px">
            <template #body="{ data }">
              <Select
                v-model="data.charging_basis"
                :options="basisOptions"
                option-label="label"
                option-value="value"
                size="small"
                fluid
                :disabled="!isDraft"
                @change="onBasisChange(data)"
              />
            </template>
          </Column>
          <Column header="Section" header-style="width: 150px">
            <template #body="{ data }">
              <Select
                v-model="data.section_id"
                :options="sectionOptions"
                option-label="label"
                option-value="value"
                size="small"
                fluid
                show-clear
                placeholder="All sections"
                :disabled="!isDraft"
                @change="onScopeChange(data)"
              />
            </template>
          </Column>
          <Column header="Phase" header-style="width: 140px">
            <template #body="{ data }">
              <Select
                v-model="data.phase_id"
                :options="phaseOptionsFor(data.section_id)"
                option-label="label"
                option-value="value"
                size="small"
                fluid
                show-clear
                placeholder="All phases"
                :disabled="!isDraft"
                @change="schedulePreview"
              />
            </template>
          </Column>
          <Column header="Estimate" header-style="width: 110px">
            <template #body="{ index }">
              <span class="afe-est__amount">{{ lineAmount('services', index) }}</span>
            </template>
          </Column>
          <Column header="" header-style="width: 3rem">
            <template #body="{ data }">
              <Button icon="pi pi-trash" size="small" severity="danger" text :disabled="!isDraft" @click="removeService(data)" />
            </template>
          </Column>

          <template #expansion="{ data, index }">
            <div class="afe-est__expansion">
              <div class="afe-est__rates">
                <p class="afe-est__rates-title">
                  Charge category rates
                  <span class="afe-est__rates-note">
                    {{ data.charging_basis === 'Daily Rate' ? 'per day (Mobilization / Demobilization / Fixed Charge are charged once)' : 'used by the selected charging basis' }}
                  </span>
                </p>
                <div class="afe-est__rates-grid">
                  <label v-for="category in CHARGE_CATEGORIES" :key="category" class="afe-est__rate">
                    <span>{{ category }}</span>
                    <InputText
                      v-model="data.rates[category]"
                      size="small"
                      inputmode="decimal"
                      placeholder="0"
                      :disabled="!isDraft"
                      :class="{ 'afe-est__rate--one-time': oneTimeCategories.includes(category as typeof oneTimeCategories[number]) }"
                    />
                  </label>
                </div>
              </div>

              <div v-if="data.charging_basis === 'Daily Rate'" class="afe-est__sub">
                <p class="afe-est__rates-title">
                  Day-based charges
                  <span class="afe-est__rates-note">
                    Operation defaults to the well's planned days; enter a quantity only to override it or to add the other categories.
                  </span>
                </p>
                <table class="afe-est__mini">
                  <thead>
                    <tr>
                      <th>Charge Category</th>
                      <th>Quantity</th>
                      <th>Unit</th>
                      <th>Unit Rate</th>
                      <th />
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-if="!data.charge_lines.length">
                      <td colspan="5" class="afe-est__mini-empty">No manual day charges — the well's planned days drive the Operation cost.</td>
                    </tr>
                    <tr v-for="(line, lineIndex) in data.charge_lines" :key="`cl-${lineIndex}`">
                      <td>
                        <Select
                          v-model="line.category"
                          :options="dayCategoryOptions"
                          option-label="label"
                          option-value="value"
                          size="small"
                          fluid
                          :disabled="!isDraft"
                        />
                      </td>
                      <td>
                        <InputText v-model="line.quantity" size="small" inputmode="decimal" :disabled="!isDraft" />
                      </td>
                      <td>
                        <Select
                          v-model="line.quantity_unit"
                          :options="unitOptions"
                          option-label="label"
                          option-value="value"
                          size="small"
                          fluid
                          :disabled="!isDraft"
                        />
                      </td>
                      <td class="afe-est__num">{{ money(data.rates[line.category]) }}</td>
                      <td>
                        <Button icon="pi pi-times" size="small" severity="danger" text :disabled="!isDraft" @click="removeChargeLine(data, lineIndex)" />
                      </td>
                    </tr>
                  </tbody>
                </table>
                <Button label="Add charge line" icon="pi pi-plus" size="small" severity="secondary" text :disabled="!isDraft" @click="addChargeLine(data)" />
              </div>

              <div v-else-if="data.charging_basis === 'Per Section Rate'" class="afe-est__sub">
                <p class="afe-est__rates-title">
                  Section rates
                  <span class="afe-est__rates-note">A constant amount for that section — add a phase to charge it inside one phase only.</span>
                </p>
                <table class="afe-est__mini">
                  <thead>
                    <tr>
                      <th>Section</th>
                      <th>Phase</th>
                      <th>Amount</th>
                      <th />
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="(entry, entryIndex) in data.section_rates" :key="`sr-${entryIndex}`">
                      <td>
                        <Select
                          v-model="entry.section_id"
                          :options="sectionOptions"
                          option-label="label"
                          option-value="value"
                          size="small"
                          fluid
                          :disabled="!isDraft"
                        />
                      </td>
                      <td>
                        <Select
                          v-model="entry.phase_id"
                          :options="phaseOptionsFor(entry.section_id)"
                          option-label="label"
                          option-value="value"
                          size="small"
                          fluid
                          show-clear
                          placeholder="Whole section"
                          :disabled="!isDraft"
                        />
                      </td>
                      <td>
                        <InputText v-model="entry.amount" size="small" inputmode="decimal" :disabled="!isDraft" />
                      </td>
                      <td>
                        <Button icon="pi pi-times" size="small" severity="danger" text :disabled="!isDraft" @click="removeSectionRate(data, entryIndex)" />
                      </td>
                    </tr>
                  </tbody>
                </table>
                <Button label="Add section rate" icon="pi pi-plus" size="small" severity="secondary" text :disabled="!isDraft" @click="addSectionRate(data)" />
              </div>

              <div v-else class="afe-est__sub">
                <label class="afe-est__rate afe-est__rate--wide">
                  <span>Per service price</span>
                  <InputText v-model="data.per_service_amount" size="small" inputmode="decimal" :disabled="!isDraft" />
                </label>
                <span class="afe-est__rates-note">Charged once, for the section / phase selected above.</span>
              </div>

              <div class="afe-est__line-meta">
                <label class="afe-est__rate afe-est__rate--wide">
                  <span>Effective date</span>
                  <InputText v-model="data.effective_date" type="date" size="small" :disabled="!isDraft" />
                </label>
                <label class="afe-est__rate afe-est__rate--grow">
                  <span>Remarks</span>
                  <InputText v-model="data.remarks" size="small" :disabled="!isDraft" />
                </label>
              </div>

              <ul v-if="lineEstimate('services', index)?.warnings?.length" class="afe-est__warnings">
                <li v-for="(warning, wIndex) in lineEstimate('services', index)!.warnings" :key="wIndex">{{ warning }}</li>
              </ul>

              <table v-if="lineEstimate('services', index)?.components?.length" class="afe-est__breakdown">
                <thead>
                  <tr>
                    <th>Charge</th>
                    <th>Qty</th>
                    <th>Rate</th>
                    <th>Amount</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="(component, cIndex) in lineEstimate('services', index)!.components" :key="cIndex">
                    <td>{{ component.description }}</td>
                    <td class="afe-est__num">{{ component.quantity == null ? '—' : num(component.quantity) }}</td>
                    <td class="afe-est__num">{{ money(component.rate) }}</td>
                    <td class="afe-est__num">{{ money(component.amount) }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </template>

          <template #empty>
            <div class="afe-est__empty">No services yet — use <strong>Add service</strong> to pick from the Master Data services.</div>
          </template>
        </DataTable>
      </section>

      <!-- Consumables -->
      <section v-else-if="activeSub === SUB_CONSUMABLES" class="afe-est__panel">
        <div class="afe-est__actions">
          <Button label="Add consumable" icon="pi pi-plus" size="small" severity="secondary" outlined :disabled="!isDraft" @click="addConsumable" />
          <span class="afe-est__hint">
            Select the consumable category and section. For drill bits, pick from the master data. For others, enter an estimated cost.
          </span>
        </div>

        <DataTable :value="consumableRows" data-key="_key" size="small" scrollable scroll-height="48vh" class="afe-est__table">
          <Column header="Category" header-style="width: 160px">
            <template #body="{ data }">
              <Select
                v-model="data.item_kind"
                :options="[{ label: 'Mud Chemicals', value: 'mud_chemical' }, { label: 'Cement Additives', value: 'cement_additive' }, { label: 'Fuel', value: 'fuel' }, { label: 'Drill Bits', value: 'drill_bit' }]"
                option-label="label"
                option-value="value"
                size="small"
                fluid
                :disabled="!isDraft"
                @change="onConsumableKindChange(data)"
              />
            </template>
          </Column>
          <Column header="Selection" header-style="width: 220px">
            <template #body="{ data }">
              <Select
                v-if="data.item_kind === 'drill_bit'"
                v-model="data.item_id"
                :options="props.consumables.filter(c => c.kind === 'drill_bit')"
                option-label="name"
                option-value="id"
                size="small"
                fluid
                placeholder="Select a Drill Bit"
                :disabled="!isDraft"
                @change="onDrillBitSelect(data, $event.value)"
              />
              <div v-else class="afe-est__cell-sub">Lump sum estimate</div>
            </template>
          </Column>
          <Column header="Section" header-style="width: 150px">
            <template #body="{ data }">
              <Select
                v-model="data.section_id"
                :options="sectionOptions"
                option-label="label"
                option-value="value"
                size="small"
                fluid
                show-clear
                placeholder="Any"
                :disabled="!isDraft"
                @change="onScopeChange(data)"
              />
            </template>
          </Column>
          <Column header="Qty" header-style="width: 90px">
            <template #body="{ data }">
              <InputText v-if="data.item_kind === 'drill_bit'" v-model="data.quantity" size="small" inputmode="decimal" :disabled="!isDraft" />
              <span v-else class="afe-est__num">—</span>
            </template>
          </Column>
          <Column header="Estimated Cost / Rate" header-style="width: 140px">
            <template #body="{ data }">
              <InputText v-model="data.override_rate" size="small" inputmode="decimal" :placeholder="data.item_kind === 'drill_bit' ? money(data.captured_rate) : '0.00'" :disabled="!isDraft" />
            </template>
          </Column>
          <Column header="Remarks" header-style="width: 150px">
            <template #body="{ data }">
              <InputText v-model="data.remarks" size="small" placeholder="Remarks" :disabled="!isDraft" />
            </template>
          </Column>
          <Column header="Total" header-style="width: 110px">
            <template #body="{ index }">
              <span class="afe-est__amount">{{ lineAmount('consumables', index) }}</span>
            </template>
          </Column>
          <Column header="" header-style="width: 3rem">
            <template #body="{ data }">
              <Button icon="pi pi-trash" size="small" severity="danger" text :disabled="!isDraft" @click="removeConsumable(data)" />
            </template>
          </Column>
          <template #empty>
            <div class="afe-est__empty">No consumables yet — use <strong>Add consumable</strong> to estimate categories.</div>
          </template>
        </DataTable>
      </section>

      <!-- Tangibles -->
      <section v-else-if="activeSub === SUB_TANGIBLES" class="afe-est__panel">
        <div class="afe-est__actions">
          <Button label="Add tangible" icon="pi pi-plus" size="small" severity="secondary" outlined :disabled="!isDraft" @click="openPicker('tangible')" />
          <span class="afe-est__hint">
            Rates are captured from the Tangibles master list. Enter an override rate and the system uses it instead.
          </span>
        </div>

        <DataTable :value="tangibleRows" data-key="_key" size="small" scrollable scroll-height="48vh" class="afe-est__table">
          <Column field="tangible_name" header="Tangible" header-style="width: 240px">
            <template #body="{ data }">
              <div class="afe-est__cell-strong">{{ data.tangible_name }}</div>
              <div class="afe-est__cell-sub">{{ data.tangible_code }}</div>
            </template>
          </Column>
          <Column header="Qty" header-style="width: 90px">
            <template #body="{ data }">
              <InputText v-model="data.quantity" size="small" inputmode="decimal" :disabled="!isDraft" />
            </template>
          </Column>
          <Column header="Captured Rate" header-style="width: 120px">
            <template #body="{ data }">
              <span class="afe-est__num">{{ money(data.captured_rate) }}</span>
            </template>
          </Column>
          <Column header="Override Rate" header-style="width: 120px">
            <template #body="{ data }">
              <InputText v-model="data.override_rate" size="small" inputmode="decimal" placeholder="—" :disabled="!isDraft" />
            </template>
          </Column>
          <Column header="UOM" header-style="width: 70px">
            <template #body="{ data }">{{ data.uom || '—' }}</template>
          </Column>
          <Column header="Estimate" header-style="width: 110px">
            <template #body="{ index }">
              <span class="afe-est__amount">{{ lineAmount('tangibles', index) }}</span>
            </template>
          </Column>
          <Column header="" header-style="width: 3rem">
            <template #body="{ data }">
              <Button icon="pi pi-trash" size="small" severity="danger" text :disabled="!isDraft" @click="removeTangible(data)" />
            </template>
          </Column>
          <template #empty>
            <div class="afe-est__empty">No tangibles yet — use <strong>Add tangible</strong> to pick from the Tangibles master list.</div>
          </template>
        </DataTable>
      </section>

      <!-- Summary -->
      <section v-else-if="activeSub === SUB_SUMMARY" class="afe-est__panel">
        <div class="afe-est__summary">
          <table class="afe-est__summary-table">
            <thead>
              <tr>
                <th>Cost Group</th>
                <th>Lines</th>
                <th class="afe-est__num">Amount</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in summaryRows" :key="row.group">
                <td>{{ row.group }}</td>
                <td>{{ row.line_count }}</td>
                <td class="afe-est__num">{{ money(row.amount) }}</td>
              </tr>
            </tbody>
            <tfoot>
              <tr>
                <th colspan="2">Total AFE cost estimate</th>
                <th class="afe-est__num">{{ grandTotal }}</th>
              </tr>
            </tfoot>
          </table>

          <table class="afe-est__summary-table">
            <thead>
              <tr>
                <th>Section</th>
                <th>Planned Days</th>
                <th class="afe-est__num">Cost</th>
              </tr>
            </thead>
            <tbody>
              <tr v-if="!rollupRows.length">
                <td colspan="3" class="afe-est__mini-empty">Nothing to summarise yet.</td>
              </tr>
              <tr v-for="row in rollupRows" :key="`roll-${row.section_id ?? 'well'}`">
                <td>{{ row.section_label }}</td>
                <td>{{ num(row.planned_days) }}</td>
                <td class="afe-est__num">{{ money(row.amount) }}</td>
              </tr>
            </tbody>
          </table>
        </div>

        <ul v-if="warningList.length" class="afe-est__warnings">
          <li v-for="(warning, index) in warningList" :key="index">{{ warning }}</li>
        </ul>
      </section>
    </div>

    <template #footer>
      <div class="afe-est__footer">
        <div class="afe-est__footer-left">
          <Button label="Print AFE" icon="pi pi-print" size="small" severity="secondary" text @click="printEstimate" />
          <span v-if="!isDraft" class="afe-est__hint">
            This AFE is {{ statusLabel }} — reopen it as Draft to edit.
          </span>
        </div>
        <div class="afe-est__footer-right">
          <Button v-if="isDraft" label="Submit" icon="pi pi-send" size="small" severity="info" outlined :disabled="saving" @click="changeStatus('submit')" />
          <Button v-if="estimate?.afe.status === 'submitted'" label="Approve" icon="pi pi-check" size="small" severity="success" :disabled="saving" @click="changeStatus('approve')" />
          <Button v-if="!isDraft" label="Reopen as Draft" icon="pi pi-undo" size="small" severity="warn" outlined :disabled="saving" @click="changeStatus('reopen')" />
          <Button label="Save" icon="pi pi-save" size="small" severity="success" :disabled="!isDraft" :loading="saving" @click="save" />
          <Button label="Close" icon="pi pi-times" size="small" severity="secondary" text @click="visibleModel = false" />
        </div>
      </div>
    </template>
  </Dialog>

  <Dialog
    v-model:visible="pickerVisible"
    :header="pickerTitle"
    modal
    :style="{ width: '720px' }"
    :breakpoints="{ '900px': '94vw' }"
  >
    <div class="afe-picker">
      <div class="afe-picker__search">
        <i class="pi pi-search" />
        <InputText v-model="pickerSearch" placeholder="Search code, name or provider…" size="small" fluid />
      </div>
      <div class="afe-picker__list">
        <label v-for="row in pickerRows" :key="row.id" class="afe-picker__row">
          <input v-model="pickerSelection" type="checkbox" :value="row.id">
          <span class="afe-picker__code">{{ row.code }}</span>
          <span class="afe-picker__name">{{ row.name }}</span>
          <span class="afe-picker__detail">{{ row.detail }}</span>
          <span class="afe-picker__extra">{{ row.extra }}</span>
        </label>
        <p v-if="!pickerRows.length" class="afe-est__mini-empty">
          Nothing matches. Add the missing record on the Master Data page first.
        </p>
      </div>
    </div>
    <template #footer>
      <Button :label="`Add ${pickerSelection.length || ''}`.trim()" icon="pi pi-plus" size="small" severity="success" :disabled="!pickerSelection.length" @click="addPicked" />
      <Button label="Cancel" size="small" severity="secondary" text @click="picker = null" />
    </template>
  </Dialog>
</template>

<style scoped>
  .afe-est {
    display: grid;
    gap: 10px;
  }

  .afe-est__head {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
    padding-bottom: 8px;
    border-bottom: 1px solid var(--app-border);
  }

  .afe-est__id {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 8px;
  }

  .afe-est__meta {
    color: var(--app-muted);
    font-size: .76rem;
  }

  .afe-est__total {
    display: grid;
    justify-items: end;
  }

  .afe-est__total-label {
    color: var(--app-muted);
    font-size: .68rem;
    font-weight: 700;
    letter-spacing: .06em;
    text-transform: uppercase;
  }

  .afe-est__total-value {
    font-size: 1.1rem;
    font-variant-numeric: tabular-nums;
  }

  .afe-est__msg {
    margin: 0;
  }

  .afe-est__count {
    padding: 0 5px;
    border-radius: 999px;
    background: var(--app-bg);
    font-size: .68rem;
    font-variant-numeric: tabular-nums;
  }

  .afe-est__panel {
    display: grid;
    gap: 8px;
  }

  .afe-est__actions {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 10px;
  }

  .afe-est__hint {
    color: var(--app-muted);
    font-size: .72rem;
  }

  .afe-est__cell-strong {
    font-weight: 650;
  }

  .afe-est__cell-sub {
    color: var(--app-muted);
    font-size: .7rem;
  }

  .afe-est__amount {
    font-variant-numeric: tabular-nums;
    font-weight: 700;
  }

  .afe-est__num {
    text-align: right;
    font-variant-numeric: tabular-nums;
  }

  .afe-est__expansion {
    display: grid;
    gap: 10px;
    padding: 10px 12px;
    background: color-mix(in srgb, var(--app-bg) 70%, var(--app-surface));
  }

  .afe-est__rates-title {
    margin: 0 0 6px;
    font-size: .74rem;
    font-weight: 750;
    letter-spacing: .03em;
    text-transform: uppercase;
  }

  .afe-est__rates-note {
    margin-left: 6px;
    color: var(--app-muted);
    font-size: .7rem;
    font-weight: 500;
    text-transform: none;
    letter-spacing: 0;
  }

  .afe-est__rates-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
    gap: 6px;
  }

  .afe-est__rate {
    display: grid;
    gap: 3px;
    font-size: .7rem;
    font-weight: 600;
  }

  .afe-est__rate--wide {
    max-width: 200px;
  }

  .afe-est__rate--grow {
    flex: 1 1 220px;
  }

  .afe-est__rate--one-time :deep(input) {
    background: color-mix(in srgb, #f59e0b 8%, transparent);
  }

  .afe-est__sub {
    display: grid;
    gap: 6px;
  }

  .afe-est__line-meta {
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
  }

  .afe-est__mini,
  .afe-est__breakdown,
  .afe-est__summary-table {
    width: 100%;
    border-collapse: collapse;
    font-size: .76rem;
  }

  .afe-est__mini th,
  .afe-est__mini td,
  .afe-est__breakdown th,
  .afe-est__breakdown td,
  .afe-est__summary-table th,
  .afe-est__summary-table td {
    padding: 4px 6px;
    border: 1px solid var(--app-border);
    text-align: left;
    vertical-align: middle;
  }

  .afe-est__mini thead th,
  .afe-est__breakdown thead th,
  .afe-est__summary-table thead th {
    background: var(--app-bg);
    font-size: .68rem;
    font-weight: 750;
    letter-spacing: .04em;
    text-transform: uppercase;
  }

  .afe-est__summary-table tfoot th {
    background: var(--app-bg);
    font-variant-numeric: tabular-nums;
  }

  .afe-est__mini-empty {
    color: var(--app-muted);
    font-size: .74rem;
    text-align: center;
  }

  .afe-est__empty {
    padding: 18px 10px;
    color: var(--app-muted);
    font-size: .78rem;
    text-align: center;
  }

  .afe-est__warnings {
    margin: 0;
    padding-left: 18px;
    color: #92400e;
    font-size: .72rem;
  }

  .afe-est__summary {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
    gap: 10px;
  }

  .afe-est__footer {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
    width: 100%;
  }

  .afe-est__footer-left,
  .afe-est__footer-right {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 6px;
  }

  .afe-picker {
    display: grid;
    gap: 8px;
  }

  .afe-picker__search {
    position: relative;
  }

  .afe-picker__search i {
    position: absolute;
    top: 50%;
    left: 10px;
    z-index: 2;
    color: var(--app-muted);
    transform: translateY(-50%);
  }

  .afe-picker__search :deep(input) {
    padding-left: 30px;
  }

  .afe-picker__list {
    display: grid;
    gap: 2px;
    max-height: 46vh;
    overflow: auto;
  }

  .afe-picker__row {
    display: grid;
    grid-template-columns: 18px 110px 1fr 110px 110px;
    align-items: center;
    gap: 8px;
    padding: 5px 6px;
    border-bottom: 1px solid var(--app-border);
    font-size: .78rem;
    cursor: pointer;
  }

  .afe-picker__row:hover {
    background: var(--app-bg);
  }

  .afe-picker__code {
    font-variant-numeric: tabular-nums;
  }

  .afe-picker__detail,
  .afe-picker__extra {
    color: var(--app-muted);
    font-size: .72rem;
  }

  .afe-picker__extra {
    text-align: right;
    font-variant-numeric: tabular-nums;
  }
</style>
