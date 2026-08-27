<script setup lang="ts">
/**
 * Excel-style bulk entry grid for master data.
 *
 * Replaces dialog/form data entry with a spreadsheet-like table: every cell is
 * always editable, multiple rows can be added/pasted/duplicated in one go and
 * committed with a single bulk "Save all" action. Modelled on the PrimeVue
 * Sakai DataTable look (gridlines, compact size, scrollable) with the
 * bulk-entry workflow from the repo's grid references.
 *
 * The grid owns row state only; all persistence flows through the host page's
 * `loadRecords` / `createRecord` / `updateRecord` / `deleteRecord` functions.
 */
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import Button from 'primevue/button'
import Checkbox from 'primevue/checkbox'
import Column from 'primevue/column'
import DataTable from 'primevue/datatable'
import Dialog from 'primevue/dialog'
import InputText from 'primevue/inputtext'
import Message from 'primevue/message'
import Select from 'primevue/select'
import Tag from 'primevue/tag'
import Textarea from 'primevue/textarea'
import { parseTsv } from '~/utils/tsv'
import type { EditableGridRow, GridColumn, GridSelectOption } from '~/types/grid'

const props = defineProps<{
  /** Plural label, e.g. "Units of Measurement". */
  title: string
  /** Singular label used in messages, e.g. "unit". */
  singular: string
  columns: GridColumn[]
  /** Field used for duplicate detection and row error labels. */
  codeField?: string
  loadRecords: () => Promise<Record<string, unknown>[]>
  /** Map an API record onto editable row fields (`_id` should be set). */
  toRow: (record: Record<string, unknown>) => Record<string, unknown>
  /** Map an editable row onto the API create/update payload. */
  toPayload: (row: EditableGridRow) => Record<string, unknown>
  createRecord: (payload: Record<string, unknown>) => Promise<unknown>
  updateRecord: (id: number, payload: Record<string, unknown>) => Promise<unknown>
  deleteRecord: (id: number) => Promise<unknown>
  /** Text describing the expected paste column order. */
  pasteHint?: string
  /** Extra line printed under the title (active filters, etc.). */
  printSubtitle?: string
}>()

const emit = defineEmits<{
  (e: 'dirty', isDirty: boolean): void
}>()

const loading = ref(false)
const saving = ref(false)
const deleting = ref(false)
const error = ref<string | null>(null)
const message = ref<string | null>(null)
const saveErrors = ref<string[]>([])

const rows = ref<EditableGridRow[]>([])
const selected = ref<EditableGridRow[]>([])
const search = ref('')
const dFirst = ref(0)
const pageSize = ref(25)
const rootEl = ref<HTMLElement | null>(null)

const pasteVisible = ref(false)
const pasteText = ref('')
const bulkVisible = ref(false)
const bulkField = ref('')
const bulkValue = ref('')
const printedAt = ref('')

let uid = 0
function nextKey(): string {
  uid += 1
  return `n${uid}`
}

const isInputColumn = (col: GridColumn): boolean => col.type !== 'slot' && !col.readonly && !col.compute
const editableColumns = computed(() => props.columns.filter(isInputColumn))
const pasteColumns = computed(() => editableColumns.value.filter(col => col.type !== 'checkbox' && !col.noPaste))
const codeColumn = computed(() => props.codeField ?? props.columns[0]?.field ?? 'code')
const dirtyCount = computed(() => rows.value.filter(row => row._state !== 'clean').length)
const selectedCount = computed(() => selected.value.length)

const filteredRows = computed(() => {
  const query = search.value.trim().toLowerCase()
  if (!query) return rows.value
  const fields = editableColumns.value.map(col => col.field)
  return rows.value.filter(row =>
    fields.some(field => String(row[field] ?? '').toLowerCase().includes(query)),
  )
})

const pageRows = computed(() => {
  const start = dFirst.value
  return filteredRows.value.slice(start, start + pageSize.value)
})

const visibleKeys = computed(() => pageRows.value.map(row => row._key))

watch(dirtyCount, count => emit('dirty', count > 0))

function blankRow(): EditableGridRow {
  const fields: Record<string, unknown> = {}
  for (const col of props.columns) {
    fields[col.field] = col.defaultValue !== undefined ? col.defaultValue : defaultFor(col)
  }
  return {
    ...fields,
    _key: nextKey(),
    _id: null,
    _state: 'new',
    _error: null,
    _original: null,
  }
}

