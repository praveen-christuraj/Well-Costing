/**
 * Reusable enterprise data grid.
 *
 * Provides server-side pagination, a filter bar, an Excel-like inline editing
 * mode for bulk entry, TSV paste, per-row Edit/Delete actions, an optional
 * `row-actions` slot for entity-specific row buttons, Excel export,
 * a printable view, and feedback messages rendered beneath the action bar.
 */
<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import Button from 'primevue/button'
import Checkbox from 'primevue/checkbox'
import Column from 'primevue/column'
import ConfirmDialog from 'primevue/confirmdialog'
import DataTable, { type DataTableSortEvent } from 'primevue/datatable'
import DatePicker from 'primevue/datepicker'
import Dialog from 'primevue/dialog'
import InputNumber from 'primevue/inputnumber'
import InputText from 'primevue/inputtext'
import Message from 'primevue/message'
import Select from 'primevue/select'
import Tag from 'primevue/tag'
import Textarea from 'primevue/textarea'
import { useConfirm } from 'primevue/useconfirm'
import ImportWizard from '~/components/cost-library/ImportWizard.vue'
import { downloadBlob, exportFilename } from '~/utils/download'
import { parseTsv } from '~/utils/tsv'
import type { EditableRow, GridColumn, GridFilterDefinition } from '~/types/grid'
import type { PageResponse } from '~/types/masterData'

const props = defineProps<{
  /** Plural entity label, e.g. 'Service orders'. */
  title: string
  /** Singular label used in messages, e.g. 'service order'. */
  singular: string
  columns: GridColumn[]
  filters?: GridFilterDefinition[]
  /** Fetch one page of records from the API. */
  fetchPage: (params: Record<string, unknown>) => Promise<PageResponse<Record<string, unknown>>>
  /** Map an API record onto an editable row. */
  toRow: (record: Record<string, unknown>) => Record<string, unknown>
  /** Map an editable row onto an API write payload. */
  toPayload: (row: EditableRow) => Record<string, unknown>
  /** Create a blank row for bulk entry. */
  blankRow: () => Record<string, unknown>
  validateRows?: (rows: Record<string, unknown>[]) => Promise<{ valid: boolean, errors: { row_index: number, message: string }[] }>
  bulkCreate: (rows: Record<string, unknown>[]) => Promise<unknown>
  bulkUpdate: (rows: Record<string, unknown>[]) => Promise<unknown>
  removeRecord: (id: string, hard: boolean) => Promise<unknown>
  defaultSort?: string
  defaultSortOrder?: 'asc' | 'desc'
  /**
   * Registry entity key enabling the built-in Excel export, e.g. 'service-orders'.
   * Downloads `/export/{entity}` with the same headers the import template uses,
   * so an exported workbook can be edited and re-imported unchanged.
   */
  exportEntity?: string
  /** Custom export handler; overrides `exportEntity` when both are supplied. */
  onExport?: () => Promise<void>
  /** Registry entity key enabling the bulk Excel/CSV import wizard, e.g. 'units'. */
  importEntity?: string
  searchPlaceholder?: string
}>()

const confirm = useConfirm()
const masterData = useMasterData()

const rows = ref<EditableRow[]>([])
const selected = ref<EditableRow[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(25)
const search = ref('')
const filterValues = ref<Record<string, unknown>>({})
const sortField = ref(props.defaultSort ?? props.columns[0]?.field ?? 'created_at')
const sortOrder = ref<'asc' | 'desc'>(props.defaultSortOrder ?? 'asc')
const showInactive = ref(false)

const loading = ref(false)
const saving = ref(false)
const error = ref<string | null>(null)
const success = ref<string | null>(null)

const pasteVisible = ref(false)
const pasteText = ref('')
const importVisible = ref(false)
const exporting = ref(false)

const editableColumns = computed(() => props.columns.filter(column => !column.readonly))
const pasteColumns = computed(() => editableColumns.value.filter(column => !column.noPaste))
const pendingCount = computed(() => rows.value.filter(row => row._state !== 'clean').length)
const firstRecord = computed(() => (total.value === 0 ? 0 : (page.value - 1) * pageSize.value + 1))
const lastRecord = computed(() => Math.min(page.value * pageSize.value, total.value))
const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize.value)))
const activeFilterCount = computed(
  () => Object.values(filterValues.value).filter(value => value !== null && value !== undefined && value !== '').length
    + (search.value ? 1 : 0)
  + (showInactive.value ? 1 : 0),
)

