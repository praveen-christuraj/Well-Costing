<script setup lang="ts">
/**
 * AFE — one page for the whole authorisation for expenditure.
 *
 * Projects and wells are registered at the top, an AFE is picked (or created)
 * for a well, and every line of that AFE is entered in the grid below. There is
 * no separate "well requirement" step any more: this page is the requirement.
 *
 * Each line records how it is charged. The rate basis pre-fills from the
 * catalogue item and can be changed for that line alone; a per-section line
 * needs a section from the hole-section configuration, and a chemical charged
 * on daily usage has its quantity computed from usage per day multiplied by
 * planned days, overridable only with a reason.
 */
import { computed, onMounted, ref, watch } from 'vue'
import Button from 'primevue/button'
import Column from 'primevue/column'
import DataTable from 'primevue/datatable'
import DatePicker from 'primevue/datepicker'
import Dialog from 'primevue/dialog'
import InputNumber from 'primevue/inputnumber'
import InputText from 'primevue/inputtext'
import Message from 'primevue/message'
import Select from 'primevue/select'
import Tag from 'primevue/tag'
import Textarea from 'primevue/textarea'
import PageHeader from '~/components/design-system/PageHeader.vue'
import { defaultRateBasisFor, rateBasesFor } from '~/types/afe'
import { parseTsv } from '~/utils/tsv'
import type { AfeLineRecord, AfeRecord, EditableAfeLine, ProjectRecord, RateBasis, WellRecord } from '~/types/afe'
import type { MasterDataRecord } from '~/types/masterData'

definePageMeta({ middleware: 'auth' })

const api = useAfe()
const master = useMasterData()

const projects = ref<ProjectRecord[]>([])
const wells = ref<WellRecord[]>([])
const afes = ref<AfeRecord[]>([])

const catalogueItems = ref<MasterDataRecord[]>([])
const costCodes = ref<MasterDataRecord[]>([])
const units = ref<MasterDataRecord[]>([])
const holeSections = ref<MasterDataRecord[]>([])

const projectFilter = ref<string | null>(null)
const wellFilter = ref<string | null>(null)
const statusFilter = ref<string | null>(null)

const selectedAfeId = ref<string>('')
const selectedAfe = ref<AfeRecord | null>(null)
const lines = ref<EditableAfeLine[]>([])

const loading = ref(false)
const loadingLines = ref(false)
const saving = ref(false)
const submitting = ref(false)
const error = ref<string | null>(null)
const success = ref<string | null>(null)

const isDraft = computed(() => selectedAfe.value?.status === 'draft')
const pendingCount = computed(() => lines.value.filter(line => line._state !== 'clean').length)

/* ------------------------------------------------ projects ------------------ */
const projectDialog = ref(false)
const projectForm = ref<{ id?: string, code: string, name: string, description: string, is_active: boolean }>({ code: '', name: '', description: '', is_active: true })

function openProjectDialog(record?: ProjectRecord): void {
  projectForm.value = record
    ? { id: record.id, code: record.code, name: record.name, description: record.description ?? '', is_active: record.is_active }
    : { code: '', name: '', description: '', is_active: true }
  projectDialog.value = true
}

async function saveProject(): Promise<void> {
  saving.value = true
  error.value = null
  try {
    const payload = { code: projectForm.value.code, name: projectForm.value.name, description: projectForm.value.description || null, is_active: projectForm.value.is_active }
    if (projectForm.value.id) await api.updateProject(projectForm.value.id, payload)
    else await api.createProject(payload)
    projectDialog.value = false
  }
  catch (caught: unknown) {
    error.value = caught instanceof Error ? caught.message : 'The project could not be saved.'
    return
  }
  finally { saving.value = false }
  // Refreshed outside the saving flag so the other dialogs stay operable.
  await loadAll()
}

async function deactivateProject(record: ProjectRecord): Promise<void> {
  if (!window.confirm(`Deactivate project ${record.code}? Wells and AFEs stay in place but it can no longer be used.`)) return
  await api.deleteProject(record.id)
  await loadAll()
}

/* ---------------------------------------------------- wells ------------------ */
const wellDialog = ref(false)
const wellForm = ref({
  id: undefined as string | undefined,
  project_id: '',
  code: '',
  name: '',
  rig_name: '',
  status: 'planning',
  spud_date: null as Date | null,
  completion_date: null as Date | null,
  description: '',
  is_active: true,
})

function toDateString(value: Date | null): string | null {
  if (!value) return null
  const offset = value.getTimezoneOffset() * 60000
  return new Date(value.getTime() - offset).toISOString().slice(0, 10)
}

function openWellDialog(record?: WellRecord): void {
  const defaultProjectId = projectFilter.value ?? activeProjectOptions.value[0]?.id ?? ''
  wellForm.value = record
    ? {
        id: record.id,
        project_id: record.project_id,
        code: record.code,
        name: record.name,
        rig_name: record.rig_name ?? '',
        status: record.status,
        spud_date: record.spud_date ? new Date(`${record.spud_date}T00:00:00`) : null,
        completion_date: record.completion_date ? new Date(`${record.completion_date}T00:00:00`) : null,
        description: record.description ?? '',
        is_active: record.is_active,
      }
    : {
        id: undefined,
        project_id: defaultProjectId,
        code: '',
        name: '',
        rig_name: '',
        status: 'planning',
        spud_date: null,
        completion_date: null,
        description: '',
        is_active: true,
      }
  wellDialog.value = true
}

