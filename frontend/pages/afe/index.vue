<script setup lang="ts">
/**
 * AFE — Authorisation for Expenditure, organised as tabs under one page.
 *
 * AFE is the financial and technical backbone for costing.
 * Projects and wells are registered first. On the AFEs tab, the user establishes
 * the AFE header, budget amount, hole sections, phases, planned days, and depths.
 * Phases are read from master data; they are not configured inside the AFE.
 *
 * AFE lines are built strictly from the classification: Primary Category →
 * Secondary Category → catalogue item.
 *
 * Submitted AFEs can be reopened for revision with mandatory audit remarks,
 * allowing edits scoped strictly to that well before resubmission.
 *
 * On the AFE Lines tab, items are planned against the configured sections and
 * rate bases without duplicating section/day/depth inputs per line.
 */
import { computed, onMounted, ref, watch } from 'vue'
import Button from 'primevue/button'
import Checkbox from 'primevue/checkbox'
import Column from 'primevue/column'
import DataTable from 'primevue/datatable'
import DatePicker from 'primevue/datepicker'
import Dialog from 'primevue/dialog'
import InputNumber from 'primevue/inputnumber'
import InputText from 'primevue/inputtext'
import Message from 'primevue/message'
import Select from 'primevue/select'
import Tab from 'primevue/tab'
import TabList from 'primevue/tablist'
import TabPanel from 'primevue/tabpanel'
import TabPanels from 'primevue/tabpanels'
import Tabs from 'primevue/tabs'
import Tag from 'primevue/tag'
import Textarea from 'primevue/textarea'
import PageHeader from '~/components/design-system/PageHeader.vue'
import { escapeHtml, formatMoneyCell, printDocument } from '~/utils/printDocument'
import type {
  AfeAuditLogRecord,
  AfeLineRecord,
  AfeRecord,
  AfeSectionRecord,
  DrillingPhaseRecord,
  EditableAfeLine,
  EditableAfeSection,
  ProjectRecord,
  RateBasis,
  WellRecord,
} from '~/types/afe'
import type { GridSelectOption } from '~/types/grid'
import type { MasterDataRecord } from '~/types/masterData'
import { SLOT } from '~/types/reference'

definePageMeta({ middleware: 'auth' })

const api = useAfe()
const estimatesApi = useAfeEstimates()
const master = useMasterData()

const projects = ref<ProjectRecord[]>([])
const wells = ref<WellRecord[]>([])
const afes = ref<AfeRecord[]>([])
const phases = ref<DrillingPhaseRecord[]>([])

/**
 * AFE lines are built from the classification and nothing else: the Primary
 * Category narrows the Secondary Categories, and the Secondary Category
 * narrows the catalogue items a line may reference. The options come from the
 * dropdown registry, so a super administrator can repoint them without a code
 * change.
 */
const references = useReferenceOptions()
const primaryCategoryOptions = ref<GridSelectOption[]>([])
const secondaryOptionsByPrimary = ref<Record<string, GridSelectOption[]>>({})
const costCodes = ref<MasterDataRecord[]>([])
const costCategories = ref<MasterDataRecord[]>([])
const units = ref<MasterDataRecord[]>([])
const holeSections = ref<MasterDataRecord[]>([])

const projectFilter = ref<string | null>(null)
const wellFilter = ref<string | null>(null)
const statusFilter = ref<string | null>(null)

const activeTab = ref<string>('projects')

const selectedAfeId = ref<string>('')
const selectedAfe = ref<AfeRecord | null>(null)
const lines = ref<EditableAfeLine[]>([])

const loading = ref(false)
const loadingLines = ref(false)
const saving = ref(false)
const submitting = ref(false)
const printingAfe = ref(false)
const reopening = ref(false)
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
  await loadAll()
}

async function deactivateProject(record: ProjectRecord): Promise<void> {
  if (!window.confirm(`Delete project ${record.code}? Linked wells must be deleted first. This cannot be undone.`)) return
  error.value = null
  try { await api.deleteProject(record.id) }
  catch (caught: unknown) {
    error.value = caught instanceof Error ? caught.message : 'The project could not be deleted.'
    return
  }
  success.value = `Project ${record.code} deleted.`
  await loadAll()
}

async function recoverProject(record: ProjectRecord): Promise<void> {
  error.value = null
  try { await api.recoverProject(record.id) }
  catch (caught: unknown) {
    error.value = caught instanceof Error ? caught.message : 'The project could not be recovered.'
    return
  }
  success.value = `Project ${record.code} recovered.`
  await loadAll()
}

async function hardDeleteProject(record: ProjectRecord): Promise<void> {
  if (!window.confirm(`Permanently delete project ${record.code}? This cannot be undone. Projects with wells cannot be permanently deleted — delete their wells first.`)) return
  error.value = null
  try { await api.hardDeleteProject(record.id) }
  catch (caught: unknown) {
    error.value = caught instanceof Error ? caught.message : 'The project could not be permanently deleted.'
    return
  }
  success.value = `Project ${record.code} permanently deleted.`
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
  if (!window.confirm(`Delete well ${record.code}? Linked AFEs must be deleted first. This cannot be undone.`)) return
  error.value = null
  try { await api.deleteWell(record.id) }
  catch (caught: unknown) {
    error.value = caught instanceof Error ? caught.message : 'The well could not be deleted.'
    return
  }
  success.value = `Well ${record.code} deleted.`
  await loadAll()
}

async function recoverWell(record: WellRecord): Promise<void> {
  error.value = null
  try { await api.recoverWell(record.id) }
  catch (caught: unknown) {
    error.value = caught instanceof Error ? caught.message : 'The well could not be recovered.'
    return
  }
  success.value = `Well ${record.code} recovered.`
  await loadAll()
}

async function hardDeleteWell(record: WellRecord): Promise<void> {
  if (!window.confirm(`Permanently delete well ${record.code}? This cannot be undone and removes its rates and daily cost entries. Wells with AFEs cannot be permanently deleted — delete those AFEs first.`)) return
  error.value = null
  try { await api.hardDeleteWell(record.id) }
  catch (caught: unknown) {
    error.value = caught instanceof Error ? caught.message : 'The well could not be permanently deleted.'
    return
  }
  success.value = `Well ${record.code} permanently deleted.`
  await loadAll()
}

/* ------------------------------------------------------- AFE ----------------- */
const afeDialog = ref(false)
const afeForm = ref({
  id: undefined as string | undefined,
  well_id: '',
  code: '',
  title: '',
  description: '',
  budget_amount: 0 as number,
  total_planned_days: 0 as number,
  total_planned_depth: 0 as number,
  depth_unit_id: '' as string,
  sections: [] as EditableAfeSection[],
})

const reopenDialog = ref(false)
const reopenTargetAfe = ref<AfeRecord | null>(null)
const reopenRemarks = ref('')

const auditHistoryDialog = ref(false)
const auditHistoryList = ref<AfeAuditLogRecord[]>([])
const auditTargetAfeTitle = ref('')


const deletedAfes = ref<AfeRecord[]>([])
const loadingDeleted = ref(false)

function openAfeDialog(record?: AfeRecord): void {
  const defaultWellId = wellFilter.value ?? wellOptions.value[0]?.id ?? ''
  const defaultDepthUnitId = units.value.find(u => u.code === 'M' || u.code === 'FT')?.id ?? units.value[0]?.id ?? ''

  if (record) {
    afeForm.value = {
      id: record.id,
      well_id: record.well_id,
      code: record.code,
      title: record.title,
      description: record.description ?? '',
      budget_amount: Number(record.budget_amount) || 0,
      total_planned_days: Number(record.total_planned_days) || 0,
      total_planned_depth: Number(record.total_planned_depth) || 0,
      depth_unit_id: record.depth_unit_id ?? defaultDepthUnitId,
      sections: (record.sections || []).map((s, idx) => ({
        id: s.id,
        sequence: s.sequence || (idx + 1),
        hole_section_id: s.hole_section_id ?? '',
        phase: s.phase || 'Drilling',
        planned_days: Number(s.planned_days) || 0,
        planned_depth_from: s.planned_depth_from !== null && s.planned_depth_from !== undefined ? Number(s.planned_depth_from) : null,
        planned_depth_to: s.planned_depth_to !== null && s.planned_depth_to !== undefined ? Number(s.planned_depth_to) : null,
        depth_unit_id: s.depth_unit_id ?? defaultDepthUnitId,
        phases: (s.phases?.length
          ? s.phases
          : [{
              id: '',
              afe_section_id: s.id,
              sequence: 1,
              phase: s.phase || 'Drilling',
              planned_days: Number(s.planned_days) || 0,
              notes: '',
              is_active: true,
            }]
        ).map((ph, phIdx) => ({
          id: ph.id,
          sequence: ph.sequence || (phIdx + 1),
          phase: ph.phase || 'Drilling',
          planned_days: Number(ph.planned_days) || 0,
          notes: ph.notes ?? '',
          is_active: ph.is_active,
        })),
        notes: s.notes ?? '',
        is_active: s.is_active,
      })),
    }
  }
  else {
    afeForm.value = {
      id: undefined,
      well_id: defaultWellId,
      code: '',
      title: '',
      description: '',
      budget_amount: 0,
      total_planned_days: 0,
      total_planned_depth: 0,
      depth_unit_id: defaultDepthUnitId,
      sections: [
        {
          sequence: 1,
          hole_section_id: holeSections.value[0]?.id ?? '',
          phase: 'Drilling',
          planned_days: 10,
          planned_depth_from: 0,
          planned_depth_to: 1000,
          depth_unit_id: defaultDepthUnitId,
          phases: [
            { sequence: 1, phase: phases.value[0]?.name ?? 'Drilling', planned_days: 10, notes: '', is_active: true },
          ],
          notes: '',
          is_active: true,
        },
      ],
    }
    recalculateSectionTotals()
  }
  afeDialog.value = true
}