function defaultFor(col: GridColumn): unknown {
  if (col.type === 'checkbox') return false
  if (col.type === 'select') return cellOptions(col)[0]?.value ?? null
  return ''
}

function wrapRow(fields: Record<string, unknown>): EditableGridRow {
  const id = (fields._id as number | null) ?? null
  const clone: Record<string, unknown> = { ...fields }
  delete clone._id
  return {
    ...clone,
    _key: id != null ? `r${id}` : nextKey(),
    _id: id,
    _state: 'clean',
    _error: null,
    _original: clone,
  }
}

async function load(preserveFailed: EditableGridRow[] = []): Promise<void> {
  loading.value = true
  error.value = null
  try {
    const records = await props.loadRecords()
    const clean = records.map(rec => wrapRow(props.toRow(rec)))
    if (preserveFailed.length) {
      const failedNew = preserveFailed.filter(row => row._state === 'new')
      const failedDirty = preserveFailed.filter(row => row._state === 'dirty')
      const failedIds = new Set(failedDirty.map(row => row._id))
      rows.value = [
        ...failedNew,
        ...clean.filter(row => row._id == null || !failedIds.has(row._id)),
        ...failedDirty,
      ]
    }
    else {
      rows.value = clean
    }
    selected.value = []
  }
  catch (caught: unknown) {
    error.value = caught instanceof Error ? caught.message : `${props.title} could not be loaded`
  }
  finally {
    loading.value = false
  }
}

function markDirty(row: EditableGridRow): void {
  if (row._state === 'clean') row._state = 'dirty'
  row._error = null
}

function stampPrintedAt(): void {
  printedAt.value = new Date().toLocaleString()
}

function cellOptions(col: GridColumn): GridSelectOption[] {
  const opts = col.options
  return Array.isArray(opts) ? opts : (opts?.value ?? [])
}

/** Select options for one row — dependent dropdowns narrow them per row. */
function rowCellOptions(col: GridColumn, row: EditableGridRow): GridSelectOption[] {
  return col.optionsFor ? col.optionsFor(row) : cellOptions(col)
}

function handleSelectChange(row: EditableGridRow, col: GridColumn): void {
  markDirty(row)
  col.onCellChange?.(row)
}

function displayValue(row: EditableGridRow, col: GridColumn): string {
  if (col.compute) return col.compute(row) || ''
  if (col.type === 'slot') {
    if (col.field === 'attachment') return String(row.attachment_original_name ?? '')
    return ''
  }
  const value = row[col.field]
  if (col.type === 'checkbox') return value ? 'Yes' : 'No'
  if (col.type === 'select') {
    const match = rowCellOptions(col, row).find(option => option.value === value)
    return match ? match.label : value == null ? '' : String(value)
  }
  if (value == null || value === '') return ''
  return String(value)
}

const printColumns = computed(() => props.columns.filter(col => col.type !== 'slot' || col.field === 'attachment'))

const printMeta = computed(() => {
  const parts = [`${filteredRows.value.length} row(s)`]
  if (search.value.trim()) parts.push(`Search: ${search.value.trim()}`)
  if (props.printSubtitle) parts.push(props.printSubtitle)
  if (printedAt.value) parts.push(`Printed ${printedAt.value}`)
  return parts.join(' · ')
})

function addRows(count = 1): void {
  const added = Array.from({ length: count }, () => blankRow())
  rows.value = [...added, ...rows.value]
  dFirst.value = 0
  selected.value = []
  void nextTick(() => focusCell(added[0]?._key ?? '', firstEditableField()))
}

function firstEditableField(): string {
  return editableColumns.value[0]?.field ?? ''
}

function duplicateSelected(): void {
  if (!selected.value.length) return
  const copies: EditableGridRow[] = selected.value.map((row) => {
    const clone: Record<string, unknown> = { ...row }
    delete clone._key
    delete clone._id
    delete clone._original
    delete clone._state
    delete clone._error
    const code = clone[codeColumn.value]
    return {
      ...clone,
      [codeColumn.value]: code ? `${String(code)}-COPY` : '',
      _key: nextKey(),
      _id: null,
      _state: 'new' as const,
      _error: null,
      _original: null,
    }
  })
  rows.value = [...copies, ...rows.value]
  dFirst.value = 0
  selected.value = []
}