function clearFeedback(): void {
  error.value = null
  success.value = null
}

function toDateString(value: unknown): string | null {
  if (!value) return null
  if (value instanceof Date) {
    const offset = value.getTimezoneOffset() * 60000
    return new Date(value.getTime() - offset).toISOString().slice(0, 10)
  }
  return String(value)
}

async function load(): Promise<void> {
  loading.value = true
  error.value = null
  try {
    const params: Record<string, unknown> = {
      page: page.value,
      page_size: pageSize.value,
      sort_by: sortField.value,
      sort_order: sortOrder.value,
    }
    if (search.value.trim()) params.search = search.value.trim()
    if (!showInactive.value) params.is_active = true
    for (const [key, value] of Object.entries(filterValues.value)) {
      if (value === null || value === undefined || value === '') continue
      params[key] = value instanceof Date ? toDateString(value) : value
    }
    const response = await props.fetchPage(params)
    rows.value = response.items.map(item => ({
      ...props.toRow(item),
      _state: 'clean' as const,
      _editing: false,
    }))
    total.value = response.total
    selected.value = []
  }
  catch (caught: unknown) {
    error.value = caught instanceof Error ? caught.message : `${props.title} could not be loaded`
  }
  finally {
    loading.value = false
  }
}

function markDirty(row: EditableRow): void {
  if (row._state === 'clean') row._state = 'dirty'
}

function addRows(count = 1): void {
  clearFeedback()
  rows.value.unshift(
    ...Array.from({ length: count }, () => ({
      ...props.blankRow(),
      _state: 'new' as const,
      _editing: true,
    })),
  )
}

function startEdit(row: EditableRow): void {
  clearFeedback()
  row._editing = true
}

function cancelRow(row: EditableRow): void {
  clearFeedback()
  if (row._state === 'new') {
    rows.value = rows.value.filter(candidate => candidate !== row)
    return
  }
  void load()
}

function duplicateRow(row: EditableRow): void {
  clearFeedback()
  const { id: _id, _state: _s, _editing: _e, ...copy } = row
  rows.value.unshift({ ...copy, _state: 'new', _editing: true })
}

function missingRequired(row: EditableRow): string[] {
  return props.columns
    .filter(column => column.required)
    .filter((column) => {
      const value = row[column.field]
      return value === null || value === undefined || value === ''
    })
    .map(column => column.header)
}

async function saveAll(): Promise<void> {
  clearFeedback()
  const newRows = rows.value.filter(row => row._state === 'new')
  const changedRows = rows.value.filter(row => row._state === 'dirty' && row.id)

  for (const row of [...newRows, ...changedRows]) {
    const missing = missingRequired(row)
    if (missing.length) {
      error.value = `Complete the required field(s) before saving: ${missing.join(', ')}.`
      return
    }
  }

  saving.value = true
  try {
    let savedCount = 0
    if (newRows.length) {
      const payload = newRows.map(row => props.toPayload(row))
      if (props.validateRows) {
        const validation = await props.validateRows(payload)
        if (!validation.valid) {
          throw new Error(
            validation.errors
              .map(item => `Row ${item.row_index + 1}: ${item.message}`)
              .join('; '),
          )
        }
      }
      await props.bulkCreate(payload)
      savedCount += newRows.length
    }
    if (changedRows.length) {
      await props.bulkUpdate(
        changedRows.map(row => ({ id: row.id, ...props.toPayload(row) })),
      )
      savedCount += changedRows.length
    }
    if (!savedCount) {
      success.value = 'There were no changes to save.'
      return
    }
    await load()
    success.value = `${savedCount} ${savedCount === 1 ? props.singular : props.title.toLowerCase()} saved successfully.`
  }
  catch (caught: unknown) {
    error.value = caught instanceof Error ? caught.message : 'The changes could not be saved.'
  }
  finally {
    saving.value = false
  }
}

function confirmDelete(row: EditableRow): void {
  clearFeedback()
  if (!row.id) {
    cancelRow(row)
    return
  }
  confirm.require({
    message: `Delete this ${props.singular}? It is removed permanently when it is not referenced elsewhere, otherwise it is deactivated.`,
    header: `Delete ${props.singular}`,
    icon: 'pi pi-exclamation-triangle',
    rejectProps: { label: 'Cancel', severity: 'secondary', outlined: true },
    acceptProps: { label: 'Delete', severity: 'danger' },
    accept: () => void removeRow(row),
  })
}

