<script setup lang="ts">
/**
 * Well configuration popup — sections → phases → days with live totals.
 *
 * Editing rules mirror the backend exactly:
 *   • a well in `draft` (and not completed) can be edited and saved;
 *   • once marked `configured` it is read-only until marked back to `draft`;
 *   • a `completed` well is fully read-only until marked `active`.
 *
 * Every status transition requires remarks and is audit-logged server-side.
 * The dialog only closes through its Cancel button — clicking the mask or
 * pressing Escape does nothing (`closable`/`dismissable-mask`/
 * `close-on-escape` are all disabled).
 */
import { computed, ref, watch } from 'vue'
import Button from 'primevue/button'
import Dialog from 'primevue/dialog'
import InputText from 'primevue/inputtext'
import Message from 'primevue/message'
import Select from 'primevue/select'
import Tag from 'primevue/tag'
import Textarea from 'primevue/textarea'

interface SectionOption { id: number; section_code: string; section_name: string }
interface PhaseOption { id: number; phase_code: string; phase_name: string }

interface PhaseDraft {
  key: string
  phase_id: number | null
  days: string
  remarks: string
}

interface SectionDraft {
  key: string
  section_id: number | null
  from_depth: string
  to_depth: string
  remarks: string
  phases: PhaseDraft[]
}

export interface WellSummary {
  id: number
  well_code: string
  well_name: string
  rig_code: string | null
  rig_name: string | null
  status: string
  config_status: string
  [key: string]: unknown
}

const props = defineProps<{
  visible: boolean
  well: WellSummary | null
}>()

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void
  (e: 'changed'): void
}>()

const api = useApi()

const dialogVisible = computed({
  get: () => props.visible,
  set: (value: boolean) => emit('update:visible', value),
})

const sectionOptions = ref<SectionOption[]>([])
const phaseOptions = ref<PhaseOption[]>([])
const depthUnit = ref<'m' | 'ft'>('m')
const sections = ref<SectionDraft[]>([])
const loading = ref(false)
const saving = ref(false)
const error = ref<string | null>(null)
const message = ref<string | null>(null)
// Authoritative lifecycle state, refreshed from the backend on every load so
// status transitions made inside this dialog reflect immediately (the parent's
// `well` object is stale until its list reloads).
const loadedStatus = ref('active')
const loadedConfigStatus = ref('draft')

let uid = 0
function nextKey(): string {
  uid += 1
  return `k${uid}`
}

const configStatus = computed(() => loadedConfigStatus.value)
const wellStatus = computed(() => loadedStatus.value)
const isEditable = computed(() => wellStatus.value !== 'completed' && configStatus.value === 'draft')

const sectionOptionList = computed(() =>
  sectionOptions.value.map(option => ({
    label: `${option.section_code} — ${option.section_name}`,
    value: option.id,
  })),
)
const phaseOptionList = computed(() =>
  phaseOptions.value.map(option => ({
    label: `${option.phase_code} — ${option.phase_name}`,
    value: option.id,
  })),
)

function sectionDays(section: SectionDraft): number {
  return section.phases.reduce((sum, phase) => sum + toNumber(phase.days), 0)
}

function wellDays(): number {
  return sections.value.reduce((sum, section) => sum + sectionDays(section), 0)
}

function totalDepth(): number | null {
  const last = sections.value[sections.value.length - 1]
  if (!last) return null
  const depth = toNumber(last.to_depth)
  return Number.isFinite(depth) ? depth : null
}

function toNumber(value: string): number {
  const parsed = Number(String(value ?? '').trim())
  return Number.isFinite(parsed) ? parsed : 0
}

function blankSection(): SectionDraft {
  return { key: nextKey(), section_id: null, from_depth: '', to_depth: '', remarks: '', phases: [] }
}

function blankPhase(): PhaseDraft {
  return { key: nextKey(), phase_id: null, days: '', remarks: '' }
}

function addSection(): void {
  sections.value = [...sections.value, blankSection()]
}

