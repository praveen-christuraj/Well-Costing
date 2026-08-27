<script setup lang="ts">
/**
 * Master Data Management Page — UOM, Currency, Phases, Activities, Hole Sections,
 * Vendors/Suppliers, Purchase Orders/Service Orders, and Deleted Entries.
 * Common template: Import, Export (xlsx/csv), Print, View/Edit/Delete, Soft Delete -> Trash, Audit.
 * Compact tables minimizing scrolling, bulk import with flexible date validation.
 */
import { ref, computed, onMounted, watch } from 'vue'
import PageHeader from '~/components/design-system/PageHeader.vue'

definePageMeta({ middleware: 'auth' })

const api = useApi()

// Tabs: 0-4 generic, 5 vendors, 6 PO/SO, 7 deleted
const activeTab = ref(0)

const modules = [
  { key: 'uom', label: 'UOM', fullLabel: 'Unit of Measurements (UOM)', codeField: 'unit_code', nameField: 'unit_name', symbolField: 'unit_symbol' },
  { key: 'currencies', label: 'Currency', fullLabel: 'Currency', codeField: 'currency_code', nameField: 'currency_name', symbolField: 'currency_symbol' },
  { key: 'phases', label: 'Phases', fullLabel: 'Phases', codeField: 'phase_code', nameField: 'phase_name', symbolField: null },
  { key: 'activities', label: 'Activities', fullLabel: 'Activities', codeField: 'activity_code', nameField: 'activity_name', symbolField: null },
  { key: 'hole-sections', label: 'Hole Sections', fullLabel: 'Hole Sections', codeField: 'section_code', nameField: 'section_name', symbolField: null },
]

const currentModule = computed(() => {
  if (activeTab.value >= 0 && activeTab.value < modules.length) {
    return modules[activeTab.value]
  }
  return null
})

const records = ref<any[]>([])
const loading = ref(false)
const searchQuery = ref('')
const pageSize = ref(15)
const currentPage = ref(1)

// Generic dialog
const showDialog = ref(false)
const isEditing = ref(false)
const editId = ref<number | null>(null)
const formData = ref({ code: '', name: '', symbol: '', description: '' })

// Generic import
const showImportDialog = ref(false)
const importFile = ref<File | null>(null)
const importResult = ref<any>(null)
const importing = ref(false)

// Vendors state
const vendorRecords = ref<any[]>([])
const vendorLoading = ref(false)
const vendorSearch = ref('')
const vendorPage = ref(1)
const vendorPageSize = ref(15)
const showVendorDialog = ref(false)
const isEditingVendor = ref(false)
const editVendorId = ref<number | null>(null)
const vendorForm = ref({ vendor_code: '', vendor_name: '', contact: '', description: '' })
const showVendorImport = ref(false)
const vendorImportFile = ref<File | null>(null)
const vendorImportResult = ref<any>(null)
const vendorImporting = ref(false)
const showVendorView = ref(false)
const vendorViewData = ref<any>(null)

// PO/SO state
const poRecords = ref<any[]>([])
const poLoading = ref(false)
const poSearch = ref('')
const poPage = ref(1)
const poPageSize = ref(12)
const poTypeFilter = ref('')
const showPODialog = ref(false)
const isEditingPO = ref(false)
const editPOId = ref<number | null>(null)
const poForm = ref({
  po_type: 'PO' as 'PO' | 'SO' | 'Callout' | 'Others',
  vendor_id: null as number | null,
  po_so_number: '',
  effective_date: '',
  value: '' as any,
  is_amendment: false,
  amendment_number: null as number | null,
  remarks: '',
})
const vendorsDropdown = ref<any[]>([])
const poAttachmentFile = ref<File | null>(null)
const showPOView = ref(false)
const poViewData = ref<any>(null)
const showPOImport = ref(false)
const poImportFile = ref<File | null>(null)
const poImportResult = ref<any>(null)
const poImporting = ref(false)
const showBulkAttachDialog = ref(false)
const bulkAttachFiles = ref<FileList | null>(null)
const bulkAttachResult = ref<any>(null)
const bulkAttachUploading = ref(false)

// Deleted
const allDeletedRecords = ref<any[]>([])

async function loadVendorsDropdown() {
  try {
    vendorsDropdown.value = await api.get<any[]>('/master-data/vendors/dropdown')
  } catch (e) {
    console.error('Failed vendors dropdown', e)
  }
}

async function loadData() {
  if (!currentModule.value) return
  loading.value = true
  try {
    const modKey = currentModule.value.key
    const res = await api.get<any[]>(`/master-data/${modKey}`)
    records.value = res
    currentPage.value = 1
  } catch (err: any) {
    console.error('Failed to load master data', err)
  } finally {
    loading.value = false
  }
}

async function loadVendors() {
  vendorLoading.value = true
  try {
    const res = await api.get<any[]>('/master-data/vendors')
    vendorRecords.value = res
    vendorPage.value = 1
  } catch (e) {
    console.error('Failed vendors', e)
  } finally {
    vendorLoading.value = false
  }
}

async function loadPO() {
  poLoading.value = true
  try {
    const res = await api.get<any[]>('/master-data/purchase-orders')
    poRecords.value = res
    poPage.value = 1
    await loadVendorsDropdown()
  } catch (e) {
    console.error('Failed PO', e)
  } finally {
    poLoading.value = false
  }
}

async function loadAllDeleted() {
  loading.value = true
  vendorLoading.value = true
  poLoading.value = true
  try {
    const genericPromises = modules.map(async m => {
      try {
        const res = await api.get<any[]>(`/master-data/${m.key}/deleted`)
        return res.map(r => ({ ...r, moduleKey: m.key, moduleName: m.fullLabel, code: r[m.codeField], name: r[m.nameField] }))
      } catch { return [] }
    })
    const vendorDeleted = api.get<any[]>('/master-data/vendors/deleted').then(res => res.map(r => ({ ...r, moduleKey: 'vendors', moduleName: 'Vendors/Suppliers', code: r.vendor_code, name: r.vendor_name }))).catch(() => [])
    const poDeleted = api.get<any[]>('/master-data/purchase-orders/deleted').then(res => res.map(r => ({ ...r, moduleKey: 'purchase-orders', moduleName: 'Purchase Orders/Service Orders', code: r.po_so_number, name: `${r.po_type} - ${r.vendor_display || r.vendor_code}` }))).catch(() => [])
    const results = await Promise.all([...genericPromises, vendorDeleted, poDeleted])
    allDeletedRecords.value = results.flat().sort((a, b) => new Date(b.deleted_at || 0).getTime() - new Date(a.deleted_at || 0).getTime())
  } catch (err) {
    console.error('Failed deleted', err)
  } finally {
    loading.value = false
    vendorLoading.value = false
    poLoading.value = false
  }
}

watch(activeTab, () => {
  searchQuery.value = ''
  vendorSearch.value = ''
  poSearch.value = ''
  if (activeTab.value < modules.length) {
    loadData()
  } else if (activeTab.value === 5) {
    loadVendors()
    loadVendorsDropdown()
  } else if (activeTab.value === 6) {
    loadPO()
  } else {
    loadAllDeleted()
  }
})

onMounted(() => {
  loadData()
  loadVendorsDropdown()
})

// Generic filtered + paginated
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
const paginatedRecords = computed(() => {
  const start = (currentPage.value - 1) * pageSize.value
  return filteredRecords.value.slice(start, start + pageSize.value)
})
const totalPages = computed(() => Math.max(1, Math.ceil(filteredRecords.value.length / pageSize.value)))