function applyPaste(): void {
  const parsed = parseTsv(pasteText.value, pasteColumns.value)
  const newRows = parsed
    .filter(values => Object.values(values).some(cell => cell !== ''))
    .map((values) => {
      const row = blankRow()
      for (const [field, value] of Object.entries(values)) {
        row[field] = value
      }
      return row
    })
  if (!newRows.length) {
    pasteVisible.value = false
    return
  }
  rows.value = [...newRows, ...rows.value]
  dFirst.value = 0
  pasteText.value = ''
  pasteVisible.value = false
  message.value = `${newRows.length} row(s) added from paste — review and Save all.`
}

const bulkFieldOptions = computed(() =>
  editableColumns.value
    .filter(col => col.type !== 'checkbox' && col.type !== 'select')
    .map(col => ({ label: col.header, value: col.field })),
)

function applyBulkEdit(): void {
  for (const row of selected.value) {
    if (bulkField.value) row[bulkField.value] = bulkValue.value
    markDirty(row)
  }
  bulkVisible.value = false
  bulkValue.value = ''
}

function revertRow(row: EditableGridRow): void {
  if (row._original) {
    for (const [field, value] of Object.entries(row._original)) {
      if (!field.startsWith('_')) row[field] = value
    }
  }
  row._state = 'clean'
  row._error = null
}

async function discardRow(row: EditableGridRow): Promise<void> {
  if (row._id != null) {
    if (!window.confirm(`Move "${rowLabel(row)}" to deleted entries?`)) return
    try {
      await props.deleteRecord(row._id)
    }
    catch (caught: unknown) {
      row._error = caught instanceof Error ? caught.message : 'Delete failed'
      return
    }
    await load()
  }
  else {
    rows.value = rows.value.filter(item => item._key !== row._key)
    selected.value = selected.value.filter(item => item._key !== row._key)
  }
}

async function deleteSelected(): Promise<void> {
  const targets = [...selected.value]
  if (!targets.length) return
  const saved = targets.filter(row => row._id != null)
  const unsaved = targets.filter(row => row._id == null)
  if (saved.length && !window.confirm(`Delete ${saved.length} saved ${props.singular} row(s) and discard ${unsaved.length} unsaved row(s)?`)) return
  deleting.value = true
  error.value = null
  try {
    const failures: EditableGridRow[] = []
    const results = await Promise.allSettled(saved.map(row => props.deleteRecord(row._id as number)))
    results.forEach((result, index) => {
      const row = saved[index]
      if (result.status === 'rejected' && row) {
        row._error = result.reason instanceof Error ? result.reason.message : 'Delete failed'
        failures.push(row)
      }
    })
    const removedKeys = new Set([
      ...unsaved.map(row => row._key),
      ...saved.filter((row, index) => results[index]?.status === 'fulfilled').map(row => row._key),
    ])
    rows.value = rows.value.filter(row => !removedKeys.has(row._key))
    if (failures.length) {
      error.value = `${failures.length} row(s) could not be deleted — see row errors.`
    }
    else {
      message.value = `${targets.length} row(s) deleted.`
    }
    selected.value = []
    await load(failures)
  }
  finally {
    deleting.value = false
  }
}

function rowLabel(row: EditableGridRow): string {
  return String(row[codeColumn.value] ?? '(blank)')
}

function isCandidate(row: EditableGridRow): boolean {
  return row._state !== 'clean'
}

function missingRequired(row: EditableGridRow, col: GridColumn): boolean {
  return !!col.required && isCandidate(row) && String(row[col.field] ?? '').trim() === ''
}

function invalidNumber(row: EditableGridRow, col: GridColumn): boolean {
  if (col.type !== 'number' || !isCandidate(row)) return false
  const raw = String(row[col.field] ?? '').trim()
  return raw !== '' && Number.isNaN(Number(raw))
}

function invalidCell(row: EditableGridRow, col: GridColumn): boolean {
  return missingRequired(row, col) || invalidNumber(row, col)
}