function addSectionRow(): void {
  const defaultDepthUnitId = afeForm.value.depth_unit_id || units.value[0]?.id || ''
  const nextSeq = afeForm.value.sections.length + 1
  const prevTo = afeForm.value.sections.length
    ? (afeForm.value.sections[afeForm.value.sections.length - 1]?.planned_depth_to ?? 0)
    : 0
  afeForm.value.sections.push({
    sequence: nextSeq,
    hole_section_id: holeSections.value[0]?.id ?? '',
    phase: phases.value[0]?.name ?? 'Drilling',
    planned_days: 5,
    planned_depth_from: prevTo ?? 0,
    planned_depth_to: prevTo ? Number(prevTo) + 500 : 500,
    depth_unit_id: defaultDepthUnitId,
    phases: [
      { sequence: 1, phase: phases.value[0]?.name ?? 'Drilling', planned_days: 5, notes: '', is_active: true },
    ],
    notes: '',
    is_active: true,
  })
  recalculateSectionTotals()
}

function addPhaseRow(sectionIndex: number): void {
  const section = afeForm.value.sections[sectionIndex]
  if (!section) return
  section.phases.push({
    sequence: section.phases.length + 1,
    phase: phases.value[0]?.name ?? 'Drilling',
    planned_days: 1,
    notes: '',
    is_active: true,
  })
  recalculateSectionTotals()
}

function removePhaseRow(sectionIndex: number, phaseIndex: number): void {
  const section = afeForm.value.sections[sectionIndex]
  const phase = section?.phases?.[phaseIndex]
  if (!section || !phase) return
  if (!window.confirm(`Remove the phase "${phase.phase}" from this section? The change will be recorded when you save the AFE.`)) return
  section.phases.splice(phaseIndex, 1)
  if (!section.phases.length) {
    section.phases.push({
      sequence: 1,
      phase: phases.value[0]?.name ?? 'Drilling',
      planned_days: 0,
      notes: '',
      is_active: true,
    })
  }
  section.phases.forEach((ph, idx) => { ph.sequence = idx + 1 })
  recalculateSectionTotals()
}

function removeSectionRow(index: number): void {
  const section = afeForm.value.sections[index]
  if (!section) return
  const label = section.hole_section_id
    ? holeSections.value.find(item => item.id === section.hole_section_id)?.code ?? `section ${index + 1}`
    : `section ${index + 1}`
  if (!window.confirm(`Remove ${label} from this AFE? The change will be recorded when you save the AFE.`)) return
  afeForm.value.sections.splice(index, 1)
  afeForm.value.sections.forEach((s, idx) => { s.sequence = idx + 1 })
  recalculateSectionTotals()
}

function safeNumber(value: unknown, fallback = 0): number {
  const numeric = typeof value === 'number' ? value : Number(value)
  return Number.isFinite(numeric) ? numeric : fallback
}

function nullableNumber(value: unknown): number | null {
  if (value === null || value === undefined || value === '') return null
  const numeric = Number(value)
  return Number.isFinite(numeric) ? numeric : null
}

function sectionPlannedDays(section: EditableAfeSection): number {
  const phases = section.phases?.length ? section.phases : []
  return phases.reduce((sum, ph) => sum + safeNumber(ph.planned_days), 0)
}

function recalculateSectionTotals(): void {
  for (const section of afeForm.value.sections) {
    section.planned_days = sectionPlannedDays(section)
  }
  const totalDays = afeForm.value.sections.reduce((sum, s) => sum + safeNumber(s.planned_days), 0)
  const maxDepth = afeForm.value.sections.reduce((max, s) => Math.max(max, safeNumber(s.planned_depth_to)), 0)
  afeForm.value.total_planned_days = totalDays
  afeForm.value.total_planned_depth = maxDepth
}

async function saveAfe(): Promise<void> {
  saving.value = true
  error.value = null
  let createdId: string | null = null
  try {
    recalculateSectionTotals()
    const payload = {
      well_id: afeForm.value.well_id,
      code: afeForm.value.code,
      title: afeForm.value.title,
      description: afeForm.value.description || null,
      budget_amount: safeNumber(afeForm.value.budget_amount),
      total_planned_days: safeNumber(afeForm.value.total_planned_days),
      total_planned_depth: safeNumber(afeForm.value.total_planned_depth),
      depth_unit_id: afeForm.value.depth_unit_id || null,
      sections: afeForm.value.sections.map((s, idx) => ({
        sequence: idx + 1,
        hole_section_id: s.hole_section_id || null,
        phase: s.phase,
        planned_days: safeNumber(s.planned_days),
        phases: (s.phases?.length ? s.phases : []).map((ph, phIdx) => ({
          sequence: phIdx + 1,
          phase: ph.phase || 'Drilling',
          planned_days: safeNumber(ph.planned_days),
          notes: ph.notes || null,
          is_active: true,
        })),
        planned_depth_from: nullableNumber(s.planned_depth_from),
        planned_depth_to: nullableNumber(s.planned_depth_to),
        depth_unit_id: s.depth_unit_id || afeForm.value.depth_unit_id || null,
        notes: s.notes || null,
        is_active: true,
      })),
    }
    if (afeForm.value.id) await api.updateAfe(afeForm.value.id, payload)
    else createdId = (await api.createAfe(payload)).id
    afeDialog.value = false
    success.value = afeForm.value.id ? 'AFE and well section planning updated.' : 'AFE created successfully.'
  }
  catch (caught: unknown) {
    error.value = caught instanceof Error ? caught.message : 'The AFE could not be saved.'
    return
  }
  finally { saving.value = false }
  await loadAll()
  if (createdId) await openAfe(createdId)
}

function promptReopen(afe: AfeRecord): void {
  reopenTargetAfe.value = afe
  reopenRemarks.value = ''
  reopenDialog.value = true
}

async function confirmReopen(): Promise<void> {
  if (!reopenTargetAfe.value || !reopenRemarks.value.trim()) return
  reopening.value = true
  error.value = null
  try {
    const updated = await api.reopen(reopenTargetAfe.value.id, reopenRemarks.value.trim())
    reopenDialog.value = false
    success.value = `AFE ${updated.code} has been reopened for editing. You can now modify sections and lines.`
    await loadAll()
    if (selectedAfeId.value === updated.id) {
      await loadLines()
    }
  }
  catch (caught: unknown) {
    error.value = caught instanceof Error ? caught.message : 'Could not reopen AFE.'
  }
  finally { reopening.value = false }
}

function showAuditHistory(afe: AfeRecord): void {
  auditTargetAfeTitle.value = `${afe.code} — ${afe.title}`
  auditHistoryList.value = afe.audit_logs || []
  auditHistoryDialog.value = true
}

async function deactivateAfe(record: AfeRecord): Promise<void> {
  const confirmMsg = `Delete AFE ${record.code} permanently? Its AFE Cost Estimate and daily-cost links must no longer be in use.`
  if (!window.confirm(confirmMsg)) return
  try { await api.deleteAfe(record.id) }
  catch (caught: unknown) {
    error.value = caught instanceof Error ? caught.message : 'The AFE could not be deleted.'
    return
  }
  success.value = `AFE ${record.code} deleted permanently.`
  if (selectedAfeId.value === record.id) {
    selectedAfeId.value = ''
    selectedAfe.value = null
    lines.value = []
  }
  await loadAll()
  await loadDeletedAfes()
}

async function recoverAfe(record: AfeRecord): Promise<void> {
  if (!window.confirm(`Recover AFE ${record.code} from Deleted AFEs?`)) return
  error.value = null
  try {
    await api.recoverAfe(record.id)
    success.value = `AFE ${record.code} recovered successfully.`
    await loadAll()
    await loadDeletedAfes()
  } catch (caught: unknown) {
    error.value = caught instanceof Error ? caught.message : 'Could not recover AFE. Another active AFE may already exist.'
  }
}

async function hardDeleteAfe(record: AfeRecord): Promise<void> {
  if (!window.confirm(`Permanently delete AFE ${record.code}? This cannot be undone and will remove all its lines and sections.`)) return
  try { await api.hardDeleteAfe(record.id) }
  catch (caught: unknown) {
    error.value = caught instanceof Error ? caught.message : 'The AFE could not be permanently deleted.'
    return
  }
  success.value = `AFE ${record.code} permanently deleted.`
  await loadDeletedAfes()
}