// Vendors filtered
const filteredVendors = computed(() => {
  if (!vendorSearch.value) return vendorRecords.value
  const q = vendorSearch.value.toLowerCase()
  return vendorRecords.value.filter(r => `${r.vendor_code} ${r.vendor_name} ${r.contact} ${r.description}`.toLowerCase().includes(q))
})
const paginatedVendors = computed(() => {
  const start = (vendorPage.value - 1) * vendorPageSize.value
  return filteredVendors.value.slice(start, start + vendorPageSize.value)
})
const vendorTotalPages = computed(() => Math.max(1, Math.ceil(filteredVendors.value.length / vendorPageSize.value)))

// PO filtered
const filteredPO = computed(() => {
  let list = poRecords.value
  if (poSearch.value) {
    const q = poSearch.value.toLowerCase()
    list = list.filter(r => `${r.po_so_number} ${r.vendor_code} ${r.vendor_name} ${r.vendor_display} ${r.remarks} ${r.po_type}`.toLowerCase().includes(q))
  }
  if (poTypeFilter.value) {
    list = list.filter(r => r.po_type === poTypeFilter.value)
  }
  return list
})
const paginatedPO = computed(() => {
  const start = (poPage.value - 1) * poPageSize.value
  return filteredPO.value.slice(start, start + poPageSize.value)
})
const poTotalPages = computed(() => Math.max(1, Math.ceil(filteredPO.value.length / poPageSize.value)))

// Generic CRUD
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
  if (!formData.value.code || !formData.value.name) {
    alert('Code and Name are mandatory')
    return
  }
  const payload: any = {
    [mod.codeField]: formData.value.code,
    [mod.nameField]: formData.value.name,
    description: formData.value.description || null,
  }
  if (mod.symbolField) payload[mod.symbolField] = formData.value.symbol
  try {
    if (isEditing.value && editId.value) {
      await api.put(`/master-data/${mod.key}/${editId.value}`, payload)
    } else {
      await api.post(`/master-data/${mod.key}`, payload)
    }
    showDialog.value = false
    loadData()
  } catch (err: any) {
    alert(err.message || 'Failed to save')
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
    alert(err.message || 'Failed to delete')
  }
}

// Vendors CRUD
function openAddVendor() {
  isEditingVendor.value = false
  editVendorId.value = null
  vendorForm.value = { vendor_code: '', vendor_name: '', contact: '', description: '' }
  showVendorDialog.value = true
}
function openEditVendor(item: any) {
  isEditingVendor.value = true
  editVendorId.value = item.id
  vendorForm.value = {
    vendor_code: item.vendor_code || '',
    vendor_name: item.vendor_name || '',
    contact: item.contact || '',
    description: item.description || '',
  }
  showVendorDialog.value = true
}
function openViewVendor(item: any) {
  vendorViewData.value = item
  showVendorView.value = true
}
async function saveVendor() {
  if (!vendorForm.value.vendor_code || !vendorForm.value.vendor_name) {
    alert('Vendor Code and Name mandatory')
    return
  }
  try {
    if (isEditingVendor.value && editVendorId.value) {
      await api.put(`/master-data/vendors/${editVendorId.value}`, vendorForm.value)
    } else {
      await api.post('/master-data/vendors', vendorForm.value)
    }
    showVendorDialog.value = false
    loadVendors()
    loadVendorsDropdown()
  } catch (err: any) {
    alert(err.message || 'Failed to save vendor')
  }
}
async function softDeleteVendor(item: any) {
  if (!confirm(`Move vendor "${item.vendor_code} - ${item.vendor_name}" to deleted?`)) return
  try {
    await api.delete(`/master-data/vendors/${item.id}`)
    loadVendors()
  } catch (err: any) {
    alert(err.message || 'Failed to delete')
  }
}

// PO CRUD
function openAddPO() {
  isEditingPO.value = false
  editPOId.value = null
  poForm.value = {
    po_type: 'PO',
    vendor_id: null,
    po_so_number: '',
    effective_date: '',
    value: '',
    is_amendment: false,
    amendment_number: null,
    remarks: '',
  }
  poAttachmentFile.value = null
  showPODialog.value = true
  loadVendorsDropdown()
}
function openEditPO(item: any) {
  isEditingPO.value = true
  editPOId.value = item.id
  poForm.value = {
    po_type: item.po_type || 'PO',
    vendor_id: item.vendor_id,
    po_so_number: item.po_so_number || '',
    effective_date: item.effective_date ? item.effective_date.split('T')[0] : '',
    value: item.value || '',
    is_amendment: !!item.is_amendment,
    amendment_number: item.amendment_number || null,
    remarks: item.remarks || '',
  }
  poAttachmentFile.value = null
  showPODialog.value = true
  loadVendorsDropdown()
}
function openViewPO(item: any) {
  poViewData.value = item
  showPOView.value = true
}
async function savePO() {
  if (!poForm.value.po_type) {
    alert('Type mandatory')
    return
  }
  if (!poForm.value.vendor_id) {
    alert('Vendor/Supplier mandatory')
    return
  }
  if (!poForm.value.po_so_number) {
    alert('PO/SO Number mandatory')
    return
  }
  if (poForm.value.is_amendment && !poForm.value.amendment_number) {
    alert('Amendment number mandatory when amendment checked (1-200)')
    return
  }
  const payload: any = {
    po_type: poForm.value.po_type,
    vendor_id: poForm.value.vendor_id,
    po_so_number: poForm.value.po_so_number,
    effective_date: poForm.value.effective_date || null,
    value: poForm.value.value !== '' ? poForm.value.value : null,
    is_amendment: poForm.value.is_amendment,
    amendment_number: poForm.value.is_amendment ? poForm.value.amendment_number : null,
    remarks: poForm.value.remarks || null,
  }
  try {
    let result: any
    if (isEditingPO.value && editPOId.value) {
      result = await api.put(`/master-data/purchase-orders/${editPOId.value}`, payload)
    } else {
      result = await api.post('/master-data/purchase-orders', payload)
    }
    // Handle attachment if selected
    const savedId = result?.id || editPOId.value
    if (poAttachmentFile.value && savedId) {
      const fd = new FormData()
      fd.append('file', poAttachmentFile.value)
      try {
        await api.postForm(`/master-data/purchase-orders/${savedId}/attachment`, fd)
      } catch (e: any) {
        console.warn('Attachment upload failed', e)
        alert('Record saved but attachment upload failed: ' + (e.message || ''))
      }
    }
    showPODialog.value = false
    loadPO()
  } catch (err: any) {
    alert(err.message || 'Failed to save PO/SO')
  }
}
async function softDeletePO(item: any) {
  if (!confirm(`Move PO/SO "${item.po_so_number}" to deleted?`)) return
  try {
    await api.delete(`/master-data/purchase-orders/${item.id}`)
    loadPO()
  } catch (err: any) {
    alert(err.message || 'Failed to delete')
  }
}
async function downloadPOAttachment(item: any) {
  try {
    const blob = await api.download(`/master-data/purchase-orders/${item.id}/attachment`)
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = item.attachment_original_name || `attachment_${item.po_so_number}`
    a.click()
    window.URL.revokeObjectURL(url)
  } catch (err: any) {
    alert(err.message || 'Failed to download attachment')
  }
}

