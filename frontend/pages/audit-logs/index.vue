<script setup lang="ts">
/**
 * Audit Log Page — Compact, paginated, with module/action filters,
 * Excel/CSV export, Print, and audit of every action.
 * Common template: Import (not needed), Export, Print, compact table.
 */
import { ref, computed, onMounted } from 'vue'
import PageHeader from '~/components/design-system/PageHeader.vue'

definePageMeta({ middleware: 'auth' })

const api = useApi()

const logs = ref<any[]>([])
const loading = ref(false)
const selectedModule = ref('')
const selectedAction = ref('')
const searchQuery = ref('')
const page = ref(1)
const pageSize = ref(20)

async function loadLogs() {
  loading.value = true
  try {
    let url = '/audit-logs?limit=1000&'
    if (selectedModule.value) url += `module=${encodeURIComponent(selectedModule.value)}&`
    if (selectedAction.value) url += `action=${encodeURIComponent(selectedAction.value)}&`
    logs.value = await api.get<any[]>(url)
    page.value = 1
  } catch (err) {
    console.error('Failed to load audit logs', err)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadLogs()
})

const filteredLogs = computed(() => {
  if (!searchQuery.value) return logs.value
  const q = searchQuery.value.toLowerCase()
  return logs.value.filter(l => `${l.user_email} ${l.action} ${l.module} ${l.entity_code} ${l.details}`.toLowerCase().includes(q))
})

const paginatedLogs = computed(() => {
  const start = (page.value - 1) * pageSize.value
  return filteredLogs.value.slice(start, start + pageSize.value)
})

const totalPages = computed(() => Math.max(1, Math.ceil(filteredLogs.value.length / pageSize.value)))

async function exportLogs(format: 'xlsx' | 'csv') {
  try {
    let url = `/audit-logs/export?format=${format}&`
    if (selectedModule.value) url += `module=${encodeURIComponent(selectedModule.value)}&`
    if (selectedAction.value) url += `action=${encodeURIComponent(selectedAction.value)}&`

    const blob = await api.download(url)
    const blobUrl = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = blobUrl
    a.download = `audit_logs_export.${format}`
    a.click()
    window.URL.revokeObjectURL(blobUrl)
    loadLogs()
  } catch (err: any) {
    alert(err.message || 'Export failed')
  }
}

function printLogs() {
  window.print()
}
</script>

<template>
  <div class="audit-logs-page p-4 max-w-[1600px] mx-auto">
    <PageHeader
      title="System Audit Log"
      description="Comprehensive audit trail recording every CREATE, UPDATE, SOFT_DELETE, RESTORE, PERMANENT_DELETE, BULK_IMPORT, EXPORT across all modules including Vendors/Suppliers and PO/SO."
    />

    <div class="bg-surface-0 dark:bg-surface-900 rounded-lg shadow-sm border border-surface-200 dark:border-surface-700 p-4">
      <!-- Toolbar & Filters -->
      <div class="flex flex-wrap items-center justify-between gap-3 mb-3">
        <div class="flex items-center gap-2 flex-wrap">
          <InputText v-model="selectedModule" placeholder="Filter module..." class="text-xs w-36 h-8" />
          <InputText v-model="selectedAction" placeholder="Filter action..." class="text-xs w-32 h-8" />
          <InputText v-model="searchQuery" placeholder="Search logs..." class="text-xs w-48 h-8" />
          <Button label="Search" icon="pi pi-search" size="small" severity="secondary" outlined class="!text-xs" @click="loadLogs" />
          <Button label="Refresh" icon="pi pi-refresh" size="small" severity="secondary" outlined class="!text-xs" @click="loadLogs" />
          <span class="text-[11px] text-surface-500 ml-2">{{ filteredLogs.length }} logs</span>
        </div>
        <div class="flex items-center gap-1.5">
          <Button label="XLSX" icon="pi pi-file-excel" size="small" severity="success" outlined class="!text-xs" @click="exportLogs('xlsx')" />
          <Button label="CSV" icon="pi pi-file" size="small" severity="help" outlined class="!text-xs" @click="exportLogs('csv')" />
          <Button label="Print" icon="pi pi-print" size="small" severity="secondary" outlined class="!text-xs" @click="printLogs" />
          <select v-model="pageSize" class="text-xs border rounded px-2 h-8 bg-surface-0 dark:bg-surface-900">
            <option :value="10">10</option>
            <option :value="20">20</option>
            <option :value="50">50</option>
            <option :value="100">100</option>
          </select>
        </div>
      </div>

      <!-- Compact Table -->
      <div class="overflow-x-auto border border-surface-200 dark:border-surface-700 rounded-md max-h-[70vh] overflow-y-auto">
        <table class="w-full text-left border-collapse text-[11px]">
          <thead class="sticky top-0 z-10">
            <tr class="bg-surface-100 dark:bg-surface-800 text-surface-700 dark:text-surface-300 font-semibold border-b">
              <th class="p-2 w-12">ID</th>
              <th class="p-2">Timestamp</th>
              <th class="p-2">User</th>
              <th class="p-2">Action</th>
              <th class="p-2">Module</th>
              <th class="p-2">Entity Code</th>
              <th class="p-2">Details</th>
              <th class="p-2">IP</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="loading"><td colspan="8" class="p-6 text-center text-surface-500 text-xs"><i class="pi pi-spin pi-spinner"/> Loading audit logs...</td></tr>
            <tr v-else-if="paginatedLogs.length === 0"><td colspan="8" class="p-6 text-center text-surface-500 text-xs">No audit logs found. Actions will appear here.</td></tr>
            <tr v-for="log in paginatedLogs" :key="log.id" class="border-b border-surface-100 dark:border-surface-800 hover:bg-surface-50 dark:hover:bg-surface-800/50 text-xs">
              <td class="p-1.5 font-mono text-[10px] text-surface-400">#{{ log.id }}</td>
              <td class="p-1.5 whitespace-nowrap text-[11px]">{{ new Date(log.timestamp).toLocaleString() }}</td>
              <td class="p-1.5 font-medium text-[11px] max-w-[120px] truncate" :title="log.user_email">{{ log.user_email }}</td>
              <td class="p-1.5">
                <span
