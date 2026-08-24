<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import Button from 'primevue/button'
import Checkbox from 'primevue/checkbox'
import Column from 'primevue/column'
import DataTable from 'primevue/datatable'
import Dialog from 'primevue/dialog'
import InputText from 'primevue/inputtext'
import Message from 'primevue/message'
import Select from 'primevue/select'
import Textarea from 'primevue/textarea'
import ImportWizard from '~/components/cost-library/ImportWizard.vue'
import { parseTsv } from '~/utils/tsv'
import type { MasterDataWrite } from '~/services/masterData'
import type { EditableMasterDataRow, MasterDataRecord } from '~/types/masterData'

const props = defineProps<{
  entity: string
  label: string
  singular: string
  supportsSymbol?: boolean
}>()

const api = useMasterData()
const rows = ref<EditableMasterDataRow[]>([])
const selected = ref<EditableMasterDataRow[]>([])
const costCategories = ref<MasterDataRecord[]>([])
const costCodes = ref<MasterDataRecord[]>([])
const units = ref<MasterDataRecord[]>([])
const loading = ref(false)
const saving = ref(false)
const error = ref<string | null>(null)
const message = ref<string | null>(null)
const search = ref('')
const importVisible = ref(false)
const pasteVisible = ref(false)
const pasteText = ref('')
const bulkVisible = ref(false)
const bulkField = ref<'description' | 'is_active'>('description')
const bulkValue = ref('')

const dirtyCount = computed(() => rows.value.filter(row => row._state !== 'clean').length)
const isCatalog = computed(() => ['services', 'tangibles', 'materials', 'equipment'].includes(props.entity))
const usesCategory = computed(() => isCatalog.value || props.entity === 'cost-codes')
const columns = computed(() => [
  { field: 'code' },
  { field: 'name' },
  ...(props.supportsSymbol ? [{ field: 'symbol' }] : []),
  { field: 'description' },
])

function editable(record: MasterDataRecord): EditableMasterDataRow {
  return {
    id: record.id,
    code: record.code,
    name: record.name,
    description: record.description ?? '',
    is_active: record.is_active,
    symbol: record.symbol ?? '',
    parent_id: record.parent_id ?? '',
    cost_category_id: record.cost_category_id ?? '',
    cost_code_id: record.cost_code_id ?? '',
    default_unit_id: record.default_unit_id ?? '',
    _state: 'clean',
  }
}

async function load(): Promise<void> {
  loading.value = true
  error.value = null
  try {
    const [response, categoryPage, codePage, unitPage] = await Promise.all([
      api.list(props.entity, search.value),
      props.entity === 'cost-categories' || usesCategory.value ? api.list('cost-categories') : Promise.resolve(null),
      isCatalog.value ? api.list('cost-codes') : Promise.resolve(null),
      isCatalog.value ? api.list('units') : Promise.resolve(null),
    ])
    rows.value = response.items.map(editable)
    costCategories.value = categoryPage?.items ?? []
    costCodes.value = codePage?.items ?? []
    units.value = unitPage?.items ?? []
    selected.value = []
  }
  catch (caught: unknown) {
    error.value = caught instanceof Error ? caught.message : 'Cost library could not be loaded'
  }
  finally {
    loading.value = false
  }
}

function markDirty(row: EditableMasterDataRow): void {
  if (row._state === 'clean') row._state = 'dirty'
}

function addRows(count = 5): void {
  // New rows are unshifted so data entry always happens at the top of the grid.
  rows.value.unshift(...Array.from({ length: count }, () => ({
    code: '',
    name: '',
    description: '',
    is_active: true,
    symbol: '',
    parent_id: '',
    cost_category_id: '',
    cost_code_id: '',
    default_unit_id: '',
    _state: 'new' as const,
  })))
}

function duplicateSelected(): void {
  const copies = selected.value.map((row) => {
    const { id: _id, ...copy } = row
    return { ...copy, code: `${row.code}-COPY`, _state: 'new' as const }
  })
  rows.value.unshift(...copies)
  selected.value = []
}

function applyPaste(): void {
  const parsed = parseTsv(pasteText.value, columns.value)
  rows.value.unshift(...parsed.map(values => ({
    code: values.code ?? '',
    name: values.name ?? '',
    symbol: values.symbol ?? '',
    description: values.description ?? '',
    is_active: true,
    _state: 'new' as const,
  })))
  pasteText.value = ''
  pasteVisible.value = false
}

