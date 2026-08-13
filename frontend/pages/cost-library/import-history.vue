<script setup lang="ts">
import { onMounted, ref } from 'vue'
import Button from 'primevue/button'
import Column from 'primevue/column'
import DataTable from 'primevue/datatable'
import Dialog from 'primevue/dialog'
import Tag from 'primevue/tag'
import PageHeader from '~/components/design-system/PageHeader.vue'
import CostLibraryNav from '~/components/cost-library/CostLibraryNav.vue'
import type { ImportBatch } from '~/types/imports'

definePageMeta({ middleware: 'auth' })

const api = useMasterData()
const batches = ref<ImportBatch[]>([])
const loading = ref(false)
const error = ref<string | null>(null)
const selectedBatch = ref<ImportBatch | null>(null)

async function load(): Promise<void> {
  loading.value = true
  try { batches.value = (await api.importHistory()).items }
  catch (caught: unknown) { error.value = caught instanceof Error ? caught.message : 'History could not be loaded' }
  finally { loading.value = false }
}

function severity(status: string): 'success' | 'danger' | 'warn' | 'info' {
  if (status === 'committed') return 'success'
  if (status === 'invalid') return 'danger'
  if (status === 'validated') return 'info'
  return 'warn'
}

onMounted(() => void load())
</script>

<template>
  <div class="library-page">
    <PageHeader title="Import history" description="Every Excel preview and commit is retained with file hash, mapping version, actor, counts, and row-level errors." />
    <CostLibraryNav active="import-history" />
    <p v-if="error" class="error-copy">{{ error }}</p>
    <DataTable :value="batches" :loading="loading" paginator :rows="25" striped-rows show-gridlines size="small" class="bulk-grid-panel">
      <Column field="created_at" header="Date" sortable><template #body="{ data }">{{ new Date(data.created_at).toLocaleString() }}</template></Column>
      <Column field="filename" header="File" />
      <Column field="entity_type" header="Entity" sortable />
      <Column field="mapping_profile" header="Mapping"><template #body="{ data }">{{ data.mapping_profile }} v{{ data.mapping_version }}</template></Column>
      <Column field="total_rows" header="Rows" />
      <Column field="error_rows" header="Errors" />
      <Column field="imported_rows" header="Imported" />
      <Column field="status" header="Status"><template #body="{ data }"><Tag :value="data.status" :severity="severity(data.status)" /></template></Column>
      <Column header="Details"><template #body="{ data }"><Button label="View errors" icon="pi pi-eye" text :disabled="!data.errors.length" @click="selectedBatch = data" /></template></Column>
      <template #empty>No import batches have been recorded.</template>
    </DataTable>
    <Dialog :visible="selectedBatch !== null" modal header="Import row errors" :style="{ width: 'min(850px, 94vw)' }" @update:visible="value => { if (!value) selectedBatch = null }">
      <DataTable :value="selectedBatch?.errors ?? []" paginator :rows="20" size="small" show-gridlines>
        <Column field="row_number" header="Excel row" />
        <Column field="column_name" header="Column" />
        <Column field="error_code" header="Code" />
        <Column field="message" header="Message" />
      </DataTable>
    </Dialog>
  </div>
</template>