function removeSection(index: number): void {
  sections.value = sections.value.filter((_, i) => i !== index)
}

function addPhase(section: SectionDraft): void {
  section.phases = [...section.phases, blankPhase()]
}

function removePhase(section: SectionDraft, index: number): void {
  section.phases = section.phases.filter((_, i) => i !== index)
}

async function loadOptions(): Promise<void> {
  const [sectionsRes, phasesRes] = await Promise.all([
    api.get<SectionOption[]>('/master-data/hole-sections'),
    api.get<PhaseOption[]>('/master-data/phases'),
  ])
  sectionOptions.value = sectionsRes
  phaseOptions.value = phasesRes
}

async function loadConfiguration(): Promise<void> {
  if (!props.well) return
  loading.value = true
  error.value = null
  message.value = null
  try {
    await loadOptions()
    const config = await api.get<{
      depth_unit: 'm' | 'ft'
      status: string
      config_status: string
      sections: Array<{
        section_id: number
        from_depth: string | number
        to_depth: string | number
        remarks: string | null
        phases: Array<{ phase_id: number; days: string | number; remarks: string | null }>
      }>
    }>(`/rig-well/wells/${props.well.id}/configuration`)

    loadedStatus.value = config.status === 'completed' ? 'completed' : 'active'
    loadedConfigStatus.value = config.config_status === 'configured' ? 'configured' : 'draft'
    depthUnit.value = config.depth_unit === 'ft' ? 'ft' : 'm'
    sections.value = (config.sections ?? []).map(section => ({
      key: nextKey(),
      section_id: section.section_id,
      from_depth: section.from_depth != null ? String(section.from_depth) : '',
      to_depth: section.to_depth != null ? String(section.to_depth) : '',
      remarks: section.remarks ?? '',
      phases: (section.phases ?? []).map(phase => ({
        key: nextKey(),
        phase_id: phase.phase_id,
        days: phase.days != null ? String(phase.days) : '',
        remarks: phase.remarks ?? '',
      })),
    }))
  }
  catch (caught: unknown) {
    error.value = caught instanceof Error ? caught.message : 'Configuration could not be loaded'
  }
  finally {
    loading.value = false
  }
}

watch(dialogVisible, (open) => {
  if (!open) return
  loadedStatus.value = props.well?.status === 'completed' ? 'completed' : 'active'
  loadedConfigStatus.value = props.well?.config_status === 'configured' ? 'configured' : 'draft'
  void loadConfiguration()
})

// --- Validation -------------------------------------------------------------

function validate(): string[] {
  const problems: string[] = []
  if (!sections.value.length) {
    problems.push('Add at least one section.')
    return problems
  }
  const seenSections = new Set<number>()
  let prevToDepth: number | null = null
  sections.value.forEach((section, i) => {
    const label = `Section ${i + 1}`
    if (section.section_id == null) {
      problems.push(`${label}: select a hole section.`)
      return
    }
    if (seenSections.has(section.section_id)) {
      problems.push(`${label}: duplicate section.`)
    }
    seenSections.add(section.section_id)

    const from = toNumber(section.from_depth)
    const to = toNumber(section.to_depth)
    if (!String(section.from_depth).trim() || !String(section.to_depth).trim()) {
      problems.push(`${label}: enter both from and to depth.`)
      return
    }
    if (from > to) {
      problems.push(`${label}: from depth cannot exceed to depth.`)
    }
    if (prevToDepth != null && from < prevToDepth) {
      problems.push(`${label}: from depth must not be less than the previous section's to depth.`)
    }
    prevToDepth = to

    const seenPhases = new Set<number>()
    if (!section.phases.length) {
      problems.push(`${label}: add at least one phase.`)
    }
    section.phases.forEach((phase, j) => {
      if (phase.phase_id == null) {
        problems.push(`${label} phase ${j + 1}: select a phase.`)
        return
      }
      if (seenPhases.has(phase.phase_id)) {
        problems.push(`${label}: duplicate phase.`)
      }
      seenPhases.add(phase.phase_id)
      const days = toNumber(phase.days)
      if (!String(phase.days).trim()) {
        problems.push(`${label} phase ${j + 1}: enter days.`)
      }
      else if (days < 0) {
        problems.push(`${label} phase ${j + 1}: days cannot be negative.`)
      }
    })
  })
  return problems
}