function applyBulkEdit(): void {
  for (const row of selected.value) {
    if (bulkField.value === 'description') row.description = bulkValue.value
    else row.is_active = ['true', 'yes', '1', 'active'].includes(bulkValue.value.toLowerCase())
    markDirty(row)
  }
  bulkVisible.value = false
}

function writeRow(row: EditableMasterDataRow, includeId = false): MasterDataWrite {
  return {
    ...(includeId && row.id ? { id: row.id } : {}),
    code: row.code,
    name: row.name,
    description: row.description || null,
    is_active: row.is_active,
    ...(props.supportsSymbol ? { symbol: row.symbol || null } : {}),
    ...(props.entity === 'cost-categories' ? { parent_id: row.parent_id || null } : {}),
    ...(usesCategory.value ? { cost_category_id: row.cost_category_id || null } : {}),
    ...(isCatalog.value ? {
      cost_code_id: row.cost_code_id || null,
      default_unit_id: row.default_unit_id || null,
    } : {}),
  }
}

async function save(): Promise<void> {
  saving.value = true
  error.value = null
  message.value = null
  try {
    const newRows = rows.value.filter(row => row._state === 'new' && row.code && row.name)
    const changedRows = rows.value.filter(row => row._state === 'dirty' && row.id)
    if (newRows.length) {
      const payload = newRows.map(row => writeRow(row))
      const validation = await api.validate(props.entity, payload)
      if (!validation.valid) throw new Error(validation.errors.map(item => `Row ${item.row_index + 1}: ${item.message}`).join('; '))
      await api.bulkCreate(props.entity, payload)
    }
    if (changedRows.length) {
      await api.bulkUpdate(props.entity, changedRows.map(row => writeRow(row, true)))
    }
    message.value = `${newRows.length + changedRows.length} rows saved.`
    await load()
  }
  catch (caught: unknown) {
    error.value = caught instanceof Error ? caught.message : 'Save failed'
  }
  finally {
    saving.value = false
  }
}

async function deactivateSelected(): Promise<void> {
  const targets = selected.value.filter(row => row.id)
  if (!targets.length) return
  if (!window.confirm(`Deactivate ${targets.length} selected ${props.label.toLowerCase()}? They will be hidden from active selectors and retained in the audit history.`)) return
  loading.value = true
  try {
    await Promise.all(selected.value.filter(row => row.id).map(row => api.deactivate(props.entity, row.id!)))
    await load()
  }
  finally {
    loading.value = false
  }
}

async function exportWorkbook(): Promise<void> {
  const blob = await api.export(props.entity)
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = `${props.entity}-export.xlsx`
  anchor.click()
  URL.revokeObjectURL(url)
}

let searchTimer: ReturnType<typeof setTimeout> | undefined
watch(search, () => {
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = setTimeout(() => void load(), 300)
})
watch(() => props.entity, () => void load())
onMounted(() => void load())
</script>

