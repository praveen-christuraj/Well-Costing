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
import type { Estimate } from '~/types/estimates'
import type { MasterDataRecord } from '~/types/masterData'
import type { AfeRecord } from '~/types/afe'
definePageMeta({ middleware: 'auth' })
const api = useEstimates(); const reqApi = useAfe(); const master = useMasterData()
const estimates = ref<Estimate[]>([]); const submittedAfes = ref<AfeRecord[]>([]); const currencies = ref<MasterDataRecord[]>([])
const visible = ref(false); const form = ref({ afe_id: '', code: '', title: '', currency_id: '' }); const error = ref<string | null>(null)
const success = ref<string | null>(null); const showDeleted = ref(false); const loading = ref(false)

const deletedCount = computed(() => estimates.value.filter(estimate => !estimate.is_active).length)
const visibleEstimates = computed(() =>
  showDeleted.value ? estimates.value : estimates.value.filter(estimate => estimate.is_active))

async function load() {
  const [e, r, c] = await Promise.all([api.list(null), reqApi.listAfes(undefined, 'submitted'), master.list('currencies')])
  estimates.value = e.items; submittedAfes.value = r.items; currencies.value = c.items.filter(x => x.is_active)
}
async function generate() {
  error.value = null
  try { const created = await api.generate(form.value); visible.value = false; await navigateTo(`/cost-builder/${created.id}`) }
  catch (caught: unknown) { error.value = caught instanceof Error ? caught.message : 'Generation failed' }
}
async function deleteEstimate(estimate: Estimate) {
  if (!window.confirm(`Delete cost build ${estimate.code}? It moves to the deleted list and can be recovered or permanently deleted from there.`)) return
  error.value = null
  try { await api.delete(estimate.id) }
  catch (caught: unknown) { error.value = caught instanceof Error ? caught.message : 'The cost build could not be deleted.'; return }
  success.value = `Cost build ${estimate.code} deleted.`; await load()
}
async function recoverEstimate(estimate: Estimate) {
  error.value = null
  try { await api.recover(estimate.id) }
  catch (caught: unknown) { error.value = caught instanceof Error ? caught.message : 'The cost build could not be recovered.'; return }
  success.value = `Cost build ${estimate.code} recovered.`; await load()
}
async function hardDeleteEstimate(estimate: Estimate) {
  if (!window.confirm(`Permanently delete cost build ${estimate.code}? This cannot be undone and removes all its versions. Cost builds with a baseline AFE snapshot cannot be permanently deleted.`)) return
  error.value = null
  try { await api.hardDelete(estimate.id) }
  catch (caught: unknown) { error.value = caught instanceof Error ? caught.message : 'The cost build could not be permanently deleted.'; return }
  success.value = `Cost build ${estimate.code} permanently deleted.`; await load()
}
onMounted(() => { loading.value = true; void load().finally(() => { loading.value = false }) })
</script>
<template><div class="library-page"><PageHeader title="Bulk cost builder" description="Generate a versioned, bulk-editable cost structure from a submitted AFE. Financial results remain pending until the full-chain rules are confirmed."><template #actions><Button label="New cost build" icon="pi pi-plus" @click="visible = true" /></template></PageHeader>
  <p v-if="success" class="success-copy">{{ success }}</p>
  <p v-if="error" class="error-copy">{{ error }}</p><DataTable :value="visibleEstimates" :loading="loading" class="bulk-grid-panel" paginator :rows="25" striped-rows show-gridlines><template #header><div class="grid-toolbar"><div><small class="toolbar-note">Deleting a cost build is recoverable until "Delete forever"; every action is written to the audit trail.</small></div><div class="grid-toolbar__actions"><Button :label="showDeleted ? 'Hide deleted' : `Deleted (${deletedCount})`" icon="pi pi-trash" text severity="secondary" :disabled="!deletedCount && !showDeleted" @click="showDeleted = !showDeleted" /></div></div></template><Column field="code" header="Code" /><Column field="title" header="Estimate"><template #body="{ data }"><NuxtLink :to="`/cost-builder/${data.id}`">{{ data.title }}</NuxtLink></template></Column><Column field="project_code" header="Project" /><Column field="well_code" header="Well" /><Column field="currency_code" header="Currency" /><Column field="current_version_number" header="Version" /><Column header="Status"><template #body="{ data }"><Tag v-if="!data.is_active" value="Deleted" severity="danger" /><Tag v-else value="Pending calculation" severity="warn" /></template></Column><Column header="Actions" :style="{ width: '170px' }"><template #body="{ data }"><template v-if="data.is_active"><Button icon="pi pi-trash" size="small" text severity="danger" aria-label="Delete cost build" title="Delete (recoverable)" @click="deleteEstimate(data)" /></template><template v-else><Button icon="pi pi-undo" size="small" text severity="success" aria-label="Recover cost build" title="Recover" @click="recoverEstimate(data)" /><Button icon="pi pi-trash" size="small" text severity="danger" aria-label="Permanently delete cost build" title="Delete forever" @click="hardDeleteEstimate(data)" /></template></template></Column><template #empty>No cost builds yet.</template></DataTable><Dialog v-model:visible="visible" modal header="Generate from AFE" :style="{ width: '520px' }"><div class="form-stack"><label>Submitted AFE<Select v-model="form.afe_id" :options="submittedAfes" option-label="title" option-value="id" filter fluid /></label><label>Estimate code<InputText v-model="form.code" fluid /></label><label>Title<InputText v-model="form.title" fluid /></label><label>Currency<Select v-model="form.currency_id" :options="currencies" option-label="code" option-value="id" fluid /></label></div><template #footer><Button label="Generate cost build" @click="generate" /></template></Dialog></div></template>