async function removeRow(row: EditableRow): Promise<void> {
  loading.value = true
  try {
    try {
      await props.removeRecord(String(row.id), true)
      success.value = `The ${props.singular} was deleted.`
    }
    catch {
      // Referenced records cannot be removed; fall back to deactivation.
      await props.removeRecord(String(row.id), false)
      success.value = `The ${props.singular} is referenced elsewhere, so it was deactivated instead of deleted.`
    }
    await load()
  }
  catch (caught: unknown) {
    error.value = caught instanceof Error ? caught.message : 'The record could not be deleted.'
  }
  finally {
    loading.value = false
  }
}

function confirmDeactivateSelected(): void {
  clearFeedback()
  confirm.require({
    message: `Deactivate ${selected.value.length} selected ${props.title.toLowerCase()}?`,
    header: 'Deactivate records',
    icon: 'pi pi-exclamation-triangle',
    rejectProps: { label: 'Cancel', severity: 'secondary', outlined: true },
    acceptProps: { label: 'Deactivate', severity: 'danger' },
    accept: () => void deactivateSelected(),
  })
}

async function deactivateSelected(): Promise<void> {
  loading.value = true
  try {
    const targets = selected.value.filter(row => row.id)
    await Promise.all(targets.map(row => props.removeRecord(String(row.id), false)))
    await load()
    success.value = `${targets.length} ${props.title.toLowerCase()} deactivated.`
  }
  catch (caught: unknown) {
    error.value = caught instanceof Error ? caught.message : 'The records could not be deactivated.'
  }
  finally {
    loading.value = false
  }
}

function applyPaste(): void {
  const parsed = parseTsv(pasteText.value, pasteColumns.value.map(column => ({ field: column.field })))
  const created = parsed.map((values) => {
    const row: Record<string, unknown> = { ...props.blankRow() }
    for (const column of pasteColumns.value) {
      const raw = values[column.field]
      if (raw === undefined || raw === '') continue
      row[column.field] = column.type === 'number' ? Number(raw) : raw
    }
    return { ...row, _state: 'new' as const, _editing: true }
  })
  rows.value.unshift(...created)
  pasteText.value = ''
  pasteVisible.value = false
  clearFeedback()
  success.value = `${created.length} row(s) added from the clipboard. Review them, then choose Save changes.`
}

const canExport = computed(() => Boolean(props.onExport || props.exportEntity))

/** Download the entity workbook, preferring a page-supplied handler. */
async function exportWorkbook(): Promise<void> {
  clearFeedback()
  exporting.value = true
  try {
    if (props.onExport) {
      await props.onExport()
    }
    else if (props.exportEntity) {
      const blob = await masterData.export(props.exportEntity)
      downloadBlob(blob, exportFilename(props.exportEntity))
    }
    else {
      return
    }
    success.value = `${props.title} exported to Excel.`
  }
  catch (caught: unknown) {
    error.value = caught instanceof Error
      ? `The export failed: ${caught.message}`
      : 'The export could not be generated.'
  }
  finally {
    exporting.value = false
  }
}

/**
 * Print the rows currently on screen. A print-only block (hidden on screen,
 * revealed by the print stylesheet) mirrors the grid as a plain table, so the
 * output is a clean sheet without editors, toolbars, or the actions column.
 * It is always rendered, so Ctrl+P produces the same result as this button.
 */
function printGrid(): void {
  clearFeedback()
  if (typeof window !== 'undefined' && typeof window.print === 'function') window.print()
}

/** Render one cell as plain text for the printable table. */
function printCell(row: EditableRow, column: GridColumn): string {
  if (column.type === 'checkbox') return row[column.field] ? 'Active' : 'Inactive'
  const rendered = displayValue(row, column)
  const suffix = column.suffixField ? row[column.suffixField] : ''
  return suffix ? `${rendered} ${String(suffix)}` : rendered
}

const printedAt = computed(() => new Date().toLocaleString())

function resetFilters(): void {
  search.value = ''
  filterValues.value = {}
  showInactive.value = false
  page.value = 1
  clearFeedback()
  void load()
}

