<script setup lang="ts">
/**
 * Requirement detail — the well's scope of catalogue items.
 *
 * Line items are entered at the top of the grid (new rows are unshifted) and
 * only the server re-sorts after saving. A draft requirement can be edited;
 * once submitted it is read-only and becomes the source for a Cost Builder AFE.
 */
import { computed, onMounted, ref } from 'vue'
import Button from 'primevue/button'
import Column from 'primevue/column'
import DataTable from 'primevue/datatable'
import InputNumber from 'primevue/inputnumber'
import InputText from 'primevue/inputtext'
import Message from 'primevue/message'
import Select from 'primevue/select'
import Tag from 'primevue/tag'
import PageHeader from '~/components/design-system/PageHeader.vue'
import type { MasterDataRecord } from '~/types/masterData'
import type { EditableRequirementItem, RequirementItemRecord, RequirementRecord } from '~/types/requirements'

definePageMeta({ middleware: 'auth' })

const id = String(useRoute().params.id)
const api = useRequirements()
const master = useMasterData()

const requirement = ref<RequirementRecord | null>(null)
const items = ref<EditableRequirementItem[]>([])
const catalogueItems = ref<MasterDataRecord[]>([])
const costCodes = ref<MasterDataRecord[]>([])
const units = ref<MasterDataRecord[]>([])

const loading = ref(false)
const saving = ref(false)
const submitting = ref(false)
const error = ref<string | null>(null)
const success = ref<string | null>(null)

const isDraft = computed(() => requirement.value?.status === 'draft')
const pendingCount = computed(() => items.value.filter(item => item._state !== 'clean').length)

function toEditable(record: RequirementItemRecord): EditableRequirementItem {
  return {
    id: record.id,
    line_number: record.line_number,
    catalog_item_id: record.catalog_item_id,
    cost_code_id: record.cost_code_id,
    quantity: String(record.quantity),
    unit_id: record.unit_id,
    section_name: record.section_name ?? '',
    planned_duration_days: record.planned_duration_days ?? '',
    planned_depth_from: record.planned_depth_from ?? '',
    planned_depth_to: record.planned_depth_to ?? '',
    depth_unit_id: record.depth_unit_id ?? '',
    notes: record.notes ?? '',
    is_active: record.is_active,
    _state: 'clean',
  }
}

const blankRow = (): EditableRequirementItem => ({
  line_number: items.value.reduce((max, item) => Math.max(max, item.line_number), 0) + 1,
  catalog_item_id: '',
  cost_code_id: '',
  quantity: '0',
  unit_id: '',
  section_name: '',
  planned_duration_days: '',
  planned_depth_from: '',
  planned_depth_to: '',
  depth_unit_id: '',
  notes: '',
  is_active: true,
  _state: 'new',
})

function addRow(): void {
  error.value = null
  items.value.unshift(blankRow())
}

function markDirty(item: EditableRequirementItem): void {
  if (item._state === 'clean') item._state = 'dirty'
}

function removeRow(item: EditableRequirementItem): void {
  error.value = null
  if (item._state === 'new') {
    items.value = items.value.filter(candidate => candidate !== item)
    return
  }
  if (!window.confirm('Remove this line item from the requirement?')) return
  void api.deactivateItem(String(item.id))
    .then(load)
    .catch((caught: unknown) => {
      error.value = caught instanceof Error ? caught.message : 'The line item could not be removed.'
    })
}

function missingRequired(item: EditableRequirementItem): string[] {
  const missing: string[] = []
  if (!item.catalog_item_id) missing.push('Item')
  if (!item.cost_code_id) missing.push('Cost code')
  if (!item.unit_id) missing.push('Unit')
  return missing
}

