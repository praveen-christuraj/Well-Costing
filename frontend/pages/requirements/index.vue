<script setup lang="ts">
import { onMounted, ref, computed } from 'vue'
import Button from 'primevue/button'
import Column from 'primevue/column'
import DataTable from 'primevue/datatable'
import Dialog from 'primevue/dialog'
import InputText from 'primevue/inputtext'
import Select from 'primevue/select'
import Tag from 'primevue/tag'
import Textarea from 'primevue/textarea'
import Message from 'primevue/message'
import { useConfirm } from 'primevue/useconfirm'
import ConfirmDialog from 'primevue/confirmdialog'
import PageHeader from '~/components/design-system/PageHeader.vue'
import type { ProjectRecord, RequirementRecord, WellRecord } from '~/types/requirements'

definePageMeta({ middleware: 'auth' })

const api = useRequirements()
const confirm = useConfirm()

// ── Data ──────────────────────────────────────────────────────────────
const projects = ref<ProjectRecord[]>([])
const wells = ref<WellRecord[]>([])
const requirements = ref<RequirementRecord[]>([])
const selectedProject = ref<ProjectRecord | null>(null)
const selectedWell = ref<WellRecord | null>(null)
const statusFilter = ref<string | null>(null)
const loading = ref(false)
const wellsLoading = ref(false)
const reqLoading = ref(false)
const feedback = ref<{ type: 'success' | 'error', msg: string } | null>(null)

// ── Dialogs ───────────────────────────────────────────────────────────
type DialogMode = 'create' | 'edit'
const projectDialog = ref(false)
const projectDialogMode = ref<DialogMode>('create')
const projectForm = ref({ id: '', code: '', name: '', description: '' })

const wellDialog = ref(false)
const wellDialogMode = ref<DialogMode>('create')
const wellForm = ref({ id: '', code: '', name: '', description: '' })

const reqDialog = ref(false)
const reqDialogMode = ref<DialogMode>('create')
const reqForm = ref({ id: '', code: '', title: '', description: '' })

const saving = ref(false)

// ── Computed ──────────────────────────────────────────────────────────
const filteredRequirements = computed(() =>
  statusFilter.value
    ? requirements.value.filter(r => r.status === statusFilter.value)
    : requirements.value,
)

// ── Load helpers ──────────────────────────────────────────────────────
function showFeedback(type: 'success' | 'error', msg: string): void {
  feedback.value = { type, msg }
  if (type === 'success') setTimeout(() => { feedback.value = null }, 4000)
}

async function loadProjects(): Promise<void> {
  loading.value = true
  try {
    projects.value = (await api.listProjects()).items
    if (!selectedProject.value && projects.value.length) {
      await chooseProject(projects.value[0]!)
    }
  }
  catch { showFeedback('error', 'Could not load projects.') }
  finally { loading.value = false }
}

async function chooseProject(project: ProjectRecord): Promise<void> {
  selectedProject.value = project
  selectedWell.value = null
  requirements.value = []
  wellsLoading.value = true
  try {
    wells.value = (await api.listWells(project.id)).items
    if (wells.value.length) await chooseWell(wells.value[0]!)
  }
  finally { wellsLoading.value = false }
}

async function chooseWell(well: WellRecord): Promise<void> {
  selectedWell.value = well
  reqLoading.value = true
  try {
    requirements.value = (await api.listRequirements(well.id)).items
  }
  finally { reqLoading.value = false }
}

// ── Project CRUD ──────────────────────────────────────────────────────
function openProjectCreate(): void {
  projectForm.value = { id: '', code: '', name: '', description: '' }
  projectDialogMode.value = 'create'
  projectDialog.value = true
}

function openProjectEdit(row: ProjectRecord, event: Event): void {
  event.stopPropagation()
  projectForm.value = { id: row.id, code: row.code, name: row.name, description: row.description ?? '' }
  projectDialogMode.value = 'edit'
  projectDialog.value = true
}

