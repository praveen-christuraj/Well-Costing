<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import Button from 'primevue/button'
import Column from 'primevue/column'
import DataTable from 'primevue/datatable'
import Dialog from 'primevue/dialog'
import InputNumber from 'primevue/inputnumber'
import InputText from 'primevue/inputtext'
import Message from 'primevue/message'
import Select from 'primevue/select'
import Tag from 'primevue/tag'
import Textarea from 'primevue/textarea'
import PageHeader from '~/components/design-system/PageHeader.vue'
import { parseTsv } from '~/utils/tsv'
import type { ImportPreview } from '~/types/imports'
import type { MasterDataRecord } from '~/types/masterData'
import type { EditableRequirementItem, RequirementItemRecord, RequirementRecord } from '~/types/requirements'

definePageMeta({ middleware: 'auth' })
const route = useRoute()
const id = String(route.params.id)
const api = useRequirements()
const masterApi = useMasterData()
const requirement = ref<RequirementRecord | null>(null)
const rows = ref<EditableRequirementItem[]>([])
const selected = ref<EditableRequirementItem[]>([])
const catalogItems = ref<MasterDataRecord[]>([])
const costCodes = ref<MasterDataRecord[]>([])
const units = ref<MasterDataRecord[]>([])
const loading = ref(false)
const saving = ref(false)
const error = ref<string | null>(null)
const message = ref<string | null>(null)
const pasteVisible = ref(false)
const pasteText = ref('')
const importVisible = ref(false)
const importFile = ref<File | null>(null)
const importPreview = ref<ImportPreview | null>(null)
const importBusy = ref(false)

const readOnly = computed(() => requirement.value?.status !== 'draft')
const dirtyCount = computed(() => rows.value.filter(row => row._state !== 'clean').length)

function editable(item: RequirementItemRecord): EditableRequirementItem {
  return {
    id: item.id, line_number: item.line_number, catalog_item_id: item.catalog_item_id,
    cost_code_id: item.cost_code_id, quantity: item.quantity, unit_id: item.unit_id,
    section_name: item.section_name ?? '', planned_duration_days: item.planned_duration_days ?? '',
    planned_depth_from: item.planned_depth_from ?? '', planned_depth_to: item.planned_depth_to ?? '',
    depth_unit_id: item.depth_unit_id ?? '', notes: item.notes ?? '', is_active: item.is_active, _state: 'clean',
  }
}

async function load(): Promise<void> {
  loading.value = true
  try {
    const [detail, services, tangibles, materials, equipment, codes, unitPage] = await Promise.all([
      api.getRequirement(id), masterApi.list('services'), masterApi.list('tangibles'), masterApi.list('materials'), masterApi.list('equipment'), masterApi.list('cost-codes'), masterApi.list('units'),
    ])
    requirement.value = detail
    rows.value = detail.items.map(editable)
    catalogItems.value = [...services.items, ...tangibles.items, ...materials.items, ...equipment.items].filter(item => item.is_active)
    costCodes.value = codes.items.filter(item => item.is_active)
    units.value = unitPage.items.filter(item => item.is_active)
  }
  catch (caught: unknown) { error.value = caught instanceof Error ? caught.message : 'Requirement could not be loaded' }
  finally { loading.value = false }
}