function onSort(event: DataTableSortEvent): void {
  if (typeof event.sortField === 'string') sortField.value = event.sortField
  sortOrder.value = event.sortOrder === -1 ? 'desc' : 'asc'
  void load()
}

function goToPage(target: number): void {
  page.value = Math.min(Math.max(1, target), totalPages.value)
  void load()
}

function changePageSize(value: number): void {
  pageSize.value = value
  page.value = 1
  void load()
}

function formatNumber(value: unknown): string {
  if (value === null || value === undefined || value === '') return '—'
  const parsed = Number(value)
  if (Number.isNaN(parsed)) return String(value)
  return parsed.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function displayValue(row: EditableRow, column: GridColumn): string {
  if (column.display) return column.display(row)
  const value = row[column.field]
  if (column.numeric) return formatNumber(value)
  if (column.type === 'select' && column.options) {
    return column.options.find(option => option.value === value)?.label ?? (value ? String(value) : '—')
  }
  if (value === null || value === undefined || value === '') return '—'
  return String(value)
}

let searchTimer: ReturnType<typeof setTimeout> | undefined
watch(search, () => {
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    page.value = 1
    void load()
  }, 300)
})
watch([filterValues, showInactive], () => {
  page.value = 1
  void load()
}, { deep: true })

onMounted(() => void load())

defineExpose({ reload: load })
</script>