async function saveProject(): Promise<void> {
  saving.value = true
  try {
    if (projectDialogMode.value === 'create') {
      const created = await api.createProject({
        code: projectForm.value.code,
        name: projectForm.value.name,
        description: projectForm.value.description || null,
      })
      projectDialog.value = false
      await loadProjects()
      await chooseProject(created)
      showFeedback('success', `Project "${created.name}" created.`)
    }
    else {
      await api.updateProject(projectForm.value.id, {
        code: projectForm.value.code,
        name: projectForm.value.name,
        description: projectForm.value.description || null,
      })
      projectDialog.value = false
      const prev = selectedProject.value
      await loadProjects()
      if (prev) {
        const refreshed = projects.value.find(p => p.id === prev.id)
        if (refreshed) await chooseProject(refreshed)
      }
      showFeedback('success', 'Project updated.')
    }
  }
  catch (e: unknown) { showFeedback('error', e instanceof Error ? e.message : 'Could not save project.') }
  finally { saving.value = false }
}

function confirmDeleteProject(row: ProjectRecord, event: Event): void {
  event.stopPropagation()
  confirm.require({
    message: `Delete project "${row.name}"? All its wells and requirements will be deactivated.`,
    header: 'Delete project',
    icon: 'pi pi-exclamation-triangle',
    rejectProps: { label: 'Cancel', severity: 'secondary', outlined: true },
    acceptProps: { label: 'Delete', severity: 'danger' },
    accept: async () => {
      try {
        await api.deleteProject(row.id)
        if (selectedProject.value?.id === row.id) {
          selectedProject.value = null
          wells.value = []
          requirements.value = []
        }
        await loadProjects()
        showFeedback('success', `Project "${row.name}" deleted.`)
      }
      catch (e: unknown) { showFeedback('error', e instanceof Error ? e.message : 'Could not delete project.') }
    },
  })
}

// ── Well CRUD ─────────────────────────────────────────────────────────
function openWellCreate(): void {
  wellForm.value = { id: '', code: '', name: '', description: '' }
  wellDialogMode.value = 'create'
  wellDialog.value = true
}

function openWellEdit(row: WellRecord, event: Event): void {
  event.stopPropagation()
  wellForm.value = { id: row.id, code: row.code, name: row.name, description: row.description ?? '' }
  wellDialogMode.value = 'edit'
  wellDialog.value = true
}

async function saveWell(): Promise<void> {
  if (!selectedProject.value) return
  saving.value = true
  try {
    if (wellDialogMode.value === 'create') {
      const created = await api.createWell({
        project_id: selectedProject.value.id,
        code: wellForm.value.code,
        name: wellForm.value.name,
        description: wellForm.value.description || null,
      })
      wellDialog.value = false
      await chooseProject(selectedProject.value)
      await chooseWell(created)
      showFeedback('success', `Well "${created.name}" created.`)
    }
    else {
      await api.updateWell(wellForm.value.id, {
        code: wellForm.value.code,
        name: wellForm.value.name,
        description: wellForm.value.description || null,
      })
      wellDialog.value = false
      const prev = selectedWell.value
      await chooseProject(selectedProject.value)
      if (prev) {
        const refreshed = wells.value.find(w => w.id === prev.id)
        if (refreshed) await chooseWell(refreshed)
      }
      showFeedback('success', 'Well updated.')
    }
  }
  catch (e: unknown) { showFeedback('error', e instanceof Error ? e.message : 'Could not save well.') }
  finally { saving.value = false }
}

function confirmDeleteWell(row: WellRecord, event: Event): void {
  event.stopPropagation()
  confirm.require({
    message: `Delete well "${row.name}"? Its requirements will be deactivated.`,
    header: 'Delete well',
    icon: 'pi pi-exclamation-triangle',
    rejectProps: { label: 'Cancel', severity: 'secondary', outlined: true },
    acceptProps: { label: 'Delete', severity: 'danger' },
    accept: async () => {
      try {
        await api.deleteWell(row.id)
        if (selectedWell.value?.id === row.id) { selectedWell.value = null; requirements.value = [] }
        if (selectedProject.value) await chooseProject(selectedProject.value)
        showFeedback('success', `Well "${row.name}" deleted.`)
      }
      catch (e: unknown) { showFeedback('error', e instanceof Error ? e.message : 'Could not delete well.') }
    },
  })
}