function buildPayload(): Record<string, unknown> {
  return {
    depth_unit: depthUnit.value,
    sections: sections.value.map(section => ({
      section_id: section.section_id,
      from_depth: toNumber(section.from_depth),
      to_depth: toNumber(section.to_depth),
      remarks: section.remarks.trim() || null,
      phases: section.phases.map(phase => ({
        phase_id: phase.phase_id,
        days: toNumber(phase.days),
        remarks: phase.remarks.trim() || null,
      })),
    })),
  }
}

async function saveDraft(): Promise<boolean> {
  if (!props.well) return false
  const problems = validate()
  if (problems.length) {
    error.value = problems.join(' ')
    return false
  }
  saving.value = true
  error.value = null
  message.value = null
  try {
    await api.put(`/rig-well/wells/${props.well.id}/configuration`, buildPayload())
    emit('changed')
    await loadConfiguration()
    message.value = 'Configuration saved as draft.'
    return true
  }
  catch (caught: unknown) {
    error.value = caught instanceof Error ? caught.message : 'Save failed'
    return false
  }
  finally {
    saving.value = false
  }
}

async function saveAndConfigure(): Promise<void> {
  const saved = await saveDraft()
  if (saved) {
    openMark('configure')
  }
}

// --- Marking (status transitions) with remarks ------------------------------

type MarkAction = 'configure' | 'draft' | 'complete' | 'activate'

const showMarkDialog = ref(false)
const markAction = ref<MarkAction>('configure')
const markRemarks = ref('')
const marking = ref(false)
const markError = ref<string | null>(null)

const markDialogTitle = computed(() => {
  switch (markAction.value) {
    case 'configure': return 'Mark as Configured'
    case 'draft': return 'Mark as Draft'
    case 'complete': return 'Mark as Completed'
    case 'activate': return 'Mark as Active'
    default: return ''
  }
})

const markDialogHint = computed(() => {
  switch (markAction.value) {
    case 'configure': return 'Once configured, this well becomes read-only until marked back to draft.'
    case 'draft': return 'Marking back to draft re-enables editing of the configuration.'
    case 'complete': return 'A completed well no longer allows any configuration changes.'
    case 'activate': return 'Re-open a completed well so its configuration can be changed again.'
    default: return ''
  }
})

function openMark(action: MarkAction): void {
  markAction.value = action
  markRemarks.value = ''
  markError.value = null
  showMarkDialog.value = true
}

async function confirmMark(): Promise<void> {
  if (!props.well) return
  if (!markRemarks.value.trim()) {
    markError.value = 'Remarks are required for this action.'
    return
  }
  marking.value = true
  markError.value = null
  try {
    await api.post(`/rig-well/wells/${props.well.id}/mark`, {
      action: markAction.value,
      remarks: markRemarks.value.trim(),
    })
    showMarkDialog.value = false
    emit('changed')
    await loadConfiguration()
  }
  catch (caught: unknown) {
    markError.value = caught instanceof Error ? caught.message : 'Action failed'
  }
  finally {
    marking.value = false
  }
}

function close(): void {
  dialogVisible.value = false
}

const statusSeverity = computed(() => (wellStatus.value === 'completed' ? 'danger' : 'success'))
const configSeverity = computed(() => (configStatus.value === 'configured' ? 'success' : 'warn'))
</script>

