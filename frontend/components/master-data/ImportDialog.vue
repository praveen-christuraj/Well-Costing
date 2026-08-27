<script setup lang="ts">
/**
 * Shared bulk import dialog (CSV/XLSX upload) used by every master data tab.
 * The host page supplies the endpoint + template; this component handles file
 * selection, upload, and the per-row import result summary.
 */
import { computed, ref, watch } from 'vue'
import Button from 'primevue/button'
import Dialog from 'primevue/dialog'

const props = defineProps<{
  visible: boolean
  title: string
  /** Endpoint that accepts multipart form-data with a `file` field. */
  endpoint: string
  /** Column-header hint shown above the upload area. */
  hint?: string
  /** Optional CSV template the user can download. */
  template?: { filename: string, csv: string } | undefined
}>()

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void
  (e: 'committed'): void
}>()

const api = useApi()
const file = ref<File | null>(null)
const importing = ref(false)
const result = ref<{ imported_count: number, error_count: number, errors?: string[] } | null>(null)
const error = ref<string | null>(null)

const dialogVisible = computed({
  get: () => props.visible,
  set: (value: boolean) => emit('update:visible', value),
})

watch(dialogVisible, (open) => {
  if (!open) return
  file.value = null
  result.value = null
  error.value = null
})

function handleFileSelect(event: Event): void {
  const input = event.target as HTMLInputElement
  file.value = input.files?.[0] ?? null
}

function downloadTemplate(): void {
  if (!props.template) return
  const blob = new Blob([props.template.csv], { type: 'text/csv' })
  const url = window.URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = props.template.filename
  a.click()
  window.URL.revokeObjectURL(url)
}

async function executeImport(): Promise<void> {
  if (!file.value) return
  importing.value = true
  error.value = null
  result.value = null
  const fd = new FormData()
  fd.append('file', file.value)
  try {
    result.value = await api.postForm<typeof result.value>(props.endpoint, fd)
    emit('committed')
  }
  catch (caught: unknown) {
    error.value = caught instanceof Error ? caught.message : 'Import failed'
  }
  finally {
    importing.value = false
  }
}
</script>

<template>
  <Dialog v-model="dialogVisible" modal :header="title" :style="{ width: '34rem' }">
    <div class="import-dialog">
      <p v-if="hint" class="import-dialog__hint">{{ hint }}</p>
      <div class="flex items-center gap-2">
        <Button
          v-if="template"
          label="Download Template"
          icon="pi pi-download"
          size="small"
          severity="secondary"
          outlined
          @click="downloadTemplate"
        />
        <span class="import-dialog__accepted">Accepts .csv, .xlsx, .xls</span>
      </div>
      <div class="import-dialog__drop">
        <input
          type="file"
          accept=".csv,.xlsx,.xls"
          class="import-dialog__file"
          @change="handleFileSelect"
        >
        <div v-if="file" class="import-dialog__selected">
          Selected: <strong>{{ file.name }}</strong> ({{ (file.size / 1024).toFixed(1) }} KB)
        </div>
      </div>

      <div v-if="importing" class="import-dialog__status"><i class="pi pi-spin pi-spinner" /> Importing…</div>
      <div v-if="error" class="import-dialog__error">{{ error }}</div>
      <div v-if="result" class="import-dialog__result">
        <div><i class="pi pi-check-circle" /> Imported: {{ result.imported_count }}</div>
        <div v-if="result.error_count" class="import-dialog__result-errors">
          Errors: {{ result.error_count }}
          <ul>
            <li v-for="(item, index) in result.errors || []" :key="index">{{ item }}</li>
          </ul>
        </div>
      </div>
    </div>
    <template #footer>
      <Button label="Close" severity="secondary" text size="small" @click="dialogVisible = false" />
      <Button label="Import" icon="pi pi-upload" size="small" :disabled="!file" :loading="importing" @click="executeImport" />
    </template>
  </Dialog>
</template>

<style scoped>
.import-dialog {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  font-size: 0.82rem;
}

.import-dialog__hint {
  margin: 0;
  color: var(--app-muted);
}

.import-dialog__accepted {
  font-size: 0.72rem;
  color: var(--app-muted);
}

.import-dialog__drop {
  border: 2px dashed var(--app-border);
  border-radius: 8px;
  padding: 0.75rem;
}

.import-dialog__file {
  display: block;
  width: 100%;
  font-size: 0.8rem;
}

.import-dialog__file::file-selector-button {
  margin-right: 0.75rem;
  padding: 0.35rem 0.75rem;
  border: none;
  border-radius: 6px;
  background: rgb(15 118 110 / 12%);
  color: var(--app-teal);
  font-size: 0.78rem;
  cursor: pointer;
}

.import-dialog__selected {
  margin-top: 0.5rem;
  color: var(--app-muted);
}

.import-dialog__status {
  color: var(--app-muted);
}

.import-dialog__error {
  color: #e11d48;
}

.import-dialog__result {
  background: var(--app-bg);
  border-radius: 8px;
  padding: 0.6rem 0.75rem;
}

.import-dialog__result-errors {
  color: #e11d48;
  margin-top: 0.25rem;
}

.import-dialog__result-errors ul {
  margin: 0.25rem 0 0;
  padding-left: 1.25rem;
  font-size: 0.72rem;
}
</style>
