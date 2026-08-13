<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import Button from 'primevue/button'
import Column from 'primevue/column'
import DataTable from 'primevue/datatable'
import Dialog from 'primevue/dialog'
import InputText from 'primevue/inputtext'
import Select from 'primevue/select'
import Tag from 'primevue/tag'
import PageHeader from '~/components/design-system/PageHeader.vue'
import type { ProjectRecord, RequirementRecord, WellRecord } from '~/types/requirements'

definePageMeta({ middleware: 'auth' })

const api = useRequirements()
const projects = ref<ProjectRecord[]>([])
const wells = ref<WellRecord[]>([])
const requirements = ref<RequirementRecord[]>([])
const selectedProject = ref<ProjectRecord | null>(null)
const selectedWell = ref<WellRecord | null>(null)
const statusFilter = ref<string | null>(null)
const loading = ref(false)
const error = ref<string | null>(null)
const projectDialog = ref(false)
const wellDialog = ref(false)
const requirementDialog = ref(false)
const projectForm = ref({ code: '', name: '', description: '' })
const wellForm = ref({ code: '', name: '', description: '' })
const requirementForm = ref({ code: '', title: '', description: '' })

const filteredRequirements = computed(() => statusFilter.value
  ? requirements.value.filter(item => item.status === statusFilter.value)
  : requirements.value)

async function loadProjects(): Promise<void> {
  projects.value = (await api.listProjects()).items
  if (!selectedProject.value && projects.value.length) await chooseProject(projects.value[0]!)
}

async function chooseProject(project: ProjectRecord): Promise<void> {
  selectedProject.value = project
  selectedWell.value = null
  wells.value = (await api.listWells(project.id)).items
  requirements.value = []
  if (wells.value.length) await chooseWell(wells.value[0]!)
}

async function chooseWell(well: WellRecord): Promise<void> {
  selectedWell.value = well
  requirements.value = (await api.listRequirements(well.id)).items
}

async function createProject(): Promise<void> {
  const created = await api.createProject(projectForm.value)
  projectDialog.value = false
  projectForm.value = { code: '', name: '', description: '' }
  await loadProjects()
  await chooseProject(created)
}

async function createWell(): Promise<void> {
  if (!selectedProject.value) return
  const created = await api.createWell({ ...wellForm.value, project_id: selectedProject.value.id })
  wellDialog.value = false
  wellForm.value = { code: '', name: '', description: '' }
  await chooseProject(selectedProject.value)
  await chooseWell(created)
}

async function createRequirement(): Promise<void> {
  if (!selectedWell.value) return
  const created = await api.createRequirement({ ...requirementForm.value, well_id: selectedWell.value.id })
  await navigateTo(`/requirements/${created.id}`)
}

onMounted(async () => {
  loading.value = true
  try { await loadProjects() }
  catch (caught: unknown) { error.value = caught instanceof Error ? caught.message : 'Requirements could not be loaded' }
  finally { loading.value = false }
})
</script>

<template>
  <div class="requirements-page">
    <PageHeader title="Requirement intake" description="Capture costing inputs supplied by the well-planning team. This module records requirements; it does not perform engineering design." />
    <p v-if="error" class="error-copy">{{ error }}</p>
    <div class="intake-columns">
      <section class="intake-panel">
        <header><div><small>STEP 1</small><h2>Projects</h2></div><Button icon="pi pi-plus" text rounded aria-label="Add project" @click="projectDialog = true" /></header>
        <DataTable :value="projects" :loading="loading" selection-mode="single" data-key="id" size="small" @row-click="chooseProject($event.data)">
          <Column field="code" header="Code" />
          <Column field="name" header="Project" />
          <template #empty>No projects yet.</template>
        </DataTable>
      </section>
      <section class="intake-panel">
        <header><div><small>STEP 2</small><h2>Wells</h2></div><Button icon="pi pi-plus" text rounded aria-label="Add well" :disabled="!selectedProject" @click="wellDialog = true" /></header>
        <DataTable :value="wells" selection-mode="single" data-key="id" size="small" @row-click="chooseWell($event.data)">
          <Column field="code" header="Code" />
          <Column field="name" header="Well" />
          <template #empty>Select a project or add its first well.</template>
        </DataTable>
      </section>
      <section class="intake-panel intake-panel--wide">
        <header>
          <div><small>STEP 3</small><h2>Requirements</h2></div>
          <div class="panel-actions"><Select v-model="statusFilter" :options="[{ label: 'All', value: null }, { label: 'Draft', value: 'draft' }, { label: 'Submitted', value: 'submitted' }]" option-label="label" option-value="value" placeholder="Status" /><Button icon="pi pi-plus" label="New" size="small" :disabled="!selectedWell" @click="requirementDialog = true" /></div>
        </header>
        <DataTable :value="filteredRequirements" data-key="id" size="small" paginator :rows="10">
          <Column field="code" header="Code" />
          <Column field="title" header="Requirement"><template #body="{ data }"><NuxtLink :to="`/requirements/${data.id}`">{{ data.title }}</NuxtLink></template></Column>
          <Column field="item_count" header="Items" />
          <Column field="status" header="Status"><template #body="{ data }"><Tag :value="data.status" :severity="data.status === 'draft' ? 'warn' : 'success'" /></template></Column>
          <template #empty>Select a well or create its first requirement.</template>
        </DataTable>
      </section>
    </div>

    <Dialog v-model:visible="projectDialog" modal header="Add project" :style="{ width: '440px' }"><div class="form-stack"><label>Code<InputText v-model="projectForm.code" fluid /></label><label>Name<InputText v-model="projectForm.name" fluid /></label><label>Description<InputText v-model="projectForm.description" fluid /></label></div><template #footer><Button label="Create project" @click="createProject" /></template></Dialog>
    <Dialog v-model:visible="wellDialog" modal header="Add well" :style="{ width: '440px' }"><div class="form-stack"><label>Code<InputText v-model="wellForm.code" fluid /></label><label>Name<InputText v-model="wellForm.name" fluid /></label><label>Description<InputText v-model="wellForm.description" fluid /></label></div><template #footer><Button label="Create well" @click="createWell" /></template></Dialog>
    <Dialog v-model:visible="requirementDialog" modal header="New requirement" :style="{ width: '480px' }"><div class="form-stack"><label>Code<InputText v-model="requirementForm.code" fluid /></label><label>Title<InputText v-model="requirementForm.title" fluid /></label><label>Description<InputText v-model="requirementForm.description" fluid /></label></div><template #footer><Button label="Create and open" @click="createRequirement" /></template></Dialog>
  </div>
</template>
