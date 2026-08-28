<script setup lang="ts">
/**
 * Rate Revision History panel — shared by Mud Chemicals, Drill Bits and
 * Tangibles. Compact, paginated read-only table of every price revision with
 * XLSX/CSV export and a clean print sheet (same workflow as all other pages).
 */
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import Button from 'primevue/button'
import { matchesAdvancedSearch } from '~/utils/search'

interface RateRevision {
  id: number
  item_kind: string | null
  item_code: string | null
  item_name: string | null
  unit_rate: string | null
  unit_rate_po: string | null
  previous_rate: string | null
  cost_uplift: string | null
  final_cost: string | null
  currency: string | null
  uom: string | null
  effective_date: string | null
  revision_number: number
  po_number: string | null
  remarks: string | null
  created_at: string | null
}

const props = defineProps<{
  /** API path returning the revision list, e.g. `/catalogue/drill-bits/rate-history`. */
  endpoint: string
  title: string
  /** 'chemical' shows unit_rate/previous_rate; 'priced' shows rate/uplift/final;
   *  'consumables' shows both (mixed Mud Chemical + Drill Bit rows). */
  kind: 'chemical' | 'priced' | 'consumables'
}>()

const api = useApi()

const revisions = ref<RateRevision[]>([])
const loading = ref(false)
const error = ref<string | null>(null)
const search = ref('')
const kindFilter = ref('')
const page = ref(1)
const pageSize = ref(15)
const printedAt = ref('')
const reloadKey = ref(0)

async function load(): Promise<void> {
  loading.value = true
  error.value = null
  try {
    revisions.value = await api.get<RateRevision[]>(props.endpoint)
    page.value = 1
  }
  catch (caught: unknown) {
    error.value = caught instanceof Error ? caught.message : 'Rate history could not be loaded'
    revisions.value = []
  }
  finally {
    loading.value = false
  }
}

defineExpose({ reload: () => load() })

onMounted(() => {
  void load()
  if (typeof window !== 'undefined') window.addEventListener('beforeprint', stampPrintedAt)
})

onBeforeUnmount(() => {
  if (typeof window !== 'undefined') window.removeEventListener('beforeprint', stampPrintedAt)
})

watch(reloadKey, () => void load())

const itemKinds = computed(() => [...new Set(revisions.value.map(r => r.item_kind).filter(Boolean))].sort())

const filtered = computed(() => {
  return revisions.value.filter((r) => {
    if (kindFilter.value && r.item_kind !== kindFilter.value) return false
    return matchesAdvancedSearch(r, search.value)
  })
})

watch(search, () => {
  page.value = 1
})

const paged = computed(() => {
  const start = (page.value - 1) * pageSize.value
  return filtered.value.slice(start, start + pageSize.value)
})

const totalPages = computed(() => Math.max(1, Math.ceil(filtered.value.length / pageSize.value)))

const columns = computed(() => {
  if (props.kind === 'consumables') {
    return [
      { key: 'item_kind', label: 'Type', price: false },
      { key: 'revision_number', label: 'Rev', price: false },
      { key: 'item_code', label: 'Code', price: false },
      { key: 'item_name', label: 'Item', price: false },
      { key: 'effective_date', label: 'Effective', price: false },
      { key: 'previous_rate', label: 'Prev. Rate', price: true },
      { key: 'unit_rate', label: 'Unit Rate', price: true },
      { key: 'unit_rate_po', label: 'Rate as per PO', price: true },
      { key: 'cost_uplift', label: 'Uplift %', price: false },
      { key: 'final_cost', label: 'Final Cost', price: true },
      { key: 'currency', label: 'Cur', price: false },
      { key: 'uom', label: 'UOM', price: false },
      { key: 'remarks', label: 'Remarks', price: false },
    ]
  }
  if (props.kind === 'chemical') {
    return [
      { key: 'revision_number', label: 'Rev', price: false },
      { key: 'item_code', label: 'Code', price: false },
      { key: 'item_name', label: 'Chemical', price: false },
      { key: 'effective_date', label: 'Effective', price: false },
      { key: 'previous_rate', label: 'Previous', price: true },
      { key: 'unit_rate', label: 'Unit Rate', price: true },
      { key: 'currency', label: 'Cur', price: false },
      { key: 'uom', label: 'UOM', price: false },
      { key: 'remarks', label: 'Remarks', price: false },
    ]
  }
  return [
    { key: 'revision_number', label: 'Rev', price: false },
    { key: 'item_code', label: 'Code', price: false },
    { key: 'item_name', label: 'Item', price: false },
    { key: 'effective_date', label: 'Effective', price: false },
    { key: 'unit_rate_po', label: 'Rate as per PO', price: true },
    { key: 'cost_uplift', label: 'Uplift %', price: false },
    { key: 'final_cost', label: 'Final Cost', price: true },
    { key: 'currency', label: 'Cur', price: false },
    { key: 'po_number', label: 'PO №', price: false },
    { key: 'remarks', label: 'Remarks', price: false },
  ]
})