class="px-1.5 py-0.5 rounded text-[10px] font-semibold"
                  :class="{
                    'bg-green-100 text-green-800': log.action === 'CREATE',
                    'bg-blue-100 text-blue-800': log.action === 'UPDATE',
                    'bg-amber-100 text-amber-800': log.action === 'SOFT_DELETE',
                    'bg-red-100 text-red-800': log.action === 'PERMANENT_DELETE',
                    'bg-purple-100 text-purple-800': log.action === 'RESTORE' || log.action === 'BULK_IMPORT',
                    'bg-surface-200 text-surface-800': log.action === 'EXPORT'
                  }"
                >{{ log.action }}</span>
              </td>
              <td class="p-1.5 font-medium text-primary text-[11px] max-w-[140px] truncate" :title="log.module">{{ log.module }}</td>
              <td class="p-1.5 font-mono text-[11px]">{{ log.entity_code || '—' }}</td>
              <td class="p-1.5 text-surface-600 dark:text-surface-400 max-w-[260px] truncate text-[11px]" :title="log.details">{{ log.details || '—' }}</td>
              <td class="p-1.5 font-mono text-[10px] text-surface-500">{{ log.ip_address || '—' }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <div class="flex items-center justify-between mt-3 text-xs">
        <span class="text-surface-500">Page {{ page }} of {{ totalPages }} — {{ filteredLogs.length }} total (showing {{ paginatedLogs.length }})</span>
        <div class="flex gap-1">
          <Button label="Prev" size="small" severity="secondary" outlined :disabled="page <= 1" class="!text-xs" @click="page--" />
          <Button label="Next" size="small" severity="secondary" outlined :disabled="page >= totalPages" class="!text-xs" @click="page++" />
        </div>
      </div>
      <div class="mt-3 p-2 bg-surface-50 dark:bg-surface-800 rounded text-[11px] text-surface-600">
        <strong>Audit Coverage:</strong> All actions from now are audited — CREATE, UPDATE, SOFT_DELETE (moves to Deleted Entries tab), RESTORE, PERMANENT_DELETE, BULK_IMPORT, EXPORT. Includes Vendors/Suppliers and PO/SO with attachment upload tracking. Common template: Export (XLSX/CSV) and Print available on every page.
      </div>
    </div>
  </div>
</template>

<style scoped>
@media print {
  .audit-logs-page button, .audit-logs-page input, .audit-logs-page select { display: none !important; }
  .audit-logs-page .overflow-x-auto { overflow: visible !important; max-height: none !important; }
}
</style>