async function saveWell(): Promise<void> {
  saving.value = true
  error.value = null
  try {
    const payload = {
      project_id: wellForm.value.project_id,
      code: wellForm.value.code,
      name: wellForm.value.name,
      rig_name: wellForm.value.rig_name || null,
      status: wellForm.value.status,
      spud_date: toDateString(wellForm.value.spud_date),
      completion_date: toDateString(wellForm.value.completion_date),
      description: wellForm.value.description || null,
      is_active: wellForm.value.is_active,
    }
    if (wellForm.value.id) await api.updateWell(wellForm.value.id, payload)
    else await api.createWell(payload)
    wellDialog.value = false
  }
  catch (caught: unknown) {
    error.value = caught instanceof Error ? caught.message : 'The well could not be saved.'
    return
  }
  finally { saving.value = false }
  await loadAll()
}

async function deactivateWell(record: WellRecord): Promise<void> {
  if (!window.confirm(`Deactivate well ${record.code}? It can no longer be used on new AFEs.`)) return
  await api.deleteWell(record.id)
  await loadAll()
}

/* ------------------------------------------------------- AFE ----------------- */
const afeDialog = ref(false)
const afeForm = ref({ id: undefined as string | undefined, well_id: '', code: '', title: '', description: '' })

function openAfeDialog(record?: AfeRecord): void {
  const defaultWellId = wellFilter.value ?? wellOptions.value[0]?.id ?? ''
  afeForm.value = record
    ? { id: record.id, well_id: record.well_id, code: record.code, title: record.title, description: record.description ?? '' }
    : { id: undefined, well_id: defaultWellId, code: '', title: '', description: '' }
  afeDialog.value = true
}

async function saveAfe(): Promise<void> {
  saving.value = true
  error.value = null
  let createdId: string | null = null
  try {
    const payload = { well_id: afeForm.value.well_id, code: afeForm.value.code, title: afeForm.value.title, description: afeForm.value.description || null }
    if (afeForm.value.id) await api.updateAfe(afeForm.value.id, payload)
    else createdId = (await api.createAfe(payload)).id
    afeDialog.value = false
  }
  catch (caught: unknown) {
    error.value = caught instanceof Error ? caught.message : 'The AFE could not be saved.'
    return
  }
  finally { saving.value = false }
  await loadAll()
  if (createdId) await openAfe(createdId)
}

async function deactivateAfe(record: AfeRecord): Promise<void> {
  if (!window.confirm(`Delete AFE ${record.code}? Only draft AFEs can be removed.`)) return
  try { await api.deleteAfe(record.id) }
  catch (caught: unknown) {
    error.value = caught instanceof Error ? caught.message : 'The AFE could not be deleted.'
    return
  }
  if (selectedAfeId.value === record.id) {
    selectedAfeId.value = ''
    selectedAfe.value = null
    lines.value = []
  }
  await loadAll()
}

/* ------------------------------------------------- AFE lines ----------------- */
const pasteVisible = ref(false)
const pasteText = ref('')
const pasteColumns = [
  { field: 'catalog_item_code' },
  { field: 'item_type' },
  { field: 'cost_code' },
  { field: 'quantity' },
  { field: 'unit_code' },
  { field: 'hole_section_code' },
  { field: 'planned_duration_days' },
]

function catalogueItemFor(line: EditableAfeLine): MasterDataRecord | undefined {
  return catalogueItems.value.find(record => record.id === line.catalog_item_id)
}

/** Bases offered for the line's catalogue item; falls back to the full list. */
function basisOptionsFor(line: EditableAfeLine): { label: string, value: RateBasis }[] {
  return rateBasesFor(catalogueItemFor(line)?.item_type)
}

function isConsumptionLine(line: EditableAfeLine): boolean {
  return line.rate_basis === 'daily_consumption'
}

function needsSection(line: EditableAfeLine): boolean {
  return line.rate_basis === 'per_section'
}

/** Usage per day times planned days — the figure the app proposes. */
function computedQuantityFor(line: EditableAfeLine): number | null {
  if (!isConsumptionLine(line)) return null
  const perDay = Number(line.daily_consumption)
  const days = Number(line.planned_duration_days)
  if (!line.daily_consumption || !line.planned_duration_days || Number.isNaN(perDay) || Number.isNaN(days)) return null
  return perDay * days
}

function isOverridden(line: EditableAfeLine): boolean {
  const computed = computedQuantityFor(line)
  return computed !== null && line.quantity !== '' && Number(line.quantity) !== computed
}

/** Keep a computed line's quantity in step with its usage and planned days. */
function syncComputedQuantity(line: EditableAfeLine): void {
  const computed = computedQuantityFor(line)
  if (computed === null) {
    line.computed_quantity = ''
    return
  }
  line.computed_quantity = String(computed)
  if (!line.quantity_override_reason.trim()) line.quantity = String(computed)
}

