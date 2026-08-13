<script setup lang="ts">
import { onMounted, ref } from 'vue'
import Button from 'primevue/button'
import Column from 'primevue/column'
import DataTable from 'primevue/datatable'
import Dialog from 'primevue/dialog'
import InputText from 'primevue/inputtext'
import Select from 'primevue/select'
import Tag from 'primevue/tag'
import PageHeader from '~/components/design-system/PageHeader.vue'
import type { Estimate } from '~/types/estimates'
import type { MasterDataRecord } from '~/types/masterData'
import type { RequirementRecord } from '~/types/requirements'
definePageMeta({ middleware: 'auth' })
const api = useEstimates(); const reqApi = useRequirements(); const master = useMasterData()
const estimates = ref<Estimate[]>([]); const requirements = ref<RequirementRecord[]>([]); const currencies = ref<MasterDataRecord[]>([])
const visible = ref(false); const form = ref({ requirement_id: '', code: '', title: '', currency_id: '' }); const error = ref<string | null>(null)
async function load() { const [e, r, c] = await Promise.all([api.list(), reqApi.listRequirements(undefined, 'submitted'), master.list('currencies')]); estimates.value = e.items; requirements.value = r.items; currencies.value = c.items.filter(x => x.is_active) }
async function generate() { try { const created = await api.generate(form.value); await navigateTo(`/cost-builder/${created.id}`) } catch (caught: unknown) { error.value = caught instanceof Error ? caught.message : 'Generation failed' } }
onMounted(() => void load())
</script>
<template><div class="requirements-page"><PageHeader title="Bulk cost builder" description="Generate a versioned, bulk-editable cost structure from a submitted requirement. Financial results remain pending until the full-chain rules are confirmed."><template #actions><Button label="New cost build" icon="pi pi-plus" @click="visible = true" /></template></PageHeader><p v-if="error" class="error-copy">{{ error }}</p><DataTable :value="estimates" class="bulk-grid-panel" paginator :rows="25" striped-rows show-gridlines><Column field="code" header="Code" /><Column field="title" header="Estimate"><template #body="{ data }"><NuxtLink :to="`/cost-builder/${data.id}`">{{ data.title }}</NuxtLink></template></Column><Column field="project_code" header="Project" /><Column field="well_code" header="Well" /><Column field="currency_code" header="Currency" /><Column field="current_version_number" header="Version" /><Column header="Status"><template #body><Tag value="Pending calculation" severity="warn" /></template></Column><template #empty>No cost builds yet.</template></DataTable><Dialog v-model:visible="visible" modal header="Generate from requirement" :style="{ width: '520px' }"><div class="form-stack"><label>Submitted requirement<Select v-model="form.requirement_id" :options="requirements" option-label="title" option-value="id" filter fluid /></label><label>Estimate code<InputText v-model="form.code" fluid /></label><label>Title<InputText v-model="form.title" fluid /></label><label>Currency<Select v-model="form.currency_id" :options="currencies" option-label="code" option-value="id" fluid /></label></div><template #footer><Button label="Generate cost build" @click="generate" /></template></Dialog></div></template>