<template>
  <div class="bulk-grid-panel">
    <div class="grid-toolbar">
      <div class="grid-toolbar__search">
        <i class="pi pi-search" />
        <InputText v-model="search" :placeholder="`Search ${label.toLowerCase()}…`" />
      </div>
      <div class="grid-toolbar__actions">
        <Button label="Add rows" icon="pi pi-plus" severity="secondary" outlined @click="addRows()" />
        <Button label="Paste" icon="pi pi-clipboard" severity="secondary" outlined @click="pasteVisible = true" />
        <Button label="Duplicate" icon="pi pi-copy" severity="secondary" text :disabled="!selected.length" @click="duplicateSelected" />
        <Button label="Bulk edit" icon="pi pi-pencil" severity="secondary" text :disabled="!selected.length" @click="bulkVisible = true" />
        <Button label="Deactivate" icon="pi pi-trash" severity="danger" text :disabled="!selected.length" @click="deactivateSelected" />
        <Button label="Import" icon="pi pi-upload" severity="secondary" outlined @click="importVisible = true" />
        <Button label="Export" icon="pi pi-download" severity="secondary" outlined @click="exportWorkbook" />
        <Button :label="`Save ${dirtyCount || ''}`" icon="pi pi-save" :disabled="!dirtyCount" :loading="saving" @click="save" />
      </div>
    </div>

    <Message v-if="error" severity="error" :closable="false">{{ error }}</Message>
    <Message v-if="message" severity="success" :closable="false">{{ message }}</Message>

    <DataTable
      v-model:selection="selected"
      :value="rows"
      :loading="loading"
      data-key="id"
      paginator
      :rows="25"
      :rows-per-page-options="[25, 50, 100]"
      striped-rows
      show-gridlines
      size="small"
      scrollable
      scroll-height="600px"
      class="excel-grid"
    >
      <Column selection-mode="multiple" header-style="width: 3rem" />
      <Column header="#" header-style="width: 4rem">
        <template #body="slotProps">{{ slotProps.index + 1 }}</template>
      </Column>
      <Column field="code" header="Code" sortable>
        <template #body="{ data }"><InputText v-model="data.code" fluid @input="markDirty(data)" /></template>
      </Column>
      <Column field="name" header="Name" sortable>
        <template #body="{ data }"><InputText v-model="data.name" fluid @input="markDirty(data)" /></template>
      </Column>
      <Column v-if="supportsSymbol" field="symbol" header="Symbol">
        <template #body="{ data }"><InputText v-model="data.symbol" fluid @input="markDirty(data)" /></template>
      </Column>
      <Column field="description" header="Description">
        <template #body="{ data }"><InputText v-model="data.description" fluid @input="markDirty(data)" /></template>
      </Column>
      <Column v-if="entity === 'cost-categories'" field="parent_id" header="Parent category" style="min-width: 170px">
        <template #body="{ data }"><Select v-model="data.parent_id" :options="costCategories.filter(item => item.id !== data.id)" option-label="name" option-value="id" show-clear filter fluid @change="markDirty(data)" /></template>
      </Column>
      <Column v-if="usesCategory" field="cost_category_id" header="Cost category" style="min-width: 170px">
        <template #body="{ data }"><Select v-model="data.cost_category_id" :options="costCategories" option-label="name" option-value="id" show-clear filter fluid @change="markDirty(data)" /></template>
      </Column>
      <Column v-if="isCatalog" field="cost_code_id" header="Cost code" style="min-width: 160px">
        <template #body="{ data }"><Select v-model="data.cost_code_id" :options="costCodes" option-label="code" option-value="id" show-clear filter fluid @change="markDirty(data)" /></template>
      </Column>
      <Column v-if="isCatalog" field="default_unit_id" header="Default unit" style="min-width: 140px">
        <template #body="{ data }"><Select v-model="data.default_unit_id" :options="units" option-label="code" option-value="id" show-clear filter fluid @change="markDirty(data)" /></template>
      </Column>
      <Column field="is_active" header="Active" header-style="width: 6rem">
        <template #body="{ data }"><Checkbox v-model="data.is_active" binary @change="markDirty(data)" /></template>
      </Column>
      <template #empty>No {{ label.toLowerCase() }} yet. Add rows, paste from Excel, or import a workbook.</template>
    </DataTable>
  </div>

  <Dialog v-model:visible="pasteVisible" modal header="Paste rows from Excel" :style="{ width: '680px' }">
    <p>Copy columns in this order: {{ columns.map(item => item.field).join(', ') }}.</p>
    <Textarea v-model="pasteText" rows="12" fluid autofocus placeholder="Paste tab-separated rows here" />
    <template #footer><Button label="Apply rows" icon="pi pi-check" :disabled="!pasteText" @click="applyPaste" /></template>
  </Dialog>

  <Dialog v-model:visible="bulkVisible" modal header="Bulk edit selected rows" :style="{ width: '460px' }">
    <div class="form-stack">
      <label>Field<Select v-model="bulkField" :options="[{ label: 'Description', value: 'description' }, { label: 'Active', value: 'is_active' }]" option-label="label" option-value="value" fluid /></label>
      <label>Value<InputText v-model="bulkValue" fluid /></label>
    </div>
    <template #footer><Button label="Apply" @click="applyBulkEdit" /></template>
  </Dialog>

  <ImportWizard v-model:visible="importVisible" :entity="entity" :entity-label="label" @committed="load" />
</template>