function onItemChange(line: EditableAfeLine): void {
  const item = catalogueItemFor(line)
  line.rate_basis = defaultRateBasisFor(item?.item_type, item?.rate_basis ?? null)
  if (item?.default_unit_id && !line.unit_id) line.unit_id = item.default_unit_id
  if (item?.cost_code_id && !line.cost_code_id) line.cost_code_id = item.cost_code_id
  onBasisChange(line)
}

function onBasisChange(line: EditableAfeLine): void {
  if (!isConsumptionLine(line)) {
    line.daily_consumption = ''
    line.computed_quantity = ''
    line.quantity_override_reason = ''
  }
  else {
    syncComputedQuantity(line)
  }
  if (!needsSection(line) && line.rate_basis !== 'daily') {
    // A section stays useful as context on any line, so it is kept as entered.
  }
  markDirty(line)
}

function onConsumptionChange(line: EditableAfeLine): void {
  syncComputedQuantity(line)
  markDirty(line)
}

/** Empty inputs become null so the API's optional fields stay valid. */
function nullableValue(value: unknown): unknown {
  return (value === '' || value === null || value === undefined) ? null : value
}

function toPayload(line: EditableAfeLine) {
  return {
    line_number: line.line_number,
    catalog_item_id: line.catalog_item_id,
    cost_code_id: line.cost_code_id,
    quantity: nullableValue(line.quantity === '' ? '' : String(line.quantity)),
    unit_id: line.unit_id,
    hole_section_id: nullableValue(line.hole_section_id),
    rate_basis: line.rate_basis,
    daily_consumption: nullableValue(line.daily_consumption),
    quantity_override_reason: nullableValue(line.quantity_override_reason.trim()),
    planned_duration_days: nullableValue(line.planned_duration_days),
    planned_depth_from: nullableValue(line.planned_depth_from),
    planned_depth_to: nullableValue(line.planned_depth_to),
    depth_unit_id: nullableValue(line.depth_unit_id),
    notes: nullableValue(line.notes),
    is_active: line.is_active,
  }
}

function toEditable(record: AfeLineRecord): EditableAfeLine {
  return {
    id: record.id,
    line_number: record.line_number,
    catalog_item_id: record.catalog_item_id,
    cost_code_id: record.cost_code_id,
    quantity: String(record.quantity),
    unit_id: record.unit_id,
    hole_section_id: record.hole_section_id ?? '',
    rate_basis: record.rate_basis,
    daily_consumption: record.daily_consumption ?? '',
    computed_quantity: record.computed_quantity ?? '',
    quantity_override_reason: record.quantity_override_reason ?? '',
    planned_duration_days: record.planned_duration_days ?? '',
    planned_depth_from: record.planned_depth_from ?? '',
    planned_depth_to: record.planned_depth_to ?? '',
    depth_unit_id: record.depth_unit_id ?? '',
    notes: record.notes ?? '',
    is_active: record.is_active,
    _state: 'clean',
  }
}

const blankLine = (): EditableAfeLine => ({
  line_number: lines.value.reduce((max, line) => Math.max(max, line.line_number), 0) + 1,
  catalog_item_id: '',
  cost_code_id: '',
  quantity: '0',
  unit_id: '',
  hole_section_id: '',
  rate_basis: 'daily',
  daily_consumption: '',
  computed_quantity: '',
  quantity_override_reason: '',
  planned_duration_days: '',
  planned_depth_from: '',
  planned_depth_to: '',
  depth_unit_id: '',
  notes: '',
  is_active: true,
  _state: 'new',
})

function addLine(): void {
  error.value = null
  lines.value.unshift(blankLine())
}

function markDirty(line: EditableAfeLine): void {
  if (line._state === 'clean') line._state = 'dirty'
}

function removeLine(line: EditableAfeLine): void {
  error.value = null
  if (line._state === 'new') {
    lines.value = lines.value.filter(candidate => candidate !== line)
    return
  }
  if (!window.confirm('Remove this line from the AFE?')) return
  void api.deactivateLine(String(line.id))
    .then(loadLines)
    .catch((caught: unknown) => {
      error.value = caught instanceof Error ? caught.message : 'The line could not be removed.'
    })
}

