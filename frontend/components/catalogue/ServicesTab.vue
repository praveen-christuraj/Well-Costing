<script setup lang="ts">
/**
 * Services tab — Service Type catalogue. Spreadsheet-style bulk entry over the
 * shared ExcelGrid: Service Code (auto, read-only), Service Name, Service
 * Provider (Vendor/Supplier dropdown), Provider Type (Inhouse / 3rd Party) and
 * Description. Import / XLSX / CSV / Print sit in the grid toolbar.
 */
import { computed, ref } from 'vue'
import ExcelGrid from '~/components/master-data/ExcelGrid.vue'
import ImportDialog from '~/components/master-data/ImportDialog.vue'
import type { EditableGridRow, GridColumn, GridSelectOption } from '~/types/grid'

const api = useApi()

const grid = ref<InstanceType<typeof ExcelGrid> | null>(null)
const showImport = ref(false)

const vendors = ref<Record<string, unknown>[]>([])
async function loadVendors(): Promise<void> {
  try {
    vendors.value = await api.get<Record<string, unknown>[]>('/master-data/vendors/dropdown')
  }
  catch (error) {
    console.error('Failed to load vendors', error)
  }
}
void loadVendors()

const vendorOptions = computed<GridSelectOption[]>(() =>
  vendors.value.map(v => ({
    label: String(v.display_name ?? `${v.vendor_code} — ${v.vendor_name}`),
    value: v.id as number,
  })),
)

const providerOptions: GridSelectOption[] = [
  { label: 'Inhouse', value: 'Inhouse' },
  { label: '3rd Party', value: '3rd Party' },
]

const columns: GridColumn[] = [
  { field: 'service_code', header: 'Service Code', width: '120px', readonly: true, placeholder: 'Auto' },
  { field: 'service_name', header: 'Service Name', required: true, width: '240px', placeholder: 'e.g. Mud Logging Services' },
  { field: 'provider_type', header: 'Provider Type', type: 'select', options: providerOptions, required: true, width: '140px', noPaste: true, defaultValue: 'Inhouse' },
  { field: 'vendor_id', header: 'Service Provider (Vendor)', type: 'select', options: vendorOptions, width: '260px', noPaste: true, placeholder: 'Required for 3rd Party' },
  { field: 'description', header: 'Description', width: '260px', placeholder: 'Optional notes' },
]

function toRow(record: Record<string, unknown>): Record<string, unknown> {
  return {
    _id: record.id as number | null,
    service_code: record.service_code ?? '',
    service_name: record.service_name ?? '',
    provider_type: record.provider_type ?? 'Inhouse',
    vendor_id: record.vendor_id ?? null,
    description: (record.description as string | null) ?? '',
  }
}

function toPayload(row: EditableGridRow): Record<string, unknown> {
  return {
    service_name: String(row.service_name ?? '').trim(),
    provider_type: row.provider_type ?? 'Inhouse',
    vendor_id: row.provider_type === '3rd Party' ? row.vendor_id : (row.vendor_id ?? null),
    description: row.description ? String(row.description) : null,
  }
}

function exportCurrent(format: 'xlsx' | 'csv'): void {
  api.download(`/catalogue/services/export?format=${format}`).then((blob) => {
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `services_export.${format}`
    a.click()
    window.URL.revokeObjectURL(url)
  }).catch((error: unknown) => console.error('Export failed', error))
}

function printTable(): void {
  window.print()
}

defineExpose({
  reload: () => grid.value?.reload(),
})
</script>

<template>
  <div class="tab-panel">
    <ExcelGrid
      ref="grid"
      title="Services (Service Type)"
      singular="service"
      :columns="columns"
      code-field="service_name"
      paste-hint="Service Code is auto-generated; the Vendor dropdown is excluded from paste — set it in the grid afterwards."
      :load-records="() => api.get('/catalogue/services')"
      :to-row="toRow"
      :to-payload="toPayload"
      :create-record="(payload: Record<string, unknown>) => api.post('/catalogue/services', payload)"
      :update-record="(id: number, payload: Record<string, unknown>) => api.put(`/catalogue/services/${id}`, payload)"
      :delete-record="(id: number) => api.delete(`/catalogue/services/${id}`)"
    >
      <template #toolbar-extra>
        <Button label="Import" icon="pi pi-upload" size="small" severity="secondary" outlined @click="showImport = true" />
        <Button label="XLSX" icon="pi pi-file-excel" size="small" severity="success" outlined @click="exportCurrent('xlsx')" />
        <Button label="CSV" icon="pi pi-file" size="small" severity="secondary" outlined @click="exportCurrent('csv')" />
        <Button label="Print" icon="pi pi-print" size="small" severity="secondary" text @click="printTable" />
      </template>
    </ExcelGrid>

    <ImportDialog
      v-model:visible="showImport"
      title="Bulk Import Services (CSV / XLSX)"
      endpoint="/catalogue/services/import"
      hint="Headers: service_name, provider_type (Inhouse/3rd Party), vendor_code (required for 3rd Party), description. Codes are auto-generated; flexible date/text values accepted."
      template-endpoint="/catalogue/services/import-template"
      template-filename="services_template.xlsx"
      @committed="grid?.reload()"
    />
  </div>
</template>

<style scoped>
.tab-panel {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}
</style>
