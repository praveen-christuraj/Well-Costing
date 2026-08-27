<script setup lang="ts">
/**
 * Shared bulk import dialog (CSV/XLSX upload) used by every master data and
 * catalogue tab. The host supplies the upload endpoint plus a template source
 * (a backend template endpoint or an inline CSV fallback); this component
 * walks the user through the full loop: download template → fill it with data
 * → upload the same file, then shows the per-row import result summary.
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
  /** Backend endpoint returning a ready-to-fill template file. */
  templateEndpoint?: string
  /** Filename used when downloading the backend template. */
  templateFilename?: string
  /** Inline CSV template fallback when no backend endpoint is configured. */
  template?: { filename: string, csv: string } | undefined
}>()

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void
  (e: 'committed'): void
}>()

const MAX_UPLOAD_BYTES = 15 * 1024 * 1024
const ACCEPTED_EXTENSIONS = ['.csv', '.xlsx', '.xls']

const api = useApi()
const file = ref<File | null>(null)
const importing = ref(false)
const downloadingTemplate = ref(false)
const dragOver = ref(false)
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
  dragOver.value = false
})

const canDownloadTemplate = computed(() => !!props.templateEndpoint || !!props.template)

function extensionOf(name: string): string {
  const index = name.lastIndexOf('.')
  return index === -1 ? '' : name.slice(index).toLowerCase()
}

function acceptFile(candidate: File | null | undefined): void {
  error.value = null
  result.value = null
  if (!candidate) return
  if (!ACCEPTED_EXTENSIONS.includes(extensionOf(candidate.name))) {
    error.value = `"${candidate.name}" is not supported — use one of: ${ACCEPTED_EXTENSIONS.join(', ')}`
    file.value = null
    return
  }
  if (candidate.size > MAX_UPLOAD_BYTES) {
    error.value = 'File size exceeds the 15 MB limit'
    file.value = null
    return
  }
  file.value = candidate
}

function handleFileSelect(event: Event): void {
  const input = event.target as HTMLInputElement
  acceptFile(input.files?.[0])
  // Allow picking the same file again after a failed attempt.
  input.value = ''
}

function handleDrop(event: DragEvent): void {
  event.preventDefault()
  dragOver.value = false
  acceptFile(event.dataTransfer?.files?.[0])
}

async function downloadTemplate(): Promise<void> {
  if (!canDownloadTemplate.value) return
  downloadingTemplate.value = true
  error.value = null
  try {
    if (props.templateEndpoint) {
      const blob = await api.download(props.templateEndpoint)
      triggerDownload(blob, props.templateFilename ?? `${props.endpoint.replace(/[^\w]+/g, '_')}_template.xlsx`)
    }
    else if (props.template) {
      triggerDownload(new Blob([props.template.csv], { type: 'text/csv' }), props.template.filename)
    }
  }
  catch (caught: unknown) {
    error.value = caught instanceof Error ? caught.message : 'Template download failed'
  }
  finally {
    downloadingTemplate.value = false
  }
}

function triggerDownload(blob: Blob, filename: string): void {
  const url = window.URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  window.URL.revokeObjectURL(url)
}