async function saveAll(): Promise<void> {
  const candidates = rows.value.filter(isCandidate)
  saveErrors.value = []
  error.value = null
  message.value = null
  if (!candidates.length) {
    message.value = 'No pending changes to save.'
    return
  }

  // Client-side validation: required cells, numeric cells, duplicate codes.
  const problems: string[] = []
  for (const row of rows.value) {
    row._error = null
  }
  for (const row of candidates) {
    for (const col of editableColumns.value) {
      if (missingRequired(row, col)) {
        row._error = `${col.header} is required`
        problems.push(`Row ${rowLabel(row) || '(blank)'}: ${col.header} is required`)
      }
      else if (invalidNumber(row, col)) {
        row._error = `${col.header} must be a number`
        problems.push(`Row ${rowLabel(row) || '(blank)'}: ${col.header} must be a number`)
      }
    }
  }
  const seen = new Map<string, string>()
  for (const row of rows.value) {
    const code = String(row[codeColumn.value] ?? '').trim().toLowerCase()
    if (!code) continue
    const previous = seen.get(code)
    if (previous) {
      const text = `Duplicate ${codeColumn.value} "${rowLabel(row)}" (${previous} also uses it)`
      problems.push(text)
      if (row._error == null) row._error = `Duplicate of ${previous}`
    }
    else {
      seen.set(code, rowLabel(row))
    }
  }
  if (problems.length) {
    saveErrors.value = problems
    return
  }

  saving.value = true
  try {
    const ops = candidates.map((row) => {
      const payload = props.toPayload(row)
      return {
        row,
        promise: row._state === 'new'
          ? props.createRecord(payload)
          : props.updateRecord(row._id as number, payload),
      }
    })
    const settled = await Promise.allSettled(ops.map(op => op.promise))
    const failed: EditableGridRow[] = []
    let savedCount = 0
    settled.forEach((result, index) => {
      const op = ops[index]
      if (!op) return
      if (result.status === 'fulfilled') {
        savedCount += 1
      }
      else {
        op.row._error = result.reason instanceof Error ? result.reason.message : 'Save failed'
        failed.push(op.row)
      }
    })
    await load(failed)
    if (failed.length) {
      saveErrors.value = failed.map(row => `Row ${rowLabel(row) || '(blank)'}: ${row._error}`)
      message.value = `Saved ${savedCount} row(s); ${failed.length} row(s) need attention.`
    }
    else {
      message.value = `Saved ${savedCount} row(s).`
    }
  }
  catch (caught: unknown) {
    error.value = caught instanceof Error ? caught.message : 'Save failed'
  }
  finally {
    saving.value = false
  }
}

// --- Excel-like keyboard navigation (Enter / arrows move between cells) ---

function cellId(row: EditableGridRow, col: GridColumn): string {
  return `${row._key}:${col.field}`
}

function focusCell(key: string, field: string): void {
  if (!key || !field) return
  const cell = rootEl.value?.querySelector(`[data-cell="${key}:${field}"]`)
  const input = cell?.querySelector<HTMLElement>('input, textarea')
  input?.focus()
}

function onCellKeydown(event: KeyboardEvent, row: EditableGridRow, col: GridColumn): void {
  let direction: 0 | 1 | -1 = 0
  if (event.key === 'Enter' && !event.shiftKey) direction = 1
  else if (event.key === 'ArrowDown') direction = 1
  else if ((event.key === 'Enter' && event.shiftKey) || event.key === 'ArrowUp') direction = -1
  if (direction === 0) return
  const keys = visibleKeys.value
  const index = keys.indexOf(row._key)
  if (index === -1) return
  const targetKey = keys[index + direction]
  if (!targetKey) return
  event.preventDefault()
  focusCell(targetKey, col.field)
}

function rowClass(data: EditableGridRow): string {
  if (data._error) return 'row-error'
  if (data._state === 'new') return 'row-new'
  if (data._state === 'dirty') return 'row-dirty'
  return ''
}

function onPage(event: { first: number }): void {
  dFirst.value = event.first
}

onMounted(() => {
  void load()
  if (typeof window !== 'undefined') window.addEventListener('beforeprint', stampPrintedAt)
})

onBeforeUnmount(() => {
  if (typeof window !== 'undefined') window.removeEventListener('beforeprint', stampPrintedAt)
})

defineExpose({
  /** Number of rows with unsaved changes. */
  dirtyCount: computed(() => dirtyCount.value),
  reload: () => load(),
})
</script>