function mark(row: EditableRequirementItem): void { if (row._state === 'clean') row._state = 'dirty' }
function addRows(): void {
  const next = Math.max(0, ...rows.value.map(row => row.line_number)) + 1
  rows.value.push(...Array.from({ length: 5 }, (_, index) => ({ id: undefined, line_number: next + index, catalog_item_id: '', cost_code_id: '', quantity: '', unit_id: '', section_name: '', planned_duration_days: '', planned_depth_from: '', planned_depth_to: '', depth_unit_id: '', notes: '', is_active: true, _state: 'new' as const })).map(({ id: _id, ...row }) => row))
}
function duplicate(): void {
  let next = Math.max(0, ...rows.value.map(row => row.line_number)) + 1
  rows.value.push(...selected.value.map((row) => { const { id: _id, ...copy } = row; return { ...copy, line_number: next++, _state: 'new' as const } }))
  selected.value = []
}
function payload(row: EditableRequirementItem, includeId = false): Record<string, unknown> {
  return {
    ...(includeId && row.id ? { id: row.id } : {}), line_number: row.line_number,
    catalog_item_id: row.catalog_item_id, cost_code_id: row.cost_code_id,
    quantity: row.quantity, unit_id: row.unit_id, section_name: row.section_name || null,
    planned_duration_days: row.planned_duration_days || null, planned_depth_from: row.planned_depth_from || null,
    planned_depth_to: row.planned_depth_to || null, depth_unit_id: row.depth_unit_id || null,
    notes: row.notes || null, is_active: row.is_active,
  }
}
async function save(): Promise<void> {
  saving.value = true; error.value = null
  try {
    const fresh = rows.value.filter(row => row._state === 'new' && row.catalog_item_id && row.cost_code_id && row.unit_id)
    const changed = rows.value.filter(row => row._state === 'dirty' && row.id)
    if (fresh.length) {
      const data = fresh.map(row => payload(row)); const validation = await api.validateItems(id, data)
      if (!validation.valid) throw new Error(validation.errors.map(item => `Row ${item.row_index + 1}: ${item.message}`).join('; '))
      await api.bulkCreateItems(id, data)
    }
    if (changed.length) await api.bulkUpdateItems(changed.map(row => payload(row, true)))
    message.value = `${fresh.length + changed.length} rows saved.`; await load()
  }
  catch (caught: unknown) { error.value = caught instanceof Error ? caught.message : 'Save failed' }
  finally { saving.value = false }
}
async function deactivate(): Promise<void> { await Promise.all(selected.value.filter(row => row.id).map(row => api.deactivateItem(row.id!))); await load() }
async function submit(): Promise<void> { try { requirement.value = await api.submit(id); await load() } catch (caught: unknown) { error.value = caught instanceof Error ? caught.message : 'Submit failed' } }
function applyPaste(): void {
  const parsed = parseTsv(pasteText.value, [{ field: 'item_code' }, { field: 'item_type' }, { field: 'cost_code' }, { field: 'quantity' }, { field: 'unit_code' }, { field: 'section_name' }, { field: 'planned_duration_days' }, { field: 'planned_depth_from' }, { field: 'planned_depth_to' }, { field: 'depth_unit_code' }, { field: 'notes' }])
  let next = Math.max(0, ...rows.value.map(row => row.line_number)) + 1
  for (const value of parsed) {
    const item = catalogItems.value.find(option => option.code === value.item_code?.toUpperCase() && option.item_type === value.item_type?.toLowerCase())
    const code = costCodes.value.find(option => option.code === value.cost_code?.toUpperCase())
    const unit = units.value.find(option => option.code === value.unit_code?.toUpperCase())
    const depthUnit = units.value.find(option => option.code === value.depth_unit_code?.toUpperCase())
    rows.value.push({ line_number: next++, catalog_item_id: item?.id ?? '', cost_code_id: code?.id ?? '', quantity: value.quantity ?? '', unit_id: unit?.id ?? '', section_name: value.section_name ?? '', planned_duration_days: value.planned_duration_days ?? '', planned_depth_from: value.planned_depth_from ?? '', planned_depth_to: value.planned_depth_to ?? '', depth_unit_id: depthUnit?.id ?? '', notes: value.notes ?? '', is_active: true, _state: 'new' })
  }
  pasteVisible.value = false; pasteText.value = ''
}
function chooseImport(event: Event): void { importFile.value = (event.target as HTMLInputElement).files?.[0] ?? null }
async function previewImport(): Promise<void> { if (!importFile.value) return; importBusy.value = true; try { importPreview.value = await api.previewImport(id, importFile.value) } catch (caught: unknown) { error.value = caught instanceof Error ? caught.message : 'Import failed' } finally { importBusy.value = false } }
async function commitImport(): Promise<void> { if (!importPreview.value) return; importBusy.value = true; try { await api.commitImport(id, importPreview.value.batch_id); importVisible.value = false; importPreview.value = null; await load() } finally { importBusy.value = false } }
async function download(kind: 'template' | 'export'): Promise<void> { const blob = kind === 'template' ? await api.template(id) : await api.export(id); const url = URL.createObjectURL(blob); const anchor = document.createElement('a'); anchor.href = url; anchor.download = kind === 'template' ? 'requirement-items-template.xlsx' : `${requirement.value?.code ?? 'requirement'}-items.xlsx`; anchor.click(); URL.revokeObjectURL(url) }
onMounted(() => void load())
</script>

