<script setup lang="ts">
/**
 * Audit Log — same shell as Master Data: PageHeader, card, compact table,
 * filters, export and a print sheet that contains only the log (not chrome).
 */
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import Button from 'primevue/button'
import PageHeader from '~/components/design-system/PageHeader.vue'
import { matchesAdvancedSearch } from '~/utils/search'

definePageMeta({ middleware: 'auth' })

interface AuditLogRow {
  id: number
  timestamp: string
  user_email: string | null
  action: string
  module: string
  entity_code: string | null
  details: string | null
  ip_address: string | null
}

const KNOWN_MODULES = [
  'Authentication',
  'Unit of Measurements',
  'Currency',
  'Phases',
  'Activities',
  'Hole Sections',
  'Vendors/Suppliers',
  'Purchase Orders/Service Orders',
  'Services',
  'Mud Chemicals',
  'Drill Bits',
  'Tangibles',
  'Dropdown Lists',
  'Consumable Rate Revisions',
  'Audit',
]

const KNOWN_ACTIONS = [
  'LOGIN',
  'CREATE',
  'UPDATE',
  'RATE_REVISION',
  'SOFT_DELETE',
  'RESTORE',
  'PERMANENT_DELETE',
  'BULK_IMPORT',
  'EXPORT',
]

const api = useApi()

const logs = ref<AuditLogRow[]>([])
const loading = ref(false)
const error = ref<string | null>(null)
const selectedModule = ref('')
const selectedAction = ref('')
const searchQuery = ref('')
const page = ref(1)
const pageSize = ref(20)
const printedAt = ref('')

async function loadLogs(): Promise<void> {
  loading.value = true
  error.value = null
  try {
    const params = new URLSearchParams({ limit: '1000' })
    if (selectedModule.value) params.set('module', selectedModule.value)
    if (selectedAction.value) params.set('action', selectedAction.value)
    logs.value = await api.get<AuditLogRow[]>(`/audit-logs?${params.toString()}`)
    page.value = 1
  }
  catch (caught: unknown) {
    error.value = caught instanceof Error ? caught.message : 'Audit logs could not be loaded'
    logs.value = []
  }
  finally {
    loading.value = false
  }
}

onMounted(() => {
  void loadLogs()
  if (typeof window !== 'undefined') window.addEventListener('beforeprint', stampPrintedAt)
})

onBeforeUnmount(() => {
  if (typeof window !== 'undefined') window.removeEventListener('beforeprint', stampPrintedAt)
})

watch([selectedModule, selectedAction], () => {
  void loadLogs()
})

const moduleOptions = computed(() => {
  const fromLogs = logs.value.map(log => log.module).filter(Boolean)
  return [...new Set([...KNOWN_MODULES, ...fromLogs])].sort((a, b) => a.localeCompare(b))
})

const actionOptions = computed(() => {
  const fromLogs = logs.value.map(log => log.action).filter(Boolean)
  return [...new Set([...KNOWN_ACTIONS, ...fromLogs])]
})

const filteredLogs = computed(() => {
  return logs.value.filter(log => matchesAdvancedSearch(log, searchQuery.value))
})

watch(searchQuery, () => {
  page.value = 1
})

const paginatedLogs = computed(() => {
  const start = (page.value - 1) * pageSize.value
  return filteredLogs.value.slice(start, start + pageSize.value)
})

const totalPages = computed(() => Math.max(1, Math.ceil(filteredLogs.value.length / pageSize.value)))

const printFilters = computed(() => {
  const parts: string[] = []
  parts.push(selectedModule.value ? `Module: ${selectedModule.value}` : 'Module: All')
  parts.push(selectedAction.value ? `Action: ${selectedAction.value}` : 'Action: All')
  if (searchQuery.value.trim()) parts.push(`Search: ${searchQuery.value.trim()}`)
  parts.push(`${filteredLogs.value.length} log(s)`)
  if (printedAt.value) parts.push(`Printed ${printedAt.value}`)
  return parts.join(' · ')
})

function stampPrintedAt(): void {
  printedAt.value = new Date().toLocaleString()
}

function actionClass(action: string): string {
  switch (action) {
    case 'CREATE':
    case 'LOGIN':
      return 'badge badge--green'
    case 'UPDATE':
      return 'badge badge--blue'
    case 'RATE_REVISION':
      return 'badge badge--teal'
    case 'SOFT_DELETE':
      return 'badge badge--amber'
    case 'PERMANENT_DELETE':
      return 'badge badge--red'
    case 'RESTORE':
    case 'BULK_IMPORT':
      return 'badge badge--purple'
    default:
      return 'badge badge--muted'
  }
}

function formatTimestamp(value: string | null): string {
  if (!value) return '—'
  const parsed = new Date(value)
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString()
}