function cellValue(r: RateRevision, key: string): string {
  if (key === 'effective_date') return r.effective_date ? String(r.effective_date).slice(0, 10) : '—'
  if (key === 'cost_uplift') return r.cost_uplift ? `${r.cost_uplift}%` : '—'
  const v = (r as unknown as Record<string, unknown>)[key]
  return v == null || v === '' ? '—' : String(v)
}

const printMeta = computed(() => {
  const parts = [`${filtered.value.length} revision(s)`]
  if (kindFilter.value) parts.push(`Type: ${kindFilter.value}`)
  if (search.value.trim()) parts.push(`Search: ${search.value.trim()}`)
  if (printedAt.value) parts.push(`Printed ${printedAt.value}`)
  return parts.join(' · ')
})

function stampPrintedAt(): void {
  printedAt.value = new Date().toLocaleString()
}

async function exportHistory(format: 'xlsx' | 'csv'): Promise<void> {
  try {
    const blob = await api.download(`${props.endpoint}/export?format=${format}`)
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${props.endpoint.split('/').pop()}_rate_history.${format}`
    a.click()
    window.URL.revokeObjectURL(url)
  }
  catch (caught: unknown) {
    window.alert(caught instanceof Error ? caught.message : 'Export failed')
  }
}

function printHistory(): void {
  stampPrintedAt()
  window.print()
}
</script>

<template>
  <div class="rate-panel">
    <div class="rate-toolbar no-print">
      <div class="rate-toolbar__filters">
        <select v-if="itemKinds.length > 1" v-model="kindFilter" class="rate-select">
          <option value="">All types</option>
          <option v-for="k in itemKinds" :key="k ?? ''" :value="k ?? ''">{{ k }}</option>
        </select>
        <div class="rate-search">
          <i class="pi pi-search" />
          <input
            v-model="search"
            type="search"
            placeholder="Search all revision fields…"
            class="rate-search__input"
            title="Advanced search: matches code, name, currency, PO number, remarks and every other column."
          >
        </div>
        <span class="rate-count">{{ filtered.length }} revision(s)</span>
      </div>
      <div class="rate-toolbar__actions">
        <Button label="XLSX" icon="pi pi-file-excel" size="small" severity="success" outlined @click="exportHistory('xlsx')" />
        <Button label="CSV" icon="pi pi-file" size="small" severity="secondary" outlined @click="exportHistory('csv')" />
        <Button label="Print" icon="pi pi-print" size="small" severity="secondary" text @click="printHistory" />
        <Button icon="pi pi-refresh" size="small" severity="secondary" text :loading="loading" @click="load" />
        <select v-model="pageSize" class="rate-select">
          <option :value="15">15 / page</option>
          <option :value="30">30 / page</option>
          <option :value="50">50 / page</option>
        </select>
      </div>
    </div>

    <p v-if="error" class="rate-error no-print">{{ error }}</p>

    <div class="rate-scroll no-print">
      <table class="rate-table">
        <thead>
          <tr>
            <th>#</th>
            <th v-for="col in columns" :key="col.key" :class="{ 'num': col.price }">{{ col.label }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="loading">
            <td :colspan="columns.length + 1" class="rate-empty"><i class="pi pi-spin pi-spinner" /> Loading…</td>
          </tr>
          <tr v-else-if="!paged.length">
            <td :colspan="columns.length + 1" class="rate-empty">No rate revisions yet. Revisions appear automatically when an item's rate changes.</td>
          </tr>
          <tr v-for="(r, i) in paged" :key="r.id">
            <td class="rate-index">{{ (page - 1) * pageSize + i + 1 }}</td>
            <td v-for="col in columns" :key="col.key" :class="col.price ? 'num rate-money' : ''">
              <span v-if="col.key === 'revision_number'" class="rate-rev">R{{ r.revision_number }}</span>
              <span v-else-if="col.key === 'item_kind'" class="rate-kind">{{ cellValue(r, col.key) }}</span>
              <span v-else-if="col.key === 'item_code'" class="mono">{{ cellValue(r, col.key) }}</span>
              <span v-else-if="col.key === 'item_name'" class="rate-name" :title="cellValue(r, col.key)">{{ cellValue(r, col.key) }}</span>
              <span v-else>{{ cellValue(r, col.key) }}</span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <div class="rate-pager no-print">
      <span>Page {{ page }} of {{ totalPages }}</span>
      <div class="rate-pager__btns">
        <Button label="Prev" size="small" severity="secondary" outlined :disabled="page <= 1" @click="page--" />
        <Button label="Next" size="small" severity="secondary" outlined :disabled="page >= totalPages" @click="page++" />
      </div>
    </div>

    <div class="rate-print" aria-hidden="true">
      <header class="rate-print__header">
        <p class="rate-print__eyebrow">Drilling Costing</p>
        <h1>{{ title }}</h1>
        <p class="rate-print__meta">{{ printMeta }}</p>
      </header>
      <table v-if="filtered.length" class="rate-print__table">
        <thead>
          <tr>
            <th>#</th>
            <th v-for="col in columns" :key="col.key">{{ col.label }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(r, i) in filtered" :key="`print-${r.id}`">
            <td>{{ i + 1 }}</td>
            <td v-for="col in columns" :key="col.key">{{ cellValue(r, col.key) }}</td>
          </tr>
        </tbody>
      </table>
      <p v-else class="rate-print__empty">No rate revisions match the current filters.</p>
    </div>
  </div>
</template>

<style scoped>
.rate-panel {
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
}

.rate-toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
}

.rate-toolbar__filters,
.rate-toolbar__actions,
.rate-pager__btns {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.35rem;
}

.rate-select {
  height: 1.9rem;
  font-size: 0.75rem;
  border: 1px solid var(--app-border);
  border-radius: 6px;
  background: var(--app-surface);
  color: var(--app-ink);
  padding: 0 0.4rem;
}

.rate-search {
  position: relative;
  display: flex;
  align-items: center;
}

.rate-search .pi-search {
  position: absolute;
  left: 0.5rem;
  color: var(--app-muted);
  font-size: 0.72rem;
  pointer-events: none;
}

.rate-search__input {
  height: 1.9rem;
  font-size: 0.75rem;
  border: 1px solid var(--app-glass-border, var(--app-border));
  border-radius: 999px;
  background: var(--app-glass, var(--app-surface));
  color: var(--app-ink);
  padding: 0 0.5rem 0 1.55rem;
  width: 16rem;
}

.rate-count {
  font-size: 0.7rem;
  color: var(--app-muted);
}

.rate-error {
  color: #e11d48;
  font-size: 0.78rem;
  margin: 0;
}

.rate-scroll {
  overflow: auto;
  max-height: 56vh;
  border: 1px solid var(--app-border);
  border-radius: 8px;
}

.rate-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.74rem;
  text-align: left;
}

.rate-table th {
  position: sticky;
  top: 0;
  background: var(--app-bg);
  font-size: 0.65rem;
  text-transform: uppercase;
  letter-spacing: 0.03em;
  color: var(--app-muted);
  padding: 0.45rem 0.55rem;
  border-bottom: 1px solid var(--app-border);
  white-space: nowrap;
}

.rate-table td {
  padding: 0.35rem 0.55rem;
  border-bottom: 1px solid var(--app-border);
  white-space: nowrap;
}

.rate-table .num {
  text-align: right;
}

.rate-money {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-weight: 600;
}

.rate-index {
  color: var(--app-muted);
  font-size: 0.68rem;
}

.rate-rev {
  display: inline-block;
  background: color-mix(in srgb, var(--p-primary-color, var(--app-teal)) 14%, transparent);
  color: var(--p-primary-color, var(--app-teal));
  border-radius: 999px;
  padding: 0.05rem 0.4rem;
  font-size: 0.66rem;
  font-weight: 700;
}

.rate-kind {
  display: inline-block;
  background: var(--app-bg);
  border-radius: 4px;
  padding: 0.05rem 0.35rem;
  font-size: 0.66rem;
  font-weight: 600;
  color: var(--app-muted);
  white-space: nowrap;
}

.mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
}

.rate-name {
  display: inline-block;
  max-width: 220px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.rate-empty {
  padding: 1.25rem !important;
  text-align: center;
  color: var(--app-muted);
}

.rate-pager {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 0.72rem;
  color: var(--app-muted);
}

.rate-print {
  display: none;
}

@media print {
  .rate-print {
    display: block;
  }

  .rate-print__header h1 {
    font-size: 16pt;
    margin: 0.2rem 0;
  }

  .rate-print__eyebrow {
    color: #666;
    font-size: 9pt;
    margin: 0;
  }

  .rate-print__meta {
    color: #666;
    font-size: 9pt;
    margin: 0 0 0.6rem;
  }

  .rate-print__table {
    width: 100%;
    border-collapse: collapse;
    font-size: 8pt;
  }

  .rate-print__table th,
  .rate-print__table td {
    border: 1px solid #999;
    padding: 0.2rem 0.35rem;
    text-align: left;
  }
}
</style>