<template>
  <Dialog
    v-model:visible="dialogVisible"
    modal
    :header="`Configure Well — ${well?.well_code ?? ''}`"
    :closable="false"
    :dismissable-mask="false"
    :close-on-escape="false"
    :style="{ width: '62rem' }"
    content-class="well-config-dialog-content"
  >
    <div v-if="!well" class="config-empty">No well selected.</div>

    <div v-else class="config">
      <!-- Well header summary -->
      <div class="config__header">
        <div class="config__header-meta">
          <span class="config__label">Rig</span>
          <strong>{{ well.rig_code }} — {{ well.rig_name }}</strong>
        </div>
        <div class="config__header-meta">
          <span class="config__label">Well</span>
          <strong>{{ well.well_code }} — {{ well.well_name }}</strong>
        </div>
        <div class="config__header-meta">
          <span class="config__label">Status</span>
          <Tag :severity="statusSeverity" :value="wellStatus === 'completed' ? 'Completed' : 'Active'" />
        </div>
        <div class="config__header-meta">
          <span class="config__label">Configuration</span>
          <Tag :severity="configSeverity" :value="configStatus === 'configured' ? 'Configured' : 'Draft'" />
        </div>
      </div>

      <Message v-if="!isEditable" severity="warn" :closable="false" class="config__notice">
        {{
          wellStatus === 'completed'
            ? 'This well is completed — no changes are allowed. Mark it Active to edit again.'
            : 'This well is configured — it is read-only. Mark it as Draft to edit again.'
        }}
      </Message>

      <Message v-if="error" severity="error" :closable="false" class="config__notice">{{ error }}</Message>
      <Message v-if="message" severity="success" :closable="false" class="config__notice">{{ message }}</Message>

      <div v-if="loading" class="config__loading"><i class="pi pi-spin pi-spinner" /> Loading configuration…</div>

      <template v-else>
        <!-- Depth unit -->
        <div class="config__unit">
          <label class="config__unit-label">Depth unit</label>
          <Select
            v-model="depthUnit"
            :options="[{ label: 'Metres (m)', value: 'm' }, { label: 'Feet (ft)', value: 'ft' }]"
            option-label="label"
            option-value="value"
            size="small"
            :disabled="!isEditable"
            style="min-width: 10rem"
          />
        </div>

        <!-- Sections -->
        <div class="config__sections">
          <div v-for="(section, index) in sections" :key="section.key" class="config__section">
            <div class="config__section-head">
              <span class="config__section-title">Section {{ index + 1 }}</span>
              <span v-if="sectionDays(section)" class="config__section-days">{{ sectionDays(section).toFixed(2) }} days</span>
              <button
                v-if="isEditable"
                class="config__icon config__icon--danger"
                title="Remove section"
                @click="removeSection(index)"
              >
                <i class="pi pi-trash" />
              </button>
            </div>

            <div class="config__section-grid">
              <label class="config__field">
                <span>Hole Section *</span>
                <Select
                  v-model="section.section_id"
                  :options="sectionOptionList"
                  option-label="label"
                  option-value="value"
                  placeholder="Select section…"
                  filter
                  size="small"
                  fluid
                  :disabled="!isEditable"
                />
              </label>
              <label class="config__field">
                <span>From depth *</span>
                <InputText v-model="section.from_depth" inputmode="decimal" size="small" fluid :disabled="!isEditable" placeholder="0" />
              </label>
              <label class="config__field">
                <span>To depth *</span>
                <InputText v-model="section.to_depth" inputmode="decimal" size="small" fluid :disabled="!isEditable" placeholder="e.g. 1500" />
              </label>
              <label class="config__field">
                <span>Section remarks</span>
                <InputText v-model="section.remarks" size="small" fluid :disabled="!isEditable" placeholder="Optional" />
              </label>
            </div>

            <!-- Phases -->
            <div class="config__phases">
              <div class="config__phases-head">
                <span class="config__phases-title">Phases</span>
                <Button
                  v-if="isEditable"
                  label="Add phase"
                  icon="pi pi-plus"
                  size="small"
                  severity="secondary"
                  outlined
                  @click="addPhase(section)"
                />
              </div>
              <div v-if="!section.phases.length" class="config__phases-empty">No phases yet.</div>
              <div v-for="(phase, pIndex) in section.phases" :key="phase.key" class="config__phase">
                <label class="config__field">
                  <span>Phase *</span>
                  <Select
                    v-model="phase.phase_id"
                    :options="phaseOptionList"
                    option-label="label"
                    option-value="value"
                    placeholder="Select phase…"
                    filter
                    size="small"
                    fluid
                    :disabled="!isEditable"
                  />
                </label>
                <label class="config__field config__field--days">
                  <span>Days *</span>
                  <InputText v-model="phase.days" inputmode="decimal" size="small" fluid :disabled="!isEditable" placeholder="e.g. 2.5" />
                </label>
                <label class="config__field">
                  <span>Phase remarks</span>
                  <InputText v-model="phase.remarks" size="small" fluid :disabled="!isEditable" placeholder="Optional" />
                </label>
                <button
                  v-if="isEditable"
                  class="config__icon config__icon--danger"
                  title="Remove phase"
                  @click="removePhase(section, pIndex)"
                >
                  <i class="pi pi-trash" />
                </button>
              </div>
            </div>
          </div>

          <Button
            v-if="isEditable"
            label="Add section"
            icon="pi pi-plus"
            size="small"
            severity="secondary"
            outlined
            @click="addSection"
          />
        </div>

        <!-- Totals -->
        <div class="config__totals">
          <div class="config__total">
            <span>Total depth</span>
            <strong>{{ totalDepth() != null ? `${totalDepth()} ${depthUnit}` : '—' }}</strong>
          </div>
          <div class="config__total">
            <span>Total days</span>
            <strong>{{ wellDays().toFixed(2) }}</strong>
          </div>
          <div class="config__total">
            <span>Sections</span>
            <strong>{{ sections.length }}</strong>
          </div>
        </div>
      </template>
    </div>

    <template #footer>
      <div class="config__footer">
        <div class="config__footer-left">
          <template v-if="isEditable && configStatus === 'draft'">
            <Button
              v-if="sections.length"
              label="Save Draft"
              icon="pi pi-save"
              size="small"
              severity="secondary"
              outlined
              :loading="saving"
              @click="saveDraft"
            />
            <Button
              v-if="sections.length"
              label="Save & Mark Configured"
              icon="pi pi-check-circle"
              size="small"
              severity="success"
              :loading="saving"
              @click="saveAndConfigure"
            />
          </template>
          <template v-if="configStatus === 'configured' && wellStatus !== 'completed'">
            <Button label="Mark as Draft" icon="pi pi-pencil" size="small" severity="warn" outlined @click="openMark('draft')" />
          </template>
          <template v-if="wellStatus === 'active'">
            <Button label="Mark Completed" icon="pi pi-check" size="small" severity="secondary" outlined @click="openMark('complete')" />
          </template>
          <template v-if="wellStatus === 'completed'">
            <Button label="Mark Active" icon="pi pi-undo" size="small" severity="secondary" outlined @click="openMark('activate')" />
          </template>
        </div>
        <Button label="Cancel" icon="pi pi-times" size="small" severity="secondary" text @click="close" />
      </div>
    </template>

    <!-- Marking remarks dialog (only closes via its own buttons) -->
    <Dialog
      v-model:visible="showMarkDialog"
      modal
      :header="markDialogTitle"
      :closable="false"
      :dismissable-mask="false"
      :close-on-escape="false"
      :style="{ width: '30rem' }"
    >
      <div class="mark-form">
        <p class="mark-form__hint">{{ markDialogHint }}</p>
        <label class="mark-form__label">
          Remarks <span class="mark-form__req">*</span>
          <Textarea v-model="markRemarks" rows="3" fluid placeholder="Reason for this change…" autofocus />
        </label>
        <p v-if="markError" class="mark-form__error">{{ markError }}</p>
      </div>
      <template #footer>
        <Button label="Cancel" severity="secondary" text size="small" @click="showMarkDialog = false" />
        <Button
          :label="markDialogTitle"
          icon="pi pi-check"
          size="small"
          severity="success"
          :loading="marking"
          :disabled="!markRemarks.trim()"
          @click="confirmMark"
        />
      </template>
    </Dialog>
  </Dialog>