/* ------------------------------------------------- AFE lines ----------------- */
/** Secondary categories under a primary, fetched once and reused. */
async function ensureSecondaryOptions(primaryId: string): Promise<void> {
  if (!primaryId || secondaryOptionsByPrimary.value[primaryId]) return
  secondaryOptionsByPrimary.value = { ...secondaryOptionsByPrimary.value, [primaryId]: await references.cascade(SLOT.afeLineSecondary, primaryId) }
}
function secondaryOptionsFor(line: EditableAfeLine): GridSelectOption[] { return secondaryOptionsByPrimary.value[line.primary_category_id] ?? [] }

function costCodeOptionsFor(line: EditableAfeLine): MasterDataRecord[] {
  if (!line.secondary_category_id) return []
  const categoryIds = new Set(costCategories.value.filter(category => category.secondary_category_id === line.secondary_category_id).map(category => category.id))
  return costCodes.value.filter(code => code.cost_category_id && categoryIds.has(code.cost_category_id))
}

function onPrimaryCategoryChange(line: EditableAfeLine): void {
  line.secondary_category_id = ''; line.cost_code_id = ''
  void ensureSecondaryOptions(line.primary_category_id); markDirty(line)
}
function onSecondaryCategoryChange(line: EditableAfeLine): void { line.cost_code_id = ''; markDirty(line) }
function onServiceTypeChange(line: EditableAfeLine): void {
  // A consumable is priced per unit in the estimate, while the quantity is
  // entered only on Daily Cost. Never switch it to a usage/day planner.
  if (line.service_type === 'consumable' || line.service_type === 'tangible') line.rate_basis = 'per_unit'
  else if (line.service_type === 'other') line.rate_basis = 'fixed'
  else line.rate_basis = 'daily'
  markDirty(line)
}

function basisOptionsFor(line: EditableAfeLine): { label: string, value: RateBasis }[] {
  if (line.service_type === 'consumable') return [{ label: 'Per unit (actual quantity in Daily Cost)', value: 'per_unit' }]
  if (line.service_type === 'tangible') return [
    { label: 'Per unit', value: 'per_unit' },
    { label: 'Fixed', value: 'fixed' },
  ]
  return [
    { label: 'Daily rate', value: 'daily' },
    { label: 'Per service / fixed', value: 'fixed' },
    { label: 'Per section', value: 'per_section' },
  ]
}

function needsSection(line: EditableAfeLine): boolean {
  return line.rate_basis === 'per_section' && !line.applies_to_all_sections
}

function onAllSectionsChange(line: EditableAfeLine): void {
  if (line.applies_to_all_sections) line.hole_section_id = ''
  markDirty(line)
}

/**
 * Per-section costing reads the section planned on this AFE. It prevents a
 * planner from selecting a section that does not belong to the current scope.
 */
function configuredAfeSections(): AfeSectionRecord[] {
  return (selectedAfe.value?.sections ?? []).filter(section => section.is_active && section.hole_section_id)
}

function sectionOptionDetail(holeSectionId: string | null | undefined): string {
  if (!holeSectionId) return ''
  const section = configuredAfeSections().find(candidate => candidate.hole_section_id === holeSectionId)
  if (!section) return ''
  const from = section.planned_depth_from != null ? Number(section.planned_depth_from) : null
  const to = section.planned_depth_to != null ? Number(section.planned_depth_to) : null
  return from !== null && to !== null
    ? `${from}–${to} ${selectedAfe.value?.depth_unit_code ?? ''}`.trim()
    : 'Configured on this AFE'
}

function sectionOptionsFor(line: EditableAfeLine): MasterDataRecord[] {
  if (!needsSection(line)) return holeSections.value
  const configuredIds = new Set(configuredAfeSections().map(section => section.hole_section_id).filter((id): id is string => Boolean(id)))
  return holeSections.value.filter(section => configuredIds.has(section.id) || section.id === line.hole_section_id)
}

function isCurrentAfeSection(holeSectionId: string | null | undefined): boolean {
  if (!holeSectionId) return false
  return configuredAfeSections().some(section => section.hole_section_id === holeSectionId)
}

function onBasisChange(line: EditableAfeLine): void {
  if (line.rate_basis === 'per_section' && !line.applies_to_all_sections && !line.hole_section_id) {
    const sections = configuredAfeSections()
    if (sections.length === 1 && sections[0]?.hole_section_id) line.hole_section_id = sections[0].hole_section_id
  }
  markDirty(line)
}

function nullableValue(value: unknown): unknown {
  return (value === '' || value === null || value === undefined) ? null : value
}

function toPayload(line: EditableAfeLine) {
  return {
    line_number: line.line_number,
    secondary_category_id: line.secondary_category_id,
    cost_code_id: line.cost_code_id,
    // Scope only: no planned quantity, UOM, usage/day, or duration belongs on
    // an AFE line. Actual consumable quantity is captured in Daily Cost.
    quantity: null,
    unit_id: null,
    service_type: line.service_type,
    hole_section_id: line.applies_to_all_sections ? null : nullableValue(line.hole_section_id),
    applies_to_all_sections: line.applies_to_all_sections,
    rate_basis: line.rate_basis,
    daily_consumption: null,
    quantity_override_reason: null,
    planned_duration_days: null,
    planned_depth_from: null,
    planned_depth_to: null,
    depth_unit_id: null,
    notes: nullableValue(line.notes),
    is_active: line.is_active,
  }
}

function toEditable(record: AfeLineRecord): EditableAfeLine {
  void ensureSecondaryOptions(record.primary_category_id ?? '')
  return {
    id: record.id,
    line_number: record.line_number,
    primary_category_id: record.primary_category_id ?? '',
    secondary_category_id: record.secondary_category_id ?? '',
    cost_code_id: record.cost_code_id,
    service_type: record.service_type ?? 'service',
    hole_section_id: record.hole_section_id ?? '',
    applies_to_all_sections: record.applies_to_all_sections,
    rate_basis: record.rate_basis === 'daily_consumption' ? 'per_unit' : record.rate_basis,
    notes: record.notes ?? '',
    is_active: record.is_active,
    _state: 'clean',
  }
}

const blankLine = (): EditableAfeLine => ({
  line_number: lines.value.reduce((max, line) => Math.max(max, line.line_number), 0) + 1,
  primary_category_id: '',
  secondary_category_id: '',
  cost_code_id: '',
  service_type: 'service',
  hole_section_id: '',
  applies_to_all_sections: false,
  rate_basis: 'daily',
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
    if (!window.confirm('Remove this unsaved AFE line? It will be discarded.')) return
    lines.value = lines.value.filter(candidate => candidate !== line)
    return
  }
  if (!window.confirm('Delete this AFE line permanently? This cannot be undone. Linked cost-estimate data must be removed first.')) return
  void api.deleteLine(String(line.id))
    .then(() => Promise.all([loadLines(), loadRemovedLines()]))
    .catch((caught: unknown) => {
      error.value = caught instanceof Error ? caught.message : 'The line could not be removed.'
    })
}

/* --------------------------------------------- removed line recovery -------- */
const removedLinesVisible = ref(false)
const removedLines = ref<AfeLineRecord[]>([])

async function loadRemovedLines(): Promise<void> {
  if (!selectedAfeId.value || !isDraft.value) {
    removedLines.value = []
    return
  }
  try {
    removedLines.value = await api.listRemovedLines(selectedAfeId.value)
  }
  catch {
    removedLines.value = []
  }
}

function openRemovedLines(): void {
  removedLinesVisible.value = true
}

async function recoverRemovedLine(line: AfeLineRecord): Promise<void> {
  error.value = null
  try {
    await api.recoverLine(line.id)
    removedLines.value = removedLines.value.filter(candidate => candidate.id !== line.id)
    await loadLines()
    if (!removedLines.value.length) removedLinesVisible.value = false
    success.value = `Line ${line.line_number} restored.`
  }
  catch (caught: unknown) {
    error.value = caught instanceof Error ? caught.message : 'The line could not be restored.'
  }
}

function missingRequired(line: EditableAfeLine): string[] {
  const missing: string[] = []
  if (!line.secondary_category_id) missing.push('Secondary category')
  if (!line.cost_code_id) missing.push('Cost code')
  if (needsSection(line) && !configuredAfeSections().length) {
    missing.push('Section (this AFE has no configured sections; add them on the AFEs tab)')
  }
  else if (needsSection(line) && !line.hole_section_id) {
    missing.push('Section (charged per section)')
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
    success.value = 'AFE submitted successfully. It feeds the AFE Cost Estimates and Daily Cost comparisons.'
    await loadAfes()
  }
  catch (caught: unknown) {
    error.value = caught instanceof Error ? caught.message : 'The AFE could not be submitted.'
  }
  finally { submitting.value = false }
}