async function exportLogs(format: 'xlsx' | 'csv'): Promise<void> {
  try {
    const params = new URLSearchParams({ format })
    if (selectedModule.value) params.set('module', selectedModule.value)
    if (selectedAction.value) params.set('action', selectedAction.value)
    const blob = await api.download(`/audit-logs/export?${params.toString()}`)
    const blobUrl = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = blobUrl
    link.download = `audit_logs_export.${format}`
    link.click()
    window.URL.revokeObjectURL(blobUrl)
  }
  catch (caught: unknown) {
    window.alert(caught instanceof Error ? caught.message : 'Export failed')
  }
}

function printLogs(): void {
  stampPrintedAt()
  window.print()
}
</script>

<template>
  <div class="audit-logs-page">
    <PageHeader
      class="no-print"
      title="System Audit Log"
      description="Every sign-in and every catalogue change — create, update, soft delete, restore, permanent delete, bulk import and export — with the acting user and timestamp."
    />

    <section class="grid-card">
      <div class="toolbar no-print">
        <div class="toolbar__filters">
          <select v-model="selectedModule" class="filter-select" aria-label="Filter by module">
            <option value="">All modules</option>
            <option v-for="module in moduleOptions" :key="module" :value="module">{{ module }}</option>
          </select>
          <select v-model="selectedAction" class="filter-select" aria-label="Filter by action">
            <option value="">All actions</option>
            <option v-for="action in actionOptions" :key="action" :value="action">{{ action }}</option>
          </select>
          <div class="search">
            <i class="pi pi-search" />
            <input
              v-model="searchQuery"
              type="search"
              placeholder="Search all log fields…"
              class="search__input"
              title="Advanced search: matches user, action, module, entity, details and IP."
            >
          </div>
          <Button label="Refresh" icon="pi pi-refresh" size="small" severity="secondary" outlined :loading="loading" @click="loadLogs" />
          <span class="count">{{ filteredLogs.length }} logs</span>
        </div>
        <div class="toolbar__actions">
          <Button label="XLSX" icon="pi pi-file-excel" size="small" severity="success" outlined @click="exportLogs('xlsx')" />
          <Button label="CSV" icon="pi pi-file" size="small" severity="secondary" outlined @click="exportLogs('csv')" />
          <Button label="Print" icon="pi pi-print" size="small" severity="secondary" text @click="printLogs" />
          <select v-model="pageSize" class="filter-select" aria-label="Rows per page">
            <option :value="10">10 / page</option>
            <option :value="20">20 / page</option>
            <option :value="50">50 / page</option>
            <option :value="100">100 / page</option>
          </select>
        </div>
      </div>

      <p v-if="error" class="error-copy no-print">{{ error }}</p>

      <div class="table-scroll no-print">
        <table class="audit-table">
          <thead>
            <tr>
              <th>ID</th>
              <th>Timestamp</th>
              <th>User</th>
              <th>Action</th>
              <th>Module</th>
              <th>Entity</th>
              <th>Details</th>
              <th>IP</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="loading">
              <td colspan="8" class="empty-cell"><i class="pi pi-spin pi-spinner" /> Loading audit logs…</td>
            </tr>
            <tr v-else-if="paginatedLogs.length === 0">
              <td colspan="8" class="empty-cell">No audit logs match the current filters. Sign-in and catalogue changes appear here.</td>
            </tr>
            <tr v-for="log in paginatedLogs" :key="log.id">
              <td class="mono muted">#{{ log.id }}</td>
              <td class="nowrap">{{ formatTimestamp(log.timestamp) }}</td>
              <td class="truncate" :title="log.user_email ?? ''">{{ log.user_email || '—' }}</td>
              <td><span :class="actionClass(log.action)">{{ log.action }}</span></td>
              <td class="module">{{ log.module }}</td>
              <td class="mono">{{ log.entity_code || '—' }}</td>
              <td class="truncate muted" :title="log.details ?? ''">{{ log.details || '—' }}</td>
              <td class="mono muted">{{ log.ip_address || '—' }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="pager no-print">
        <span>Page {{ page }} of {{ totalPages }} — {{ filteredLogs.length }} total</span>
        <div class="pager__buttons">
          <Button label="Prev" size="small" severity="secondary" outlined :disabled="page <= 1" @click="page--" />
          <Button label="Next" size="small" severity="secondary" outlined :disabled="page >= totalPages" @click="page++" />
        </div>
      </div>

      <div class="print-sheet" aria-hidden="true">
        <header class="print-sheet__header">
          <p class="print-sheet__eyebrow">Drilling Costing</p>
          <h1>System Audit Log</h1>
          <p class="print-sheet__meta">{{ printFilters }}</p>
        </header>
        <table v-if="filteredLogs.length" class="print-sheet__table">
          <thead>
            <tr>
              <th>ID</th>
              <th>Timestamp</th>
              <th>User</th>
              <th>Action</th>
              <th>Module</th>
              <th>Entity</th>
              <th>Details</th>
              <th>IP</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="log in filteredLogs" :key="`print-${log.id}`">
              <td>{{ log.id }}</td>
              <td>{{ formatTimestamp(log.timestamp) }}</td>
              <td>{{ log.user_email || '—' }}</td>
              <td>{{ log.action }}</td>
              <td>{{ log.module }}</td>
              <td>{{ log.entity_code || '—' }}</td>
              <td>{{ log.details || '—' }}</td>
              <td>{{ log.ip_address || '—' }}</td>
            </tr>
          </tbody>
        </table>
        <p v-else class="print-sheet__empty">No audit logs match the current filters.</p>
      </div>
    </section>
  </div>
</template>

<style scoped>
.audit-logs-page {
  max-width: 1600px;
  margin: 0 auto;
}

.grid-card {
  background: var(--app-surface);
  border: 1px solid var(--app-border);
  border-radius: 12px;
  box-shadow: var(--app-shadow);
  padding: 1rem;
}

.toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  margin-bottom: 0.75rem;
}

