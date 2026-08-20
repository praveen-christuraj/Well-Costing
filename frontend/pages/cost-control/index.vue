<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import Button from 'primevue/button'
import Column from 'primevue/column'
import DataTable from 'primevue/datatable'
import Dialog from 'primevue/dialog'
import InputText from 'primevue/inputtext'
import Message from 'primevue/message'
import Select from 'primevue/select'
import Tag from 'primevue/tag'
import Textarea from 'primevue/textarea'
import PageHeader from '~/components/design-system/PageHeader.vue'
import type { Estimate } from '~/types/estimates'
import type { CostControlBatch, CostControlLineInput, CostState } from '~/types/costControl'
import { parseTsv } from '~/utils/tsv'

definePageMeta({ middleware: 'auth' })
const api = useCostControl(); const estimatesApi = useEstimates()
const estimates = ref<Estimate[]>([]); const batches = ref<CostControlBatch[]>([])
const estimateId = ref(''); const versionId = ref(''); const costState = ref<CostState>('field_estimate')
const activeBatch = ref<CostControlBatch | null>(null); const error = ref<string | null>(null); const posting = ref(false); const validating = ref(false)
const pasteVisible = ref(false); const pasteText = ref('')
type GridRow = CostControlLineInput & { _key: number }
let key = 0
const blank = (): GridRow => ({ _key: ++key, transaction_date: new Date().toISOString().slice(0, 10), source_document_type: '', source_document_reference: '', external_transaction_id: null, cost_code: '', vendor_code: null, description: '', quantity: null, unit_code: null, currency_code: '', amount: '', correction_kind: 'original', reverses_transaction_id: null })
const rows = ref<GridRow[]>([blank()])
const selectedEstimate = computed(() => estimates.value.find(item => item.id === estimateId.value))
const versions = computed(() => selectedEstimate.value?.versions ?? [])
const stateOptions = [
  { label: 'Field estimate', value: 'field_estimate' }, { label: 'Commitment', value: 'commitment' },
  { label: 'Accrual', value: 'accrual' }, { label: 'Booked actual', value: 'actual' }, { label: 'Forecast', value: 'forecast' },
]
const pasteColumns = ['transaction_date', 'source_document_type', 'source_document_reference', 'external_transaction_id', 'cost_code', 'vendor_code', 'description', 'quantity', 'unit_code', 'currency_code', 'amount'].map(field => ({ field }))
function chooseEstimate() { versionId.value = versions.value.find(item => item.version_number === selectedEstimate.value?.current_version_number)?.id ?? versions.value[0]?.id ?? '' }
async function load() { const [estimatePage, batchPage] = await Promise.all([estimatesApi.list(), api.list()]); estimates.value = estimatePage.items; batches.value = batchPage.items; if (!estimateId.value && estimates.value[0]) { estimateId.value = estimates.value[0].id; chooseEstimate() } }
function addRow() { rows.value.unshift(blank()) }
function duplicateRow(row: GridRow) { rows.value.unshift({ ...row, _key: ++key }) }
function applyPaste() { const parsed = parseTsv(pasteText.value, pasteColumns); rows.value.unshift(...parsed.map(item => ({ ...blank(), ...item, external_transaction_id: item.external_transaction_id || null, vendor_code: item.vendor_code || null, quantity: item.quantity || null, unit_code: item.unit_code || null }))); pasteVisible.value = false; pasteText.value = '' }
async function validateBatch() { if (!versionId.value) { error.value = 'Select an estimate version.'; return } validating.value = true; error.value = null; try { activeBatch.value = await api.validate(versionId.value, costState.value, rows.value.map(({ _key, ...row }) => row)); await load() } catch (caught: unknown) { error.value = caught instanceof Error ? caught.message : 'Validation failed' } finally { validating.value = false } }
async function postBatch() { if (!activeBatch.value) return; posting.value = true; error.value = null; try { activeBatch.value = await api.post(activeBatch.value.id) } catch (caught: unknown) { error.value = caught instanceof Error ? caught.message : 'Posting blocked'; activeBatch.value = await api.get(activeBatch.value.id); await load() } finally { posting.value = false } }
async function upload(event: Event) { const input = event.target as HTMLInputElement; const file = input.files?.[0]; if (!file || !versionId.value) return; error.value = null; try { activeBatch.value = (await api.preview(versionId.value, costState.value, file)).batch; await load() } catch (caught: unknown) { error.value = caught instanceof Error ? caught.message : 'Import preview failed' } finally { input.value = '' } }
async function downloadTemplate() { const blob = await api.template(); const url = URL.createObjectURL(blob); const link = document.createElement('a'); link.href = url; link.download = 'cost-control-template.xlsx'; link.click(); URL.revokeObjectURL(url) }
onMounted(() => void load().catch((caught: unknown) => { error.value = caught instanceof Error ? caught.message : 'Load failed' }))
</script>