function resetForAnotherFile(): void {
  file.value = null
  result.value = null
  error.value = null
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
  <Dialog v-model:visible="dialogVisible" modal :header="title" :style="{ width: '36rem' }">
    <div class="import-dialog">
      <p v-if="hint" class="import-dialog__hint">{{ hint }}</p>

      <div v-if="canDownloadTemplate" class="import-step">
        <span class="import-step__num">1</span>
        <div class="import-step__body">
          <p class="import-step__title">Download the template</p>
          <p class="import-step__text">
            Fill it with your data — keep the header row unchanged, one record per row.
          </p>
          <Button
            label="Download Template"
            icon="pi pi-download"
            size="small"
            severity="success"
            outlined
            data-testid="download-template"
            :loading="downloadingTemplate"
            @click="downloadTemplate"
          />
        </div>
      </div>

      <div class="import-step">
        <span class="import-step__num">2</span>
        <div class="import-step__body">
          <p class="import-step__title">Upload the filled file</p>
          <p class="import-step__text">Accepts {{ ACCEPTED_EXTENSIONS.join(', ') }} — max 15 MB.</p>
          <div
            class="import-dialog__drop"
            :class="{ 'import-dialog__drop--over': dragOver, 'import-dialog__drop--filled': file }"
            data-testid="import-dropzone"
            @dragover.prevent="dragOver = true"
            @dragleave.prevent="dragOver = false"
            @drop="handleDrop"
          >
            <input
              type="file"
              :accept="ACCEPTED_EXTENSIONS.join(',')"
              class="import-dialog__file"
              data-testid="import-file-input"
              @change="handleFileSelect"
            >
            <div v-if="file" class="import-dialog__selected">
              <i class="pi pi-file" /> <strong>{{ file.name }}</strong>
              ({{ (file.size / 1024).toFixed(1) }} KB)
            </div>
            <div v-else class="import-dialog__drop-hint">
              <i class="pi pi-upload" /> Drag &amp; drop the file here, or use the chooser above
            </div>
          </div>
        </div>
      </div>

      <div v-if="importing" class="import-dialog__status"><i class="pi pi-spin pi-spinner" /> Importing…</div>
      <div v-if="error" class="import-dialog__error" data-testid="import-error">{{ error }}</div>
      <div v-if="result" class="import-dialog__result" data-testid="import-result">
        <div class="import-dialog__result-line">
          <i class="pi pi-check-circle" /> Imported: <strong>{{ result.imported_count }}</strong>
          <span v-if="result.error_count"> · Errors: <strong>{{ result.error_count }}</strong></span>
        </div>
        <ul v-if="result.error_count" class="import-dialog__result-errors">
          <li v-for="(item, index) in result.errors || []" :key="index">{{ item }}</li>
        </ul>
        <Button
          label="Import another file"
          icon="pi pi-replay"
          size="small"
          severity="secondary"
          text
          @click="resetForAnotherFile"
        />
      </div>
    </div>
    <template #footer>
      <Button label="Close" severity="secondary" text size="small" @click="dialogVisible = false" />
      <Button
        label="Import"
        icon="pi pi-upload"
        size="small"
        data-testid="execute-import"
        :disabled="!file || !!result"
        :loading="importing"
        @click="executeImport"
      />
    </template>
  </Dialog>
</template>

<style scoped>
.import-dialog {
  display: flex;
  flex-direction: column;
  gap: 0.85rem;
  font-size: 0.82rem;
}

.import-dialog__hint {
  margin: 0;
  color: var(--app-muted);
}

.import-step {
  display: flex;
  gap: 0.65rem;
}

.import-step__num {
  flex: none;
  width: 1.35rem;
  height: 1.35rem;
  border-radius: 50%;
  background: rgb(15 118 110 / 12%);
  color: var(--app-teal);
  font-size: 0.72rem;
  font-weight: 700;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.import-step__body {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  flex: 1;
}

.import-step__title {
  margin: 0;
  font-weight: 600;
  font-size: 0.82rem;
}

.import-step__text {
  margin: 0;
  color: var(--app-muted);
  font-size: 0.75rem;
}

.import-dialog__drop {
  border: 2px dashed var(--app-border);
  border-radius: 8px;
  padding: 0.75rem;
  transition: border-color 0.15s ease, background 0.15s ease;
}

.import-dialog__drop--over {
  border-color: var(--app-teal);
  background: rgb(15 118 110 / 6%);
}

.import-dialog__drop--filled {
  border-color: var(--app-teal);
  border-style: solid;
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

.import-dialog__drop-hint {
  margin-top: 0.5rem;
  color: var(--app-muted);
  font-size: 0.72rem;
  display: flex;
  align-items: center;
  gap: 0.35rem;
}

.import-dialog__selected {
  margin-top: 0.5rem;
  color: var(--app-ink);
  font-size: 0.78rem;
  display: flex;
  align-items: center;
  gap: 0.35rem;
}

.import-dialog__selected .pi-file {
  color: var(--app-teal);
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
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.import-dialog__result-line {
  display: flex;
  align-items: center;
  gap: 0.4rem;
}

.import-dialog__result-line .pi-check-circle {
  color: var(--app-teal);
}

.import-dialog__result-errors {
  color: #e11d48;
  margin: 0;
  padding-left: 1.25rem;
  font-size: 0.72rem;
  max-height: 9rem;
  overflow-y: auto;
}
</style>