<template>
  <div v-if="requirement" class="requirement-detail-page">
    <PageHeader :title="requirement.title" :description="`${requirement.project_code} / ${requirement.well_code} · ${requirement.code} · Revision ${requirement.revision_number}`">
      <template #actions><Tag :value="requirement.status" :severity="requirement.status === 'draft' ? 'warn' : 'success'" /><Button v-if="!readOnly" label="Submit" icon="pi pi-send" severity="success" outlined @click="submit" /></template>
    </PageHeader>
    <div class="scope-warning"><i class="pi pi-info-circle" /><span>Values below are supplied planning requirements. No trajectory, hydraulics, casing, cement, BHA, or simulation calculation occurs here.</span></div>
    <Message v-if="error" severity="error" :closable="false">{{ error }}</Message><Message v-if="message" severity="success" :closable="false">{{ message }}</Message>
    <div class="grid-toolbar bulk-grid-panel requirement-toolbar">
      <div><strong>{{ rows.length }} line items</strong><small class="toolbar-note">Bulk-first requirement entry</small></div>
      <div class="grid-toolbar__actions"><Button label="Add rows" icon="pi pi-plus" outlined :disabled="readOnly" @click="addRows" /><Button label="Paste" icon="pi pi-clipboard" outlined :disabled="readOnly" @click="pasteVisible = true" /><Button label="Duplicate" icon="pi pi-copy" text :disabled="readOnly || !selected.length" @click="duplicate" /><Button label="Deactivate" icon="pi pi-trash" severity="danger" text :disabled="readOnly || !selected.length" @click="deactivate" /><Button label="Import" icon="pi pi-upload" outlined :disabled="readOnly" @click="importVisible = true" /><Button label="Template" icon="pi pi-file-excel" text @click="download('template')" /><Button label="Export" icon="pi pi-download" text @click="download('export')" /><Button :label="`Save ${dirtyCount || ''}`" icon="pi pi-save" :disabled="readOnly || !dirtyCount" :loading="saving" @click="save" /></div>
    </div>
    <DataTable v-model:selection="selected" :value="rows" :loading="loading" data-key="id" paginator :rows="25" :rows-per-page-options="[25, 50, 100]" show-gridlines striped-rows size="small" scrollable class="bulk-grid-panel requirement-grid">
      <Column selection-mode="multiple" /><Column field="line_number" header="#"><template #body="{ data }"><InputNumber v-model="data.line_number" :disabled="readOnly" :min="1" fluid @input="mark(data)" /></template></Column>
      <Column header="Required item" style="min-width: 230px"><template #body="{ data }"><Select v-model="data.catalog_item_id" :options="catalogItems" option-label="name" option-value="id" filter :disabled="readOnly" fluid @change="mark(data)"><template #option="{ option }">{{ option.code }} — {{ option.name }}</template></Select></template></Column>
      <Column header="Cost code" style="min-width: 130px"><template #body="{ data }"><Select v-model="data.cost_code_id" :options="costCodes" option-label="code" option-value="id" filter :disabled="readOnly" fluid @change="mark(data)" /></template></Column>
      <Column header="Quantity"><template #body="{ data }"><InputNumber v-model="data.quantity" :disabled="readOnly" :min="0" :max-fraction-digits="4" fluid @input="mark(data)" /></template></Column>
      <Column header="Unit"><template #body="{ data }"><Select v-model="data.unit_id" :options="units" option-label="code" option-value="id" filter :disabled="readOnly" fluid @change="mark(data)" /></template></Column>
      <Column header="Section"><template #body="{ data }"><InputText v-model="data.section_name" :disabled="readOnly" fluid @input="mark(data)" /></template></Column>
      <Column header="Planned days"><template #body="{ data }"><InputNumber v-model="data.planned_duration_days" :disabled="readOnly" :min="0" :max-fraction-digits="4" fluid @input="mark(data)" /></template></Column>
      <Column header="Depth from"><template #body="{ data }"><InputNumber v-model="data.planned_depth_from" :disabled="readOnly" :min="0" fluid @input="mark(data)" /></template></Column>
      <Column header="Depth to"><template #body="{ data }"><InputNumber v-model="data.planned_depth_to" :disabled="readOnly" :min="0" fluid @input="mark(data)" /></template></Column>
      <Column header="Depth unit"><template #body="{ data }"><Select v-model="data.depth_unit_id" :options="units" option-label="code" option-value="id" show-clear :disabled="readOnly" fluid @change="mark(data)" /></template></Column>
      <Column header="Notes"><template #body="{ data }"><InputText v-model="data.notes" :disabled="readOnly" fluid @input="mark(data)" /></template></Column>
      <template #empty>No requirement items. Add rows, paste from Excel, or import a workbook.</template>
    </DataTable>

    <Dialog v-model:visible="pasteVisible" modal header="Paste requirement lines" :style="{ width: '780px' }"><p>Column order: item code, item type, cost code, quantity, unit, section, planned days, depth from, depth to, depth unit, notes.</p><Textarea v-model="pasteText" rows="14" fluid /><template #footer><Button label="Apply rows" @click="applyPaste" /></template></Dialog>
    <Dialog v-model:visible="importVisible" modal header="Import requirement items" :style="{ width: '820px' }"><input type="file" accept=".xlsx,.xlsm,.xls" data-testid="requirement-import-file" @change="chooseImport"><Button label="Preview and validate" :disabled="!importFile" :loading="importBusy" @click="previewImport" /><div v-if="importPreview" class="validation-summary"><div><span>Total</span><strong>{{ importPreview.total_rows }}</strong></div><div class="valid"><span>Valid</span><strong>{{ importPreview.valid_rows }}</strong></div><div :class="{ invalid: importPreview.error_rows }"><span>Errors</span><strong>{{ importPreview.error_rows }}</strong></div></div><DataTable v-if="importPreview?.errors.length" :value="importPreview.errors" size="small"><Column field="row_index" header="Row" /><Column field="message" header="Error" /></DataTable><template #footer><Button label="Commit" :disabled="importPreview?.status !== 'validated'" :loading="importBusy" @click="commitImport" /></template></Dialog>
  </div>
</template>