// ── Requirement CRUD ──────────────────────────────────────────────────
function openReqCreate(): void {
  reqForm.value = { id: '', code: '', title: '', description: '' }
  reqDialogMode.value = 'create'
  reqDialog.value = true
}

function openReqEdit(row: RequirementRecord, event: Event): void {
  event.stopPropagation()
  reqForm.value = { id: row.id, code: row.code, title: row.title, description: row.description ?? '' }
  reqDialogMode.value = 'edit'
  reqDialog.value = true
}

async function saveReq(): Promise<void> {
  if (!selectedWell.value) return
  saving.value = true
  try {
    if (reqDialogMode.value === 'create') {
      const created = await api.createRequirement({
        well_id: selectedWell.value.id,
        code: reqForm.value.code,
        title: reqForm.value.title,
        description: reqForm.value.description || null,
      })
      reqDialog.value = false
      await navigateTo(`/requirements/${created.id}`)
    }
    else {
      await api.updateRequirement(reqForm.value.id, {
        code: reqForm.value.code,
        title: reqForm.value.title,
        description: reqForm.value.description || null,
      })
      reqDialog.value = false
      await chooseWell(selectedWell.value)
      showFeedback('success', 'Requirement updated.')
    }
  }
  catch (e: unknown) { showFeedback('error', e instanceof Error ? e.message : 'Could not save requirement.') }
  finally { saving.value = false }
}

function confirmDeleteReq(row: RequirementRecord, event: Event): void {
  event.stopPropagation()
  confirm.require({
    message: `Delete requirement "${row.title}"?`,
    header: 'Delete requirement',
    icon: 'pi pi-exclamation-triangle',
    rejectProps: { label: 'Cancel', severity: 'secondary', outlined: true },
    acceptProps: { label: 'Delete', severity: 'danger' },
    accept: async () => {
      try {
        await api.deleteRequirement(row.id)
        if (selectedWell.value) await chooseWell(selectedWell.value)
        showFeedback('success', `Requirement "${row.title}" deleted.`)
      }
      catch (e: unknown) { showFeedback('error', e instanceof Error ? e.message : 'Could not delete requirement.') }
    },
  })
}

onMounted(loadProjects)
</script>