<template>
  <section class="eg">
    <ConfirmDialog />
    <ImportWizard
      v-if="importEntity"
      v-model:visible="importVisible"
      :entity="importEntity"
      :entity-label="title"
      @committed="load"
    />

    <!-- Filter bar -->
    <div class="eg__filters">
      <div class="eg__search">
        <i class="pi pi-search" aria-hidden="true" />
        <InputText
          v-model="search"
          :placeholder="searchPlaceholder ?? `Search ${title.toLowerCase()}…`"
          :aria-label="`Search ${title}`"
        />
      </div>

      <div v-for="filter in filters ?? []" :key="filter.key" class="eg__filter">
        <label :for="`filter-${filter.key}`">{{ filter.label }}</label>
        <Select
          v-if="filter.type === 'select'"
          :id="`filter-${filter.key}`"
          v-model="filterValues[filter.key]"
          :options="filter.options ?? []"
          option-label="label"
          option-value="value"
          :placeholder="filter.placeholder ?? 'All'"
          show-clear
          filter
          :style="{ width: filter.width ?? '190px' }"
        />
        <DatePicker
          v-else-if="filter.type === 'date'"
          :id="`filter-${filter.key}`"
          v-model="filterValues[filter.key] as Date | null"
          date-format="yy-mm-dd"
          show-icon
          icon-display="input"
          :placeholder="filter.placeholder ?? 'Any date'"
          :style="{ width: filter.width ?? '180px' }"
        />
        <InputText
          v-else
          :id="`filter-${filter.key}`"
          v-model="filterValues[filter.key] as string"
          :placeholder="filter.placeholder"
          :style="{ width: filter.width ?? '180px' }"
        />
      </div>

      <div class="eg__filter eg__filter--inline">
        <Checkbox v-model="showInactive" input-id="show-inactive" binary />
        <label for="show-inactive">Include inactive</label>
      </div>

      <Button
        v-if="activeFilterCount"
        label="Clear filters"
        icon="pi pi-filter-slash"
        severity="secondary"
        text
        @click="resetFilters"
      />
    </div>

    <!-- Action bar -->
    <div class="eg__actions">
      <div class="eg__actions-group">
        <Button label="Add row" icon="pi pi-plus" @click="addRows(1)" />
        <Button label="Add 5 rows" icon="pi pi-plus-circle" severity="secondary" outlined @click="addRows(5)" />
        <Button label="Paste from Excel" icon="pi pi-clipboard" severity="secondary" outlined @click="pasteVisible = true" />
      </div>
      <div class="eg__actions-group">
        <Button
          label="Deactivate selected"
          icon="pi pi-ban"
          severity="danger"
          text
          :disabled="!selected.length"
          @click="confirmDeactivateSelected"
        />
        <Button v-if="importEntity" label="Import" icon="pi pi-upload" severity="secondary" outlined @click="importVisible = true" />
        <Button
          v-if="canExport"
          label="Export"
          icon="pi pi-file-excel"
          severity="secondary"
          outlined
          :loading="exporting"
          @click="exportWorkbook"
        />
        <Button
          label="Print"
          icon="pi pi-print"
          severity="secondary"
          outlined
          @click="printGrid"
        />
        <slot name="actions" />
        <Button
          :label="pendingCount ? `Save changes (${pendingCount})` : 'Save changes'"
          icon="pi pi-save"
          :disabled="!pendingCount"
          :loading="saving"
          @click="saveAll"
        />
      </div>
    </div>

    <!-- Feedback sits immediately below the action buttons -->
    <div class="eg__feedback" aria-live="polite">
      <Message v-if="error" severity="error" :closable="true" @close="error = null">
        {{ error }}
      </Message>
      <Message v-if="success" severity="success" :closable="true" @close="success = null">
        {{ success }}
      </Message>
    </div>

    <DataTable
      v-model:selection="selected"
      :value="rows"
      :loading="loading"
      data-key="id"
      striped-rows
      show-gridlines
      size="small"
      scrollable
      scroll-height="560px"
      removable-sort
      :sort-field="sortField"
      :sort-order="sortOrder === 'desc' ? -1 : 1"
      class="eg__table"
      @sort="onSort"
    >
      <Column selection-mode="multiple" header-style="width: 3rem" :frozen="true" />
      <Column header="#" header-style="width: 3.5rem">
        <template #body="{ index }">
          <span class="eg__rownum">{{ (page - 1) * pageSize + index + 1 }}</span>
        </template>
      </Column>

      <Column
        v-for="column in columns"
        :key="column.field"
        :field="column.field"
        :header="column.header"
        :sortable="column.sortable"
        :style="column.width ? { minWidth: column.width } : { minWidth: '150px' }"
      >
        <template #body="{ data }">
          <!-- Edit mode -->
          <template v-if="(data._editing || data._state === 'new') && !column.readonly">
            <Select
              v-if="column.type === 'select'"
              v-model="data[column.field]"
              :options="column.options ?? []"
              option-label="label"
              option-value="value"
              :placeholder="column.placeholder ?? 'Select'"
              show-clear
              filter
              fluid
              :invalid="column.required && !data[column.field]"
              @change="markDirty(data)"
            />
            <DatePicker
              v-else-if="column.type === 'date'"
              v-model="data[column.field] as Date | null"
              date-format="yy-mm-dd"
              show-icon
              icon-display="input"
              fluid
              :invalid="column.required && !data[column.field]"
              @update:model-value="markDirty(data)"
            />
            <InputNumber
              v-else-if="column.type === 'number'"
              v-model="data[column.field] as number"
              :min-fraction-digits="2"
              :max-fraction-digits="4"
              fluid
              :invalid="column.required && (data[column.field] === null || data[column.field] === '')"
              @input="markDirty(data)"
            />
            <Checkbox
              v-else-if="column.type === 'checkbox'"
              v-model="data[column.field]"
              binary
              @change="markDirty(data)"
            />
            <Textarea
              v-else-if="column.type === 'textarea'"
              v-model="data[column.field] as string"
              rows="1"
              auto-resize
              fluid
              @input="markDirty(data)"
            />
            <InputText
              v-else
              v-model="data[column.field] as string"
              fluid
              :placeholder="column.placeholder"
              :invalid="column.required && !data[column.field]"
              @input="markDirty(data)"
            />
          </template>

          <!-- Read mode -->
          <template v-else>
            <Tag
              v-if="column.type === 'checkbox'"
              :value="data[column.field] ? 'Active' : 'Inactive'"
              :severity="data[column.field] ? 'success' : 'secondary'"
            />
            <span v-else :class="{ 'eg__num': column.numeric }">
              {{ displayValue(data, column) }}
              <small v-if="column.suffixField && data[column.suffixField]" class="eg__suffix">
                {{ data[column.suffixField] }}
              </small>
            </span>
          </template>
        </template>
      </Column>

      <Column header="Actions" :frozen="true" align-frozen="right" header-style="width: 12rem">
        <template #body="{ data }">
          <div class="eg__row-actions">
            <template v-if="data._editing || data._state === 'new'">
              <Button
                label="Done"
                icon="pi pi-check"
                size="small"
                severity="success"
                text
                @click="data._editing = false"
              />
              <Button
                label="Cancel"
                icon="pi pi-times"
                size="small"
                severity="secondary"
                text
                @click="cancelRow(data)"
              />
            </template>
            <template v-else>
              <!-- Entity-specific actions, e.g. "Revise rate" on master rates. -->
              <slot name="row-actions" :row="data" />
              <Button
                v-tooltip.top="'Edit'"
                icon="pi pi-pencil"
                size="small"
                severity="secondary"
                text
                aria-label="Edit"
                @click="startEdit(data)"
              />
              <Button
                v-tooltip.top="'Duplicate'"
                icon="pi pi-copy"
                size="small"
                severity="secondary"
                text
                aria-label="Duplicate"
                @click="duplicateRow(data)"
              />
              <Button
                v-tooltip.top="'Delete'"
                icon="pi pi-trash"
                size="small"
                severity="danger"
                text
                aria-label="Delete"
                @click="confirmDelete(data)"
              />
            </template>
          </div>
        </template>
      </Column>

      <template #empty>
        <div class="eg__empty">
          <i class="pi pi-inbox" aria-hidden="true" />
          <p><strong>No {{ title.toLowerCase() }} found.</strong></p>
          <p>Add a row, paste rows from Excel, or relax the filters above.</p>
        </div>
      </template>
    </DataTable>

    <!-- Server-side pagination -->
    <div class="eg__pager">
      <span class="eg__pager-info">
        Showing <strong>{{ firstRecord }}</strong>–<strong>{{ lastRecord }}</strong>
        of <strong>{{ total }}</strong> {{ title.toLowerCase() }}
      </span>
      <div class="eg__pager-controls">
        <label for="page-size">Rows</label>
        <Select
          id="page-size"
          :model-value="pageSize"
          :options="[10, 25, 50, 100, 200]"
          style="width: 92px"
          @update:model-value="changePageSize"
        />
        <Button icon="pi pi-angle-double-left" text :disabled="page === 1" aria-label="First page" @click="goToPage(1)" />
        <Button icon="pi pi-angle-left" text :disabled="page === 1" aria-label="Previous page" @click="goToPage(page - 1)" />
        <span class="eg__pager-page">Page {{ page }} of {{ totalPages }}</span>
        <Button icon="pi pi-angle-right" text :disabled="page >= totalPages" aria-label="Next page" @click="goToPage(page + 1)" />
        <Button icon="pi pi-angle-double-right" text :disabled="page >= totalPages" aria-label="Last page" @click="goToPage(totalPages)" />
      </div>
    </div>

    <!-- Print-only rendering: hidden on screen, used by the browser print dialog -->
    <div class="eg__print" aria-hidden="true">
      <header class="eg__print-header">
        <h2>{{ title }}</h2>
        <p>
          {{ total }} record(s) · page {{ page }} of {{ totalPages }} · printed {{ printedAt }}
        </p>
      </header>
      <table class="eg__print-table">
        <thead>
          <tr>
            <th>#</th>
            <th v-for="column in columns" :key="column.field">{{ column.header }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(row, index) in rows" :key="String(row.id ?? index)">
            <td>{{ (page - 1) * pageSize + index + 1 }}</td>
            <td v-for="column in columns" :key="column.field" :class="{ 'eg__num': column.numeric }">
              {{ printCell(row, column) }}
            </td>
          </tr>
        </tbody>
      </table>
      <p v-if="!rows.length" class="eg__print-empty">No {{ title.toLowerCase() }} matched the current filters.</p>
    </div>

    <Dialog v-model:visible="pasteVisible" modal header="Paste rows from Excel" :style="{ width: '760px' }">
      <p class="eg__paste-hint">
        Copy cells directly from your workbook. Columns are read in this order:
      </p>
      <ol class="eg__paste-columns">
        <li v-for="column in pasteColumns" :key="column.field">
          {{ column.header }}
        </li>
      </ol>
      <Textarea v-model="pasteText" rows="12" fluid autofocus placeholder="Paste tab-separated rows here" />
      <template #footer>
        <Button label="Cancel" severity="secondary" outlined @click="pasteVisible = false" />
        <Button label="Add rows" icon="pi pi-check" :disabled="!pasteText.trim()" @click="applyPaste" />
      </template>
    </Dialog>
  </section>
</template>