// Deleted handling
async function restoreRecord(item: any, modKey?: string) {
  const mKey = modKey || currentModule.value?.key
  if (!mKey) return
  try {
    if (mKey === 'vendors') {
      await api.post(`/master-data/vendors/${item.id}/restore`, {})
    } else if (mKey === 'purchase-orders') {
      await api.post(`/master-data/purchase-orders/${item.id}/restore`, {})
    } else {
      await api.post(`/master-data/${mKey}/${item.id}/restore`, {})
    }
    loadAllDeleted()
    if (activeTab.value === 5) loadVendors()
    if (activeTab.value === 6) loadPO()
    if (activeTab.value < modules.length) loadData()
  } catch (err: any) {
    alert(err.message || 'Restore failed')
  }
}
async function permanentDelete(item: any, modKey?: string) {
  const mKey = modKey || currentModule.value?.key
  if (!mKey) return
  if (!confirm('Permanently delete? Cannot be undone.')) return
  try {
    if (mKey === 'vendors') {
      await api.delete(`/master-data/vendors/${item.id}/permanent`)
    } else if (mKey === 'purchase-orders') {
      await api.delete(`/master-data/purchase-orders/${item.id}/permanent`)
    } else {
      await api.delete(`/master-data/${mKey}/${item.id}/permanent`)
    }
    loadAllDeleted()
    if (activeTab.value === 5) loadVendors()
    if (activeTab.value === 6) loadPO()
    if (activeTab.value < modules.length) loadData()
  } catch (err: any) {
    alert(err.message || 'Permanent delete failed')
  }
}

// Export / Print
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
async function exportVendors(format: 'xlsx' | 'csv') {
  try {
    const blob = await api.download(`/master-data/vendors/export?format=${format}`)
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `vendors_export.${format}`
    a.click()
    window.URL.revokeObjectURL(url)
  } catch (err: any) {
    alert(err.message || 'Export failed')
  }
}
async function exportPO(format: 'xlsx' | 'csv') {
  try {
    const blob = await api.download(`/master-data/purchase-orders/export?format=${format}`)
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `purchase_orders_export.${format}`
    a.click()
    window.URL.revokeObjectURL(url)
  } catch (err: any) {
    alert(err.message || 'Export failed')
  }
}
function printTable() {
  window.print()
}