<template>
  <div class="wi-page">
    <ConfirmDialog />
    <PageHeader
      title="Well Intake"
      description="Register projects and wells from the planning team. Each well has one or more requirement packages that feed into the AFE."
    />

    <!-- Global feedback -->
    <div v-if="feedback" class="wi-feedback">
      <Message :severity="feedback.type === 'error' ? 'error' : 'success'" :closable="true" @close="feedback = null">
        {{ feedback.msg }}
      </Message>
    </div>

    <div class="wi-columns">

      <!-- ── Projects panel ── -->
      <section class="wi-panel">
        <header class="wi-panel__header">
          <div>
            <span class="wi-step">Step 1</span>
            <h2>Projects</h2>
          </div>
          <Button icon="pi pi-plus" size="small" label="Add" @click="openProjectCreate" />
        </header>
        <DataTable
          :value="projects"
          :loading="loading"
          selection-mode="single"
          data-key="id"
          size="small"
          scroll-height="340px"
          scrollable
          class="wi-table"
          :row-class="(row: ProjectRecord) => ({ 'wi-row--selected': row.id === selectedProject?.id })"
          @row-click="chooseProject($event.data)"
        >
          <Column field="code" header="Code" style="width: 90px" />
          <Column field="name" header="Project name" />
          <Column header="" style="width: 80px; text-align: right">
            <template #body="{ data }">
              <div class="wi-row-actions">
                <Button
                  v-tooltip.top="'Edit'"
                  icon="pi pi-pencil"
                  size="small"
                  text
                  severity="secondary"
                  aria-label="Edit project"
                  @click="openProjectEdit(data, $event)"
                />
                <Button
                  v-tooltip.top="'Delete'"
                  icon="pi pi-trash"
                  size="small"
                  text
                  severity="danger"
                  aria-label="Delete project"
                  @click="confirmDeleteProject(data, $event)"
                />
              </div>
            </template>
          </Column>
          <template #empty><span class="wi-empty">No projects yet — add one to start.</span></template>
        </DataTable>
      </section>

      <!-- ── Wells panel ── -->
      <section class="wi-panel">
        <header class="wi-panel__header">
          <div>
            <span class="wi-step">Step 2</span>
            <h2>Wells <span v-if="selectedProject" class="wi-context">in {{ selectedProject.name }}</span></h2>
          </div>
          <Button icon="pi pi-plus" size="small" label="Add" :disabled="!selectedProject" @click="openWellCreate" />
        </header>
        <DataTable
          :value="wells"
          :loading="wellsLoading"
          selection-mode="single"
          data-key="id"
          size="small"
          scroll-height="340px"
          scrollable
          class="wi-table"
          :row-class="(row: WellRecord) => ({ 'wi-row--selected': row.id === selectedWell?.id })"
          @row-click="chooseWell($event.data)"
        >
          <Column field="code" header="Code" style="width: 90px" />
          <Column field="name" header="Well name" />
          <Column header="" style="width: 80px; text-align: right">
            <template #body="{ data }">
              <div class="wi-row-actions">
                <Button
                  v-tooltip.top="'Edit'"
                  icon="pi pi-pencil"
                  size="small"
                  text
                  severity="secondary"
                  aria-label="Edit well"
                  @click="openWellEdit(data, $event)"
                />
                <Button
                  v-tooltip.top="'Delete'"
                  icon="pi pi-trash"
                  size="small"
                  text
                  severity="danger"
                  aria-label="Delete well"
                  @click="confirmDeleteWell(data, $event)"
                />
              </div>
            </template>
          </Column>
          <template #empty>
            <span class="wi-empty">{{ selectedProject ? 'No wells — add the first one.' : 'Select a project first.' }}</span>
          </template>
        </DataTable>
      </section>

      <!-- ── Requirements panel ── -->
      <section class="wi-panel wi-panel--wide">
        <header class="wi-panel__header">
          <div>
            <span class="wi-step">Step 3</span>
            <h2>
              Requirements
              <span v-if="selectedWell" class="wi-context">for {{ selectedWell.name }}</span>
            </h2>
          </div>
          <div class="wi-panel__controls">
            <Select
              v-model="statusFilter"
              :options="[{ label: 'All statuses', value: null }, { label: 'Draft', value: 'draft' }, { label: 'Submitted', value: 'submitted' }]"
              option-label="label"
              option-value="value"
              placeholder="All statuses"
              style="width: 150px"
            />
            <Button icon="pi pi-plus" size="small" label="New" :disabled="!selectedWell" @click="openReqCreate" />
          </div>
        </header>
        <DataTable
          :value="filteredRequirements"
          :loading="reqLoading"
          data-key="id"
          size="small"
          paginator
          :rows="15"
          scroll-height="340px"
          scrollable
          class="wi-table"
        >
          <Column field="code" header="Code" style="width: 100px" />
          <Column field="title" header="Requirement title">
            <template #body="{ data }">
              <NuxtLink :to="`/requirements/${data.id}`" class="wi-link">{{ data.title }}</NuxtLink>
            </template>
          </Column>
          <Column field="revision_number" header="Rev." style="width: 60px" />
          <Column field="item_count" header="Items" style="width: 70px" />
          <Column field="status" header="Status" style="width: 100px">
            <template #body="{ data }">
              <Tag
                :value="data.status"
                :severity="data.status === 'draft' ? 'warn' : 'success'"
              />
            </template>
          </Column>
          <Column header="" style="width: 90px; text-align: right">
            <template #body="{ data }">
              <div class="wi-row-actions">
                <Button
                  v-tooltip.top="'Open'"
                  icon="pi pi-arrow-right"
                  size="small"
                  text
                  severity="secondary"
                  aria-label="Open requirement"
                  @click="navigateTo(`/requirements/${data.id}`)"
                />
                <Button
                  v-tooltip.top="'Edit'"
                  icon="pi pi-pencil"
                  size="small"
                  text
                  severity="secondary"
                  aria-label="Edit requirement"
                  @click="openReqEdit(data, $event)"
                />
                <Button
                  v-tooltip.top="'Delete'"
                  icon="pi pi-trash"
                  size="small"
                  text
                  severity="danger"
                  aria-label="Delete requirement"
                  @click="confirmDeleteReq(data, $event)"
                />
              </div>
            </template>
          </Column>
          <template #empty>
            <span class="wi-empty">{{ selectedWell ? 'No requirements — create the first one.' : 'Select a well first.' }}</span>
          </template>
        </DataTable>
      </section>
    </div>

    <!-- ── Project dialog ── -->
    <Dialog
      v-model:visible="projectDialog"
      modal
      :header="projectDialogMode === 'create' ? 'Add project' : 'Edit project'"
      style="width: 460px"
    >
      <div class="form-stack">
        <label>Code <span class="wi-required">*</span><InputText v-model="projectForm.code" fluid placeholder="e.g. PROJ-001" /></label>
        <label>Project name <span class="wi-required">*</span><InputText v-model="projectForm.name" fluid /></label>
        <label>Description<Textarea v-model="projectForm.description" fluid rows="2" auto-resize /></label>
      </div>
      <template #footer>
        <Button label="Cancel" severity="secondary" outlined @click="projectDialog = false" />
        <Button
          :label="projectDialogMode === 'create' ? 'Create project' : 'Save changes'"
          icon="pi pi-save"
          :loading="saving"
          :disabled="!projectForm.code || !projectForm.name"
          @click="saveProject"
        />
      </template>
    </Dialog>

    <!-- ── Well dialog ── -->
    <Dialog
      v-model:visible="wellDialog"
      modal
      :header="wellDialogMode === 'create' ? 'Add well' : 'Edit well'"
      style="width: 460px"
    >
      <div class="form-stack">
        <label>Well code <span class="wi-required">*</span><InputText v-model="wellForm.code" fluid placeholder="e.g. WL-001" /></label>
        <label>Well name <span class="wi-required">*</span><InputText v-model="wellForm.name" fluid placeholder="e.g. Block-A Well-1" /></label>
        <label>Description<Textarea v-model="wellForm.description" fluid rows="2" auto-resize /></label>
      </div>
      <template #footer>
        <Button label="Cancel" severity="secondary" outlined @click="wellDialog = false" />
        <Button
          :label="wellDialogMode === 'create' ? 'Create well' : 'Save changes'"
          icon="pi pi-save"
          :loading="saving"
          :disabled="!wellForm.code || !wellForm.name"
          @click="saveWell"
        />
      </template>
    </Dialog>

    <!-- ── Requirement dialog ── -->
    <Dialog
      v-model:visible="reqDialog"
      modal
      :header="reqDialogMode === 'create' ? 'New requirement package' : 'Edit requirement'"
      style="width: 480px"
    >
      <div class="form-stack">
        <label>Code <span class="wi-required">*</span><InputText v-model="reqForm.code" fluid placeholder="e.g. REQ-001" /></label>
        <label>Title <span class="wi-required">*</span><InputText v-model="reqForm.title" fluid placeholder="e.g. Drilling Phase Requirements" /></label>
        <label>Description<Textarea v-model="reqForm.description" fluid rows="2" auto-resize /></label>
      </div>
      <template #footer>
        <Button label="Cancel" severity="secondary" outlined @click="reqDialog = false" />
        <Button
          :label="reqDialogMode === 'create' ? 'Create & open' : 'Save changes'"
          icon="pi pi-arrow-right"
          :loading="saving"
          :disabled="!reqForm.code || !reqForm.title"
          @click="saveReq"
        />
      </template>
    </Dialog>
  </div>
</template>