<template>
  <div class="cost-control-page">
    <PageHeader title="Cost control staging" description="Keep field estimates, commitments, accruals, booked actuals, and forecasts separate. Posting remains blocked until authoritative recognition and allocation rules are approved.">
      <template #actions><Button label="Template" icon="pi pi-file-excel" outlined @click="downloadTemplate" /><label class="p-button p-component p-button-outlined"><i class="pi pi-upload" /> Excel preview<input type="file" accept=".xlsx,.xlsm,.xls" hidden @change="upload"></label></template>
    </PageHeader>
    <Message severity="warn" :closable="false">All rows are staging records only. No AFE posting, reconciliation, forecast, or reversal amount is calculated under policy <strong>pending-all-cost-states</strong>.</Message>
    <Message v-if="error" severity="error" :closable="false">{{ error }}</Message>

    <section class="cost-control-setup bulk-grid-panel">
      <label>Estimate<Select v-model="estimateId" :options="estimates" option-label="title" option-value="id" filter fluid @change="chooseEstimate" /></label>
      <label>Version<Select v-model="versionId" :options="versions" option-label="version_number" option-value="id" fluid /></label>
      <label>Cost state<Select v-model="costState" :options="stateOptions" option-label="label" option-value="value" fluid /></label>
    </section>

    <div class="grid-toolbar bulk-grid-panel"><strong>Bulk staging grid</strong><div class="grid-toolbar__actions"><Button label="Add row" icon="pi pi-plus" text @click="addRow" /><Button label="Paste" icon="pi pi-clipboard" text @click="pasteVisible = true" /><Button label="Validate batch" icon="pi pi-check" :loading="validating" @click="validateBatch" /></div></div>
    <DataTable :value="rows" data-key="_key" show-gridlines scrollable class="bulk-grid-panel" :rows="25" paginator>
      <Column header="#"><template #body="{ index }">{{ index + 1 }}</template></Column>
      <Column header="Date" style="min-width:130px"><template #body="{ data }"><InputText v-model="data.transaction_date" fluid /></template></Column>
      <Column header="Document type" style="min-width:150px"><template #body="{ data }"><InputText v-model="data.source_document_type" fluid /></template></Column>
      <Column header="Document reference" style="min-width:170px"><template #body="{ data }"><InputText v-model="data.source_document_reference" fluid /></template></Column>
      <Column header="Cost code" style="min-width:130px"><template #body="{ data }"><InputText v-model="data.cost_code" fluid /></template></Column>
      <Column header="Vendor" style="min-width:130px"><template #body="{ data }"><InputText v-model="data.vendor_code" fluid /></template></Column>
      <Column header="Description" style="min-width:220px"><template #body="{ data }"><InputText v-model="data.description" fluid /></template></Column>
      <Column header="Qty" style="min-width:110px"><template #body="{ data }"><InputText v-model="data.quantity" fluid /></template></Column>
      <Column header="Unit" style="min-width:100px"><template #body="{ data }"><InputText v-model="data.unit_code" fluid /></template></Column>
      <Column header="Currency" style="min-width:110px"><template #body="{ data }"><InputText v-model="data.currency_code" fluid /></template></Column>
      <Column header="Amount" style="min-width:130px"><template #body="{ data }"><InputText v-model="data.amount" fluid /></template></Column>
      <Column header="Correction" style="min-width:140px"><template #body="{ data }"><Select v-model="data.correction_kind" :options="['original','reversal','adjustment']" fluid /></template></Column>
      <Column header=""><template #body="{ data }"><Button icon="pi pi-copy" text aria-label="Duplicate row" @click="duplicateRow(data)" /></template></Column>
    </DataTable>

    <section v-if="activeBatch" class="cost-control-batch-panel">
      <div><span class="eyebrow">Active batch</span><h2>{{ activeBatch.cost_state.replace('_', ' ') }}</h2></div>
      <Tag :value="activeBatch.status" :severity="activeBatch.status === 'validated' ? 'success' : 'warn'" />
      <span>{{ activeBatch.valid_rows }} valid · {{ activeBatch.error_rows }} errors · AFE {{ activeBatch.afe_snapshot_id ? 'linked' : 'missing' }}</span>
      <Button label="Post immutable records" icon="pi pi-lock" :disabled="activeBatch.status === 'invalid'" :loading="posting" @click="postBatch" />
    </section>

    <section class="cost-control-history"><h2>Staging history</h2><DataTable :value="batches" show-gridlines class="bulk-grid-panel"><Column field="cost_state" header="Cost state" /><Column field="source_type" header="Source" /><Column field="total_rows" header="Rows" /><Column field="status" header="Status"><template #body="{ data }"><Tag :value="data.status" /></template></Column><Column field="created_at" header="Created" /></DataTable></section>

    <Dialog v-model:visible="pasteVisible" modal header="Paste cost-control rows" :style="{ width: '760px' }"><p>Column order: date, document type, document reference, external ID, cost code, vendor, description, quantity, unit, currency, amount.</p><Textarea v-model="pasteText" rows="10" fluid /><template #footer><Button label="Apply rows" @click="applyPaste" /></template></Dialog>
  </div>
</template>