// Import handlers
function handleFileSelect(event: any) {
  const file = event.target.files?.[0]
  if (file) importFile.value = file
}
async function executeImport() {
  if (!importFile.value || !currentModule.value) return
  importing.value = true
  importResult.value = null
  const fd = new FormData()
  fd.append('file', importFile.value)
  try {
    const res = await api.postForm<any>(`/master-data/${currentModule.value.key}/import`, fd)
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

// Vendor import
function handleVendorFileSelect(event: any) {
  const file = event.target.files?.[0]
  if (file) vendorImportFile.value = file
}
async function executeVendorImport() {
  if (!vendorImportFile.value) return
  vendorImporting.value = true
  vendorImportResult.value = null
  const fd = new FormData()
  fd.append('file', vendorImportFile.value)
  try {
    const res = await api.postForm<any>('/master-data/vendors/import', fd)
    vendorImportResult.value = res
    loadVendors()
    loadVendorsDropdown()
  } catch (err: any) {
    alert(err.message || 'Import failed')
  } finally {
    vendorImporting.value = false
  }
}
function downloadVendorTemplate() {
  const csv = `vendor_code,vendor_name,contact,description\nVEND001,Acme Drilling Services,+1-555-0100,Primary drilling contractor\nVEND002,Baker Tools Inc,baker@example.com,Tool supplier\n`
  const blob = new Blob([csv], { type: 'text/csv' })
  const url = window.URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = 'vendors_template.csv'
  a.click()
  window.URL.revokeObjectURL(url)
}

// PO import
function handlePOFileSelect(event: any) {
  const file = event.target.files?.[0]
  if (file) poImportFile.value = file
}
async function executePOImport() {
  if (!poImportFile.value) return
  poImporting.value = true
  poImportResult.value = null
  const fd = new FormData()
  fd.append('file', poImportFile.value)
  try {
    const res = await api.postForm<any>('/master-data/purchase-orders/import', fd)
    poImportResult.value = res
    loadPO()
  } catch (err: any) {
    alert(err.message || 'Import failed')
  } finally {
    poImporting.value = false
  }
}
function downloadPOTemplate() {
  const csv = `po_type,vendor_code,po_so_number,effective_date,value,is_amendment,amendment_number,remarks\nPO,VEND001,PO-2024-001,2024-01-15,50000,No,,Initial purchase order\nSO,VEND002,SO-2024-002,15/01/2024,75000.50,No,,Service order for maintenance\nPO,VEND001,PO-2024-001,2024-02-01,55000,Yes,1,Amendment for additional work\nCallout,VEND001,CALL-2024-005,2024-03-10,12000,No,,Callout for emergency\nOthers,VEND002,OTH-2024-001,10-03-2024,3000,No,,Miscellaneous\n`
  const blob = new Blob([csv], { type: 'text/csv' })
  const url = window.URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = 'purchase_orders_template.csv'
  a.click()
  window.URL.revokeObjectURL(url)
}

// Bulk attachments
function handleBulkAttachSelect(event: any) {
  bulkAttachFiles.value = event.target.files
}
async function executeBulkAttach() {
  if (!bulkAttachFiles.value || bulkAttachFiles.value.length === 0) {
    alert('Select at least one file')
    return
  }
  bulkAttachUploading.value = true
  bulkAttachResult.value = null
  const fd = new FormData()
  for (let i = 0; i < bulkAttachFiles.value.length; i++) {
    const f = bulkAttachFiles.value[i]
    if (f) fd.append('files', f)
  }
  try {
    const res = await api.postForm<any>('/master-data/purchase-orders/attachments/bulk', fd)
    bulkAttachResult.value = res
    loadPO()
  } catch (err: any) {
    alert(err.message || 'Bulk upload failed')
  } finally {
    bulkAttachUploading.value = false
  }
}

function handlePOAttachmentSelect(event: any) {
  const file = event.target.files?.[0]
  if (file) {
    if (file.size > 15 * 1024 * 1024) {
      alert('File size exceeds 15 MB')
      return
    }
    poAttachmentFile.value = file
  }
}
</script>

<template>
  <div class="master-data-page p-4 max-w-[1600px] mx-auto">
    <PageHeader
      title="Master Data Configuration"
      description="Configure UOM, Currencies, Phases, Activities, Hole Sections, Vendors/Suppliers, Purchase Orders/Service Orders with Import/Export, Print, Soft Delete & Audit."
    />

    <!-- Tabs Header -->
    <div class="flex border-b border-surface-200 dark:border-surface-700 mb-4 overflow-x-auto scrollbar-thin">
      <button
        v-for="(mod, index) in modules"
        :key="mod.key"
        @click="activeTab = index"
        class="px-4 py-2.5 font-medium text-xs border-b-2 whitespace-nowrap transition-colors"
        :class="activeTab === index ? 'border-primary text-primary font-semibold bg-primary/5' : 'border-transparent text-surface-600 dark:text-surface-400 hover:text-surface-900'"
      >
        {{ mod.label }}
      </button>
      <button
        @click="activeTab = 5"
        class="px-4 py-2.5 font-medium text-xs border-b-2 whitespace-nowrap transition-colors"
        :class="activeTab === 5 ? 'border-primary text-primary font-semibold bg-primary/5' : 'border-transparent text-surface-600 dark:text-surface-400 hover:text-surface-900'"
      >
        <i class="pi pi-truck mr-1"></i> Vendors/Suppliers
      </button>
      <button
        @click="activeTab = 6"
        class="px-4 py-2.5 font-medium text-xs border-b-2 whitespace-nowrap transition-colors"
        :class="activeTab === 6 ? 'border-primary text-primary font-semibold bg-primary/5' : 'border-transparent text-surface-600 dark:text-surface-400 hover:text-surface-900'"
      >
        <i class="pi pi-file-edit mr-1"></i> PO/SO Orders
      </button>
      <button
        @click="activeTab = 7; loadAllDeleted()"
        class="px-4 py-2.5 font-medium text-xs border-b-2 whitespace-nowrap transition-colors text-red-600 dark:text-red-400"
        :class="activeTab === 7 ? 'border-red-600 font-semibold bg-red-50 dark:bg-red-900/20' : 'border-transparent hover:text-red-700'"
      >
        <i class="pi pi-trash mr-1"></i> Deleted Entries
      </button>
    </div>

    <!-- Generic Module View -->
    <div v-if="activeTab < modules.length && currentModule" class="bg-surface-0 dark:bg-surface-900 rounded-lg shadow-sm border border-surface-200 dark:border-surface-700 p-4">
      <div class="flex flex-wrap items-center justify-between gap-3 mb-3">
        <div class="flex items-center gap-1.5 flex-wrap">
          <Button label="Add" icon="pi pi-plus" size="small" severity="primary" @click="openAddDialog" class="!text-xs !py-1" />
          <Button label="Import" icon="pi pi-upload" size="small" severity="secondary" outlined @click="showImportDialog = true" class="!text-xs" />
          <Button label="XLSX" icon="pi pi-file-excel" size="small" severity="success" outlined @click="exportData('xlsx')" class="!text-xs" />
          <Button label="CSV" icon="pi pi-file" size="small" severity="help" outlined @click="exportData('csv')" class="!text-xs" />
          <Button label="Print" icon="pi pi-print" size="small" severity="secondary" outlined @click="printTable" class="!text-xs" />
          <span class="text-[11px] text-surface-500 ml-2">{{ filteredRecords.length }} records</span>
        </div>
        <div class="flex items-center gap-2">
          <InputText v-model="searchQuery" placeholder="Search..." class="w-56 text-xs h-8" />
          <select v-model="pageSize" class="text-xs border rounded px-2 h-8 bg-surface-0 dark:bg-surface-900">
            <option :value="10">10 / page</option>
            <option :value="15">15 / page</option>
            <option :value="25">25 / page</option>
            <option :value="50">50 / page</option>
          </select>
        </div>
      </div>

      <div class="overflow-x-auto border border-surface-200 dark:border-surface-700 rounded-md max-h-[65vh] overflow-y-auto">
        <table class="w-full text-left border-collapse text-xs">
          <thead class="sticky top-0 z-10">
            <tr class="bg-surface-100 dark:bg-surface-800 text-surface-700 dark:text-surface-300 font-semibold border-b border-surface-200 dark:border-surface-700">
              <th class="p-2 w-12">ID</th>
              <th class="p-2 uppercase text-[11px]">Code</th>
              <th class="p-2 uppercase text-[11px]">Name</th>
              <th v-if="currentModule.symbolField" class="p-2 uppercase text-[11px]">Symbol</th>
              <th class="p-2 uppercase text-[11px]">Description</th>
              <th class="p-2 text-right uppercase text-[11px] w-28">Actions</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="loading"><td :colspan="currentModule.symbolField ? 6 : 5" class="p-6 text-center text-surface-500"><i class="pi pi-spin pi-spinner"></i> Loading...</td></tr>
            <tr v-else-if="paginatedRecords.length === 0"><td :colspan="currentModule.symbolField ? 6 : 5" class="p-6 text-center text-surface-500">No records. Add or Import.</td></tr>
            <tr v-for="item in paginatedRecords" :key="item.id" class="border-b border-surface-100 dark:border-surface-800 hover:bg-surface-50 dark:hover:bg-surface-800/50">
              <td class="p-2 font-mono text-[11px] text-surface-500">#{{ item.id }}</td>
              <td class="p-2 font-medium font-mono text-primary text-xs">{{ item[currentModule.codeField] }}</td>
              <td class="p-2 text-xs">{{ item[currentModule.nameField] }}</td>
              <td v-if="currentModule.symbolField" class="p-2 font-semibold text-xs">{{ item[currentModule.symbolField] }}</td>
              <td class="p-2 text-surface-600 dark:text-surface-400 text-[11px] max-w-[240px] truncate" :title="item.description">{{ item.description || '—' }}</td>
              <td class="p-2 text-right">
                <button @click="openEditDialog(item)" class="p-1 mx-0.5 text-surface-600 hover:text-primary" title="Edit"><i class="pi pi-pencil text-xs"></i></button>
                <button @click="softDelete(item)" class="p-1 mx-0.5 text-red-500 hover:text-red-700" title="Delete"><i class="pi pi-trash text-xs"></i></button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <div class="flex items-center justify-between mt-3 text-xs">
        <span class="text-surface-500">Page {{ currentPage }} of {{ totalPages }} — {{ filteredRecords.length }} total</span>
        <div class="flex gap-1">
          <Button label="Prev" size="small" severity="secondary" outlined :disabled="currentPage <= 1" @click="currentPage--" class="!text-xs" />
          <Button label="Next" size="small" severity="secondary" outlined :disabled="currentPage >= totalPages" @click="currentPage++" class="!text-xs" />
        </div>
      </div>
    </div>

    <!-- Vendors/Suppliers Tab -->
    <div v-else-if="activeTab === 5" class="bg-surface-0 dark:bg-surface-900 rounded-lg shadow-sm border border-surface-200 dark:border-surface-700 p-4">
      <div class="flex flex-wrap items-center justify-between gap-3 mb-3">
        <div class="flex items-center gap-1.5 flex-wrap">
          <Button label="Add Vendor" icon="pi pi-plus" size="small" severity="primary" @click="openAddVendor" class="!text-xs" />
          <Button label="Import Bulk" icon="pi pi-upload" size="small" severity="secondary" outlined @click="showVendorImport = true" class="!text-xs" />
          <Button label="XLSX" icon="pi pi-file-excel" size="small" severity="success" outlined @click="exportVendors('xlsx')" class="!text-xs" />
          <Button label="CSV" icon="pi pi-file" size="small" severity="help" outlined @click="exportVendors('csv')" class="!text-xs" />
          <Button label="Print" icon="pi pi-print" size="small" severity="secondary" outlined @click="printTable" class="!text-xs" />
          <span class="text-[11px] text-surface-500 ml-2">{{ filteredVendors.length }} vendors</span>
        </div>
        <div class="flex items-center gap-2">
          <InputText v-model="vendorSearch" placeholder="Search vendors..." class="w-56 text-xs h-8" />
          <select v-model="vendorPageSize" class="text-xs border rounded px-2 h-8 bg-surface-0 dark:bg-surface-900">
            <option :value="10">10</option>
            <option :value="15">15</option>
            <option :value="25">25</option>
            <option :value="50">50</option>
          </select>
        </div>
      </div>

      <div class="overflow-x-auto border border-surface-200 dark:border-surface-700 rounded-md max-h-[65vh] overflow-y-auto">
        <table class="w-full text-left border-collapse text-xs">
          <thead class="sticky top-0 z-10">
            <tr class="bg-surface-100 dark:bg-surface-800 text-surface-700 dark:text-surface-300 font-semibold border-b">
              <th class="p-2 w-12">ID</th>
              <th class="p-2 uppercase text-[11px]">Vendor Code *</th>
              <th class="p-2 uppercase text-[11px]">Vendor/Supplier Name *</th>
              <th class="p-2 uppercase text-[11px]">Contact</th>
              <th class="p-2 uppercase text-[11px]">Description</th>
              <th class="p-2 text-right uppercase text-[11px] w-32">Actions</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="vendorLoading"><td colspan="6" class="p-6 text-center"><i class="pi pi-spin pi-spinner"></i> Loading...</td></tr>
            <tr v-else-if="paginatedVendors.length === 0"><td colspan="6" class="p-6 text-center text-surface-500">No vendors. Add or Import.</td></tr>
            <tr v-for="item in paginatedVendors" :key="item.id" class="border-b border-surface-100 dark:border-surface-800 hover:bg-surface-50">
              <td class="p-2 font-mono text-[11px] text-surface-500">#{{ item.id }}</td>
              <td class="p-2 font-medium font-mono text-primary">{{ item.vendor_code }}</td>
              <td class="p-2 font-medium">{{ item.vendor_name }}</td>
              <td class="p-2 text-[11px] text-surface-600 max-w-[180px] truncate" :title="item.contact">{{ item.contact || '—' }}</td>
              <td class="p-2 text-[11px] text-surface-600 max-w-[200px] truncate" :title="item.description">{{ item.description || '—' }}</td>
              <td class="p-2 text-right">
                <button @click="openViewVendor(item)" class="p-1 mx-0.5 text-blue-600 hover:text-blue-800" title="View"><i class="pi pi-eye text-xs"></i></button>
                <button @click="openEditVendor(item)" class="p-1 mx-0.5 text-surface-600 hover:text-primary" title="Edit"><i class="pi pi-pencil text-xs"></i></button>
                <button @click="softDeleteVendor(item)" class="p-1 mx-0.5 text-red-500 hover:text-red-700" title="Delete"><i class="pi pi-trash text-xs"></i></button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <div class="flex items-center justify-between mt-3 text-xs">
        <span class="text-surface-500">Page {{ vendorPage }} of {{ vendorTotalPages }} — {{ filteredVendors.length }} total</span>
        <div class="flex gap-1">
          <Button label="Prev" size="small" severity="secondary" outlined :disabled="vendorPage <= 1" @click="vendorPage--" class="!text-xs" />
          <Button label="Next" size="small" severity="secondary" outlined :disabled="vendorPage >= vendorTotalPages" @click="vendorPage++" class="!text-xs" />
        </div>
      </div>
    </div>

    <!-- Purchase Orders / Service Orders Tab -->
    <div v-else-if="activeTab === 6" class="bg-surface-0 dark:bg-surface-900 rounded-lg shadow-sm border border-surface-200 dark:border-surface-700 p-4">
      <div class="flex flex-wrap items-center justify-between gap-3 mb-3">
        <div class="flex items-center gap-1.5 flex-wrap">
          <Button label="Add PO/SO" icon="pi pi-plus" size="small" severity="primary" @click="openAddPO" class="!text-xs" />
          <Button label="Import Bulk" icon="pi pi-upload" size="small" severity="secondary" outlined @click="showPOImport = true" class="!text-xs" />
          <Button label="Bulk Attach" icon="pi pi-paperclip" size="small" severity="secondary" outlined @click="showBulkAttachDialog = true" class="!text-xs" />
          <Button label="XLSX" icon="pi pi-file-excel" size="small" severity="success" outlined @click="exportPO('xlsx')" class="!text-xs" />
          <Button label="CSV" icon="pi pi-file" size="small" severity="help" outlined @click="exportPO('csv')" class="!text-xs" />
          <Button label="Print" icon="pi pi-print" size="small" severity="secondary" outlined @click="printTable" class="!text-xs" />
          <span class="text-[11px] text-surface-500 ml-2">{{ filteredPO.length }} orders</span>
        </div>
        <div class="flex items-center gap-2">
          <select v-model="poTypeFilter" class="text-xs border rounded px-2 h-8 bg-surface-0 dark:bg-surface-900">
            <option value="">All Types</option>
            <option value="PO">PO</option>
            <option value="SO">SO</option>
            <option value="Callout">Callout</option>
            <option value="Others">Others</option>
          </select>
          <InputText v-model="poSearch" placeholder="Search PO/SO..." class="w-48 text-xs h-8" />
          <select v-model="poPageSize" class="text-xs border rounded px-2 h-8 bg-surface-0 dark:bg-surface-900">
            <option :value="10">10</option>
            <option :value="12">12</option>
            <option :value="20">20</option>
            <option :value="30">30</option>
          </select>
        </div>
      </div>

      <div class="overflow-x-auto border border-surface-200 dark:border-surface-700 rounded-md max-h-[65vh] overflow-y-auto">
        <table class="w-full text-left border-collapse text-[11px]">
          <thead class="sticky top-0 z-10">
            <tr class="bg-surface-100 dark:bg-surface-800 text-surface-700 dark:text-surface-300 font-semibold border-b text-[11px]">
              <th class="p-2 w-10">ID</th>
              <th class="p-2 uppercase">Type *</th>
              <th class="p-2 uppercase">Vendor/Supplier *</th>
              <th class="p-2 uppercase">PO/SO Number *</th>
              <th class="p-2 uppercase">Effective Date</th>
              <th class="p-2 uppercase">Value</th>
              <th class="p-2 uppercase">Amend?</th>
              <th class="p-2 uppercase">If Yes</th>
              <th class="p-2 uppercase">Remarks</th>
              <th class="p-2 uppercase">Copy</th>
              <th class="p-2 text-right uppercase w-28">Actions</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="poLoading"><td colspan="11" class="p-6 text-center"><i class="pi pi-spin pi-spinner"></i> Loading PO/SO...</td></tr>
            <tr v-else-if="paginatedPO.length === 0"><td colspan="11" class="p-6 text-center text-surface-500">No PO/SO found. Add or Import bulk.</td></tr>
            <tr v-for="item in paginatedPO" :key="item.id" class="border-b border-surface-100 dark:border-surface-800 hover:bg-surface-50 text-xs">
              <td class="p-2 font-mono text-[10px]">#{{ item.id }}</td>
              <td class="p-2"><span class="px-1.5 py-0.5 rounded text-[10px] font-semibold" :class="{'bg-blue-100 text-blue-800': item.po_type==='PO','bg-green-100 text-green-800': item.po_type==='SO','bg-amber-100 text-amber-800': item.po_type==='Callout','bg-surface-200': item.po_type==='Others'}">{{ item.po_type }}</span></td>
              <td class="p-2 max-w-[140px] truncate" :title="item.vendor_display"><span class="font-mono font-medium text-primary text-[11px]">{{ item.vendor_code }}</span> <span class="text-[11px]">{{ item.vendor_name }}</span></td>
              <td class="p-2 font-mono font-medium">{{ item.po_so_number }}</td>
              <td class="p-2 whitespace-nowrap">{{ item.effective_date ? new Date(item.effective_date).toLocaleDateString() : '—' }}</td>
              <td class="p-2 text-right font-mono">{{ item.value != null ? Number(item.value).toLocaleString() : '—' }}</td>
              <td class="p-2 text-center"><i v-if="item.is_amendment" class="pi pi-check text-green-600"></i><span v-else class="text-surface-400">—</span></td>
              <td class="p-2 text-center">{{ item.amendment_number || '—' }}</td>
              <td class="p-2 max-w-[120px] truncate text-[11px]" :title="item.remarks">{{ item.remarks || '—' }}</td>
              <td class="p-2 text-center">
                <button v-if="item.attachment_original_name" @click="downloadPOAttachment(item)" class="text-blue-600 hover:text-blue-800" :title="item.attachment_original_name"><i class="pi pi-paperclip"></i> <span class="text-[10px]">{{ item.attachment_original_name.length > 12 ? item.attachment_original_name.substring(0,12)+'...' : item.attachment_original_name }}</span></button>
                <span v-else class="text-surface-400">—</span>
              </td>
              <td class="p-2 text-right">
                <button @click="openViewPO(item)" class="p-1 mx-0.5 text-blue-600 hover:text-blue-800" title="View"><i class="pi pi-eye text-[11px]"></i></button>
                <button @click="openEditPO(item)" class="p-1 mx-0.5 text-surface-600 hover:text-primary" title="Edit"><i class="pi pi-pencil text-[11px]"></i></button>
                <button @click="softDeletePO(item)" class="p-1 mx-0.5 text-red-500 hover:text-red-700" title="Delete"><i class="pi pi-trash text-[11px]"></i></button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <div class="flex items-center justify-between mt-3 text-xs">
        <span class="text-surface-500">Page {{ poPage }} of {{ poTotalPages }} — {{ filteredPO.length }} total</span>
        <div class="flex gap-1">
          <Button label="Prev" size="small" severity="secondary" outlined :disabled="poPage <= 1" @click="poPage--" class="!text-xs" />
          <Button label="Next" size="small" severity="secondary" outlined :disabled="poPage >= poTotalPages" @click="poPage++" class="!text-xs" />
        </div>
      </div>
      <div class="mt-3 p-2 bg-blue-50 dark:bg-blue-900/20 rounded text-[11px] text-blue-800 dark:text-blue-300">
        <strong>Bulk Attachments:</strong> Name files as <code>PO_NUMBER.pdf</code> or <code>PO_NUMBER__AMENDMENT.pdf</code> (e.g., PO-2024-001.pdf, PO-2024-001__1.pdf). System matches by PO/SO Number automatically.
      </div>
    </div>

    <!-- Deleted Entries View -->
    <div v-else class="bg-surface-0 dark:bg-surface-900 rounded-lg shadow-sm border border-surface-200 dark:border-surface-700 p-4">
      <div class="flex items-center justify-between mb-3">
        <h3 class="text-sm font-semibold">Deleted Entries (Trash) — {{ allDeletedRecords.length }} items</h3>
        <span class="text-[11px] text-surface-500">Restore or permanently delete. Audit logged.</span>
      </div>
      <div class="overflow-x-auto border border-surface-200 dark:border-surface-700 rounded-md max-h-[65vh] overflow-y-auto">
        <table class="w-full text-left border-collapse text-xs">
          <thead class="sticky top-0 z-10">
            <tr class="bg-surface-100 dark:bg-surface-800 font-semibold border-b">
              <th class="p-2">Module</th>
              <th class="p-2">Code / Number</th>
              <th class="p-2">Name / Details</th>
              <th class="p-2">Deleted At</th>
              <th class="p-2 text-right w-36">Actions</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="loading"><td colspan="5" class="p-6 text-center">Loading deleted...</td></tr>
            <tr v-else-if="allDeletedRecords.length === 0"><td colspan="5" class="p-6 text-center text-surface-500">No deleted entries.</td></tr>
            <tr v-for="item in allDeletedRecords" :key="item.id + '-' + item.moduleKey" class="border-b hover:bg-surface-50">
              <td class="p-2 font-semibold text-[11px] text-primary">{{ item.moduleName }}</td>
              <td class="p-2 font-mono text-xs">{{ item.code || item.vendor_code || item.po_so_number || '—' }}</td>
              <td class="p-2 text-xs max-w-[300px] truncate">{{ item.name || item.vendor_name || item.description || item.remarks || '—' }}</td>
              <td class="p-2 text-[11px] text-surface-500">{{ item.deleted_at ? new Date(item.deleted_at).toLocaleString() : '—' }}</td>
              <td class="p-2 text-right">
                <Button label="Restore" size="small" severity="success" outlined @click="restoreRecord(item, item.moduleKey)" class="!text-[11px] !py-0.5" />
                <Button label="Del" size="small" severity="danger" outlined @click="permanentDelete(item, item.moduleKey)" class="!text-[11px] !py-0.5 ml-1" />
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Generic Add/Edit Dialog -->
    <Dialog v-model:visible="showDialog" :header="isEditing ? 'Edit Entry' : 'New Entry'" :style="{ width: '28rem' }" modal>
      <div class="space-y-3 pt-2" v-if="currentModule">
        <div><label class="block text-[11px] font-semibold uppercase mb-1">Code *</label><InputText v-model="formData.code" class="w-full text-sm" placeholder="Code" /></div>
        <div><label class="block text-[11px] font-semibold uppercase mb-1">Name *</label><InputText v-model="formData.name" class="w-full text-sm" placeholder="Name" /></div>
        <div v-if="currentModule.symbolField"><label class="block text-[11px] font-semibold uppercase mb-1">Symbol *</label><InputText v-model="formData.symbol" class="w-full text-sm" placeholder="Symbol" /></div>
        <div><label class="block text-[11px] font-semibold uppercase mb-1">Description</label><Textarea v-model="formData.description" rows="2" class="w-full text-sm" /></div>
      </div>
      <template #footer>
        <Button label="Cancel" severity="secondary" text @click="showDialog = false" size="small" />
        <Button :label="isEditing ? 'Update' : 'Create'" severity="primary" @click="saveRecord" size="small" />
      </template>
    </Dialog>

    <!-- Generic Import Dialog -->
    <Dialog v-model:visible="showImportDialog" header="Bulk Import (CSV / XLSX)" :style="{ width: '32rem' }" modal>
      <div class="space-y-3 pt-2 text-xs">
        <p class="text-surface-600">Upload CSV/XLSX. Headers: code, name, symbol (if applicable), description. Flexible date parsing supported.</p>
        <Button label="Download Template" icon="pi pi-download" size="small" severity="secondary" outlined @click="downloadTemplate" class="!text-xs" />
        <div class="border-2 border-dashed border-surface-300 rounded p-4 text-center">
          <input type="file" accept=".csv,.xlsx,.xls" @change="handleFileSelect" class="block w-full text-xs file:mr-3 file:py-1.5 file:px-3 file:rounded file:border-0 file:text-xs file:bg-primary/10 file:text-primary" />
        </div>
        <div v-if="importing" class="text-center py-2"><i class="pi pi-spin pi-spinner"></i> Importing...</div>
        <div v-if="importResult" class="p-3 rounded bg-surface-100 dark:bg-surface-800 space-y-1">
          <div>Imported: {{ importResult.imported_count }}</div>
          <div v-if="importResult.error_count" class="text-red-500">Errors: {{ importResult.error_count }}
            <ul class="list-disc pl-4 text-[11px]"><li v-for="(e,i) in importResult.errors" :key="i">{{ e }}</li></ul>
          </div>
        </div>
      </div>
      <template #footer>
        <Button label="Close" severity="secondary" text @click="showImportDialog = false" size="small" />
        <Button label="Import" severity="primary" :loading="importing" @click="executeImport" size="small" />
      </template>
    </Dialog>

    <!-- Vendor Dialog -->
    <Dialog v-model:visible="showVendorDialog" :header="isEditingVendor ? 'Edit Vendor/Supplier' : 'New Vendor/Supplier'" :style="{ width: '30rem' }" modal>
      <div class="space-y-3 pt-2 text-xs">
        <div><label class="block text-[11px] font-semibold uppercase mb-1">Vendor/Supplier Code *</label><InputText v-model="vendorForm.vendor_code" class="w-full text-sm" placeholder="e.g. VEND001" /></div>
        <div><label class="block text-[11px] font-semibold uppercase mb-1">Vendor/Supplier Name *</label><InputText v-model="vendorForm.vendor_name" class="w-full text-sm" placeholder="e.g. Acme Drilling" /></div>
        <div><label class="block text-[11px] font-semibold uppercase mb-1">Contact</label><Textarea v-model="vendorForm.contact" rows="2" class="w-full text-sm" placeholder="Phone, Email, Address..." /></div>
        <div><label class="block text-[11px] font-semibold uppercase mb-1">Description</label><Textarea v-model="vendorForm.description" rows="2" class="w-full text-sm" placeholder="Optional..." /></div>
      </div>
      <template #footer>
        <Button label="Cancel" severity="secondary" text @click="showVendorDialog = false" size="small" />
        <Button :label="isEditingVendor ? 'Update' : 'Create'" severity="primary" @click="saveVendor" size="small" />
      </template>
    </Dialog>

    <Dialog v-model:visible="showVendorView" header="Vendor/Supplier Details" :style="{ width: '28rem' }" modal>
      <div v-if="vendorViewData" class="space-y-2 text-xs pt-2">
        <div class="grid grid-cols-3 gap-2"><span class="font-semibold">Code:</span><span class="col-span-2 font-mono text-primary">{{ vendorViewData.vendor_code }}</span></div>
        <div class="grid grid-cols-3 gap-2"><span class="font-semibold">Name:</span><span class="col-span-2">{{ vendorViewData.vendor_name }}</span></div>
        <div class="grid grid-cols-3 gap-2"><span class="font-semibold">Contact:</span><span class="col-span-2 whitespace-pre-wrap">{{ vendorViewData.contact || '—' }}</span></div>
        <div class="grid grid-cols-3 gap-2"><span class="font-semibold">Description:</span><span class="col-span-2">{{ vendorViewData.description || '—' }}</span></div>
        <div class="grid grid-cols-3 gap-2"><span class="font-semibold">Created:</span><span class="col-span-2">{{ vendorViewData.created_at ? new Date(vendorViewData.created_at).toLocaleString() : '—' }}</span></div>
      </div>
      <template #footer><Button label="Close" severity="secondary" @click="showVendorView = false" size="small" /></template>
    </Dialog>

    <Dialog v-model:visible="showVendorImport" header="Bulk Import Vendors (CSV / XLSX)" :style="{ width: '32rem' }" modal>
      <div class="space-y-3 pt-2 text-xs">
        <p>Headers: vendor_code, vendor_name, contact, description. Flexible validation.</p>
        <Button label="Download Template" icon="pi pi-download" size="small" severity="secondary" outlined @click="downloadVendorTemplate" class="!text-xs" />
        <div class="border-2 border-dashed rounded p-4 text-center"><input type="file" accept=".csv,.xlsx,.xls" @change="handleVendorFileSelect" class="block w-full text-xs file:mr-3 file:py-1.5 file:px-3 file:rounded file:border-0 file:text-xs file:bg-primary/10 file:text-primary" /></div>
        <div v-if="vendorImporting" class="text-center"><i class="pi pi-spin pi-spinner"></i> Importing...</div>
        <div v-if="vendorImportResult" class="p-3 rounded bg-surface-100 dark:bg-surface-800"><div>Imported: {{ vendorImportResult.imported_count }}</div><div v-if="vendorImportResult.error_count" class="text-red-500">Errors: {{ vendorImportResult.error_count }}<ul class="list-disc pl-4"><li v-for="(e,i) in vendorImportResult.errors" :key="i">{{ e }}</li></ul></div></div>
      </div>
      <template #footer>
        <Button label="Close" severity="secondary" text @click="showVendorImport = false" size="small" />
        <Button label="Import" severity="primary" :loading="vendorImporting" @click="executeVendorImport" size="small" />
      </template>
    </Dialog>

    <!-- PO/SO Dialog -->
    <Dialog v-model:visible="showPODialog" :header="isEditingPO ? 'Edit PO/SO' : 'New PO/SO'" :style="{ width: '36rem' }" modal>
      <div class="space-y-3 pt-2 text-xs max-h-[70vh] overflow-y-auto pr-2">
        <div class="grid grid-cols-2 gap-3">
          <div><label class="block text-[11px] font-semibold uppercase mb-1">Type *</label>
            <select v-model="poForm.po_type" class="w-full border rounded px-2 py-1.5 text-sm bg-surface-0 dark:bg-surface-900">
              <option value="PO">PO</option><option value="SO">SO</option><option value="Callout">Callout</option><option value="Others">Others</option>
            </select>
          </div>
          <div><label class="block text-[11px] font-semibold uppercase mb-1">Vendor/Supplier *</label>
            <select v-model="poForm.vendor_id" class="w-full border rounded px-2 py-1.5 text-sm bg-surface-0 dark:bg-surface-900">
              <option :value="null">-- Select Vendor --</option>
              <option v-for="v in vendorsDropdown" :key="v.id" :value="v.id">{{ v.display_name }}</option>
            </select>
          </div>
        </div>
        <div><label class="block text-[11px] font-semibold uppercase mb-1">PO/SO Number *</label><InputText v-model="poForm.po_so_number" class="w-full text-sm" placeholder="e.g. PO-2024-001" /></div>
        <div class="grid grid-cols-2 gap-3">
          <div><label class="block text-[11px] font-semibold uppercase mb-1">Effective Date (optional)</label><InputText type="date" v-model="poForm.effective_date" class="w-full text-sm" /></div>
          <div><label class="block text-[11px] font-semibold uppercase mb-1">Value (currency, optional)</label><InputText v-model="poForm.value" class="w-full text-sm" placeholder="e.g. 50000 or $50,000.00" /></div>
        </div>
        <div class="flex items-center gap-3 p-2 bg-surface-50 dark:bg-surface-800 rounded">
          <label class="flex items-center gap-2 cursor-pointer"><input type="checkbox" v-model="poForm.is_amendment" class="rounded" /> <span class="font-semibold">Amendment?</span></label>
          <div v-if="poForm.is_amendment" class="flex items-center gap-2">
            <label class="text-[11px] font-semibold">If Yes *</label>
            <select v-model="poForm.amendment_number" class="border rounded px-2 py-1 text-sm bg-surface-0 dark:bg-surface-900">
              <option :value="null">-- Select --</option>
              <option v-for="n in 200" :key="n" :value="n">{{ n }}</option>
            </select>
            <span class="text-[11px] text-surface-500">Same PO number + amendment avoids duplication</span>
          </div>
        </div>
        <div><label class="block text-[11px] font-semibold uppercase mb-1">Remarks (optional)</label><Textarea v-model="poForm.remarks" rows="2" class="w-full text-sm" placeholder="Optional remarks..." /></div>
        <div><label class="block text-[11px] font-semibold uppercase mb-1">Upload Copy (pdf, docx, doc, xlsx, csv, xls, jpg, jpeg, png &lt;15MB)</label>
          <input type="file" :accept="'.pdf,.docx,.doc,.xlsx,.xls,.csv,.jpg,.jpeg,.png'" @change="handlePOAttachmentSelect" class="block w-full text-xs file:mr-3 file:py-1.5 file:px-3 file:rounded file:border-0 file:text-xs file:bg-primary/10 file:text-primary" />
          <div v-if="poAttachmentFile" class="mt-1 text-[11px] text-green-600">Selected: {{ poAttachmentFile.name }} ({{ (poAttachmentFile.size/1024/1024).toFixed(2) }} MB)</div>
        </div>
      </div>
      <template #footer>
        <Button label="Cancel" severity="secondary" text @click="showPODialog = false" size="small" />
        <Button :label="isEditingPO ? 'Update' : 'Create'" severity="primary" @click="savePO" size="small" />
      </template>
    </Dialog>

    <Dialog v-model:visible="showPOView" header="PO/SO Details" :style="{ width: '34rem' }" modal>
      <div v-if="poViewData" class="space-y-2 text-xs pt-2">
        <div class="grid grid-cols-3 gap-2"><span class="font-semibold">Type:</span><span class="col-span-2"><span class="px-2 py-0.5 rounded text-[10px] font-semibold bg-blue-100 text-blue-800">{{ poViewData.po_type }}</span></span></div>
        <div class="grid grid-cols-3 gap-2"><span class="font-semibold">Vendor:</span><span class="col-span-2">{{ poViewData.vendor_display || poViewData.vendor_code }}</span></div>
        <div class="grid grid-cols-3 gap-2"><span class="font-semibold">PO/SO Number:</span><span class="col-span-2 font-mono font-medium">{{ poViewData.po_so_number }}</span></div>
        <div class="grid grid-cols-3 gap-2"><span class="font-semibold">Effective Date:</span><span class="col-span-2">{{ poViewData.effective_date ? new Date(poViewData.effective_date).toLocaleDateString() : '—' }}</span></div>
        <div class="grid grid-cols-3 gap-2"><span class="font-semibold">Value:</span><span class="col-span-2 font-mono">{{ poViewData.value != null ? Number(poViewData.value).toLocaleString() : '—' }}</span></div>
        <div class="grid grid-cols-3 gap-2"><span class="font-semibold">Amendment:</span><span class="col-span-2">{{ poViewData.is_amendment ? `Yes — ${poViewData.amendment_number}` : 'No' }}</span></div>
        <div class="grid grid-cols-3 gap-2"><span class="font-semibold">Remarks:</span><span class="col-span-2 whitespace-pre-wrap">{{ poViewData.remarks || '—' }}</span></div>
        <div class="grid grid-cols-3 gap-2"><span class="font-semibold">Attachment:</span><span class="col-span-2"><span v-if="poViewData.attachment_original_name" class="text-blue-600"><i class="pi pi-paperclip"></i> {{ poViewData.attachment_original_name }} ({{ poViewData.attachment_size ? (poViewData.attachment_size/1024).toFixed(1)+' KB' : '' }}) <Button label="Download" size="small" severity="secondary" outlined @click="downloadPOAttachment(poViewData)" class="!text-[11px] ml-2" /></span><span v-else>— No attachment —</span></span></div>
        <div class="grid grid-cols-3 gap-2"><span class="font-semibold">Created:</span><span class="col-span-2">{{ poViewData.created_at ? new Date(poViewData.created_at).toLocaleString() : '—' }}</span></div>
      </div>
      <template #footer><Button label="Close" severity="secondary" @click="showPOView = false" size="small" /></template>
    </Dialog>

    <Dialog v-model:visible="showPOImport" header="Bulk Import PO/SO (CSV / XLSX)" :style="{ width: '36rem' }" modal>
      <div class="space-y-3 pt-2 text-xs">
        <p>Headers: po_type (PO/SO/Callout/Others), vendor_code, po_so_number, effective_date (flexible), value, is_amendment (Yes/No), amendment_number (1-200), remarks. Vendor lookup by code or name.</p>
        <Button label="Download Template" icon="pi pi-download" size="small" severity="secondary" outlined @click="downloadPOTemplate" class="!text-xs" />
        <div class="border-2 border-dashed rounded p-4 text-center"><input type="file" accept=".csv,.xlsx,.xls" @change="handlePOFileSelect" class="block w-full text-xs file:mr-3 file:py-1.5 file:px-3 file:rounded file:border-0 file:text-xs file:bg-primary/10 file:text-primary" /></div>
        <div v-if="poImporting" class="text-center"><i class="pi pi-spin pi-spinner"></i> Importing...</div>
        <div v-if="poImportResult" class="p-3 rounded bg-surface-100 dark:bg-surface-800"><div>Imported: {{ poImportResult.imported_count }}</div><div v-if="poImportResult.error_count" class="text-red-500">Errors: {{ poImportResult.error_count }}<ul class="list-disc pl-4 text-[11px]"><li v-for="(e,i) in poImportResult.errors" :key="i">{{ e }}</li></ul></div></div>
        <div class="p-2 bg-amber-50 dark:bg-amber-900/20 rounded text-[11px]">After bulk import, upload attachments one by one via Edit, or use Bulk Attach (filename contains PO number).</div>
      </div>
      <template #footer>
        <Button label="Close" severity="secondary" text @click="showPOImport = false" size="small" />
        <Button label="Import" severity="primary" :loading="poImporting" @click="executePOImport" size="small" />
      </template>
    </Dialog>

    <Dialog v-model:visible="showBulkAttachDialog" header="Bulk Upload Attachments for PO/SO" :style="{ width: '34rem' }" modal>
      <div class="space-y-3 pt-2 text-xs">
        <p>Name files as <code>PO_NUMBER.pdf</code> or <code>PO_NUMBER__AMENDMENT.pdf</code> to auto-match. Allowed: pdf, docx, doc, xlsx, csv, xls, jpg, jpeg, png &lt;15MB each.</p>
        <div class="border-2 border-dashed rounded p-4 text-center">
          <input type="file" multiple :accept="'.pdf,.docx,.doc,.xlsx,.xls,.csv,.jpg,.jpeg,.png'" @change="handleBulkAttachSelect" class="block w-full text-xs file:mr-3 file:py-1.5 file:px-3 file:rounded file:border-0 file:text-xs file:bg-primary/10 file:text-primary" />
        </div>
        <div v-if="bulkAttachUploading" class="text-center"><i class="pi pi-spin pi-spinner"></i> Uploading...</div>
        <div v-if="bulkAttachResult" class="p-3 rounded bg-surface-100 dark:bg-surface-800"><div>Uploaded: {{ bulkAttachResult.uploaded_count }}</div><div v-if="bulkAttachResult.error_count" class="text-red-500">Errors: {{ bulkAttachResult.error_count }}<ul class="list-disc pl-4"><li v-for="(e,i) in bulkAttachResult.errors" :key="i">{{ e }}</li></ul></div></div>
      </div>
      <template #footer>
        <Button label="Close" severity="secondary" text @click="showBulkAttachDialog = false" size="small" />
        <Button label="Upload All" severity="primary" :loading="bulkAttachUploading" @click="executeBulkAttach" size="small" />
      </template>
    </Dialog>
  </div>
</template>

<style scoped>
@media print {
  .master-data-page button, .master-data-page input, .master-data-page select {
    display: none !important;
  }
  .master-data-page .overflow-x-auto {
    overflow: visible !important;
    max-height: none !important;
  }
}
</style>