/** Print a record-quality, well-scoped copy of the selected AFE. */
function money(value: string | number | null | undefined): string {
  return formatMoneyCell(value)
}

function sectionPhasesFor(section: AfeSectionRecord): { phase: string, planned_days: number | string, sequence: number, is_active: boolean }[] {
  const phases = section.phases?.length
    ? section.phases
    : [{ phase: section.phase, planned_days: section.planned_days, sequence: 1, is_active: true }]
  return phases.filter(ph => ph.is_active)
}

function lineRowsHtml(
  items: AfeLineRecord[],
  rateMap: Map<string, { unit_rate: number, estimated_amount: number }>,
): string {
  if (!items.length) return '<tr><td colspan="9">No AFE lines configured.</td></tr>'
  return items.map((item) => {
    const rate = rateMap.get(item.id)
    const estimatedRate = rate?.unit_rate ?? 0
    const estimated = rate?.estimated_amount ?? estimatedRate
    const sectionLabel = item.applies_to_all_sections ? 'All sections' : (item.hole_section_code ?? '—')
    return `
    <tr>
      <td class="num">${item.line_number}</td>
      <td>${escapeHtml(item.primary_category_name ?? item.primary_category_code ?? '—')}</td>
      <td>${escapeHtml(item.secondary_category_name ?? item.secondary_category_code ?? item.catalog_item_name ?? '—')}</td>
      <td>${escapeHtml(item.cost_code ?? '')}</td>
      <td>${escapeHtml(item.service_type)}</td>
      <td>${escapeHtml(item.rate_basis.replace(/_/g, ' '))}</td>
      <td>${escapeHtml(sectionLabel)}</td>
      <td class="num">${money(estimatedRate)}</td>
      <td class="num">${money(estimated)}</td>
    </tr>`
  }).join('')
}

async function printAfe(): Promise<void> {
  const afe = selectedAfe.value
  if (!afe) return
  if (pendingCount.value) {
    error.value = 'Save the pending AFE line changes before printing so the printout contains the current AFE record only.'
    return
  }

  printingAfe.value = true
  error.value = null
  const well = wells.value.find(candidate => candidate.id === afe.well_id)
  const project = projects.value.find(candidate => candidate.id === well?.project_id)

  try {
    // Browser print is client-side. Record the action before opening the
    // current AFE document so it is visible in the global and AFE audit logs.
    await api.recordPrint(afe.id)

    // Submitted AFEs can be priced. A draft AFE print remains a scope record;
    // it never calls a retired estimate/cost-builder module.
    let rateMap = new Map<string, { unit_rate: number, estimated_amount: number }>()
    let estimatedTotal = 0
    let pricedFootnote = 'Draft scope — submit this AFE to enter estimate rates.'
    if (afe.status === 'submitted') {
      try {
        const estimate = await estimatesApi.get(afe.id)
        estimatedTotal = Number(estimate.estimated_total) || 0
        rateMap = new Map(estimate.lines.map(line => [
          line.afe_line_id,
          { unit_rate: Number(line.unit_rate) || 0, estimated_amount: Number(line.estimated_amount) || 0 },
        ]))
        pricedFootnote = 'Estimate rates and totals come from the current AFE Cost Estimates module.'
      }
      catch {
        pricedFootnote = 'Submitted scope — estimate rates have not been saved yet.'
      }
    }

    const meta = [
      ['AFE Number', `${afe.code} (rev ${afe.revision_number})`],
      ['Well Name', `${well?.code ?? ''} — ${well?.name ?? ''}`],
      ['Rig Name', well?.rig_name ?? '—'],
      ['Project Name', `${project?.code ?? ''} — ${project?.name ?? ''}`],
      ['Title', afe.title],
      ['Status', afe.status],
      ['AFE Budget', money(afe.budget_amount)],
      ['Total Planned Days', `${Number(afe.total_planned_days || 0).toFixed(1)} days`],
      ['Total Planned Depth', `${Number(afe.total_planned_depth || 0).toFixed(0)} ${afe.depth_unit_code ?? ''}`],
      ['Submitted', afe.submitted_at ? new Date(afe.submitted_at).toLocaleString() : '—'],
    ]
    const metaHtml = meta
      .map(([label, value]) => `<div><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></div>`)
      .join('')

    const sectionRows = (afe.sections ?? []).map((section) => {
      const phaseRows = sectionPhasesFor(section)
      const span = phaseRows.length || 1
      return phaseRows.map((ph, index) => `
      <tr>
        ${index === 0 ? `<td rowspan="${span}">${escapeHtml(section.hole_section_code ?? '—')}</td>` : ''}
        ${index === 0 ? `<td class="num" rowspan="${span}">${section.planned_depth_from != null ? Number(section.planned_depth_from) : '—'}</td>` : ''}
        ${index === 0 ? `<td class="num" rowspan="${span}">${section.planned_depth_to != null ? Number(section.planned_depth_to) : '—'}</td>` : ''}
        <td>${escapeHtml(ph.phase)}</td>
        <td class="num">${Number(ph.planned_days)}</td>
        ${index === phaseRows.length - 1 ? `<td class="num" rowspan="${span}"><strong>${Number(section.planned_days || 0).toFixed(1)}</strong></td>` : ''}
      </tr>`).join('')
    }).join('')

    const configuredLineRows = lineRowsHtml(afe.items ?? [], rateMap)

    printDocument(`AFE ${afe.code}`, `
      <h1>AUTHORISATION FOR EXPENDITURE</h1>
      <p class="doc-subtitle">Current AFE scope using the classifications configured in Master Data. Consumable quantity and UOM are entered in Daily Cost, not in this document.</p>
      <div class="meta-grid">${metaHtml}</div>

      <h2>Sections &amp; phases</h2>
      <table>
        <thead><tr><th>Hole section</th><th class="num">Depth from</th><th class="num">Depth to</th><th>Phase</th><th class="num">Planned days</th><th class="num">Section total (days)</th></tr></thead>
        <tbody>${sectionRows || '<tr><td colspan="6">No sections configured.</td></tr>'}</tbody>
        <tfoot><tr class="total-row"><td colspan="4">Total planned days</td><td class="num" colspan="2">${Number(afe.total_planned_days || 0).toFixed(1)} days</td></tr></tfoot>
      </table>

      <h2>Configured AFE lines</h2>
      <table>
        <thead><tr><th class="num">#</th><th>Primary category</th><th>Secondary category</th><th>Cost code</th><th>Type</th><th>Costing method</th><th>Section</th><th class="num">Estimated total rate</th><th class="num">Estimated cost</th></tr></thead>
        <tbody>${configuredLineRows}</tbody>
        <tfoot><tr class="total-row"><td colspan="8">Total estimated cost</td><td class="num">${money(estimatedTotal)}</td></tr></tfoot>
      </table>

      <h2>Cost summary</h2>
      <table>
        <thead><tr><th>Component</th><th class="num">Amount</th></tr></thead>
        <tbody>
          <tr><td>AFE cost estimate</td><td class="num">${money(estimatedTotal)}</td></tr>
          <tr><td>AFE budget</td><td class="num">${money(afe.budget_amount)}</td></tr>
          <tr class="total-row"><td>Variance to budget</td><td class="num">${money(Number(afe.budget_amount || 0) - estimatedTotal)}</td></tr>
        </tbody>
      </table>

      <div class="signatures"><div>Prepared by</div><div>Reviewed by</div><div>Approved by</div></div>
      <p class="print-footer">Printed ${new Date().toLocaleString()} — ${escapeHtml(pricedFootnote)}</p>
    `)
  }
  catch (caught: unknown) {
    error.value = caught instanceof Error ? caught.message : 'The AFE could not be printed.'
  }
  finally { printingAfe.value = false }
}

/* --------------------------------------------------------------- loading ---- */
const showDeletedProjects = ref(false)
const showDeletedWells = ref(false)

const filteredWells = computed(() => (projectFilter.value ? wells.value.filter(well => well.project_id === projectFilter.value) : wells.value))
const deletedProjectCount = computed(() => projects.value.filter(project => !project.is_active).length)
const deletedWellCount = computed(() => filteredWells.value.filter(well => !well.is_active).length)
const visibleProjects = computed(() =>
  showDeletedProjects.value ? projects.value : projects.value.filter(project => project.is_active))
const visibleWells = computed(() =>
  showDeletedWells.value ? filteredWells.value : filteredWells.value.filter(well => well.is_active))
const filteredAfes = computed(() => afes.value.filter(afe =>
  (!wellFilter.value || afe.well_id === wellFilter.value)
  && (!statusFilter.value || afe.status === statusFilter.value),
))

const activeProjectOptions = computed(() => projects.value.filter(project => project.is_active))
const wellOptions = computed(() => filteredWells.value.filter(well => well.is_active))
const wellName = (id: string): string => wells.value.find(well => well.id === id)?.code ?? '—'
const unitCode = (id?: string | null): string => units.value.find(u => u.id === id)?.code ?? '—'

