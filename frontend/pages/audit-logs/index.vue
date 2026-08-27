<script setup lang="ts">
/**
 * Audit Log Page — Track all system operations, with module/action filters,
 * Excel/CSV export, and print capabilities.
 */
import { ref, onMounted } from 'vue'
import PageHeader from '~/components/design-system/PageHeader.vue'

definePageMeta({ middleware: 'auth' })

const api = useApi()

const logs = ref<any[]>([])
const loading = ref(false)
const selectedModule = ref('')
const selectedAction = ref('')

async function loadLogs() {
  loading.value = true
  try {
    let url = '/audit-logs?'
    if (selectedModule.value) url += `module=${encodeURIComponent(selectedModule.value)}&`
    if (selectedAction.value) url += `action=${encodeURIComponent(selectedAction.value)}&`
    logs.value = await api.get<any[]>(url)
  } catch (err) {
    console.error('Failed to load audit logs', err)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadLogs()
})

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
    loadLogs() // refresh logs after export audit
  } catch (err: any) {
    alert(err.message || 'Export failed')
  }
}

function printLogs() {
  window.print()
}
</script>

<template>
  <div class="audit-logs-page p-6 max-w-7xl mx-auto">
    <PageHeader
      title="System Audit Log"
      description="Comprehensive audit trail recording every creation, update, deletion, import, export, and print action across the application."
    />

    <div class="bg-surface-0 dark:bg-surface-900 rounded-xl shadow-sm border border-surface-200 dark:border-surface-700 p-5">
      <!-- Toolbar & Filters -->
      <div class="flex flex-wrap items-center justify-between gap-4 mb-4">
        <div class="flex items-center gap-3">
          <InputText v-model="selectedModule" placeholder="Filter by module..." class="text-sm w-48" @input="loadLogs" />
          <InputText v-model="selectedAction" placeholder="Filter by action..." class="text-sm w-48" @input="loadLogs" />
          <Button label="Refresh" icon="pi pi-refresh" size="small" severity="secondary" outlined @click="loadLogs" />
        </div>
        <div class="flex items-center gap-2">
          <Button label="Export XLSX" icon="pi pi-file-excel" size="small" severity="success" outlined @click="exportLogs('xlsx')" />
          <Button label="Export CSV" icon="pi pi-file" size="small" severity="help" outlined @click="exportLogs('csv')" />
          <Button label="Print" icon="pi pi-print" size="small" severity="secondary" outlined @click="printLogs" />
        </div>
      </div>

      <!-- Compact Table -->
      <div class="overflow-x-auto border border-surface-200 dark:border-surface-700 rounded-lg">
        <table class="w-full text-left border-collapse text-xs">
          <thead>
            <tr class="bg-surface-100 dark:bg-surface-800 text-surface-700 dark:text-surface-300 font-semibold border-b border-surface-200 dark:border-surface-700">
              <th class="p-3 w-16">ID</th>
              <th class="p-3">Timestamp</th>
              <th class="p-3">User</th>
              <th class="p-3">Action</th>
              <th class="p-3">Module</th>
              <th class="p-3">Entity Code</th>
              <th class="p-3">Details</th>
              <th class="p-3">IP Address</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="loading">
              <td colspan="8" class="p-8 text-center text-surface-500">
                <i class="pi pi-spin pi-spinner text-xl"></i> Loading audit logs...
              </td>
            </tr>
            <tr v-else-if="logs.length === 0">
              <td colspan="8" class="p-8 text-center text-surface-500">
                No audit logs recorded yet.
              </td>
            </tr>
            <tr
              v-for="log in logs"
              :key="log.id"
              class="border-b border-surface-100 dark:border-surface-800 hover:bg-surface-50 dark:hover:bg-surface-800/50"
            >
              <td class="p-3 font-mono text-surface-400">#{{ log.id }}</td>
              <td class="p-3 whitespace-nowrap">{{ new Date(log.timestamp).toLocaleString() }}</td>
              <td class="p-3 font-medium">{{ log.user_email }}</td>
              <td class="p-3 font-semibold">
                <span
                  class="px-2 py-0.5 rounded text-[10px]"
                  :class="{
                    'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300': log.action === 'CREATE',
                    'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300': log.action === 'UPDATE',
                    'bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-300': log.action === 'SOFT_DELETE' || log.action === 'PERMANENT_DELETE',
                    'bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-300': log.action === 'RESTORE' || log.action === 'BULK_IMPORT',
                    'bg-surface-200 text-surface-800 dark:bg-surface-700 dark:text-surface-300': log.action === 'EXPORT' || log.action === 'PRINT'
                  }"
                >
                  {{ log.action }}
                </span>
              </td>
              <td class="p-3 font-medium text-primary">{{ log.module }}</td>
              <td class="p-3 font-mono">{{ log.entity_code || '—' }}</td>
              <td class="p-3 text-surface-600 dark:text-surface-400 max-w-xs truncate" :title="log.details">{{ log.details || '—' }}</td>
              <td class="p-3 font-mono text-surface-500 text-[11px]">{{ log.ip_address || '—' }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>
