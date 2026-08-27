<script setup lang="ts">
/**
 * Master Data Management Page — UOM, Currency, Phases, Activities, Hole Sections, and Deleted Entries.
 * Follows old excel-like entry format, compact tables minimizing scrolling,
 * Import/Export (XLSX/CSV), Print, Edit, Soft Delete, Restore, Permanent Delete, and Audit logging.
 */
import { ref, computed, onMounted } from 'vue'
import PageHeader from '~/components/design-system/PageHeader.vue'

definePageMeta({ middleware: 'auth' })

const api = useApi()

// Active tab index: 0=UOM, 1=Currency, 2=Phases, 3=Activities, 4=Hole Sections, 5=Deleted Entries
const activeTab = ref(0)

const modules = [
  { key: 'uom', label: 'Unit of Measurements (UOM)', codeField: 'unit_code', nameField: 'unit_name', symbolField: 'unit_symbol' },
  { key: 'currencies', label: 'Currency', codeField: 'currency_code', nameField: 'currency_name', symbolField: 'currency_symbol' },
  { key: 'phases', label: 'Phases', codeField: 'phase_code', nameField: 'phase_name', symbolField: null },
  { key: 'activities', label: 'Activities', codeField: 'activity_code', nameField: 'activity_name', symbolField: null },
  { key: 'hole-sections', label: 'Hole Sections', codeField: 'section_code', nameField: 'section_name', symbolField: null },
]

const currentModule = computed(() => {
  if (activeTab.value >= 0 && activeTab.value < modules.length) {
    return modules[activeTab.value]
  }
  return null
})

const records = ref<any[]>([])
const deletedRecords = ref<any[]>([])
const loading = ref(false)
const searchQuery = ref('')

// Dialog state
const showDialog = ref(false)
const isEditing = ref(false)
const editId = ref<number | null>(null)
const formData = ref({
  code: '',
  name: '',
  symbol: '',
  description: '',
})

// Bulk Import dialog state
const showImportDialog = ref(false)
const importFile = ref<File | null>(null)
const importResult = ref<any>(null)
const importing = ref(false)

async function loadData() {
  if (!currentModule.value) return
  loading.value = true
  try {
    const modKey = currentModule.value.key
    const [activeRes, deletedRes] = await Promise.all([
      api.get<any[]>(`/master-data/${modKey}`),
      api.get<any[]>(`/master-data/${modKey}/deleted`),
    ])
    records.value = activeRes
    deletedRecords.value = deletedRes
  } catch (err: any) {
    console.error('Failed to load master data', err)
  } finally {
    loading.value = false
  }
}

// Watch tab change
import { watch } from 'vue'
watch(activeTab, () => {
  searchQuery.value = ''
  if (activeTab.value < modules.length) {
    loadData()
  } else {
    loadAllDeleted()
  }
})

const allDeletedRecords = ref<any[]>([])
async function loadAllDeleted() {
  loading.value = true
  try {
    const results = await Promise.all(
      modules.map(async m => {
        const res = await api.get<any[]>(`/master-data/${m.key}/deleted`)
        return res.map(r => ({ ...r, moduleKey: m.key, moduleName: m.label }))
      })
    )
    allDeletedRecords.value = results.flat()
  } catch (err) {
    console.error('Failed to load deleted entries', err)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadData()
})

const filteredRecords = computed(() => {
  if (!searchQuery.value) return records.value
  const q = searchQuery.value.toLowerCase()
  const mod = currentModule.value
  if (!mod) return records.value
  return records.value.filter(r => {
    const code = String(r[mod.codeField] || '').toLowerCase()
    const name = String(r[mod.nameField] || '').toLowerCase()
    const desc = String(r.description || '').toLowerCase()
    return code.includes(q) || name.includes(q) || desc.includes(q)
  })
})

function openAddDialog() {
  isEditing.value = false
  editId.value = null
  formData.value = { code: '', name: '', symbol: '', description: '' }
  showDialog.value = true
}

function openEditDialog(item: any) {
  isEditing.value = true
  editId.value = item.id
  const mod = currentModule.value
  if (!mod) return
  formData.value = {
    code: item[mod.codeField] || '',
    name: item[mod.nameField] || '',
    symbol: mod.symbolField ? item[mod.symbolField] || '' : '',
    description: item.description || '',
  }
  showDialog.value = true
}

