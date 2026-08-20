/**
 * Master rate change log.
 *
 * Read-only by design: rates are revised, never overwritten, so this page is
 * the audit trail of what the catalogue charged, from when, and why it moved.
 * Wells that copied a rate into their rate book are unaffected by anything
 * listed here — see the well's own rate-book history for that.
 */
<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import Button from 'primevue/button'
import Column from 'primevue/column'
import DataTable from 'primevue/datatable'
import Message from 'primevue/message'
import Select from 'primevue/select'
import Tag from 'primevue/tag'
import MasterDataNav from '~/components/master-data/MasterDataNav.vue'
import PageHeader from '~/components/design-system/PageHeader.vue'
import { downloadBlob, exportFilename } from '~/utils/download'
import { RATE_CHANGE_TYPES, type RateRevisionRecord } from '~/types/procurement'

definePageMeta({ middleware: 'auth' })

const procurement = useProcurement()
const masterData = useMasterData()
const references = useReferenceOptions()

const revisions = ref<RateRevisionRecord[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(25)
const loading = ref(false)
const exporting = ref(false)
const error = ref<string | null>(null)
const success = ref<string | null>(null)
const itemFilter = ref<string | null>(null)
const changeTypeFilter = ref<string | null>(null)

const first = computed(() => (page.value - 1) * pageSize.value)
const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize.value)))
const printedAt = computed(() => new Date().toLocaleString())

async function load(): Promise<void> {
  loading.value = true
  error.value = null
  try {
    const response = await procurement.rateRevisions({
      page: page.value,
      page_size: pageSize.value,
      item_id: itemFilter.value,
      change_type: changeTypeFilter.value,
    })
    revisions.value = response.items
    total.value = response.total
  }
  catch (caught: unknown) {
    error.value = caught instanceof Error ? caught.message : 'The rate change log could not be loaded.'
  }
  finally {
    loading.value = false
  }
}

/** Export the whole change log (not just the current page) to Excel. */
async function exportWorkbook(): Promise<void> {
  exporting.value = true
  error.value = null
  try {
    const blob = await masterData.export('rate-revisions')
    downloadBlob(blob, exportFilename('rate-revisions'))
    success.value = 'Rate revisions exported to Excel.'
  }
  catch (caught: unknown) {
    error.value = caught instanceof Error
      ? `The export failed: ${caught.message}`
      : 'The export could not be generated.'
  }
  finally {
    exporting.value = false
  }
}

function printLog(): void {
  if (typeof window !== 'undefined' && typeof window.print === 'function') window.print()
}

function onPage(event: { page: number, rows: number }): void {
  page.value = event.page + 1
  pageSize.value = event.rows
  void load()
}

function severity(changeType: string): 'success' | 'info' | 'warn' {
  if (changeType === 'created') return 'success'
  if (changeType === 'revised') return 'info'
  return 'warn'
}

function money(value: string | null): string {
  return value === null ? '—' : Number(value).toLocaleString(undefined, { minimumFractionDigits: 2 })
}

function delta(value: string | null): string {
  if (value === null) return '—'
  const numeric = Number(value)
  return `${numeric > 0 ? '+' : ''}${numeric.toLocaleString(undefined, { minimumFractionDigits: 2 })}`
}

watch([itemFilter, changeTypeFilter], () => {
  page.value = 1
  void load()
})

onMounted(() => {
  void references.load(['catalogue'])
  void load()
})
</script>

