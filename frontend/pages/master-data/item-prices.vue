/**
 * Master tangible rates.
 *
 * Services carry no master rate — they are priced per well — so this page holds
 * the catalogue rate for tangibles and consumables only. A rate is never
 * overwritten: **Revise** closes the current row and opens the next revision,
 * and wells that already copied the rate into their rate book keep the number
 * they were planned with until the well is complete.
 */
<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import Button from 'primevue/button'
import DatePicker from 'primevue/datepicker'
import Dialog from 'primevue/dialog'
import InputNumber from 'primevue/inputnumber'
import Message from 'primevue/message'
import Textarea from 'primevue/textarea'
import EnterpriseGrid from '~/components/data-grid/EnterpriseGrid.vue'
import MasterDataNav from '~/components/master-data/MasterDataNav.vue'
import PageHeader from '~/components/design-system/PageHeader.vue'
import type { EditableRow, GridColumn, GridFilterDefinition } from '~/types/grid'
import type { PageResponse } from '~/types/masterData'
import type { ItemPriceRecord } from '~/types/procurement'

definePageMeta({ middleware: 'auth' })

const procurement = useProcurement()
const references = useReferenceOptions()
const itemTypeOptions = [
  { label: 'Tangible', value: 'tangible' },
  { label: 'Mud chemical', value: 'mud_chemical' },
  { label: 'Cement additive', value: 'cement_additive' },
  { label: 'Material', value: 'material' },
]

onMounted(() => {
  void references.load(['vendors', 'currencies', 'units', 'purchase-orders', 'catalogue'])
})

const columns = computed<GridColumn[]>(() => [
    { field: 'item_id', header: 'Item', type: 'select', options: references.catalogueItems.value, required: true, width: '260px' },
    { field: 'item_type', header: 'Type', readonly: true, width: '145px', display: row => itemTypeOptions.find(option => option.value === row.item_type)?.label ?? '—' },
    { field: 'vendor_id', header: 'Vendor', type: 'select', options: references.vendors.value, width: '210px', placeholder: 'Any vendor' },
    { field: 'purchase_order_id', header: 'Purchase order', type: 'select', options: references.purchaseOrders.value, width: '225px' },
    { field: 'unit_price', header: 'Rate', type: 'number', numeric: true, required: true, sortable: true, width: '160px' },
    { field: 'currency_id', header: 'Currency', type: 'select', options: references.currencies.value, required: true, width: '155px' },
    { field: 'unit_id', header: 'UOM', type: 'select', options: references.units.value, required: true, width: '150px' },
    { field: 'effective_from', header: 'Effective from', type: 'date', required: true, sortable: true, width: '170px' },
    { field: 'effective_to', header: 'Effective to', type: 'date', sortable: true, width: '165px' },
    { field: 'revision_number', header: 'Rev.', readonly: true, numeric: true, noPaste: true, width: '90px' },
    { field: 'change_reason', header: 'Revision reason', readonly: true, noPaste: true, width: '220px' },
    { field: 'description', header: 'Notes', type: 'textarea', width: '190px' },
    { field: 'is_active', header: 'Active', type: 'checkbox', width: '110px' },
])

const filters = computed<GridFilterDefinition[]>(() => [
    { key: 'item_type', label: 'Item type', type: 'select', options: itemTypeOptions, width: '175px' },
    { key: 'vendor_id', label: 'Vendor', type: 'select', options: references.vendors.value, width: '205px' },
    { key: 'purchase_order_id', label: 'Purchase order', type: 'select', options: references.purchaseOrders.value, width: '215px' },
    { key: 'effective_on', label: 'Effective on', type: 'date' },
])

function fetchPage(params: Record<string, unknown>): Promise<PageResponse<Record<string, unknown>>> {
  return procurement.itemPrices.list(params as never) as unknown as Promise<PageResponse<Record<string, unknown>>>
}

function toRow(record: Record<string, unknown>) {
  const price = record as unknown as ItemPriceRecord
  return {
    id: price.id,
    item_id: price.item_id,
    item_type: price.item_type ?? '',
    vendor_id: price.vendor_id ?? '',
    purchase_order_id: price.purchase_order_id ?? '',
    unit_price: Number(price.unit_price),
    currency_id: price.currency_id,
    unit_id: price.unit_id,
    effective_from: price.effective_from,
    effective_to: price.effective_to ?? '',
    revision_number: price.revision_number,
    change_reason: price.change_reason ?? '',
    description: price.description ?? '',
    is_active: price.is_active,
  }
}

function asDate(value: unknown): string | null {
  if (!value) return null
  if (value instanceof Date) {
    const offset = value.getTimezoneOffset() * 60000
    return new Date(value.getTime() - offset).toISOString().slice(0, 10)
  }
  return String(value)
}

function toPayload(row: EditableRow) {
  return {
    item_id: row.item_id,
    vendor_id: row.vendor_id || null,
    purchase_order_id: row.purchase_order_id || null,
    unit_price: row.unit_price === null || row.unit_price === '' ? '0' : String(row.unit_price),
    currency_id: row.currency_id,
    unit_id: row.unit_id,
    effective_from: asDate(row.effective_from),
    effective_to: asDate(row.effective_to),
    description: row.description || null,
    is_active: row.is_active !== false,
  }
}