<template>
  <div ref="rootEl" class="excel-grid-panel" data-testid="excel-grid">
    <div class="grid-toolbar no-print">
      <div class="grid-toolbar__search">
        <i class="pi pi-search" />
        <InputText v-model="search" :placeholder="`Search ${title.toLowerCase()}…`" size="small" />
      </div>
      <div class="grid-toolbar__actions">
        <Button label="Add row" icon="pi pi-plus" size="small" severity="secondary" outlined data-testid="add-row" @click="addRows(1)" />
        <Button label="+5 Rows" icon="pi pi-plus" size="small" severity="secondary" text data-testid="add-five-rows" @click="addRows(5)" />
        <Button label="Paste" icon="pi pi-clipboard" size="small" severity="secondary" outlined @click="pasteVisible = true" />
        <Button label="Duplicate" icon="pi pi-copy" size="small" severity="secondary" text :disabled="!selectedCount" @click="duplicateSelected" />
        <Button label="Bulk Edit" icon="pi pi-pencil" size="small" severity="secondary" text :disabled="!selectedCount" @click="bulkVisible = true" />
        <Button label="Delete" icon="pi pi-trash" size="small" severity="danger" text :disabled="!selectedCount" :loading="deleting" @click="deleteSelected" />
        <slot name="toolbar-extra" />
        <Tag
          v-if="dirtyCount"
          class="ml-1"
          severity="warn"
          :value="`${dirtyCount} unsaved`"
          data-testid="dirty-count"
        />
        <Button
          :label="`Save All${dirtyCount ? ` (${dirtyCount})` : ''}`"
          icon="pi pi-save"
          size="small"
          severity="success"
          :disabled="!dirtyCount"
          :loading="saving"
          @click="saveAll"
        />
      </div>
    </div>

    <Message v-if="error" severity="error" class="mb-2 no-print" :closable="false">{{ error }}</Message>
    <Message v-if="message && !saveErrors.length" severity="success" class="mb-2 no-print" :closable="false">{{ message }}</Message>
    <Message v-if="saveErrors.length" severity="error" class="mb-2 no-print" :closable="false">
      <div class="save-errors">
        <div v-for="(item, index) in saveErrors" :key="index">{{ item }}</div>
      </div>
    </Message>

    <DataTable
      v-model:selection="selected"
      :value="filteredRows"
      :loading="loading"
      data-key="_key"
      :row-class="rowClass"
      :first="dFirst"
      :rows="pageSize"
      :rows-per-page-options="[25, 50, 100]"
      paginator
      paginator-template="CurrentPageReport FirstPageLink PrevPageLink PageLinks NextPageLink LastPageLink RowsPerPageDropdown"
      current-page-report-template="Showing {first}–{last} of {totalRecords}"
      show-gridlines
      size="small"
      scrollable
      scroll-height="58vh"
      class="excel-grid no-print"
      @page="onPage"
    >
      <Column selection-mode="multiple" header-style="width: 2.75rem" />
      <Column header="#" header-style="width: 3.25rem" class="num-col">
        <template #body="{ index }">{{ dFirst + index + 1 }}</template>
      </Column>
      <Column header="Status" header-style="width: 5.75rem">
        <template #body="{ data }">
          <span v-if="data._error" class="row-error-text" :title="data._error">
            <i class="pi pi-exclamation-circle" /> Error
          </span>
          <Tag v-else-if="data._state === 'new'" severity="success" value="NEW" />
          <Tag v-else-if="data._state === 'dirty'" severity="warn" value="EDIT" />
          <span v-else class="row-clean-text">—</span>
        </template>
      </Column>

      <Column
        v-for="col in columns"
        :key="col.field"
        :header="col.header + (col.required ? ' *' : '')"
        :header-style="col.width ? { width: col.width } : undefined"
      >
        <template #body="{ data }">
          <slot v-if="col.type === 'slot'" :name="`cell-${col.field}`" :data="data" />
          <div v-else-if="col.compute" class="cell cell-computed">
            <span class="cell-computed__value">{{ col.compute(data) || '—' }}</span>
          </div>
          <div v-else-if="col.readonly" class="cell">
            <span class="cell-readonly" :title="displayValue(data, col)">{{ displayValue(data, col) || '—' }}</span>
          </div>
          <div v-else-if="col.type === 'select'" class="cell" :data-cell="cellId(data, col)">
            <Select
              v-model="data[col.field]"
              :options="rowCellOptions(col, data)"
              option-label="label"
              option-value="value"
              :placeholder="col.placeholder ?? 'Select…'"
              :filter="rowCellOptions(col, data).length > 8"
              show-clear
              fluid
              size="small"
              class="cell-select"
              :class="{ 'cell-invalid': invalidCell(data, col) }"
              @change="handleSelectChange(data, col)"
            />
          </div>
          <div v-else-if="col.type === 'checkbox'" class="cell cell-center" :data-cell="cellId(data, col)">
            <Checkbox
              v-model="data[col.field]"
              binary
              :invalid="invalidCell(data, col)"
              @change="markDirty(data)"
            />
          </div>
          <div v-else class="cell" :data-cell="cellId(data, col)">
            <InputText
              v-model="data[col.field]"
              :type="col.type === 'date' ? 'date' : 'text'"
              :inputmode="col.type === 'number' ? 'decimal' : undefined"
              :placeholder="col.placeholder ?? ''"
              fluid
              size="small"
              class="cell-input"
              :class="{ 'cell-invalid': invalidCell(data, col) }"
              @input="markDirty(data)"
              @keydown="onCellKeydown($event, data, col)"
            />
          </div>
        </template>
      </Column>

      <Column header="Actions" header-style="width: 5.5rem" class="no-print">
        <template #body="{ data }">
          <div class="row-actions">
            <slot name="row-actions" :data="data" />
            <button
              v-if="data._state === 'dirty' && data._original"
              class="icon-btn"
              title="Revert changes"
              @click="revertRow(data)"
            >
              <i class="pi pi-undo" />
            </button>
            <button class="icon-btn icon-btn--danger" title="Remove row" @click="discardRow(data)">
              <i class="pi pi-trash" />
            </button>
          </div>
        </template>
      </Column>

      <template #empty>
        <div class="grid-empty">
          No {{ title.toLowerCase() }} yet. Use <strong>Add row</strong> for a single entry,
          <strong>+5 Rows</strong> or <strong>Paste</strong> from Excel for bulk entry, then
          <strong>Save All</strong>.
        </div>
      </template>
    </DataTable>

    <div class="print-sheet" aria-hidden="true">
      <header class="print-sheet__header">
        <p class="print-sheet__eyebrow">Drilling Costing</p>
        <h1>{{ title }}</h1>
        <p class="print-sheet__meta">{{ printMeta }}</p>
      </header>
      <table v-if="filteredRows.length" class="print-sheet__table">
        <thead>
          <tr>
            <th>#</th>
            <th v-for="col in printColumns" :key="col.field">{{ col.header }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(row, index) in filteredRows" :key="row._key">
            <td>{{ index + 1 }}</td>
            <td v-for="col in printColumns" :key="col.field">{{ displayValue(row, col) }}</td>
          </tr>
        </tbody>
      </table>
      <p v-else class="print-sheet__empty">No {{ title.toLowerCase() }} to print.</p>
    </div>

    <Dialog v-model:visible="pasteVisible" modal :header="`Paste ${title} from Excel`" :style="{ width: '680px' }">
      <p class="paste-hint">
        Copy cells in Excel/Sheets and paste below (tab-separated). Column order:
        <strong>{{ pasteColumns.map(col => col.header).join(' · ') }}</strong>.
        <span v-if="pasteHint">{{ pasteHint }}</span>
      </p>
      <Textarea v-model="pasteText" rows="12" fluid autofocus placeholder="Paste rows here — one line per row, tabs between columns" />
      <template #footer>
        <Button label="Cancel" severity="secondary" text size="small" @click="pasteVisible = false" />
        <Button label="Add rows" icon="pi pi-check" size="small" :disabled="!pasteText.trim()" @click="applyPaste" />
      </template>
    </Dialog>

    <Dialog v-model:visible="bulkVisible" modal header="Bulk edit selected rows" :style="{ width: '460px' }">
      <div class="bulk-edit-form">
        <label class="bulk-edit-form__label">
          Field
          <Select v-model="bulkField" :options="bulkFieldOptions" option-label="label" option-value="value" placeholder="Select field" fluid size="small" />
        </label>
        <label class="bulk-edit-form__label">
          Value
          <InputText v-model="bulkValue" fluid size="small" placeholder="Value to apply" />
        </label>
        <p class="text-xs text-surface-500 mt-0 mb-0">Applies to {{ selectedCount }} selected row(s) — remember to Save All afterwards.</p>
      </div>
      <template #footer>
        <Button label="Cancel" severity="secondary" text size="small" @click="bulkVisible = false" />
        <Button label="Apply" icon="pi pi-check" size="small" :disabled="!bulkField || !selectedCount" @click="applyBulkEdit" />
      </template>
    </Dialog>
  </div>
</template>

<style scoped>
.excel-grid-panel {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.grid-toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
}

.grid-toolbar__search {
  position: relative;
  display: flex;
  align-items: center;
  min-width: 240px;
}

.grid-toolbar__search :deep(input) {
  padding-left: 2rem;
  width: 100%;
}

.grid-toolbar__search .pi-search {
  position: absolute;
  left: 0.65rem;
  color: var(--app-muted);
  font-size: 0.8rem;
  z-index: 1;
}

.grid-toolbar__actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.35rem;
}