<template>
  <div class="library-page">
    <PageHeader
      title="Rate Revisions"
      description="Every master rate change, newest first: the amount before and after, the date it takes effect, the reason, and who made it. Rates are superseded rather than overwritten, so any past date still resolves to exactly one rate."
    >
      <template #actions>
        <Button
          label="Export"
          icon="pi pi-file-excel"
          severity="secondary"
          outlined
          :loading="exporting"
          @click="exportWorkbook"
        />
        <Button
          label="Print"
          icon="pi pi-print"
          severity="secondary"
          outlined
          @click="printLog"
        />
      </template>
    </PageHeader>
    <MasterDataNav active="rate-revisions" />

    <div class="rr__filters">
      <Select
        v-model="itemFilter"
        :options="references.catalogueItems.value"
        option-label="label"
        option-value="value"
        placeholder="All items"
        show-clear
        filter
        style="width: 20rem"
      />
      <Select
        v-model="changeTypeFilter"
        :options="RATE_CHANGE_TYPES"
        option-label="label"
        option-value="value"
        placeholder="All change types"
        show-clear
        style="width: 14rem"
      />
    </div>

    <Message v-if="success" severity="success" :closable="true" @close="success = null">{{ success }}</Message>
    <Message v-if="error" severity="error" :closable="false">{{ error }}</Message>

    <DataTable
      :value="revisions"
      :loading="loading"
      lazy
      paginator
      :rows="pageSize"
      :first="first"
      :total-records="total"
      :rows-per-page-options="[10, 25, 50, 100]"
      striped-rows
      show-gridlines
      size="small"
      class="bulk-grid-panel"
      @page="onPage"
    >
      <Column header="Changed" sortable>
        <template #body="{ data }">{{ new Date(data.created_at).toLocaleString() }}</template>
      </Column>
      <Column header="Item">
        <template #body="{ data }">
          <strong>{{ data.item_code ?? '—' }}</strong>
          <div class="rr__muted">{{ data.item_name }}</div>
        </template>
      </Column>
      <Column header="Change">
        <template #body="{ data }">
          <Tag :value="data.change_type" :severity="severity(data.change_type)" />
        </template>
      </Column>
      <Column header="Rev." field="revision_number" />
      <Column header="Previous">
        <template #body="{ data }">{{ money(data.previous_amount) }}</template>
      </Column>
      <Column header="New">
        <template #body="{ data }">{{ money(data.new_amount) }}</template>
      </Column>
      <Column header="Delta">
        <template #body="{ data }">{{ delta(data.delta_amount) }}</template>
      </Column>
      <Column header="Currency">
        <template #body="{ data }">{{ data.currency_code ?? '—' }} / {{ data.unit_code ?? '—' }}</template>
      </Column>
      <Column header="Effective from" field="effective_from" />
      <Column header="Reason">
        <template #body="{ data }">{{ data.reason ?? '—' }}</template>
      </Column>
      <template #empty>No master rate has been changed yet.</template>
    </DataTable>

    <!-- Print-only rendering: hidden on screen, used by the browser print dialog -->
    <div class="eg__print" aria-hidden="true">
      <header class="eg__print-header">
        <h2>Rate revisions</h2>
        <p>
          {{ total }} record(s) · page {{ page }} of {{ totalPages }} · printed {{ printedAt }}
        </p>
      </header>
      <table class="eg__print-table">
        <thead>
          <tr>
            <th>Changed</th>
            <th>Item</th>
            <th>Change</th>
            <th>Rev.</th>
            <th>Previous</th>
            <th>New</th>
            <th>Delta</th>
            <th>Currency / UOM</th>
            <th>Effective from</th>
            <th>Reason</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="data in revisions" :key="data.id">
            <td>{{ new Date(data.created_at).toLocaleString() }}</td>
            <td>{{ data.item_code ?? '—' }} — {{ data.item_name }}</td>
            <td>{{ data.change_type }}</td>
            <td>{{ data.revision_number }}</td>
            <td>{{ money(data.previous_amount) }}</td>
            <td>{{ money(data.new_amount) }}</td>
            <td>{{ delta(data.delta_amount) }}</td>
            <td>{{ data.currency_code ?? '—' }} / {{ data.unit_code ?? '—' }}</td>
            <td>{{ data.effective_from ?? '—' }}</td>
            <td>{{ data.reason ?? '—' }}</td>
          </tr>
        </tbody>
      </table>
      <p v-if="!revisions.length" class="eg__print-empty">No master rate changes match the current filters.</p>
    </div>
  </div>
</template>

<style scoped>
.rr__filters {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
  margin-bottom: 1rem;
}

.rr__muted {
  color: var(--p-text-muted-color, #6b7280);
  font-size: 0.85em;
}
</style>