async function save(): Promise<void> {
  error.value = null
  success.value = null
  for (const item of [...items.value]) {
    const missing = missingRequired(item)
    if (missing.length) {
      error.value = `Complete the required field(s) on every row before saving: ${missing.join(', ')}.`
      return
    }
  }
  saving.value = true
  try {
    const newRows = items.value.filter(item => item._state === 'new')
    const changedRows = items.value.filter(item => item._state === 'dirty' && item.id)
    if (newRows.length) {
      const payload = newRows.map(item => ({
        line_number: item.line_number,
        catalog_item_id: item.catalog_item_id,
        cost_code_id: item.cost_code_id,
        quantity: String(item.quantity),
        unit_id: item.unit_id,
        section_name: item.section_name || null,
        planned_duration_days: item.planned_duration_days ?? null,
        planned_depth_from: item.planned_depth_from ?? null,
        planned_depth_to: item.planned_depth_to ?? null,
        depth_unit_id: item.depth_unit_id || null,
        notes: item.notes || null,
        is_active: item.is_active,
      }))
      const validation = await api.validateItems(id, payload)
      if (!validation.valid) {
        throw new Error(validation.errors.map(item => `Row ${item.row_index + 1}: ${item.message}`).join('; '))
      }
      await api.bulkCreateItems(id, payload)
    }
    if (changedRows.length) {
      await api.bulkUpdateItems(changedRows.map(item => ({
        id: item.id,
        line_number: item.line_number,
        catalog_item_id: item.catalog_item_id,
        cost_code_id: item.cost_code_id,
        quantity: String(item.quantity),
        unit_id: item.unit_id,
        section_name: item.section_name || null,
        planned_duration_days: item.planned_duration_days ?? null,
        planned_depth_from: item.planned_depth_from ?? null,
        planned_depth_to: item.planned_depth_to ?? null,
        depth_unit_id: item.depth_unit_id || null,
        notes: item.notes || null,
        is_active: item.is_active,
      })))
    }
    success.value = 'Requirement items saved. The grid is re-sorted by line number.'
    await load()
  }
  catch (caught: unknown) {
    error.value = caught instanceof Error ? caught.message : 'The items could not be saved.'
  }
  finally { saving.value = false }
}

async function submit(): Promise<void> {
  error.value = null
  success.value = null
  if (!window.confirm('Submit this requirement? It becomes read-only and can be used to generate a cost build (AFE).')) return
  submitting.value = true
  try {
    requirement.value = await api.submit(id)
    success.value = 'Requirement submitted. Open the Cost Builder to generate the AFE cost build from it.'
  }
  catch (caught: unknown) {
    error.value = caught instanceof Error ? caught.message : 'The requirement could not be submitted.'
  }
  finally { submitting.value = false }
}

async function download(kind: 'export' | 'template'): Promise<void> {
  const blob = kind === 'export' ? await api.export(id) : await api.template(id)
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = `requirement-${kind}.xlsx`
  anchor.click()
  URL.revokeObjectURL(url)
}

async function load(): Promise<void> {
  loading.value = true
  error.value = null
  try {
    const [detail, catalogue, codePage, unitPage] = await Promise.all([
      api.getRequirement(id),
      Promise.all([
        master.list('services'),
        master.list('tangibles'),
        master.list('materials'),
        master.list('equipment'),
      ]),
      master.list('cost-codes'),
      master.list('units'),
    ])
    requirement.value = detail
    catalogueItems.value = [...catalogue[0].items, ...catalogue[1].items, ...catalogue[2].items, ...catalogue[3].items]
    costCodes.value = codePage.items
    units.value = unitPage.items
    items.value = detail.items.map(toEditable)
  }
  catch (caught: unknown) {
    error.value = caught instanceof Error ? caught.message : 'The requirement could not be loaded.'
  }
  finally { loading.value = false }
}

onMounted(() => void load())
</script>