/** Rows pasted from Excel: item code, type, cost code, qty, unit, section, days. */
function applyPaste(): void {
  error.value = null
  const parsed = parseTsv(pasteText.value, pasteColumns)
  const created: EditableAfeLine[] = []
  for (const values of parsed) {
    const item = catalogueItems.value.find(record => record.code === values.catalog_item_code)
    const costCode = costCodes.value.find(record => record.code === values.cost_code)
    const unit = units.value.find(record => record.code === values.unit_code)
    if (!item || !costCode || !unit) {
      error.value = `Paste row '${values.catalog_item_code}' needs an existing item, cost code, and unit code.`
      return
    }
    const sectionCode = values.hole_section_code
    const section = sectionCode
      ? holeSections.value.find(record => record.code.toUpperCase() === sectionCode.toUpperCase() || record.name.toUpperCase() === sectionCode.toUpperCase())
      : undefined
    if (sectionCode && !section) {
      error.value = `Section '${sectionCode}' is not configured. Add it under Master Data › Hole Sections first.`
      return
    }
    const line = {
      ...blankLine(),
      line_number: Math.max(
        lines.value.reduce((max, row) => Math.max(max, row.line_number), 0),
        created.reduce((max, row) => Math.max(max, row.line_number), 0),
      ) + 1,
      catalog_item_id: item.id,
      cost_code_id: costCode.id,
      quantity: values.quantity || '0',
      unit_id: unit.id,
      hole_section_id: section?.id ?? '',
      planned_duration_days: values.planned_duration_days ?? '',
    }
    line.rate_basis = defaultRateBasisFor(item.item_type, item.rate_basis ?? null)
    syncComputedQuantity(line)
    created.push(line)
  }
  lines.value.unshift(...created)
  pasteText.value = ''
  pasteVisible.value = false
  success.value = `${created.length} rows added from the clipboard. Review them, then choose Save.`
}

function missingRequired(line: EditableAfeLine): string[] {
  const missing: string[] = []
  if (!line.catalog_item_id) missing.push('Item')
  if (!line.cost_code_id) missing.push('Cost code')
  if (!line.unit_id) missing.push('Unit')
  if (needsSection(line) && !line.hole_section_id) missing.push('Section (charged per section)')
  if (isConsumptionLine(line) && (!line.daily_consumption || !line.planned_duration_days)) {
    missing.push('Usage per day and planned days (charged on daily usage)')
  }
  if (isOverridden(line) && !line.quantity_override_reason.trim()) {
    missing.push('Override reason (quantity differs from the computed total)')
  }
  return missing
}

async function saveLines(): Promise<void> {
  error.value = null
  success.value = null
  for (const line of lines.value) {
    const missing = missingRequired(line)
    if (missing.length) {
      error.value = `Complete every row before saving — line ${line.line_number} needs: ${missing.join(', ')}.`
      return
    }
  }
  saving.value = true
  try {
    const newRows = lines.value.filter(line => line._state === 'new')
    const changedRows = lines.value.filter(line => line._state === 'dirty' && line.id)
    if (newRows.length) {
      const payload = newRows.map(toPayload)
      const validation = await api.validateLines(selectedAfeId.value, payload)
      if (!validation.valid) {
        throw new Error(validation.errors.map(item => `Row ${item.row_index + 1}: ${item.message}`).join('; '))
      }
      await api.bulkCreateLines(selectedAfeId.value, payload)
    }
    if (changedRows.length) {
      await api.bulkUpdateLines(changedRows.map(line => ({ id: line.id, ...toPayload(line) })))
    }
    success.value = `${newRows.length + changedRows.length} rows saved.`
    await loadLines()
    await loadAfes()
  }
  catch (caught: unknown) {
    error.value = caught instanceof Error ? caught.message : 'The lines could not be saved.'
  }
  finally { saving.value = false }
}

async function submitAfe(): Promise<void> {
  error.value = null
  success.value = null
  submitting.value = true
  try {
    selectedAfe.value = await api.submit(selectedAfeId.value)
    lines.value = selectedAfe.value.items.map(toEditable)
    success.value = 'AFE submitted. Open the Cost Builder to generate the cost build from it.'
    await loadAfes()
  }
  catch (caught: unknown) {
    error.value = caught instanceof Error ? caught.message : 'The AFE could not be submitted.'
  }
  finally { submitting.value = false }
}

async function download(kind: 'export' | 'template'): Promise<void> {
  if (!selectedAfeId.value) return
  const blob = kind === 'export' ? await api.export(selectedAfeId.value) : await api.template(selectedAfeId.value)
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = `afe-${kind}.xlsx`
  anchor.click()
  URL.revokeObjectURL(url)
}

/* --------------------------------------------------------------- loading ---- */
const filteredWells = computed(() => (projectFilter.value ? wells.value.filter(well => well.project_id === projectFilter.value) : wells.value))
const filteredAfes = computed(() => afes.value.filter(afe =>
  (!wellFilter.value || afe.well_id === wellFilter.value)
  && (!statusFilter.value || afe.status === statusFilter.value),
))

const activeProjectOptions = computed(() => projects.value.filter(project => project.is_active))
const wellOptions = computed(() => filteredWells.value.filter(well => well.is_active))
const wellName = (id: string): string => wells.value.find(well => well.id === id)?.code ?? '—'

const WELL_STATUSES = [
  { label: 'Planning', value: 'planning' },
  { label: 'Active', value: 'active' },
  { label: 'Suspended', value: 'suspended' },
  { label: 'Completed', value: 'completed' },
  { label: 'Abandoned', value: 'abandoned' },
]

async function openAfe(id: string): Promise<void> {
  selectedAfeId.value = id
  await loadLines()
}

async function loadLines(): Promise<void> {
  if (!selectedAfeId.value) {
    selectedAfe.value = null
    lines.value = []
    return
  }
  loadingLines.value = true
  error.value = null
  try {
    const detail = await api.getAfe(selectedAfeId.value)
    selectedAfe.value = detail
    lines.value = detail.items.map(toEditable)
  }
  catch (caught: unknown) {
    error.value = caught instanceof Error ? caught.message : 'The AFE lines could not be loaded.'
  }
  finally { loadingLines.value = false }
}