.toolbar__filters,
.toolbar__actions,
.pager__buttons {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.4rem;
}

.filter-select,
.search__input {
  height: 2rem;
  font-size: 0.78rem;
  border: 1px solid var(--app-border);
  border-radius: 6px;
  background: var(--app-surface);
  color: var(--app-ink);
  padding: 0 0.5rem;
}

.search {
  position: relative;
  display: flex;
  align-items: center;
}

.search .pi-search {
  position: absolute;
  left: 0.55rem;
  color: var(--app-muted);
  font-size: 0.75rem;
  pointer-events: none;
}

.search__input {
  padding-left: 1.7rem;
  width: 16rem;
  border-radius: 999px;
  background: var(--app-glass, var(--app-surface));
  border-color: var(--app-glass-border, var(--app-border));
}

.count {
  font-size: 0.72rem;
  color: var(--app-muted);
}

.table-scroll {
  overflow: auto;
  max-height: 65vh;
  border: 1px solid var(--app-border);
  border-radius: 8px;
}

.audit-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.78rem;
  text-align: left;
}

.audit-table th {
  position: sticky;
  top: 0;
  background: var(--app-bg);
  font-size: 0.68rem;
  text-transform: uppercase;
  letter-spacing: 0.03em;
  color: var(--app-muted);
  padding: 0.55rem 0.6rem;
  border-bottom: 1px solid var(--app-border);
}

.audit-table td {
  padding: 0.45rem 0.6rem;
  border-bottom: 1px solid var(--app-border);
  vertical-align: top;
}

.module {
  color: var(--app-teal);
  font-weight: 600;
}

.mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
}

.muted {
  color: var(--app-muted);
  font-size: 0.72rem;
}

.nowrap {
  white-space: nowrap;
}

.truncate {
  max-width: 220px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.empty-cell {
  padding: 1.5rem !important;
  text-align: center;
  color: var(--app-muted);
}

.pager {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 0.75rem;
  font-size: 0.75rem;
  color: var(--app-muted);
}

.badge {
  display: inline-block;
  padding: 0.1rem 0.45rem;
  border-radius: 999px;
  font-size: 0.65rem;
  font-weight: 700;
  letter-spacing: 0.02em;
}

.badge--green { background: color-mix(in srgb, #16a34a 18%, var(--app-surface)); color: #166534; }
.badge--blue { background: color-mix(in srgb, #2563eb 18%, var(--app-surface)); color: #1e40af; }
.badge--teal { background: color-mix(in srgb, var(--p-primary-color, #0f766e) 18%, var(--app-surface)); color: var(--p-primary-color, #0f766e); }
.badge--amber { background: color-mix(in srgb, #d97706 18%, var(--app-surface)); color: #92400e; }
.badge--red { background: color-mix(in srgb, #e11d48 18%, var(--app-surface)); color: #991b1b; }
.badge--purple { background: color-mix(in srgb, #7c3aed 18%, var(--app-surface)); color: #6b21a8; }
.badge--muted { background: var(--app-bg); color: var(--app-ink); }

.app-dark .badge--green { color: #86efac; }
.app-dark .badge--blue { color: #93c5fd; }
.app-dark .badge--amber { color: #fcd34d; }
.app-dark .badge--red { color: #fda4af; }
.app-dark .badge--purple { color: #d8b4fe; }

.print-sheet {
  display: none;
}
</style>
