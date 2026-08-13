<script setup lang="ts">
import { onMounted, ref } from 'vue'
import Button from 'primevue/button'
import Column from 'primevue/column'
import DataTable from 'primevue/datatable'
import InputNumber from 'primevue/inputnumber'
import InputText from 'primevue/inputtext'
import Message from 'primevue/message'
import Select from 'primevue/select'
import ImportWizard from '~/components/cost-library/ImportWizard.vue'
import type { EditableRateRow, MasterDataRecord, RateRecord } from '~/types/masterData'

const api = useMasterData()
const rows = ref<EditableRateRow[]>([])
const selected = ref<EditableRateRow[]>([])
const items = ref<MasterDataRecord[]>([])
const vendors = ref<MasterDataRecord[]>([])
const currencies = ref<MasterDataRecord[]>([])
const units = ref<MasterDataRecord[]>([])
const loading = ref(false)
const saving = ref(false)
const error = ref<string | null>(null)
const importVisible = ref(false)

function editable(rate: RateRecord): EditableRateRow {
  return {
    id: rate.id,
    item_id: rate.item_id,
    vendor_id: rate.vendor_id,
    currency_id: rate.currency_id,
    unit_id: rate.unit_id,
    amount: rate.amount,
    effective_from: rate.effective_from,
    effective_to: rate.effective_to ?? '',
    description: rate.description ?? '',
    is_active: rate.is_active,
    _state: 'clean',
  }
}

async function load(): Promise<void> {
  loading.value = true
  try {
    const [rates, serviceItems, tangibleItems, materialItems, equipmentItems, vendorPage, currencyPage, unitPage] = await Promise.all([
      api.listRates(), api.list('services'), api.list('tangibles'), api.list('materials'), api.list('equipment'), api.list('vendors'), api.list('currencies'), api.list('units'),
    ])
    rows.value = rates.items.map(editable)
    items.value = [...serviceItems.items, ...tangibleItems.items, ...materialItems.items, ...equipmentItems.items]
    vendors.value = vendorPage.items
    currencies.value = currencyPage.items
    units.value = unitPage.items
  }
  catch (caught: unknown) {
    error.value = caught instanceof Error ? caught.message : 'Rates could not be loaded'
  }
  finally { loading.value = false }
}

function addRows(): void {
  rows.value.push(...Array.from({ length: 5 }, () => ({
    item_id: '', vendor_id: '', currency_id: '', unit_id: '', amount: '', effective_from: '', effective_to: '', description: '', is_active: true, _state: 'new' as const,
  })))
}

function dirty(row: EditableRateRow): void { if (row._state === 'clean') row._state = 'dirty' }

async function save(): Promise<void> {
  saving.value = true
  error.value = null
  try {
    const clean = (row: EditableRateRow) => ({
      ...(row.id ? { id: row.id } : {}), item_id: row.item_id, vendor_id: row.vendor_id, currency_id: row.currency_id, unit_id: row.unit_id, amount: String(row.amount), effective_from: row.effective_from, effective_to: row.effective_to || null, description: row.description || null, is_active: row.is_active,
    })
    const created = rows.value.filter(row => row._state === 'new' && row.item_id && row.vendor_id && row.amount).map(clean)
    const updated = rows.value.filter(row => row._state === 'dirty' && row.id).map(clean)
    if (created.length) await api.bulkCreateRates(created)
    if (updated.length) await api.bulkUpdateRates(updated)
    await load()
  }
  catch (caught: unknown) { error.value = caught instanceof Error ? caught.message : 'Rate save failed' }
  finally { saving.value = false }
}

async function deactivate(): Promise<void> {
  await Promise.all(selected.value.filter(row => row.id).map(row => api.deactivateRate(row.id!)))
  await load()
}

async function exportWorkbook(): Promise<void> {
  const blob = await api.export('rates')
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = 'rates-export.xlsx'
  anchor.click()
  URL.revokeObjectURL(url)
}

onMounted(() => void load())
</script>

<template>
  <div class="bulk-grid-panel">
    <div class="grid-toolbar">
      <div><strong>Effective-dated vendor rates</strong><small class="toolbar-note">Overlap rules remain pending business confirmation.</small></div>
      <div class="grid-toolbar__actions">
        <Button label="Add rows" icon="pi pi-plus" severity="secondary" outlined @click="addRows" />
        <Button label="Deactivate" icon="pi pi-trash" severity="danger" text :disabled="!selected.length" @click="deactivate" />
        <Button label="Import" icon="pi pi-upload" severity="secondary" outlined @click="importVisible = true" />
        <Button label="Export" icon="pi pi-download" severity="secondary" outlined @click="exportWorkbook" />
        <Button label="Save" icon="pi pi-save" :loading="saving" @click="save" />
      </div>
    </div>
    <Message v-if="error" severity="error" :closable="false">{{ error }}</Message>
    <DataTable v-model:selection="selected" :value="rows" :loading="loading" data-key="id" paginator :rows="25" show-gridlines striped-rows size="small" scrollable>
      <Column selection-mode="multiple" />
      <Column header="Item" style="min-width: 220px"><template #body="{ data }"><Select v-model="data.item_id" :options="items" option-label="name" option-value="id" filter fluid @change="dirty(data)"><template #option="{ option }"><span>{{ option.code }} — {{ option.name }}</span></template></Select></template></Column>
      <Column header="Vendor" style="min-width: 180px"><template #body="{ data }"><Select v-model="data.vendor_id" :options="vendors" option-label="name" option-value="id" filter fluid @change="dirty(data)" /></template></Column>
      <Column header="Currency"><template #body="{ data }"><Select v-model="data.currency_id" :options="currencies" option-label="code" option-value="id" fluid @change="dirty(data)" /></template></Column>
      <Column header="Unit"><template #body="{ data }"><Select v-model="data.unit_id" :options="units" option-label="code" option-value="id" fluid @change="dirty(data)" /></template></Column>
      <Column header="Amount"><template #body="{ data }"><InputNumber v-model="data.amount" :min="0" :max-fraction-digits="4" fluid @input="dirty(data)" /></template></Column>
      <Column header="Effective from"><template #body="{ data }"><InputText v-model="data.effective_from" type="date" fluid @input="dirty(data)" /></template></Column>
      <Column header="Effective to"><template #body="{ data }"><InputText v-model="data.effective_to" type="date" fluid @input="dirty(data)" /></template></Column>
      <Column header="Description"><template #body="{ data }"><InputText v-model="data.description" fluid @input="dirty(data)" /></template></Column>
    </DataTable>
  </div>
  <ImportWizard v-model:visible="importVisible" entity="rates" entity-label="Rates" @committed="load" />
</template>