async function loadAfes(): Promise<void> {
  const page = await api.listAfes()
  afes.value = page.items
}

async function loadAll(): Promise<void> {
  loading.value = true
  error.value = null
  try {
    const [projectPage, wellPage, afePage, catalogue, codePage, unitPage, sectionPage] = await Promise.all([
      api.listProjects(),
      api.listWells(),
      api.listAfes(),
      Promise.all([
        master.list('services'),
        master.list('tangibles'),
        master.list('materials'),
        master.list('equipment'),
        master.list('mud-chemicals'),
        master.list('cement-additives'),
      ]),
      master.list('cost-codes'),
      master.list('units'),
      master.list('hole-sections'),
    ])
    projects.value = projectPage.items
    wells.value = wellPage.items
    afes.value = afePage.items
    catalogueItems.value = catalogue.flatMap(page => page.items)
    costCodes.value = codePage.items
    units.value = unitPage.items
    holeSections.value = sectionPage.items.filter(section => section.is_active)
  }
  catch (caught: unknown) {
    error.value = caught instanceof Error ? caught.message : 'The AFE workspace could not be loaded.'
  }
  finally { loading.value = false }
}

watch(selectedAfeId, () => void loadLines())

onMounted(() => void loadAll())
</script>

<template>
  <div class="library-page">
    <PageHeader
      title="AFE"
      description="Register the project and well, then build the AFE line by line. Each line records how it is charged — daily, per section, per service, fixed, per unit, or on daily usage for chemicals — and submitted AFEs feed the Cost Builder."
    >
      <template #actions>
        <Button label="New AFE" icon="pi pi-plus" @click="openAfeDialog()" />
      </template>
    </PageHeader>

    <Message v-if="success" severity="success" :closable="true" @close="success = null">{{ success }}</Message>
    <Message v-if="error" severity="error" :closable="true" @close="error = null">{{ error }}</Message>

    <!-- AFE lines: the heart of the page -->
    <section class="afe-section bulk-grid-panel">
      <div class="grid-toolbar">
        <div class="afe-picker">
          <strong>AFE lines</strong>
          <Select
            v-model="selectedAfeId"
            :options="filteredAfes"
            option-value="id"
            placeholder="Select an AFE to enter its lines"
            filter
            show-clear
            style="width: 320px"
            data-testid="afe-picker"
          >
            <template #option="{ option }">{{ option.code }} — {{ option.title }} ({{ wellName(option.well_id) }})</template>
            <template #value="{ value }">
              <span v-if="value">{{ afes.find(afe => afe.id === value)?.code }} — {{ afes.find(afe => afe.id === value)?.title }}</span>
              <span v-else>Select an AFE to enter its lines</span>
            </template>
          </Select>
          <Tag v-if="selectedAfe" :value="selectedAfe.status" :severity="selectedAfe.status === 'submitted' ? 'success' : 'warn'" />
        </div>
        <div class="grid-toolbar__actions">
          <Button label="Add row" icon="pi pi-plus" :disabled="!isDraft" @click="addLine" />
          <Button label="Paste" icon="pi pi-clipboard" text :disabled="!isDraft" @click="pasteVisible = true" />
          <Button label="Template" icon="pi pi-file-excel" text :disabled="!isDraft" @click="download('template')" />
          <Button label="Export" icon="pi pi-download" text :disabled="!selectedAfeId" @click="download('export')" />
          <Button :label="pendingCount ? `Save ${pendingCount}` : 'Save'" icon="pi pi-save" :disabled="!isDraft || !pendingCount" :loading="saving" @click="saveLines" />
          <Button label="Submit" icon="pi pi-send" severity="secondary" :disabled="!isDraft || !lines.length" :loading="submitting" @click="submitAfe" />
        </div>
      </div>

      <Message v-if="selectedAfe && !isDraft" severity="info" :closable="false">
        This AFE is submitted and read-only. Further changes must be raised on a new revision.
      </Message>

      <DataTable
        :value="lines"
        :loading="loadingLines"
        data-key="id"
        striped-rows
        show-gridlines
        size="small"
        scrollable
        scroll-height="520px"
        class="afe-lines"
      >
        <Column field="line_number" header="#" :style="{ width: '60px' }" />
        <Column header="Item" :style="{ minWidth: '230px' }">
          <template #body="{ data }">
            <Select
              v-model="data.catalog_item_id"
              :options="catalogueItems"
              option-label="name"
              option-value="id"
              filter
              show-clear
              fluid
              :disabled="!isDraft"
              @change="onItemChange(data)"
            >
              <template #option="{ option }">{{ option.item_type }} · {{ option.code }} — {{ option.name }}</template>
            </Select>
          </template>
        </Column>
        <Column header="Cost code" :style="{ width: '150px' }">
          <template #body="{ data }">
            <Select v-model="data.cost_code_id" :options="costCodes" option-label="code" option-value="id" filter show-clear fluid :disabled="!isDraft" @change="markDirty(data)" />
          </template>
        </Column>
        <Column header="Rate basis" :style="{ width: '160px' }">
          <template #body="{ data }">
            <Select
              v-model="data.rate_basis"
              :options="basisOptionsFor(data)"
              option-label="label"
              option-value="value"
              fluid
              :disabled="!isDraft"
              data-testid="rate-basis"
              @change="onBasisChange(data)"
            />
          </template>
        </Column>
        <Column header="Section" :style="{ width: '170px' }">
          <template #body="{ data }">
            <Select
              v-model="data.hole_section_id"
              :options="holeSections"
              option-value="id"
              filter
              show-clear
              fluid
              :disabled="!isDraft"
              :invalid="needsSection(data) && !data.hole_section_id"
              :placeholder="needsSection(data) ? 'Required' : 'Section'"
              data-testid="hole-section"
              @change="markDirty(data)"
            >
              <template #option="{ option }">{{ option.code }} — {{ option.name }}</template>
              <template #value="{ value }">
                <span v-if="value">{{ holeSections.find(section => section.id === value)?.code }}</span>
                <span v-else class="afe-placeholder">{{ needsSection(data) ? 'Required' : 'Section' }}</span>
              </template>
            </Select>
          </template>
        </Column>
        <Column header="Usage / day" :style="{ width: '120px' }">
          <template #body="{ data }">
            <InputNumber
              v-if="isConsumptionLine(data)"
              v-model="data.daily_consumption"
              :min="0"
              :max-fraction-digits="4"
              fluid
              :disabled="!isDraft"
              @input="onConsumptionChange(data)"
            />
            <span v-else class="afe-na">—</span>
          </template>
        </Column>
        <Column header="Planned days" :style="{ width: '120px' }">
          <template #body="{ data }">
            <InputNumber v-model="data.planned_duration_days" :min="0" :max-fraction-digits="4" fluid :disabled="!isDraft" @input="onConsumptionChange(data)" />
          </template>
        </Column>
        <Column header="Qty" :style="{ width: '135px' }">
          <template #body="{ data }">
            <InputNumber v-model="data.quantity" :min="0" :max-fraction-digits="4" fluid :disabled="!isDraft" @input="markDirty(data)" />
            <small v-if="isOverridden(data)" class="afe-hint afe-hint--warn">Overrides {{ computedQuantityFor(data) }}</small>
            <small v-else-if="isConsumptionLine(data) && computedQuantityFor(data) !== null" class="afe-hint">Computed</small>
          </template>
        </Column>
        <Column header="Override reason" :style="{ minWidth: '170px' }">
          <template #body="{ data }">
            <InputText
              v-if="isConsumptionLine(data)"
              v-model="data.quantity_override_reason"
              fluid
              :disabled="!isDraft"
              :invalid="isOverridden(data) && !data.quantity_override_reason.trim()"
              placeholder="Why the total differs"
              @input="markDirty(data)"
            />
            <span v-else class="afe-na">—</span>
          </template>
        </Column>
        <Column header="Unit" :style="{ width: '120px' }">
          <template #body="{ data }">
            <Select v-model="data.unit_id" :options="units" option-label="code" option-value="id" filter show-clear fluid :disabled="!isDraft" @change="markDirty(data)" />
          </template>
        </Column>
        <Column header="Depth from" :style="{ width: '110px' }">
          <template #body="{ data }">
            <InputNumber v-model="data.planned_depth_from" :min="0" :max-fraction-digits="4" fluid :disabled="!isDraft" @input="markDirty(data)" />
          </template>
        </Column>
        <Column header="Depth to" :style="{ width: '110px' }">
          <template #body="{ data }">
            <InputNumber v-model="data.planned_depth_to" :min="0" :max-fraction-digits="4" fluid :disabled="!isDraft" @input="markDirty(data)" />
          </template>
        </Column>
        <Column header="Depth unit" :style="{ width: '115px' }">
          <template #body="{ data }">
            <Select v-model="data.depth_unit_id" :options="units" option-label="code" option-value="id" filter show-clear fluid :disabled="!isDraft" @change="markDirty(data)" />
          </template>
        </Column>
        <Column header="Notes" :style="{ minWidth: '150px' }">
          <template #body="{ data }">
            <InputText v-model="data.notes" fluid :disabled="!isDraft" @input="markDirty(data)" />
          </template>
        </Column>
        <Column header="" :style="{ width: '60px' }">
          <template #body="{ data }">
            <Button icon="pi pi-trash" size="small" text severity="danger" aria-label="Remove line" :disabled="!isDraft" @click="removeLine(data)" />
          </template>
        </Column>
        <template #empty>
          <div class="eg__empty">
            <i class="pi pi-inbox" aria-hidden="true" />
            <p v-if="!selectedAfeId"><strong>Pick an AFE above</strong></p>
            <p v-else><strong>No lines yet.</strong></p>
            <p v-if="!selectedAfeId">Or create one with “New AFE” to start entering lines.</p>
            <p v-else>Add a row to start building the well's scope.</p>
          </div>
        </template>
      </DataTable>
    </section>

    <!-- AFEs -->
    <section class="afe-section bulk-grid-panel">
      <div class="grid-toolbar">
        <div>
          <strong>AFEs</strong><small class="toolbar-note">Every AFE raised against a well. Submitted AFEs become cost builds.</small>
          <Select v-model="wellFilter" :options="wellOptions" option-label="code" option-value="id" placeholder="All wells" show-clear filter style="width: 170px; margin-left: 1rem" />
          <Select v-model="statusFilter" :options="[{ label: 'Draft', value: 'draft' }, { label: 'Submitted', value: 'submitted' }]" option-label="label" option-value="value" placeholder="All statuses" show-clear style="width: 160px; margin-left: 0.5rem" />
        </div>
        <div class="grid-toolbar__actions">
          <Button label="New AFE" icon="pi pi-plus" @click="openAfeDialog()" />
        </div>
      </div>
      <DataTable :value="filteredAfes" :loading="loading" data-key="id" striped-rows show-gridlines size="small" :rows="10" paginator class="afe-table">
        <Column field="code" header="Code" sortable />
        <Column field="title" header="Title" sortable />
        <Column header="Well">
          <template #body="{ data }">{{ wellName(data.well_id) }}</template>
        </Column>
        <Column field="item_count" header="Lines">
          <template #body="{ data }">{{ data.item_count }}</template>
        </Column>
        <Column header="Status">
          <template #body="{ data }">
            <Tag :value="data.status" :severity="data.status === 'submitted' ? 'success' : 'warn'" />
          </template>
        </Column>
        <Column header="Actions" :style="{ width: '200px' }">
          <template #body="{ data }">
            <Button icon="pi pi-folder-open" size="small" text severity="secondary" aria-label="Open AFE" @click="openAfe(data.id)" />
            <Button icon="pi pi-pencil" size="small" text severity="secondary" aria-label="Edit AFE" :disabled="data.status === 'submitted'" @click="openAfeDialog(data)" />
            <Button icon="pi pi-ban" size="small" text severity="danger" aria-label="Delete AFE" :disabled="data.status === 'submitted'" @click="deactivateAfe(data)" />
          </template>
        </Column>
        <template #empty>No AFEs yet — create one for a well, then enter its lines above.</template>
      </DataTable>
    </section>

    <!-- Projects and wells -->
    <section class="afe-section bulk-grid-panel">
      <div class="grid-toolbar">
        <div><strong>Projects</strong><small class="toolbar-note">The top-level grouping every well belongs to.</small></div>
        <div class="grid-toolbar__actions">
          <Button label="Add project" icon="pi pi-plus" @click="openProjectDialog()" />
        </div>
      </div>
      <DataTable :value="projects" data-key="id" striped-rows show-gridlines size="small" :rows="5" paginator class="afe-table">
        <Column field="code" header="Code" sortable />
        <Column field="name" header="Name" sortable />
        <Column field="description" header="Description" />
        <Column header="Status">
          <template #body="{ data }">
            <Tag :value="data.is_active ? 'Active' : 'Inactive'" :severity="data.is_active ? 'success' : 'secondary'" />
          </template>
        </Column>
        <Column header="Actions" :style="{ width: '160px' }">
          <template #body="{ data }">
            <Button icon="pi pi-pencil" size="small" text severity="secondary" aria-label="Edit project" @click="openProjectDialog(data)" />
            <Button icon="pi pi-ban" size="small" text severity="danger" aria-label="Deactivate project" @click="deactivateProject(data)" />
          </template>
        </Column>
        <template #empty>No projects yet — create the first one to start entering well data.</template>
      </DataTable>
    </section>

    <section class="afe-section bulk-grid-panel">
      <div class="grid-toolbar">
        <div>
          <strong>Wells</strong><small class="toolbar-note">The well itself: rig, status, and planned dates.</small>
          <Select v-model="projectFilter" :options="projects" option-label="code" option-value="id" placeholder="All projects" show-clear filter style="width: 180px; margin-left: 1rem" />
        </div>
        <div class="grid-toolbar__actions">
          <Button label="Add well" icon="pi pi-plus" @click="openWellDialog()" />
        </div>
      </div>
      <DataTable :value="filteredWells" data-key="id" striped-rows show-gridlines size="small" :rows="5" paginator class="afe-table">
        <Column field="code" header="Code" sortable />
        <Column field="name" header="Name" sortable />
        <Column header="Project">
          <template #body="{ data }">{{ data.project_code }}</template>
        </Column>
        <Column field="rig_name" header="Rig">
          <template #body="{ data }">{{ data.rig_name ?? '—' }}</template>
        </Column>
        <Column field="status" header="Status" sortable>
          <template #body="{ data }">
            <Tag :value="data.status.replace('_', ' ')" :severity="data.status === 'active' ? 'success' : 'info'" />
          </template>
        </Column>
        <Column field="spud_date" header="Spud date">
          <template #body="{ data }">{{ data.spud_date ?? '—' }}</template>
        </Column>
        <Column header="Actions" :style="{ width: '160px' }">
          <template #body="{ data }">
            <Button icon="pi pi-pencil" size="small" text severity="secondary" aria-label="Edit well" @click="openWellDialog(data)" />
            <Button icon="pi pi-ban" size="small" text severity="danger" aria-label="Deactivate well" @click="deactivateWell(data)" />
          </template>
        </Column>
        <template #empty>No wells found for the current filters.</template>
      </DataTable>
    </section>

    <!-- Project dialog -->
    <Dialog v-model:visible="projectDialog" modal :header="projectForm.id ? 'Edit project' : 'Add project'" :style="{ width: '480px' }">
      <div class="form-stack">
        <label>Code<InputText v-model="projectForm.code" fluid placeholder="e.g. PG-2026-01" /></label>
        <label>Name<InputText v-model="projectForm.name" fluid placeholder="e.g. North Sea Campaign" /></label>
        <label>Description<Textarea v-model="projectForm.description" rows="3" fluid /></label>
      </div>
      <template #footer>
        <Button label="Cancel" severity="secondary" text @click="projectDialog = false" />
        <Button label="Create project" icon="pi pi-check" :loading="saving" :disabled="!projectForm.code.trim() || !projectForm.name.trim()" @click="saveProject" />
      </template>
    </Dialog>

    <!-- Well dialog -->
    <Dialog v-model:visible="wellDialog" modal :header="wellForm.id ? 'Edit well' : 'Add well'" :style="{ width: '520px' }">
      <div class="form-stack">
        <label>Project<Select v-model="wellForm.project_id" :options="activeProjectOptions" option-label="code" option-value="id" placeholder="Select project" filter fluid /></label>
        <label>Code<InputText v-model="wellForm.code" fluid placeholder="e.g. W-101" /></label>
        <label>Name<InputText v-model="wellForm.name" fluid placeholder="e.g. Well 101 (Alpha)" /></label>
        <label>Rig<InputText v-model="wellForm.rig_name" fluid placeholder="e.g. Rig 9" /></label>
        <label>Status<Select v-model="wellForm.status" :options="WELL_STATUSES" option-label="label" option-value="value" fluid /></label>
        <div class="form-row">
          <label>Spud date<DatePicker v-model="wellForm.spud_date" date-format="yy-mm-dd" show-icon fluid /></label>
          <label>Completion date<DatePicker v-model="wellForm.completion_date" date-format="yy-mm-dd" show-icon fluid /></label>
        </div>
        <label>Description<Textarea v-model="wellForm.description" rows="2" fluid /></label>
      </div>
      <template #footer>
        <Button label="Cancel" severity="secondary" text @click="wellDialog = false" />
        <Button label="Create well" icon="pi pi-check" :loading="saving" :disabled="!wellForm.project_id || !wellForm.code.trim() || !wellForm.name.trim()" @click="saveWell" />
      </template>
    </Dialog>

    <!-- AFE dialog -->
    <Dialog v-model:visible="afeDialog" modal :header="afeForm.id ? 'Edit AFE' : 'New AFE'" :style="{ width: '500px' }">
      <div class="form-stack">
        <label>Well<Select v-model="afeForm.well_id" :options="wellOptions" option-label="code" option-value="id" placeholder="Select well" filter fluid /></label>
        <label>AFE code<InputText v-model="afeForm.code" fluid placeholder="e.g. AFE-W101-01" /></label>
        <label>Title<InputText v-model="afeForm.title" fluid placeholder="e.g. W101 Drilling & Completion Scope" /></label>
        <label>Description<Textarea v-model="afeForm.description" rows="3" fluid /></label>
      </div>
      <template #footer>
        <Button label="Cancel" severity="secondary" text @click="afeDialog = false" />
        <Button label="Create and open" icon="pi pi-check" :loading="saving" :disabled="!afeForm.well_id || !afeForm.code.trim() || !afeForm.title.trim()" @click="saveAfe" />
      </template>
    </Dialog>

    <!-- Paste dialog -->
    <Dialog v-model:visible="pasteVisible" modal header="Paste AFE lines" :style="{ width: '720px' }">
      <p class="afe-paste-hint">
        Copy cells from your workbook in this column order: item code, item type,
        cost code, quantity, unit code, section code, planned days. The section
        must already exist under Master Data › Hole Sections.
      </p>
      <Textarea v-model="pasteText" rows="10" fluid autofocus placeholder="Paste tab-separated rows here" />
      <template #footer>
        <Button label="Cancel" severity="secondary" text @click="pasteVisible = false" />
        <Button label="Apply rows" icon="pi pi-check" :disabled="!pasteText.trim()" @click="applyPaste" />
      </template>
    </Dialog>
  </div>
</template>

<style scoped>
.afe-section {
  margin-bottom: 1.25rem;
  padding: 1rem;
}

.afe-table,
.afe-lines {
  margin-top: 0.75rem;
}

.afe-picker {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.afe-hint {
  display: block;
  margin-top: 2px;
  font-size: 0.68rem;
  color: var(--app-muted);
}

.afe-hint--warn {
  color: var(--app-orange);
}

.afe-na,
.afe-placeholder {
  color: var(--app-muted);
}

.form-row {
  display: flex;
  gap: 1rem;
}

.form-row label {
  flex: 1;
}
</style>
