<script setup lang="ts">
/**
 * Well Intake — the entry point for entering well data.
 *
 * Three layers, top to bottom: Projects, Wells (which belong to a project), and
 * Requirements (the well's AFE input). A requirement is built up from catalogue
 * items and submitted; submitted requirements feed the Cost Builder (AFE).
 */
import { computed, onMounted, ref } from 'vue'
import Button from 'primevue/button'
import Column from 'primevue/column'
import DataTable from 'primevue/datatable'
import DatePicker from 'primevue/datepicker'
import Dialog from 'primevue/dialog'
import InputText from 'primevue/inputtext'
import InputTextarea from 'primevue/textarea'
import Message from 'primevue/message'
import Select from 'primevue/select'
import Tag from 'primevue/tag'
import PageHeader from '~/components/design-system/PageHeader.vue'
import type { ProjectRecord, RequirementRecord, WellRecord } from '~/types/requirements'

definePageMeta({ middleware: 'auth' })

const api = useRequirements()

const projects = ref<ProjectRecord[]>([])
const wells = ref<WellRecord[]>([])
const requirements = ref<RequirementRecord[]>([])

const projectFilter = ref<string | null>(null)
const wellFilter = ref<string | null>(null)
const statusFilter = ref<string | null>(null)

const error = ref<string | null>(null)
const saving = ref(false)

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
    await loadAll()
  }
  catch (caught: unknown) {
    error.value = caught instanceof Error ? caught.message : 'The project could not be saved.'
  }
  finally { saving.value = false }
}

async function deactivateProject(record: ProjectRecord): Promise<void> {
  if (!window.confirm(`Deactivate project ${record.code}? Wells and requirements stay in place but it can no longer be used.`)) return
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
    await loadAll()
  }
  catch (caught: unknown) {
    error.value = caught instanceof Error ? caught.message : 'The well could not be saved.'
  }
  finally { saving.value = false }
}

async function deactivateWell(record: WellRecord): Promise<void> {
  if (!window.confirm(`Deactivate well ${record.code}? It can no longer be used on new requirements.`)) return
  await api.deleteWell(record.id)
  await loadAll()
}

/* --------------------------------------------------- requirements ------------ */
const requirementDialog = ref(false)
const requirementForm = ref({ id: undefined as string | undefined, well_id: '', code: '', title: '', description: '' })

function openRequirementDialog(record?: RequirementRecord): void {
  const defaultWellId = wellFilter.value ?? wellOptions.value[0]?.id ?? ''
  requirementForm.value = record
    ? { id: record.id, well_id: record.well_id, code: record.code, title: record.title, description: record.description ?? '' }
    : { id: undefined, well_id: defaultWellId, code: '', title: '', description: '' }
  requirementDialog.value = true
}

async function saveRequirement(): Promise<void> {
  saving.value = true
  error.value = null
  try {
    const payload = { well_id: requirementForm.value.well_id, code: requirementForm.value.code, title: requirementForm.value.title, description: requirementForm.value.description || null }
    if (requirementForm.value.id) {
      await api.updateRequirement(requirementForm.value.id, payload)
      requirementDialog.value = false
      await loadAll()
    }
    else {
      const created = await api.createRequirement(payload)
      requirementDialog.value = false
      await navigateTo(`/requirements/${created.id}`)
    }
  }
  catch (caught: unknown) {
    error.value = caught instanceof Error ? caught.message : 'The requirement could not be saved.'
  }
  finally { saving.value = false }
}

async function deactivateRequirement(record: RequirementRecord): Promise<void> {
  if (!window.confirm(`Delete requirement ${record.code}? Only draft requirements can be removed.`)) return
  try { await api.deleteRequirement(record.id) }
  catch (caught: unknown) {
    error.value = caught instanceof Error ? caught.message : 'The requirement could not be deleted.'
    return
  }
  await loadAll()
}

