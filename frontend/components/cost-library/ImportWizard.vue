<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import Button from 'primevue/button'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Message from 'primevue/message'
import ProgressSpinner from 'primevue/progressspinner'
import Textarea from 'primevue/textarea'
import { useImportWizardStore } from '~/stores/importWizard'

const props = defineProps<{
  visible: boolean
  entity: string
  entityLabel: string
}>()
const emit = defineEmits<{
  'update:visible': [value: boolean]
  committed: []
}>()

const wizard = useImportWizardStore()
const api = useMasterData()
const busy = computed(() => wizard.step === 'uploading' || wizard.step === 'committing')
const mappingJson = ref('')

watch(
  () => props.visible,
  (visible) => {
    if (visible) {
      wizard.reset()
      mappingJson.value = ''
    }
  },
)

function selectFile(event: Event): void {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (file) wizard.selectFile(file)
}

async function preview(): Promise<void> {
  if (!wizard.file) return
  wizard.startUpload()
  try {
    wizard.setPreview(await api.previewImport(props.entity, wizard.file, mappingJson.value))
  }
  catch (error: unknown) {
    wizard.fail(error instanceof Error ? error.message : 'Workbook preview failed')
  }
}

async function commit(): Promise<void> {
  if (!wizard.preview) return
  wizard.startCommit()
  try {
    const result = await api.commitImport(props.entity, wizard.preview.batch_id)
    wizard.complete(`${result.imported_rows} rows imported successfully.`)
    emit('committed')
  }
  catch (error: unknown) {
    wizard.fail(error instanceof Error ? error.message : 'Import commit failed')
  }
}

async function downloadTemplate(format: 'xlsx' | 'csv' = 'xlsx'): Promise<void> {
  const blob = await api.downloadTemplate(props.entity, format)
  downloadBlob(blob, `${props.entity}-template.${format}`)
}

function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  anchor.click()
  URL.revokeObjectURL(url)
}
</script>

<template>
  <div v-if="visible" class="import-overlay" role="dialog" aria-modal="true">
    <section class="import-dialog">
      <header class="import-dialog__header">
        <h2>Import {{ entityLabel }}</h2>
        <Button icon="pi pi-times" text rounded aria-label="Close import" @click="emit('update:visible', false)" />
      </header>
    <div class="import-steps" aria-label="Import workflow">
      <span :class="{ active: ['idle', 'file-selected'].includes(wizard.step) }">1. File</span>
      <span :class="{ active: ['uploading', 'validation-ready'].includes(wizard.step) }">2. Validate</span>
      <span :class="{ active: ['committing', 'complete'].includes(wizard.step) }">3. Commit</span>
    </div>

    <div v-if="wizard.step === 'idle' || wizard.step === 'file-selected'" class="import-dropzone">
      <i class="pi pi-file-excel" aria-hidden="true" />
      <strong>Select an Excel workbook or CSV file</strong>
      <span>.xlsx, .xlsm, .xls, or .csv — maximum 15 MB</span>
      <input type="file" accept=".xlsx,.xlsm,.xls,.csv" data-testid="import-file" @change="selectFile">
      <small v-if="wizard.file">Selected: {{ wizard.file.name }}</small>
      <details class="mapping-override">
        <summary>Confirm or override ambiguous column mapping</summary>
        <p>Optional JSON format: {"source_to_target":{"Workbook Header":"target_field"}}</p>
        <Textarea v-model="mappingJson" rows="4" fluid placeholder='{"source_to_target":{"Vendor ID":"code"}}' />
      </details>
      <div class="import-dropzone__actions">
        <Button label="Excel template" icon="pi pi-download" text @click="downloadTemplate('xlsx')" />
        <Button label="CSV template" icon="pi pi-download" text @click="downloadTemplate('csv')" />
        <Button label="Preview and validate" icon="pi pi-search" :disabled="!wizard.file" @click="preview" />
      </div>
    </div>

    <div v-else-if="busy" class="import-busy">
      <ProgressSpinner />
      <p>{{ wizard.step === 'uploading' ? 'Reading and validating workbook…' : 'Committing validated rows…' }}</p>
    </div>

    <template v-else-if="wizard.preview && wizard.step === 'validation-ready'">
      <div class="validation-summary">
        <div><span>Total rows</span><strong>{{ wizard.preview.total_rows }}</strong></div>
        <div class="valid"><span>Valid</span><strong>{{ wizard.preview.valid_rows }}</strong></div>
        <div :class="{ invalid: wizard.preview.error_rows > 0 }"><span>Error rows</span><strong>{{ wizard.preview.error_rows }}</strong></div>
        <div><span>Profile</span><strong>{{ wizard.preview.mapping_profile }} v{{ wizard.preview.mapping_version }}</strong></div>
      </div>

      <Message v-if="wizard.preview.status === 'invalid'" severity="error" :closable="false">
        Correct all workbook errors and upload again. No business records have been committed.
      </Message>
      <Message v-else severity="success" :closable="false">
        All rows passed structural and reference validation.
      </Message>

      <DataTable v-if="wizard.preview.errors.length" :value="wizard.preview.errors" size="small" paginator :rows="10">
        <Column field="row_index" header="Excel row" />
        <Column field="column" header="Column" />
        <Column field="code" header="Error code" />
        <Column field="message" header="Message" />
      </DataTable>

      <div class="import-dialog__footer">
        <Button label="Choose another file" severity="secondary" outlined @click="wizard.reset" />
        <Button label="Commit import" icon="pi pi-check" :disabled="!wizard.canCommit" @click="commit" />
      </div>
    </template>

    <Message v-else-if="wizard.step === 'complete'" severity="success" :closable="false">
      {{ wizard.message }}
    </Message>
      <Message v-else-if="wizard.step === 'error'" severity="error" :closable="false">
        {{ wizard.message }}
      </Message>
    </section>
  </div>
</template>