<template>
  <div v-if="requirement" class="library-page">
    <PageHeader
      :title="requirement.title"
      :description="`${requirement.well_code} · ${requirement.project_code} · ${requirement.code} — ${requirement.item_count} item(s)`"
    >
      <template #actions>
        <Tag :value="requirement.status" :severity="requirement.status === 'submitted' ? 'success' : 'warn'" />
        <Button
          label="Submit requirement"
          icon="pi pi-send"
          :disabled="!isDraft || !items.length"
          :loading="submitting"
          @click="submit"
        />
        <Button v-if="requirement.status === 'submitted'" label="Generate AFE cost build" icon="pi pi-calculator" @click="navigateTo('/cost-builder')" />
      </template>
    </PageHeader>

    <Message v-if="success" severity="success" :closable="true" @close="success = null">{{ success }}</Message>
    <Message v-if="error" severity="error" :closable="true" @close="error = null">{{ error }}</Message>
    <Message v-if="!isDraft" severity="info" :closable="false">
      This requirement is submitted and read-only. New line items must be raised on a new requirement revision.
    </Message>

    <div class="bulk-grid-panel">
      <div class="grid-toolbar">
        <div><strong>Requirement line items</strong><small class="toolbar-note">New rows are added at the top; the grid re-sorts by line number only after saving.</small></div>
        <div class="grid-toolbar__actions">
          <Button label="Add row" icon="pi pi-plus" :disabled="!isDraft" @click="addRow" />
          <Button label="Template" icon="pi pi-file-excel" text :disabled="!isDraft" @click="download('template')" />
          <Button label="Export" icon="pi pi-download" text @click="download('export')" />
          <Button :label="pendingCount ? `Save items (${pendingCount})` : 'Save items'" icon="pi pi-save" :disabled="!isDraft || !pendingCount" :loading="saving" @click="save" />
        </div>
      </div>

      <DataTable :value="items" :loading="loading" data-key="id" striped-rows show-gridlines size="small" scrollable scroll-height="520px" class="wi-items">
        <Column field="line_number" header="#" :style="{ width: '70px' }" />
        <Column header="Item" :style="{ minWidth: '240px' }">
          <template #body="{ data }">
            <Select
              v-model="data.catalog_item_id"
              :options="catalogueItems"
              option-label="name"
              option-value="id"
              filter
              show-clear
              fluid
              :disabled="!isDraft"
              @change="markDirty(data)"
            >
              <template #option="{ option }">{{ option.item_type }} · {{ option.code }} — {{ option.name }}</template>
            </Select>
          </template>
        </Column>
        <Column header="Cost code" :style="{ minWidth: '150px' }">
          <template #body="{ data }">
            <Select v-model="data.cost_code_id" :options="costCodes" option-label="code" option-value="id" filter show-clear fluid :disabled="!isDraft" @change="markDirty(data)" />
          </template>
        </Column>
        <Column header="Qty" :style="{ width: '110px' }">
          <template #body="{ data }">
            <InputNumber v-model="data.quantity" :min="0" :max-fraction-digits="4" fluid :disabled="!isDraft" @input="markDirty(data)" />
          </template>
        </Column>
        <Column header="Unit" :style="{ width: '130px' }">
          <template #body="{ data }">
            <Select v-model="data.unit_id" :options="units" option-label="code" option-value="id" filter show-clear fluid :disabled="!isDraft" @change="markDirty(data)" />
          </template>
        </Column>
        <Column header="Section" :style="{ width: '130px' }">
          <template #body="{ data }">
            <InputText v-model="data.section_name" fluid :disabled="!isDraft" @input="markDirty(data)" />
          </template>
        </Column>
        <Column header="Planned days" :style="{ width: '120px' }">
          <template #body="{ data }">
            <InputNumber v-model="data.planned_duration_days" :min="0" :max-fraction-digits="4" fluid :disabled="!isDraft" @input="markDirty(data)" />
          </template>
        </Column>
        <Column header="Depth from" :style="{ width: '115px' }">
          <template #body="{ data }">
            <InputNumber v-model="data.planned_depth_from" :min="0" :max-fraction-digits="4" fluid :disabled="!isDraft" @input="markDirty(data)" />
          </template>
        </Column>
        <Column header="Depth to" :style="{ width: '115px' }">
          <template #body="{ data }">
            <InputNumber v-model="data.planned_depth_to" :min="0" :max-fraction-digits="4" fluid :disabled="!isDraft" @input="markDirty(data)" />
          </template>
        </Column>
        <Column header="Depth unit" :style="{ width: '120px' }">
          <template #body="{ data }">
            <Select v-model="data.depth_unit_id" :options="units" option-label="code" option-value="id" filter show-clear fluid :disabled="!isDraft" @change="markDirty(data)" />
          </template>
        </Column>
        <Column header="Notes" :style="{ minWidth: '160px' }">
          <template #body="{ data }">
            <InputText v-model="data.notes" fluid :disabled="!isDraft" @input="markDirty(data)" />
          </template>
        </Column>
        <Column header="Active" :style="{ width: '100px' }">
          <template #body="{ data }">
            <Tag :value="data.is_active ? 'Active' : 'Inactive'" :severity="data.is_active ? 'success' : 'secondary'" />
          </template>
        </Column>
        <Column header="" :style="{ width: '70px' }">
          <template #body="{ data }">
            <Button icon="pi pi-trash" size="small" text severity="danger" aria-label="Remove line item" :disabled="!isDraft" @click="removeRow(data)" />
          </template>
        </Column>
        <template #empty>
          <div class="eg__empty">
            <i class="pi pi-inbox" aria-hidden="true" />
            <p><strong>No line items yet.</strong></p>
            <p>Add a row to start building the well's scope.</p>
          </div>
        </template>
      </DataTable>
    </div>
  </div>
</template>

<style scoped>
.wi-items {
  margin-top: 0.75rem;
}
</style>