/* --------------------------------------------------------------- loading ---- */
const filteredWells = computed(() => (projectFilter.value ? wells.value.filter(well => well.project_id === projectFilter.value) : wells.value))
const filteredRequirements = computed(() => requirements.value.filter(requirement =>
  (!wellFilter.value || requirement.well_id === wellFilter.value)
  && (!statusFilter.value || requirement.status === statusFilter.value),
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

async function loadAll(): Promise<void> {
  error.value = null
  try {
    const [projectPage, wellPage, requirementPage] = await Promise.all([
      api.listProjects(), api.listWells(), api.listRequirements(),
    ])
    projects.value = projectPage.items
    wells.value = wellPage.items
    requirements.value = requirementPage.items
  }
  catch (caught: unknown) {
    error.value = caught instanceof Error ? caught.message : 'Well intake could not be loaded.'
  }
}

onMounted(() => void loadAll())
</script>

<template>
  <div class="library-page">
    <PageHeader
      title="Well Intake"
      description="Enter the well data that feeds the AFE: register projects and wells, then build a requirement of catalogue items for each well. Submitted requirements flow into the Cost Builder, where the AFE cost build is generated."
    />

    <Message v-if="error" severity="error" :closable="true" @close="error = null">{{ error }}</Message>

    <!-- Projects -->
    <section class="wi-section bulk-grid-panel">
      <div class="grid-toolbar">
        <div><strong>Projects</strong><small class="toolbar-note">The top-level grouping every well belongs to.</small></div>
        <div class="grid-toolbar__actions">
          <Button label="Add project" icon="pi pi-plus" @click="openProjectDialog()" />
        </div>
      </div>
      <DataTable :value="projects" data-key="id" striped-rows show-gridlines size="small" :rows="10" paginator class="wi-table">
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

    <!-- Wells -->
    <section class="wi-section bulk-grid-panel">
      <div class="grid-toolbar">
        <div>
          <strong>Wells</strong><small class="toolbar-note">The well itself: rig, status, and planned dates.</small>
          <Select v-model="projectFilter" :options="projects" option-label="code" option-value="id" placeholder="All projects" show-clear filter style="width: 180px; margin-left: 1rem" />
        </div>
        <div class="grid-toolbar__actions">
          <Button label="Add well" icon="pi pi-plus" @click="openWellDialog()" />
        </div>
      </div>
      <DataTable :value="filteredWells" data-key="id" striped-rows show-gridlines size="small" :rows="10" paginator class="wi-table">
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

    <!-- Requirements -->
    <section class="wi-section bulk-grid-panel">
      <div class="grid-toolbar">
        <div>
          <strong>Requirements</strong><small class="toolbar-note">The well's scope of services and tangibles. Submitted requirements become AFE cost builds.</small>
          <Select v-model="wellFilter" :options="wellOptions" option-label="code" option-value="id" placeholder="All wells" show-clear filter style="width: 170px; margin-left: 1rem" />
          <Select v-model="statusFilter" :options="[{ label: 'Draft', value: 'draft' }, { label: 'Submitted', value: 'submitted' }]" option-label="label" option-value="value" placeholder="All statuses" show-clear style="width: 160px; margin-left: 0.5rem" />
        </div>
        <div class="grid-toolbar__actions">
          <Button label="New" icon="pi pi-plus" @click="openRequirementDialog()" />
        </div>
      </div>
      <DataTable :value="filteredRequirements" data-key="id" striped-rows show-gridlines size="small" :rows="10" paginator class="wi-table">
        <Column field="code" header="Code" sortable />
        <Column field="title" header="Title" sortable />
        <Column header="Well">
          <template #body="{ data }">{{ wellName(data.well_id) }}</template>
        </Column>
        <Column field="item_count" header="Items">
          <template #body="{ data }">{{ data.item_count }}</template>
        </Column>
        <Column header="Status">
          <template #body="{ data }">
            <Tag :value="data.status" :severity="data.status === 'submitted' ? 'success' : 'warn'" />
          </template>
        </Column>
        <Column header="Actions" :style="{ width: '200px' }">
          <template #body="{ data }">
            <Button icon="pi pi-folder-open" size="small" text severity="secondary" aria-label="Open requirement" @click="navigateTo(`/requirements/${data.id}`)" />
            <Button icon="pi pi-pencil" size="small" text severity="secondary" aria-label="Edit requirement" :disabled="data.status === 'submitted'" @click="openRequirementDialog(data)" />
            <Button icon="pi pi-ban" size="small" text severity="danger" aria-label="Delete requirement" :disabled="data.status === 'submitted'" @click="deactivateRequirement(data)" />
          </template>
        </Column>
        <template #empty>No requirements yet — create one for a well, then open it to add the line items.</template>
      </DataTable>
    </section>

    <!-- Project dialog -->
    <Dialog v-model:visible="projectDialog" modal :header="projectForm.id ? 'Edit project' : 'Add project'" :style="{ width: '480px' }">
      <div class="form-stack">
        <label>Code<InputText v-model="projectForm.code" fluid placeholder="e.g. PG-2026-01" /></label>
        <label>Name<InputText v-model="projectForm.name" fluid placeholder="e.g. North Sea Campaign" /></label>
        <label>Description<InputTextarea v-model="projectForm.description" rows="3" fluid /></label>
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
        <label>Description<InputTextarea v-model="wellForm.description" rows="2" fluid /></label>
      </div>
      <template #footer>
        <Button label="Cancel" severity="secondary" text @click="wellDialog = false" />
        <Button label="Create well" icon="pi pi-check" :loading="saving" :disabled="!wellForm.project_id || !wellForm.code.trim() || !wellForm.name.trim()" @click="saveWell" />
      </template>
    </Dialog>

    <!-- Requirement dialog -->
    <Dialog v-model:visible="requirementDialog" modal :header="requirementForm.id ? 'Edit requirement' : 'New requirement'" :style="{ width: '500px' }">
      <div class="form-stack">
        <label>Well<Select v-model="requirementForm.well_id" :options="wellOptions" option-label="code" option-value="id" placeholder="Select well" filter fluid /></label>
        <label>Requirement code<InputText v-model="requirementForm.code" fluid placeholder="e.g. REQ-W101-01" /></label>
        <label>Title<InputText v-model="requirementForm.title" fluid placeholder="e.g. W101 Drilling & Completion Scope" /></label>
        <label>Description<InputTextarea v-model="requirementForm.description" rows="3" fluid /></label>
      </div>
      <template #footer>
        <Button label="Cancel" severity="secondary" text @click="requirementDialog = false" />
        <Button label="Create and open" icon="pi pi-check" :loading="saving" :disabled="!requirementForm.well_id || !requirementForm.code.trim() || !requirementForm.title.trim()" @click="saveRequirement" />
      </template>
    </Dialog>
  </div>
</template>

<style scoped>
.wi-section {
  margin-bottom: 1.25rem;
  padding: 1rem;
}

.wi-table {
  margin-top: 0.75rem;
}

.form-row {
  display: flex;
  gap: 1rem;
}

.form-row label {
  flex: 1;
}
</style>