const blankRow = () => ({
  item_id: '',
  item_type: '',
  vendor_id: '',
  purchase_order_id: '',
  unit_price: 0,
  currency_id: '',
  unit_id: '',
  effective_from: '',
  effective_to: '',
  revision_number: 1,
  change_reason: '',
  description: '',
  is_active: true,
})

/* -------------------------------------------------- revise a master rate --- */
const grid = ref<{ reload: () => Promise<void> } | null>(null)
const reviseVisible = ref(false)
const reviseSaving = ref(false)
const reviseError = ref<string | null>(null)
const reviseSuccess = ref<string | null>(null)
const reviseRow = ref<Record<string, unknown> | null>(null)
const revision = ref({ unit_price: 0, effective_from: null as Date | null, change_reason: '' })

const reviseTitle = computed(() =>
  reviseRow.value ? `Revise rate — revision ${Number(reviseRow.value.revision_number ?? 1) + 1}` : 'Revise rate',
)
const reviseValid = computed(
  () => Boolean(revision.value.effective_from) && revision.value.change_reason.trim().length > 0,
)

function openRevise(row: Record<string, unknown>): void {
  reviseRow.value = row
  reviseError.value = null
  revision.value = { unit_price: Number(row.unit_price ?? 0), effective_from: null, change_reason: '' }
  reviseVisible.value = true
}

async function submitRevision(): Promise<void> {
  if (!reviseRow.value?.id || !reviseValid.value) return
  reviseSaving.value = true
  reviseError.value = null
  try {
    await procurement.reviseItemPrice(String(reviseRow.value.id), {
      unit_price: String(revision.value.unit_price ?? 0),
      effective_from: asDate(revision.value.effective_from) as string,
      change_reason: revision.value.change_reason.trim(),
    })
    reviseVisible.value = false
    reviseSuccess.value = 'Rate revised. Wells already using the previous rate keep it until completion.'
    await grid.value?.reload()
  }
  catch (error) {
    reviseError.value = error instanceof Error ? error.message : 'The rate could not be revised.'
  }
  finally {
    reviseSaving.value = false
  }
}
</script>

<template>
  <div class="library-page">
    <PageHeader
      title="Tangible Rates"
      description="Effective-dated master rates for tangibles and consumables. Services are priced per well, so they have no master rate here. Use Revise to supersede a rate: the current row is closed, the change is logged, and wells already drilling keep the rate they were planned with."
    />
    <MasterDataNav active="item-prices" />
    <Message v-if="reviseSuccess" severity="success" :closable="true" @close="reviseSuccess = null">
      {{ reviseSuccess }}
    </Message>
    <EnterpriseGrid
      ref="grid"
      title="Tangible rates"
      singular="tangible rate"
      :columns="columns"
      :filters="filters"
      :fetch-page="fetchPage"
      :to-row="toRow"
      :to-payload="toPayload"
      :blank-row="blankRow"
      :validate-rows="rows => procurement.itemPrices.validate(rows)"
      :bulk-create="rows => procurement.itemPrices.bulkCreate(rows)"
      :bulk-update="rows => procurement.itemPrices.bulkUpdate(rows)"
      :remove-record="(id, hard) => procurement.itemPrices.remove(id, hard)"
      import-entity="item-prices"
      export-entity="item-prices"
      default-sort="effective_from"
      default-sort-order="desc"
      search-placeholder="Search by item code, name, or material number…"
    >
      <template #row-actions="{ row }">
        <Button
          v-tooltip.top="'Revise rate'"
          icon="pi pi-history"
          size="small"
          severity="secondary"
          text
          aria-label="Revise rate"
          @click="openRevise(row)"
        />
      </template>
    </EnterpriseGrid>

    <Dialog v-model:visible="reviseVisible" modal :header="reviseTitle" :style="{ width: '32rem' }">
      <div class="revise">
        <Message severity="info" :closable="false">
          The current rate is closed the day before the new rate takes effect. Wells that already
          added this item keep their own rate until completion.
        </Message>
        <label class="revise__field">
          <span>New rate</span>
          <InputNumber v-model="revision.unit_price" :min-fraction-digits="2" :max-fraction-digits="4" fluid />
        </label>
        <label class="revise__field">
          <span>Effective from</span>
          <DatePicker v-model="revision.effective_from" date-format="yy-mm-dd" show-icon fluid />
        </label>
        <label class="revise__field">
          <span>Reason for the revision</span>
          <Textarea v-model="revision.change_reason" rows="3" auto-resize placeholder="e.g. Contract renegotiation Q1 2026" />
        </label>
        <Message v-if="reviseError" severity="error" :closable="false">{{ reviseError }}</Message>
      </div>
      <template #footer>
        <Button label="Cancel" severity="secondary" text @click="reviseVisible = false" />
        <Button label="Save revision" icon="pi pi-check" :disabled="!reviseValid" :loading="reviseSaving" @click="submitRevision" />
      </template>
    </Dialog>
  </div>
</template>

<style scoped>
.revise {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.revise__field {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  font-weight: 600;
}
</style>