async function saveRecord() {
  const mod = currentModule.value
  if (!mod) return
  const payload: any = {
    [mod.codeField]: formData.value.code,
    [mod.nameField]: formData.value.name,
    description: formData.value.description || null,
  }
  if (mod.symbolField) {
    payload[mod.symbolField] = formData.value.symbol
  }

  try {
    if (isEditing.value && editId.value) {
      await api.put(`/master-data/${mod.key}/${editId.value}`, payload)
    } else {
      await api.post(`/master-data/${mod.key}`, payload)
    }
    showDialog.value = false
    loadData()
  } catch (err: any) {
    alert(err.message || 'Failed to save record')
  }
}

async function softDelete(item: any) {
  const mod = currentModule.value
  if (!mod) return
  if (!confirm(`Move "${item[mod.nameField]}" to deleted entries?`)) return
  try {
    await api.delete(`/master-data/${mod.key}/${item.id}`)
    loadData()
  } catch (err: any) {
    alert(err.message || 'Failed to delete record')
  }
}

async function restoreRecord(item: any, modKey?: string) {
  const mKey = modKey || currentModule.value?.key
  if (!mKey) return
  try {
    await api.post(`/master-data/${mKey}/${item.id}/restore`, {})
    if (activeTab.value === modules.length) {
      loadAllDeleted()
    } else {
      loadData()
    }
  } catch (err: any) {
    alert(err.message || 'Failed to restore record')
  }
}

async function permanentDelete(item: any, modKey?: string) {
  const mKey = modKey || currentModule.value?.key
  if (!mKey) return
  if (!confirm('Permanently delete this entry? This action cannot be undone.')) return
  try {
    await api.delete(`/master-data/${mKey}/${item.id}/permanent`)
    if (activeTab.value === modules.length) {
      loadAllDeleted()
    } else {
      loadData()
    }
  } catch (err: any) {
    alert(err.message || 'Failed to permanently delete record')
  }
}