/* --- Spreadsheet look: borderless cells that light up on focus --- */
.excel-grid :deep(.p-datatable-tbody > tr > td) {
  padding: 0.125rem 0.25rem;
}

.excel-grid :deep(td .p-inputtext),
.excel-grid :deep(td .p-select) {
  background: transparent;
  border-color: transparent;
  box-shadow: none;
}

.excel-grid :deep(td .p-inputtext:hover) {
  border-color: var(--app-border);
}

.excel-grid :deep(td .p-inputtext:focus),
.excel-grid :deep(td .p-select.p-focus) {
  border-color: var(--p-primary-color);
  background: var(--app-surface);
}

.excel-grid :deep(td .p-select) {
  width: 100%;
}

.excel-grid :deep(td .p-select-label) {
  padding: 0.3rem 0.5rem;
}

.cell :deep(input) {
  font-family: inherit;
}

.cell-center {
  display: flex;
  justify-content: center;
}

.cell-computed {
  justify-content: flex-end;
}

.cell-computed__value {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 0.74rem;
  font-weight: 700;
  color: var(--app-teal);
  white-space: nowrap;
  padding: 0 0.35rem;
}

.cell-readonly {
  display: inline-block;
  width: 100%;
  padding: 0.3rem 0.5rem;
  font-size: 0.76rem;
  color: var(--app-muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.cell-invalid,
.excel-grid :deep(.cell-invalid.p-inputtext),
.excel-grid :deep(.cell-invalid.p-select) {
  border-color: #e11d48 !important;
  background: rgb(225 29 72 / 6%) !important;
}

/* Row state tints */
.excel-grid :deep(tr.row-new) {
  background: rgb(15 118 110 / 7%);
}

.excel-grid :deep(tr.row-dirty) {
  background: rgb(217 119 6 / 9%);
}

.excel-grid :deep(tr.row-error) {
  background: rgb(225 29 72 / 10%);
}

.row-error-text {
  color: #e11d48;
  font-size: 0.68rem;
  font-weight: 600;
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
}

.row-clean-text {
  color: var(--app-muted);
}

.num-col :deep(.p-column-title) {
  font-size: 0.7rem;
}

.row-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 0.15rem;
}

.icon-btn {
  border: none;
  background: transparent;
  color: var(--app-muted);
  cursor: pointer;
  padding: 0.3rem;
  border-radius: 4px;
  font-size: 0.75rem;
  line-height: 1;
}

.icon-btn:hover {
  background: var(--app-bg);
  color: var(--p-primary-color);
}

.icon-btn--danger:hover {
  color: #e11d48;
}

.grid-empty {
  padding: 1.5rem 1rem;
  color: var(--app-muted);
  font-size: 0.85rem;
  text-align: center;
}

.paste-hint {
  font-size: 0.8rem;
  color: var(--app-muted);
  margin-top: 0;
}

.bulk-edit-form {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.bulk-edit-form__label {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
  color: var(--app-muted);
}

.save-errors {
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
  font-size: 0.78rem;
  max-height: 10rem;
  overflow-y: auto;
}

.print-sheet {
  display: none;
}
</style>