</template>

<style scoped>
.config-empty,
.config__loading {
  padding: 1.5rem;
  text-align: center;
  color: var(--app-muted);
}

.config {
  display: flex;
  flex-direction: column;
  gap: 0.85rem;
}

.config__header {
  display: flex;
  flex-wrap: wrap;
  gap: 1.25rem;
  padding: 0.65rem 0.75rem;
  background: var(--app-bg);
  border: 1px solid var(--app-border);
  border-radius: 8px;
}

.config__header-meta {
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
  font-size: 0.8rem;
}

.config__label {
  font-size: 0.66rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--app-muted);
}

.config__notice {
  margin: 0;
}

.config__unit {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  font-size: 0.8rem;
}

.config__unit-label {
  font-size: 0.7rem;
  font-weight: 600;
  text-transform: uppercase;
  color: var(--app-muted);
}

.config__sections {
  display: flex;
  flex-direction: column;
  gap: 0.85rem;
  max-height: 46vh;
  overflow-y: auto;
}

.config__section {
  border: 1px solid var(--app-border);
  border-radius: 10px;
  padding: 0.75rem;
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
}

.config__section-head {
  display: flex;
  align-items: center;
  gap: 0.6rem;
}

.config__section-title {
  font-weight: 700;
  font-size: 0.85rem;
}