const WELL_STATUSES = [
  { label: 'Planning', value: 'planning' },
  { label: 'Active', value: 'active' },
  { label: 'Suspended', value: 'suspended' },
  { label: 'Completed', value: 'completed' },
  { label: 'Abandoned', value: 'abandoned' },
]

async function openAfe(id: string): Promise<void> {
  selectedAfeId.value = id
  activeTab.value = 'lines'
  await loadLines()
}

async function loadLines(): Promise<void> {
  if (!selectedAfeId.value) {
    selectedAfe.value = null
    lines.value = []
    removedLines.value = []
    return
  }
  loadingLines.value = true
  error.value = null
  try {
    const detail = await api.getAfe(selectedAfeId.value)
    selectedAfe.value = detail
    lines.value = detail.items.map(toEditable)
    await loadRemovedLines()
  }
  catch (caught: unknown) {
    error.value = caught instanceof Error ? caught.message : 'The AFE lines could not be loaded.'
  }
  finally { loadingLines.value = false }
}

async function loadAfes(): Promise<void> {
  const page = await api.listAfes(undefined, undefined, true)
  afes.value = page.items
}

async function loadDeletedAfes(): Promise<void> {
  loadingDeleted.value = true
  try {
    const page = await api.listDeletedAfes()
    deletedAfes.value = page.items
  } catch {
    deletedAfes.value = []
  } finally {
    loadingDeleted.value = false
  }
}