// Export / Import / Print
async function exportData(format: 'xlsx' | 'csv') {
  const mod = currentModule.value
  if (!mod) return
  try {
    const blob = await api.download(`/master-data/${mod.key}/export?format=${format}`)
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${mod.key}_export.${format}`
    a.click()
    window.URL.revokeObjectURL(url)
  } catch (err: any) {
    alert(err.message || 'Export failed')
  }
}

function printTable() {
  window.print()
}

function handleFileSelect(event: any) {
  const file = event.target.files?.[0]
  if (file) {
    importFile.value = file
  }
}

async function executeImport() {
  if (!importFile.value || !currentModule.value) return
  importing.value = true
  importResult.value = null
  const formDataObj = new FormData()
  formDataObj.append('file', importFile.value)

  try {
    const res = await api.postForm<any>(`/master-data/${currentModule.value.key}/import`, formDataObj)
    importResult.value = res
    loadData()
  } catch (err: any) {
    alert(err.message || 'Import failed')
  } finally {
    importing.value = false
  }
}

function downloadTemplate() {
  const mod = currentModule.value
  if (!mod) return
  const headers = mod.symbolField ? `${mod.codeField},${mod.nameField},${mod.symbolField},description\n` : `${mod.codeField},${mod.nameField},description\n`
  const sample = mod.symbolField ? `CODE1,Sample Name,SYM,Sample description\n` : `CODE1,Sample Name,Sample description\n`
  const blob = new Blob([headers + sample], { type: 'text/csv' })
  const url = window.URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `${mod.key}_template.csv`
  a.click()
  window.URL.revokeObjectURL(url)
}
</script>

<template>
  <div class="master-data-page p-6 max-w-7xl mx-auto">
    <PageHeader
      title="Master Data Configuration"
      description="Configure Unit of Measurements, Currencies, Phases, Activities, and Hole Sections with Excel-like entry and audit logging."
    />

    <!-- Tabs Header -->
    <div class="flex border-b border-surface-200 dark:border-surface-700 mb-6 overflow-x-auto">
      <button
        v-for="(mod, index) in modules"
        :key="mod.key"
        @click="activeTab = index"
        class="px-5 py-3 font-medium text-sm border-b-2 whitespace-nowrap transition-colors"
        :class="activeTab === index ? 'border-primary text-primary font-semibold' : 'border-transparent text-surface-600 dark:text-surface-400 hover:text-surface-900'"
      >
        {{ mod.label }}
      </button>
      <button
        @click="activeTab = modules.length; loadAllDeleted()"
        class="px-5 py-3 font-medium text-sm border-b-2 whitespace-nowrap transition-colors text-red-600 dark:text-red-400"
        :class="activeTab === modules.length ? 'border-red-600 font-semibold' : 'border-transparent hover:text-red-700'"
      >
        <i class="pi pi-trash mr-1"></i> Deleted Entries
      </button>
    </div>

    <!-- Active Module View -->
    <div v-if="activeTab < modules.length && currentModule" class="bg-surface-0 dark:bg-surface-900 rounded-xl shadow-sm border border-surface-200 dark:border-surface-700 p-5">
      <!-- Toolbar -->
      <div class="flex flex-wrap items-center justify-between gap-4 mb-4">
        <div class="flex items-center gap-2">
          <Button label="Add Entry" icon="pi pi-plus" size="small" severity="primary" @click="openAddDialog" />
          <Button label="Import Bulk" icon="pi pi-upload" size="small" severity="secondary" outlined @click="showImportDialog = true" />
          <Button label="Export XLSX" icon="pi pi-file-excel" size="small" severity="success" outlined @click="exportData('xlsx')" />
          <Button label="Export CSV" icon="pi pi-file" size="small" severity="help" outlined @click="exportData('csv')" />
          <Button label="Print" icon="pi pi-print" size="small" severity="secondary" outlined @click="printTable" />
        </div>
        <div class="w-full sm:w-72">
          <span class="p-input-icon-left w-full">
            <InputText v-model="searchQuery" placeholder="Search records..." class="w-full text-sm" />
          </span>
        </div>
      </div>

      <!-- Compact Excel-like DataTable -->
      <div class="overflow-x-auto border border-surface-200 dark:border-surface-700 rounded-lg">
        <table class="w-full text-left border-collapse text-sm">
          <thead>
            <tr class="bg-surface-100 dark:bg-surface-800 text-surface-700 dark:text-surface-300 font-semibold border-b border-surface-200 dark:border-surface-700">
              <th class="p-3 w-16">ID</th>
              <th class="p-3 uppercase text-xs">Code</th>
              <th class="p-3 uppercase text-xs">Name</th>
              <th v-if="currentModule.symbolField" class="p-3 uppercase text-xs">Symbol</th>
              <th class="p-3 uppercase text-xs">Description</th>
              <th class="p-3 text-right uppercase text-xs w-32">Actions</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="loading">
              <td :colspan="currentModule.symbolField ? 6 : 5" class="p-8 text-center text-surface-500">
                <i class="pi pi-spin pi-spinner text-2xl"></i> Loading records...
              </td>
            </tr>
            <tr v-else-if="filteredRecords.length === 0">
              <td :colspan="currentModule.symbolField ? 6 : 5" class="p-8 text-center text-surface-500">
                No records found. Click "Add Entry" or "Import Bulk" to populate data.
              </td>
            </tr>
            <tr
              v-for="item in filteredRecords"
              :key="item.id"
              class="border-b border-surface-100 dark:border-surface-800 hover:bg-surface-50 dark:hover:bg-surface-800/50 transition-colors"
            >
              <td class="p-3 font-mono text-xs text-surface-500">#{{ item.id }}</td>
              <td class="p-3 font-medium font-mono text-primary">{{ item[currentModule.codeField] }}</td>
              <td class="p-3">{{ item[currentModule.nameField] }}</td>
              <td v-if="currentModule.symbolField" class="p-3 font-semibold">{{ item[currentModule.symbolField] }}</td>
              <td class="p-3 text-surface-600 dark:text-surface-400 text-xs">{{ item.description || '—' }}</td>
              <td class="p-3 text-right space-x-2">
                <button
                  @click="openEditDialog(item)"
                  class="p-1 text-surface-600 hover:text-primary transition-colors"
                  title="Edit"
                >
                  <i class="pi pi-pencil"></i>
                </button>
                <button
                  @click="softDelete(item)"
                  class="p-1 text-red-500 hover:text-red-700 transition-colors"
                  title="Delete (Soft Delete)"
                >
                  <i class="pi pi-trash"></i>
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Deleted Entries View -->
    <div v-else class="bg-surface-0 dark:bg-surface-900 rounded-xl shadow-sm border border-surface-200 dark:border-surface-700 p-5">
      <div class="flex items-center justify-between mb-4">
        <h3 class="text-lg font-semibold text-surface-800 dark:text-surface-100">Deleted Entries (Trash)</h3>
        <span class="text-xs text-surface-500">Items here can be restored or permanently deleted.</span>
      </div>

      <div class="overflow-x-auto border border-surface-200 dark:border-surface-700 rounded-lg">
        <table class="w-full text-left border-collapse text-sm">
          <thead>
            <tr class="bg-surface-100 dark:bg-surface-800 text-surface-700 dark:text-surface-300 font-semibold border-b border-surface-200 dark:border-surface-700">
              <th class="p-3">Module</th>
              <th class="p-3">Code</th>
              <th class="p-3">Name</th>
              <th class="p-3">Deleted At</th>
              <th class="p-3 text-right w-40">Actions</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="loading">
              <td colspan="5" class="p-8 text-center text-surface-500">Loading deleted entries...</td>
            </tr>
            <tr v-else-if="allDeletedRecords.length === 0">
              <td colspan="5" class="p-8 text-center text-surface-500">No deleted entries found.</td>
            </tr>
            <tr
              v-for="item in allDeletedRecords"
              :key="item.id + item.moduleKey"
              class="border-b border-surface-100 dark:border-surface-800 hover:bg-surface-50"
            >
              <td class="p-3 font-semibold text-xs text-primary">{{ item.moduleName }}</td>
              <td class="p-3 font-mono font-medium">{{ item.unit_code || item.currency_code || item.phase_code || item.activity_code || item.section_code }}</td>
              <td class="p-3">{{ item.unit_name || item.currency_name || item.phase_name || item.activity_name || item.section_name }}</td>
              <td class="p-3 text-xs text-surface-500">{{ item.deleted_at ? new Date(item.deleted_at).toLocaleString() : '—' }}</td>
              <td class="p-3 text-right space-x-2">
                <Button label="Restore" size="small" severity="success" outlined @click="restoreRecord(item, item.moduleKey)" />
                <Button label="Delete" size="small" severity="danger" outlined @click="permanentDelete(item, item.moduleKey)" />
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Add/Edit Dialog -->
    <Dialog v-model:visible="showDialog" :header="isEditing ? 'Edit Entry' : 'New Entry'" :style="{ width: '30rem' }" modal>
      <div class="space-y-4 pt-2" v-if="currentModule">
        <div>
          <label class="block text-xs font-semibold uppercase mb-1 text-surface-600">Code *</label>
          <InputText v-model="formData.code" class="w-full" placeholder="e.g. USD, M, PHASE1" />
        </div>
        <div>
          <label class="block text-xs font-semibold uppercase mb-1 text-surface-600">Name *</label>
          <InputText v-model="formData.name" class="w-full" placeholder="e.g. US Dollar, Meter" />
        </div>
        <div v-if="currentModule.symbolField">
          <label class="block text-xs font-semibold uppercase mb-1 text-surface-600">Symbol *</label>
          <InputText v-model="formData.symbol" class="w-full" placeholder="e.g. $, m" />
        </div>
        <div>
          <label class="block text-xs font-semibold uppercase mb-1 text-surface-600">Description</label>
          <Textarea v-model="formData.description" rows="3" class="w-full" placeholder="Optional description..." />
        </div>
      </div>
      <template #footer>
        <Button label="Cancel" severity="secondary" text @click="showDialog = false" />
        <Button :label="isEditing ? 'Update' : 'Create'" severity="primary" @click="saveRecord" />
      </template>
    </Dialog>

    <!-- Bulk Import Dialog -->
    <Dialog v-model:visible="showImportDialog" header="Bulk Import Data (CSV / XLSX)" :style="{ width: '35rem' }" modal>
      <div class="space-y-4 pt-2">
        <p class="text-sm text-surface-600 dark:text-surface-400">
          Upload a CSV or Excel file containing your master data. Make sure the first row contains column headers matching your fields.
        </p>
        <div class="flex items-center justify-between">
          <Button label="Download CSV Template" icon="pi pi-download" size="small" severity="secondary" outlined @click="downloadTemplate" />
        </div>
        <div class="border-2 border-dashed border-surface-300 dark:border-surface-700 rounded-lg p-6 text-center">
          <input type="file" accept=".csv, .xlsx, .xls" @change="handleFileSelect" class="block w-full text-sm text-surface-500 file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-sm file:font-semibold file:bg-primary/10 file:text-primary hover:file:bg-primary/20" />
        </div>

        <div v-if="importing" class="text-center py-4">
          <i class="pi pi-spin pi-spinner text-xl text-primary"></i> Importing records...
        </div>

        <div v-if="importResult" class="p-4 rounded-lg bg-surface-100 dark:bg-surface-800 text-sm space-y-2">
          <div class="font-semibold">Import Summary:</div>
          <div class="text-success-600">Successfully imported: {{ importResult.imported_count }} records</div>
          <div v-if="importResult.error_count > 0" class="text-red-500">
            Errors encountered: {{ importResult.error_count }}
            <ul class="list-disc pl-5 mt-1 text-xs">
              <li v-for="(err, idx) in importResult.errors" :key="idx">{{ err }}</li>
            </ul>
          </div>
        </div>
      </div>
      <template #footer>
        <Button label="Close" severity="secondary" text @click="showImportDialog = false" />
        <Button label="Upload & Import" severity="primary" :loading="importing" @click="executeImport" />
      </template>
    </Dialog>
  </div>
</template>