.config__section-days {
  font-size: 0.72rem;
  font-weight: 700;
  color: var(--app-teal);
  background: rgb(15 118 110 / 12%);
  padding: 0.1rem 0.5rem;
  border-radius: 999px;
}

.config__section-grid {
  display: grid;
  grid-template-columns: 1.2fr 0.8fr 0.8fr 1.4fr;
  gap: 0.6rem;
}

.config__field {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  font-size: 0.7rem;
  font-weight: 600;
  text-transform: uppercase;
  color: var(--app-muted);
}

.config__field--days {
  max-width: 9rem;
}

.config__phases {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  border-top: 1px dashed var(--app-border);
  padding-top: 0.6rem;
}

.config__phases-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.config__phases-title {
  font-size: 0.72rem;
  font-weight: 700;
  text-transform: uppercase;
  color: var(--app-muted);
}

.config__phases-empty {
  font-size: 0.76rem;
  color: var(--app-muted);
  font-style: italic;
}

.config__phase {
  display: grid;
  grid-template-columns: 1.2fr 0.8fr 1.4fr auto;
  gap: 0.6rem;
  align-items: end;
}

.config__icon {
  border: none;
  background: transparent;
  color: var(--app-muted);
  cursor: pointer;
  padding: 0.3rem;
  border-radius: 4px;
  font-size: 0.8rem;
  line-height: 1;
}

.config__icon:hover {
  background: var(--app-bg);
}

.config__icon--danger:hover {
  color: #e11d48;
}

.config__totals {
  display: flex;
  gap: 1.5rem;
  padding: 0.65rem 0.75rem;
  background: var(--app-bg);
  border: 1px solid var(--app-border);
  border-radius: 8px;
}

.config__total {
  display: flex;
  flex-direction: column;
  gap: 0.1rem;
  font-size: 0.7rem;
  text-transform: uppercase;
  color: var(--app-muted);
}

.config__total strong {
  font-size: 1rem;
  color: var(--app-teal);
}

.config__footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.config__footer-left {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.mark-form {
  display: flex;
  flex-direction: column;
  gap: 0.7rem;
  font-size: 0.82rem;
}

.mark-form__hint {
  margin: 0;
  color: var(--app-muted);
}

.mark-form__label {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--app-muted);
}

.mark-form__req {
  color: #e11d48;
}

.mark-form__error {
  color: #e11d48;
  margin: 0;
}
</style>