async function loadAll(): Promise<void> {
  loading.value = true
  error.value = null
  try {
    const [projectPage, wellPage, afePage, deletedPage, phaseList, codePage, categoryPage, unitPage, sectionPage] = await Promise.all([
      api.listProjects(),
      api.listWells(),
      api.listAfes(undefined, undefined, true),
      api.listDeletedAfes(),
      api.listDrillingPhases(),
      master.list('cost-codes'),
      master.list('cost-categories'),
      master.list('units'),
      master.list('hole-sections'),
    ])
    projects.value = projectPage.items
    wells.value = wellPage.items
    afes.value = afePage.items
    deletedAfes.value = deletedPage.items
    phases.value = phaseList
    costCodes.value = codePage.items
    costCategories.value = categoryPage.items
    units.value = unitPage.items
    holeSections.value = sectionPage.items.filter(section => section.is_active)
    primaryCategoryOptions.value = (await references.slot(SLOT.afeLinePrimary))
      .map(option => ({ label: option.label, value: option.value }))
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
      title="AFE & Well Scope"
      description="Configure projects, wells and AFE scope. Lines contain classification, cost code, type and section only; estimate rates are entered after submission, while actual consumable quantity is entered in Daily Cost."
    >
      <template #actions>
        <Button label="New AFE" icon="pi pi-plus" @click="openAfeDialog()" />
      </template>
    </PageHeader>

    <Message v-if="success" severity="success" :closable="true" @close="success = null">{{ success }}</Message>
    <Message v-if="error" severity="error" :closable="true" @close="error = null">{{ error }}</Message>

    <Tabs v-model:value="activeTab" class="afe-tabs">
      <TabList>
        <Tab value="projects">Projects</Tab>
        <Tab value="wells">Wells</Tab>
        <Tab value="afes">AFEs</Tab>
        <Tab value="lines">AFE Lines</Tab>
        <Tab value="deleted">Deleted AFEs ({{ deletedAfes.length }})</Tab>
      </TabList>
      <TabPanels>
        <!-- Projects -->
        <TabPanel value="projects">
          <section class="afe-section bulk-grid-panel">
            <div class="grid-toolbar">
              <div><strong>Projects</strong><small class="toolbar-note">The top-level grouping every well belongs to. Register projects before wells.</small></div>
              <div class="grid-toolbar__actions">
                <Button
                  :label="showDeletedProjects ? 'Hide deleted' : `Deleted (${deletedProjectCount})`"
                  icon="pi pi-trash"
                  text
                  severity="secondary"
                  :disabled="!deletedProjectCount && !showDeletedProjects"
                  @click="showDeletedProjects = !showDeletedProjects"
                />
                <Button label="Add project" icon="pi pi-plus" @click="openProjectDialog()" />
              </div>
            </div>
            <DataTable :value="visibleProjects" data-key="id" striped-rows show-gridlines size="small" :rows="10" paginator class="afe-table">
              <Column field="code" header="Code" sortable />
              <Column field="name" header="Name" sortable />
              <Column field="description" header="Description" />
              <Column header="Status">
                <template #body="{ data }">
                  <Tag :value="data.is_active ? 'Active' : 'Deleted'" :severity="data.is_active ? 'success' : 'danger'" />
                </template>
              </Column>
              <Column header="Actions" :style="{ width: '170px' }">
                <template #body="{ data }">
                  <template v-if="data.is_active">
                    <Button icon="pi pi-pencil" size="small" text severity="secondary" aria-label="Edit project" @click="openProjectDialog(data)" />
                    <Button icon="pi pi-trash" size="small" text severity="danger" aria-label="Delete project" title="Delete (recoverable)" @click="deactivateProject(data)" />
                  </template>
                  <template v-else>
                    <Button icon="pi pi-undo" size="small" text severity="success" aria-label="Recover project" title="Recover project" @click="recoverProject(data)" />
                    <Button icon="pi pi-trash" size="small" text severity="danger" aria-label="Permanently delete project" title="Delete forever" @click="hardDeleteProject(data)" />
                  </template>
                </template>
              </Column>
              <template #empty>No projects yet — create the first one to start entering well data.</template>
            </DataTable>
          </section>
        </TabPanel>

        <!-- Wells -->
        <TabPanel value="wells">
          <section class="afe-section bulk-grid-panel">
            <div class="grid-toolbar">
              <div>
                <strong>Wells</strong><small class="toolbar-note">The well itself: rig, status, and planned dates. Wells belong to a project.</small>
                <Select v-model="projectFilter" :options="projects" option-label="code" option-value="id" placeholder="All projects" show-clear filter style="width: 180px; margin-left: 1rem" />
              </div>
              <div class="grid-toolbar__actions">
                <Button
                  :label="showDeletedWells ? 'Hide deleted' : `Deleted (${deletedWellCount})`"
                  icon="pi pi-trash"
                  text
                  severity="secondary"
                  :disabled="!deletedWellCount && !showDeletedWells"
                  @click="showDeletedWells = !showDeletedWells"
                />
                <Button label="Add well" icon="pi pi-plus" @click="openWellDialog()" />
              </div>
            </div>
            <DataTable :value="visibleWells" data-key="id" striped-rows show-gridlines size="small" :rows="10" paginator class="afe-table">
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
              <Column header="Record">
                <template #body="{ data }">
                  <Tag :value="data.is_active ? 'Active' : 'Deleted'" :severity="data.is_active ? 'success' : 'danger'" />
                </template>
              </Column>
              <Column field="spud_date" header="Spud date">
                <template #body="{ data }">{{ data.spud_date ?? '—' }}</template>
              </Column>
              <Column header="Actions" :style="{ width: '170px' }">
                <template #body="{ data }">
                  <template v-if="data.is_active">
                    <Button icon="pi pi-pencil" size="small" text severity="secondary" aria-label="Edit well" @click="openWellDialog(data)" />
                    <Button icon="pi pi-trash" size="small" text severity="danger" aria-label="Delete well" title="Delete (recoverable)" @click="deactivateWell(data)" />
                  </template>
                  <template v-else>
                    <Button icon="pi pi-undo" size="small" text severity="success" aria-label="Recover well" title="Recover well" @click="recoverWell(data)" />
                    <Button icon="pi pi-trash" size="small" text severity="danger" aria-label="Permanently delete well" title="Delete forever" @click="hardDeleteWell(data)" />
                  </template>
                </template>
              </Column>
              <template #empty>No wells found for the current filters.</template>
            </DataTable>
          </section>
        </TabPanel>

        <!-- AFEs -->
        <TabPanel value="afes">
          <section class="afe-section bulk-grid-panel">
            <div class="grid-toolbar">
              <div>
                <strong>AFEs & Well Configuration</strong><small class="toolbar-note">AFE budget, section planning, days, and depths. Reopen submitted AFEs with remarks to revise.</small>
                <Select v-model="wellFilter" :options="wellOptions" option-label="code" option-value="id" placeholder="All wells" show-clear filter style="width: 170px; margin-left: 1rem" />
                <Select v-model="statusFilter" :options="[{ label: 'Draft', value: 'draft' }, { label: 'Submitted', value: 'submitted' }]" option-label="label" option-value="value" placeholder="All statuses" show-clear style="width: 160px; margin-left: 0.5rem" />
              </div>
              <div class="grid-toolbar__actions">
                <Button label="New AFE" icon="pi pi-plus" @click="openAfeDialog()" />
              </div>
            </div>
            <DataTable :value="filteredAfes" :loading="loading" data-key="id" striped-rows show-gridlines size="small" :rows="10" paginator class="afe-table">
              <Column field="code" header="AFE Code" sortable />
              <Column field="title" header="Title" sortable />
              <Column header="Well">
                <template #body="{ data }">{{ wellName(data.well_id) }}</template>
              </Column>
              <Column header="Budget Amount">
                <template #body="{ data }">
                  <strong>{{ Number(data.budget_amount || 0).toLocaleString(undefined, { minimumFractionDigits: 2 }) }}</strong>
                </template>
              </Column>
              <Column header="Planned Days">
                <template #body="{ data }">
                  {{ Number(data.total_planned_days || 0).toFixed(1) }} days
                </template>
              </Column>
              <Column header="Planned Depth">
                <template #body="{ data }">
                  {{ Number(data.total_planned_depth || 0).toFixed(0) }} {{ data.depth_unit_code || unitCode(data.depth_unit_id) }}
                </template>
              </Column>
              <Column field="item_count" header="Lines">
                <template #body="{ data }">{{ data.item_count }}</template>
              </Column>
              <Column header="Status">
                <template #body="{ data }">
                  <Tag :value="data.status" :severity="data.status === 'submitted' ? 'success' : 'warn'" />
                </template>
              </Column>
              <Column header="Actions" :style="{ width: '340px' }">
                <template #body="{ data }">
                  <Button icon="pi pi-folder-open" size="small" text severity="secondary" aria-label="Open AFE lines" title="Open AFE lines" @click="openAfe(data.id)" />
                  <Button v-if="data.status === 'draft'" icon="pi pi-pencil" size="small" text severity="secondary" aria-label="Edit AFE" title="Edit AFE Header & Sections" @click="openAfeDialog(data)" />
                  <Button v-if="data.status === 'submitted'" icon="pi pi-lock-open" size="small" text severity="warn" aria-label="Reopen AFE" title="Reopen AFE for Revision" @click="promptReopen(data)" />
                  <Button icon="pi pi-history" size="small" text severity="info" aria-label="Audit History" title="View Audit Trail" @click="showAuditHistory(data)" />
                  <Button icon="pi pi-trash" size="small" text severity="danger" aria-label="Delete AFE" :title="data.status === 'submitted' ? 'Delete submitted AFE' : 'Delete draft AFE'" @click="deactivateAfe(data)" />
                </template>
              </Column>
              <template #empty>No AFEs yet — create one for a well, enter its section planning, then add its lines.</template>
            </DataTable>
          </section>
        </TabPanel>

        <!-- Deleted AFEs -->
        <TabPanel value="deleted">
          <section class="afe-section bulk-grid-panel">
            <div class="grid-toolbar">
              <div>
                <strong>Deleted AFEs</strong><small class="toolbar-note">Soft-deleted AFEs (draft or submitted). Recover to restore, or permanently delete to remove completely. Recovery fails if another active AFE already exists.</small>
              </div>
              <div class="grid-toolbar__actions">
                <Button label="Refresh" icon="pi pi-refresh" outlined :loading="loadingDeleted" @click="loadDeletedAfes" />
              </div>
            </div>
            <Message v-if="deletedAfes.length && afes.length" severity="warn" :closable="false">An active AFE already exists ({{ afes.length }} active). Recovery is blocked until the active AFE is deleted — only one active AFE is allowed at a time for recovery.</Message>
            <DataTable :value="deletedAfes" :loading="loadingDeleted" data-key="id" striped-rows show-gridlines size="small" :rows="10" paginator class="afe-table">
              <Column field="code" header="AFE Code" sortable />
              <Column field="title" header="Title" sortable />
              <Column header="Well">
                <template #body="{ data }">{{ wellName(data.well_id) }}</template>
              </Column>
              <Column header="Status">
                <template #body="{ data }">
                  <Tag :value="data.status" :severity="data.status === 'submitted' ? 'success' : 'warn'" />
                </template>
              </Column>
              <Column header="Deleted">
                <template #body="{ data }">{{ data.deleted_at ? new Date(data.deleted_at).toLocaleString() : '—' }}</template>
              </Column>
              <Column header="Actions" :style="{ width: '260px' }">
                <template #body="{ data }">
                  <Button label="Recover" icon="pi pi-undo" size="small" severity="success" outlined :disabled="!!afes.length" title="Recover — blocked if another active AFE exists" @click="recoverAfe(data)" />
                  <Button label="Delete forever" icon="pi pi-trash" size="small" severity="danger" text @click="hardDeleteAfe(data)" />
                </template>
              </Column>
              <template #empty>No deleted AFEs — soft-deleted AFEs (draft or submitted) will appear here for recovery or permanent deletion.</template>
            </DataTable>
          </section>
        </TabPanel>

        <!-- AFE Lines -->
        <TabPanel value="lines">
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
                <Button v-if="selectedAfe && !isDraft" label="Reopen AFE" icon="pi pi-lock-open" size="small" severity="warn" outlined @click="promptReopen(selectedAfe)" />
              </div>
              <div class="grid-toolbar__actions">
                <Button label="Add row" icon="pi pi-plus" :disabled="!isDraft" @click="addLine" />
                <Button
                  v-if="isDraft && removedLines.length"
                  :label="`Removed (${removedLines.length})`"
                  icon="pi pi-undo"
                  text
                  severity="warn"
                  title="Restore removed lines"
                  @click="openRemovedLines"
                />
                <Button label="Print" icon="pi pi-print" text :loading="printingAfe" :disabled="!selectedAfe || !!pendingCount" @click="printAfe" />
                <Button :label="pendingCount ? `Save ${pendingCount}` : 'Save'" icon="pi pi-save" :disabled="!isDraft || !pendingCount" :loading="saving" @click="saveLines" />
                <Button :label="selectedAfe?.reopened_at ? 'Resubmit' : 'Submit'" icon="pi pi-send" severity="secondary" :disabled="!isDraft || !lines.length" :loading="submitting" @click="submitAfe" />
              </div>
            </div>

            <Message v-if="selectedAfe && !isDraft" severity="info" :closable="false">
              This AFE is submitted. Click <strong>"Reopen AFE"</strong> above to enter remarks, edit scope lines, adjust rates, and resubmit. Changes apply to this well only.
            </Message>

            <div v-if="selectedAfe" class="afe-summary-banner">
              <span><strong>Well:</strong> {{ wellName(selectedAfe.well_id) }}</span>
              <span><strong>Budget:</strong> ${{ Number(selectedAfe.budget_amount || 0).toLocaleString(undefined, { minimumFractionDigits: 2 }) }}</span>
              <span><strong>Planned Days:</strong> {{ Number(selectedAfe.total_planned_days || 0).toFixed(1) }} days</span>
              <span><strong>Planned TD:</strong> {{ Number(selectedAfe.total_planned_depth || 0).toFixed(0) }} {{ selectedAfe.depth_unit_code || 'M' }}</span>
              <span v-if="selectedAfe.sections?.length"><strong>Sections:</strong> {{ selectedAfe.sections.map(s => s.hole_section_code || s.phase).join(' → ') }}</span>
            </div>

            <DataTable
              :value="lines"
              :loading="loadingLines"
              data-key="line_number"
              striped-rows
              show-gridlines
              size="small"
              scrollable
              scroll-height="calc(100vh - 300px)"
              class="afe-lines"
            >
              <Column field="line_number" header="#" :style="{ width: '52px' }" />
              <Column header="Classification" :style="{ minWidth: '260px' }">
                <template #body="{ data }">
                  <div class="compact-cell compact-cell--pair">
                    <Select
                      v-model="data.primary_category_id"
                      :options="primaryCategoryOptions"
                      option-label="label"
                      option-value="value"
                      filter
                      show-clear
                      fluid
                      placeholder="Primary category"
                      :disabled="!isDraft"
                      data-testid="line-primary-category"
                      @change="onPrimaryCategoryChange(data)"
                    />
                    <Select
                      v-model="data.secondary_category_id"
                      :options="secondaryOptionsFor(data)"
                      option-label="label"
                      option-value="value"
                      filter
                      show-clear
                      fluid
                      :disabled="!isDraft || !data.primary_category_id"
                      :placeholder="data.primary_category_id ? 'Secondary category' : 'Select primary first'"
                      data-testid="line-secondary-category"
                      @change="onSecondaryCategoryChange(data)"
                    />
                  </div>
                </template>
              </Column>
              <Column header="Cost code" :style="{ minWidth: '190px' }">
                <template #body="{ data }">
                  <Select
                    v-model="data.cost_code_id"
                    :options="costCodeOptionsFor(data)"
                    option-label="name"
                    option-value="id"
                    filter
                    show-clear
                    fluid
                    :disabled="!isDraft || !data.secondary_category_id"
                    :placeholder="data.secondary_category_id ? 'Select cost code' : 'Select category first'"
                    @change="markDirty(data)"
                  >
                    <template #option="{ option }">{{ option.name }}</template>
                  </Select>
                </template>
              </Column>
              <Column header="Type & method" :style="{ minWidth: '175px' }">
                <template #body="{ data }">
                  <div class="compact-cell compact-cell--pair">
                    <Select
                      v-model="data.service_type"
                      :options="[
                        { label: 'Service', value: 'service' }, { label: 'Tangible', value: 'tangible' },
                        { label: 'Consumable', value: 'consumable' }, { label: 'Other', value: 'other' },
                      ]"
                      option-label="label"
                      option-value="value"
                      fluid
                      :disabled="!isDraft"
                      @change="onServiceTypeChange(data)"
                    />
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
                  </div>
                </template>
              </Column>
              <Column header="Scope" :style="{ minWidth: '205px' }">
                <template #body="{ data }">
                  <div class="compact-cell">
                    <label class="all-sections-inline">
                      <Checkbox
                        v-model="data.applies_to_all_sections"
                        binary
                        :disabled="!isDraft"
                        data-testid="all-sections"
                        @change="onAllSectionsChange(data)"
                      />
                      <span>All sections</span>
                    </label>
                    <Select
                      v-if="needsSection(data) || data.hole_section_id"
                      v-model="data.hole_section_id"
                      :options="sectionOptionsFor(data)"
                      option-value="id"
                      :option-label="(opt) => `${opt.code} — ${opt.name}`"
                      :filter="!needsSection(data)"
                      :show-clear="!needsSection(data)"
                      fluid
                      :disabled="!isDraft || data.applies_to_all_sections"
                      :invalid="needsSection(data) && !data.hole_section_id"
                      :placeholder="needsSection(data) ? 'Select configured section' : 'Optional section'"
                      data-testid="hole-section"
                      @change="markDirty(data)"
                    >
                      <template #option="{ option }">
                        <div class="section-option">
                          <span class="section-option__code">{{ option.code }} — {{ option.name }}</span>
                          <small v-if="needsSection(data)" class="section-option__meta">{{ sectionOptionDetail(option.id) }}</small>
                        </div>
                      </template>
                      <template #value="{ value }">
                        <span v-if="value">{{ holeSections.find(section => section.id === value)?.code }}</span>
                        <span v-else class="afe-placeholder">{{ needsSection(data) ? 'Select configured section' : 'Optional section' }}</span>
                      </template>
                    </Select>
                    <small v-if="data.service_type === 'consumable'" class="afe-hint">Actual quantity is entered in Daily Cost.</small>
                    <small v-else-if="needsSection(data) && !configuredAfeSections().length" class="afe-hint afe-hint--warn">Add a configured section on the AFEs tab first.</small>
                    <small v-else-if="needsSection(data) && data.hole_section_id && !isCurrentAfeSection(data.hole_section_id)" class="afe-hint afe-hint--warn">Select a current AFE section before saving.</small>
                  </div>
                </template>
              </Column>
              <Column header="Notes" :style="{ minWidth: '150px' }">
                <template #body="{ data }">
                  <InputText v-model="data.notes" fluid :disabled="!isDraft" placeholder="Line notes" @input="markDirty(data)" />
                </template>
              </Column>
              <Column header="" :style="{ width: '48px' }">
                <template #body="{ data }">
                  <Button icon="pi pi-trash" size="small" text severity="danger" aria-label="Remove line" :disabled="!isDraft" @click="removeLine(data)" />
                </template>
              </Column>
              <template #empty>
                <div class="eg__empty">
                  <i class="pi pi-inbox" aria-hidden="true" />
                  <p v-if="!selectedAfeId"><strong>Pick an AFE above</strong></p>
                  <p v-else><strong>No lines yet.</strong></p>
                  <p v-if="!selectedAfeId">Choose an AFE from the AFEs tab, or create one with “New AFE”.</p>
                  <p v-else>Add a compact scope row. Consumption and quantities are entered later in Daily Cost.</p>
                </div>
              </template>
            </DataTable>
          </section>
        </TabPanel>
      </TabPanels>
    </Tabs>

    <!-- Project dialog -->
    <Dialog v-model:visible="projectDialog" :dismissable-mask="false" :close-on-escape="false" modal :header="projectForm.id ? 'Edit project' : 'Add project'" :style="{ width: '480px' }">
      <div class="form-stack">
        <label>Code<InputText v-model="projectForm.code" fluid placeholder="e.g. PG-2026-01" /></label>
        <label>Name<InputText v-model="projectForm.name" fluid placeholder="e.g. North Sea Campaign" /></label>
        <label>Description<Textarea v-model="projectForm.description" rows="3" fluid /></label>
      </div>
      <template #footer>
        <Button label="Cancel" severity="secondary" text @click="projectDialog = false" />
        <Button label="Save project" icon="pi pi-check" :loading="saving" :disabled="!projectForm.code.trim() || !projectForm.name.trim()" @click="saveProject" />
      </template>
    </Dialog>

    <!-- Well dialog -->
    <Dialog v-model:visible="wellDialog" :dismissable-mask="false" :close-on-escape="false" modal :header="wellForm.id ? 'Edit well' : 'Add well'" :style="{ width: '520px' }">
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
        <Button label="Save well" icon="pi pi-check" :loading="saving" :disabled="!wellForm.project_id || !wellForm.code.trim() || !wellForm.name.trim()" @click="saveWell" />
      </template>
    </Dialog>

    <!-- AFE Dialog with Section & Phase Breakdown -->
    <Dialog v-model:visible="afeDialog" :dismissable-mask="false" :close-on-escape="false" modal :header="afeForm.id ? 'Edit AFE & Well Sections' : 'New AFE & Well Plan'" :style="{ width: '880px' }">
      <div class="form-stack">
        <div class="form-row">
          <label>Well<Select v-model="afeForm.well_id" :options="wellOptions" option-label="code" option-value="id" placeholder="Select well" filter fluid /></label>
          <label>AFE Code<InputText v-model="afeForm.code" fluid placeholder="e.g. AFE-W101-01" /></label>
        </div>
        <label>Title<InputText v-model="afeForm.title" fluid placeholder="e.g. W101 Drilling & Completion Scope" /></label>
        <div class="form-row">
          <label>Depth Unit<Select v-model="afeForm.depth_unit_id" :options="units" option-label="code" option-value="id" placeholder="Select unit" fluid /></label>
        </div>
        <label>Description<Textarea v-model="afeForm.description" rows="2" fluid placeholder="AFE scope description and technical summary" /></label>

        <!-- Section & Phase breakdown table -->
        <div class="afe-section-planner">
          <div class="section-planner-header">
            <div>
              <strong>Well Section & Phase Breakdown</strong>
              <small class="planner-subtitle">Define each hole section with its depth interval, then add the phases and planned days inside it. Section days roll up from its phases; the AFE total is the sum of all sections.</small>
            </div>
            <Button label="Add Section" icon="pi pi-plus" size="small" outlined @click="addSectionRow" />
          </div>

          <table class="section-planning-table">
            <thead>
              <tr>
                <th style="width: 40px">#</th>
                <th style="min-width: 150px">Hole Section</th>
                <th style="width: 105px">Depth From</th>
                <th style="width: 105px">Depth To</th>
                <th style="min-width: 170px">Phase</th>
                <th style="width: 120px">Planned Days</th>
                <th style="width: 120px">Actions</th>
              </tr>
            </thead>
            <tbody>
              <template v-for="(sec, idx) in afeForm.sections" :key="idx">
                <tr class="section-row">
                  <td class="section-index">{{ idx + 1 }}</td>
                  <td>
                    <Select
                      v-model="sec.hole_section_id"
                      :options="holeSections"
                      option-label="code"
                      option-value="id"
                      placeholder="Section size"
                      fluid
                      size="small"
                    >
                      <template #option="{ option }">{{ option.code }} ({{ option.name }})</template>
                    </Select>
                  </td>
                  <td>
                    <InputNumber
                      v-model="sec.planned_depth_from"
                      :min="0"
                      :max-fraction-digits="1"
                      fluid
                      size="small"
                      @input="recalculateSectionTotals"
                    />
                  </td>
                  <td>
                    <InputNumber
                      v-model="sec.planned_depth_to"
                      :min="0"
                      :max-fraction-digits="1"
                      fluid
                      size="small"
                      @input="recalculateSectionTotals"
                    />
                  </td>
                  <td colspan="2">
                    <span class="section-total">
                      Section total: <strong>{{ sectionPlannedDays(sec).toFixed(1) }} days</strong>
                    </span>
                  </td>
                  <td class="section-actions">
                    <Button
                      icon="pi pi-plus"
                      size="small"
                      text
                      title="Add phase to this section"
                      aria-label="Add phase"
                      @click="addPhaseRow(idx)"
                    />
                    <Button
                      icon="pi pi-trash"
                      size="small"
                      text
                      severity="danger"
                      title="Remove section"
                      aria-label="Remove section"
                      @click="removeSectionRow(idx)"
                    />
                  </td>
                </tr>
                <tr v-for="(ph, phIdx) in sec.phases" :key="phIdx" class="phase-row">
                  <td />
                  <td class="phase-indent">
                    <span class="phase-badge">Phase {{ phIdx + 1 }}</span>
                  </td>
                  <td />
                  <td />
                  <td>
                    <Select
                      v-model="ph.phase"
                      :options="phases"
                      option-label="name"
                      option-value="name"
                      :placeholder="phases.length ? 'Select phase' : 'No phases configured'"
                      :disabled="!phases.length"
                      fluid
                      size="small"
                      data-testid="section-phase"
                    />
                  </td>
                  <td>
                    <InputNumber
                      v-model="ph.planned_days"
                      :min="0"
                      :max-fraction-digits="2"
                      fluid
                      size="small"
                      @input="recalculateSectionTotals"
                    />
                  </td>
                  <td>
                    <Button
                      icon="pi pi-times"
                      size="small"
                      text
                      severity="danger"
                      title="Remove phase"
                      aria-label="Remove phase"
                      @click="removePhaseRow(idx, phIdx)"
                    />
                  </td>
                </tr>
              </template>
              <tr v-if="!afeForm.sections.length">
                <td colspan="7" class="text-center text-muted" style="padding: 12px">No sections configured. Click "Add Section" to establish the well profile.</td>
              </tr>
            </tbody>
            <tfoot>
              <tr>
                <td colspan="4" style="text-align: right; font-weight: bold">Total Planned Days / Max Depth:</td>
                <td style="font-weight: bold">{{ Number(afeForm.total_planned_days).toFixed(1) }} days</td>
                <td style="font-weight: bold">{{ Number(afeForm.total_planned_depth).toFixed(0) }}</td>
                <td />
              </tr>
            </tfoot>
          </table>
        </div>
      </div>
      <template #footer>
        <Button label="Cancel" severity="secondary" text @click="afeDialog = false" />
        <Button label="Save AFE & Sections" icon="pi pi-check" :loading="saving" :disabled="!afeForm.well_id || !afeForm.code.trim() || !afeForm.title.trim()" @click="saveAfe" />
      </template>
    </Dialog>

    <!-- Reopen AFE Dialog -->
    <Dialog v-model:visible="reopenDialog" :dismissable-mask="false" :close-on-escape="false" modal header="Reopen Submitted AFE" :style="{ width: '540px' }">
      <div class="form-stack">
        <Message severity="warn" :closable="false">
          Reopening <strong>{{ reopenTargetAfe?.code }}</strong> will unlock the AFE and allow editing of its section breakdown, items, and well-scoped rates.
        </Message>
        <label>
          <strong>Reason / Remarks for Reopening (Mandatory)</strong>
          <Textarea v-model="reopenRemarks" rows="4" fluid placeholder="e.g. Scope change for 12-1/4 section duration and Mud Chemical rate revision." />
        </label>
      </div>
      <template #footer>
        <Button label="Cancel" severity="secondary" text @click="reopenDialog = false" />
        <Button label="Confirm Reopen" icon="pi pi-lock-open" severity="warn" :loading="reopening" :disabled="!reopenRemarks.trim()" @click="confirmReopen" />
      </template>
    </Dialog>

    <!-- Audit History Dialog -->
    <Dialog v-model:visible="auditHistoryDialog" :dismissable-mask="false" :close-on-escape="false" modal :header="`AFE Audit History: ${auditTargetAfeTitle}`" :style="{ width: '680px' }">
      <DataTable :value="auditHistoryList" data-key="id" striped-rows show-gridlines size="small">
        <Column field="action" header="Action">
          <template #body="{ data }">
            <Tag :value="data.action" :severity="data.action === 'reopened' ? 'warn' : (data.action === 'submitted' || data.action === 'resubmitted' ? 'success' : 'info')" />
          </template>
        </Column>
        <Column header="Status Transition">
          <template #body="{ data }">
            {{ data.previous_status || 'initial' }} → <strong>{{ data.new_status }}</strong>
          </template>
        </Column>
        <Column field="remarks" header="Remarks / Reason" />
        <Column header="Actor">
          <template #body="{ data }">{{ data.actor_id ? `${data.actor_id.slice(0, 8)}…` : 'System' }}</template>
        </Column>
        <Column header="Date & Time">
          <template #body="{ data }">
            {{ new Date(data.created_at).toLocaleString() }}
          </template>
        </Column>
        <template #empty>No audit trail records recorded yet.</template>
      </DataTable>
      <template #footer>
        <Button label="Close" severity="secondary" text @click="auditHistoryDialog = false" />
      </template>
    </Dialog>

    <!-- Removed lines dialog -->
    <Dialog v-model:visible="removedLinesVisible" :dismissable-mask="false" :close-on-escape="false" modal header="Removed lines" :style="{ width: '640px' }">
      <p class="afe-paste-hint">
        Lines removed from this draft AFE. Restoring a line brings it back with its original details —
        the action is recorded in the audit trail.
      </p>
      <DataTable :value="removedLines" data-key="id" striped-rows show-gridlines size="small">
        <Column field="line_number" header="#" :style="{ width: '60px' }" />
        <Column header="Secondary category">
          <template #body="{ data }">{{ data.secondary_category_name ?? data.secondary_category_code ?? '—' }}</template>
        </Column>
        <Column header="Type / method">
          <template #body="{ data }">{{ data.service_type }} · {{ data.rate_basis.replaceAll('_', ' ') }}</template>
        </Column>
        <Column header="Actions" :style="{ width: '120px' }">
          <template #body="{ data }">
            <Button label="Restore" icon="pi pi-undo" size="small" severity="success" text @click="recoverRemovedLine(data)" />
          </template>
        </Column>
        <template #empty>No removed lines for this AFE.</template>
      </DataTable>
      <template #footer>
        <Button label="Close" severity="secondary" text @click="removedLinesVisible = false" />
      </template>
    </Dialog>

  </div>
</template>

<style scoped>
.afe-tabs {
  margin-top: -8px;
}

.afe-section {
  margin-bottom: 1.25rem;
  padding: 1rem;
}

.afe-table,
.afe-lines {
  margin-top: 0.75rem;
}

/* Keep the AFE scope grid readable without a long horizontal/vertical scroll. */
.afe-lines :deep(.p-datatable-thead > tr > th),
.afe-lines :deep(.p-datatable-tbody > tr > td) {
  padding: .32rem .4rem;
  font-size: .8rem;
  vertical-align: top;
}

.afe-lines :deep(.p-select-label),
.afe-lines :deep(.p-inputtext) {
  font-size: .8rem;
  padding-block: .33rem;
}

.compact-cell {
  display: grid;
  gap: .28rem;
}

.compact-cell--pair {
  gap: .22rem;
}

.all-sections-inline {
  display: inline-flex;
  align-items: center;
  gap: .35rem;
  color: var(--text-color-secondary);
  font-size: .76rem;
  white-space: nowrap;
}

.afe-picker {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.afe-summary-banner {
  display: flex;
  flex-wrap: wrap;
  gap: 1.5rem;
  padding: 0.75rem 1rem;
  background: var(--surface-card, #f8fafc);
  border: 1px solid var(--surface-border, #e2e8f0);
  border-radius: 6px;
  margin-bottom: 0.75rem;
  font-size: 0.85rem;
}

.afe-section-planner {
  border: 1px solid var(--surface-border, #e2e8f0);
  border-radius: 8px;
  padding: 0.85rem;
  background: #fdfdfd;
  margin-top: 0.5rem;
}

.section-planner-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.65rem;
}

.planner-subtitle {
  display: block;
  color: var(--text-color-secondary, #64748b);
  font-size: 0.75rem;
}

.section-planning-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.82rem;
}

.section-planning-table th,
.section-planning-table td {
  padding: 6px 8px;
  border: 1px solid var(--surface-border, #e2e8f0);
}

.section-planning-table thead th {
  background: #f1f5f9;
  font-weight: 600;
  text-align: left;
}

.section-planning-table tfoot td {
  background: #f8fafc;
  padding: 8px;
}

.section-planning-table .section-row {
  background: #f8fafc;
}

.section-planning-table .section-row > td {
  border-top: 2px solid #cbd5e1;
}

.section-index {
  font-weight: 700;
  color: #0f766e;
}

.section-total {
  display: block;
  color: #334155;
  font-size: 0.78rem;
}

.section-total strong {
  color: #0f766e;
}

.section-actions {
  white-space: nowrap;
}

.phase-row > td {
  background: #ffffff;
  padding-top: 3px;
  padding-bottom: 3px;
}

.phase-indent {
  padding-left: 22px !important;
}

.phase-badge {
  display: inline-block;
  background: #eef2ff;
  color: #4338ca;
  border-radius: 10px;
  padding: 1px 8px;
  font-size: 0.7rem;
  font-weight: 600;
  white-space: nowrap;
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

.all-sections-cell {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 2px;
}

.section-cell {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.section-option {
  display: flex;
  flex-direction: column;
  line-height: 1.25;
}

.section-option__code {
  font-weight: 600;
  font-size: 0.82rem;
}

.section-option__meta {
  display: block;
  color: var(--app-muted, #62717f);
  font-size: 0.7rem;
}

.section-hint {
  margin: 4px 0 0;
}

.form-row {
  display: flex;
  gap: 1rem;
}

.form-row label {
  flex: 1;
}

.text-center {
  text-align: center;
}

.text-muted {
  color: #64748b;
}
</style>
