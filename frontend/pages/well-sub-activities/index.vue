<script setup lang="ts">
/**
 * Well Sub Activities — completely well scoped.
 *
 * The user first picks the Rig and then the corresponding Well; every sub
 * activity entered afterwards belongs to that well and the grid reloads when
 * the well context changes. Columns:
 *   • Sub Activity Code  — manual, mandatory, never duplicated within the well
 *   • Sub Activity Name  — manual, mandatory
 *   • Activity           — dropdown controlled by the Master Data Activities
 *   • Responsible Party/Company — manual, mandatory
 *   • Description/Remarks — manual, mandatory
 *
 * Both tabs (Sub Activities + Deleted Entries) are scoped to the selected well
 * and carry the common template: Import (XLSX/CSV), XLSX/CSV export, Print,
 * edit and soft delete, with every action audit-logged server-side.
 */
import { computed, onMounted, ref, watch } from 'vue'
import Button from 'primevue/button'
import Message from 'primevue/message'
import Select from 'primevue/select'
import PageHeader from '~/components/design-system/PageHeader.vue'
import ExcelGrid from '~/components/master-data/ExcelGrid.vue'
import ImportDialog from '~/components/master-data/ImportDialog.vue'
import type { EditableGridRow, GridColumn, GridSelectOption } from '~/types/grid'
import { matchesAdvancedSearch } from '~/utils/search'

definePageMeta({ middleware: 'auth' })

const api = useApi()

const TAB_ENTRIES = 0
const TAB_DELETED = 1

const tabs = [
  { label: 'Well Sub Activities', icon: 'pi pi-list-check' },
  { label: 'Deleted Entries', icon: 'pi pi-trash' },
]

const activeTab = ref(0)
const tabDirty = ref(false)

function switchTab(index: number): void {
  if (index === activeTab.value) return
  if (tabDirty.value && !window.confirm('This tab has unsaved rows. Switch tab and discard the unsaved entries?')) return
  activeTab.value = index
  tabDirty.value = false
}

// ---------------------------------------------------------------------------
// Well context: rig → well selection drives everything else on the page
// ---------------------------------------------------------------------------

interface RigDropdown { id: number, rig_code: string, rig_name: string, display_name: string }
interface WellRecord {
  id: number
  rig_id: number
  well_code: string
  well_name: string
  status: string
  [key: string]: unknown
}
interface ActivityRecord {
  id: number
  activity_code: string
  activity_name: string
  [key: string]: unknown
}

const rigs = ref<RigDropdown[]>([])
const wells = ref<WellRecord[]>([])
const activities = ref<ActivityRecord[]>([])
const lookupError = ref<string | null>(null)

const selectedRigId = ref<number | null>(null)
const selectedWellId = ref<number | null>(null)
/** Selected-but-rejected values so a cancelled switch keeps the old context. */
const rigSelectorValue = ref<number | null>(null)
const wellSelectorValue = ref<number | null>(null)

const filteredWells = computed(() =>
  selectedRigId.value == null
    ? wells.value
    : wells.value.filter(well => well.rig_id === selectedRigId.value),
)

const rigOptions = computed(() => rigs.value)
const wellOptions = computed(() =>
  filteredWells.value.map(well => ({ ...well, display: `${well.well_code} - ${well.well_name}` })),
)
const selectedWell = computed<WellRecord | null>(() =>
  wells.value.find(well => well.id === selectedWellId.value) ?? null,
)
const selectedRig = computed<RigDropdown | null>(() =>
  rigs.value.find(rig => rig.id === selectedRigId.value) ?? null,
)

const hasRigs = computed(() => rigs.value.length > 0)
const hasWellsForRig = computed(() => filteredWells.value.length > 0)
const hasActivities = computed(() => activities.value.length > 0)

const activityOptions = computed<GridSelectOption[]>(() =>
  activities.value.map(activity => ({
    label: `${activity.activity_code} - ${activity.activity_name}`,
    value: activity.id,
  })),
)

async function loadLookups(): Promise<void> {
  lookupError.value = null
  try {
    const [rigList, wellList, activityList] = await Promise.all([
      api.get<RigDropdown[]>('/rig-well/rigs/dropdown'),
      api.get<WellRecord[]>('/rig-well/wells'),
      api.get<ActivityRecord[]>('/master-data/activities'),
    ])
    rigs.value = rigList
    wells.value = wellList
    activities.value = activityList
    // A rig/well may have disappeared (or a new well appeared) since the
    // context was picked — drop a stale selection so nothing loads sideways.
    if (selectedRigId.value != null && !rigs.value.some(rig => rig.id === selectedRigId.value)) {
      selectedRigId.value = null
      rigSelectorValue.value = null
      selectedWellId.value = null
      wellSelectorValue.value = null
    }
    if (selectedWellId.value != null && !filteredWells.value.some(well => well.id === selectedWellId.value)) {
      selectedWellId.value = null
      wellSelectorValue.value = null
    }
  }
  catch (caught: unknown) {
    lookupError.value = caught instanceof Error ? caught.message : 'Rigs, wells or activities could not be loaded'
  }
}

function confirmDiscardUnsaved(action: string): boolean {
  if (!tabDirty.value) return true
  return window.confirm(`This well has unsaved sub activities. ${action} and discard the unsaved entries?`)
}

function onRigChange(value: number | null): void {
  if (value === selectedRigId.value) return
  if (!confirmDiscardUnsaved('Switch rig')) {
    rigSelectorValue.value = selectedRigId.value
    return
  }
  tabDirty.value = false
  selectedRigId.value = value
  rigSelectorValue.value = value
  selectedWellId.value = null
  wellSelectorValue.value = null
}

function onWellChange(value: number | null): void {
  if (value === selectedWellId.value) return
  if (!confirmDiscardUnsaved('Switch well')) {
    wellSelectorValue.value = selectedWellId.value
    return
  }
  tabDirty.value = false
  selectedWellId.value = value
  wellSelectorValue.value = value
  if (activeTab.value === TAB_DELETED) void loadDeleted()
}

// ---------------------------------------------------------------------------
// Sub Activities tab (bulk entry grid)
// ---------------------------------------------------------------------------

const subActivityColumns = computed<GridColumn[]>(() => [
  {
    field: 'sub_activity_code',
    header: 'Sub Activity Code',
    required: true,
    width: '150px',
    placeholder: 'e.g. RIH-01',
  },
  {
    field: 'sub_activity_name',
    header: 'Sub Activity Name',
    required: true,
    width: '220px',
    placeholder: 'e.g. Run in hole with tubing',
  },
  {
    field: 'activity_id',
    header: 'Activity',
    type: 'select',
    options: activityOptions.value,
    required: true,
    width: '220px',
    noPaste: true,
    placeholder: 'Select activity',
  },
  {
    field: 'responsible_party',
    header: 'Responsible Party/Company',
    required: true,
    width: '200px',
    placeholder: 'e.g. Schlumberger',
  },
  {
    field: 'description',
    header: 'Description/Remarks',
    required: true,
    width: '280px',
    placeholder: 'Describe the sub activity',
  },
])

function subActivityToRow(record: Record<string, unknown>): Record<string, unknown> {
  return {
    _id: record.id as number | null,
    sub_activity_code: record.sub_activity_code,
    sub_activity_name: record.sub_activity_name,
    activity_id: record.activity_id ?? null,
    responsible_party: record.responsible_party,
    description: record.description,
  }
}

function subActivityToPayload(row: EditableGridRow): Record<string, unknown> {
  return {
    well_id: selectedWellId.value,
    sub_activity_code: String(row.sub_activity_code ?? '').trim(),
    sub_activity_name: String(row.sub_activity_name ?? '').trim(),
    activity_id: row.activity_id,
    responsible_party: String(row.responsible_party ?? '').trim(),
    description: String(row.description ?? '').trim(),
  }
}

const printSubtitle = computed(() => {
  if (!selectedRig.value || !selectedWell.value) return ''
  return `Rig: ${selectedRig.value.display_name} · Well: ${selectedWell.value.well_code} - ${selectedWell.value.well_name}`
})

// ---------------------------------------------------------------------------
// Import / Export / Print
// ---------------------------------------------------------------------------

const showImport = ref(false)
const importEndpoint = computed(() => `/well-sub-activities/import?well_id=${selectedWellId.value}`)

function exportSubActivities(format: 'xlsx' | 'csv'): void {
  if (selectedWellId.value == null) return
  api.download(`/well-sub-activities/export?format=${format}&well_id=${selectedWellId.value}`).then((blob) => {
    const url = window.URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = `well_sub_activities_${selectedWell.value?.well_code ?? 'export'}.${format}`
    anchor.click()
    window.URL.revokeObjectURL(url)
  }).catch((error: unknown) => {
    console.error('Export failed', error)
  })
}

function printPage(): void {
  window.print()
}

// ---------------------------------------------------------------------------
// Deleted Entries tab (scoped to the selected well)
// ---------------------------------------------------------------------------

interface SubActivityRow {
  id: number
  well_id: number
  sub_activity_code: string
  sub_activity_name: string
  activity_id: number | null
  responsible_party: string
  description: string
  deleted_at?: string | null
  activity_code?: string | null
  activity_name?: string | null
  activity_display?: string | null
  [key: string]: unknown
}

const deletedRecords = ref<SubActivityRow[]>([])
const deletedLoading = ref(false)
const trashSearch = ref('')

const filteredTrash = computed(() =>
  deletedRecords.value.filter(item => matchesAdvancedSearch(item, trashSearch.value)),
)

async function loadDeleted(): Promise<void> {
  if (selectedWellId.value == null) {
    deletedRecords.value = []
    return
  }
  deletedLoading.value = true
  try {
    deletedRecords.value = await api.get<SubActivityRow[]>(`/well-sub-activities/deleted?well_id=${selectedWellId.value}`)
  }
  catch (error) {
    console.error('Failed to load deleted entries', error)
  }
  finally {
    deletedLoading.value = false
  }
}

async function restoreRecord(item: SubActivityRow): Promise<void> {
  try {
    await api.post(`/well-sub-activities/${item.id}/restore`, {})
    await loadDeleted()
    reloadKey.value += 1
  }
  catch (error: unknown) {
    window.alert(error instanceof Error ? error.message : 'Restore failed')
  }
}

async function permanentDelete(item: SubActivityRow): Promise<void> {
  if (!window.confirm(`Permanently delete sub activity ${item.sub_activity_code}? This cannot be undone.`)) return
  try {
    await api.delete(`/well-sub-activities/${item.id}/permanent`)
    await loadDeleted()
  }
  catch (error: unknown) {
    window.alert(error instanceof Error ? error.message : 'Permanent delete failed')
  }
}

/** Bumped to remount the grid (fresh load) after restores/imports. */
const reloadKey = ref(0)

onMounted(() => {
  void loadLookups()
})

watch(activeTab, (tab) => {
  if (tab === TAB_DELETED) void loadDeleted()
  if (tab === TAB_ENTRIES) void loadLookups()
})
</script>

<template>
  <div class="sub-activities-page">
    <PageHeader
      class="no-print"
      title="Well Sub Activities"
      description="Break each well's main Activities down into the sub activities executed by the responsible parties/companies. Everything here is completely well scoped: pick the rig and the corresponding well first, then enter the sub activities — code, name, the controlling Activity from Master Data, the responsible party/company and the description/remarks. Import (XLSX/CSV), export, print, soft delete and full audit logging included."
    />

    <!-- Well context selector -->
    <section class="context-card grid-card no-print">
      <div class="context-fields">
        <label class="context-field">
          <span class="context-label">Rig</span>
          <Select
            :model-value="rigSelectorValue"
            :options="rigOptions"
            option-label="display_name"
            option-value="id"
            placeholder="Select rig"
            filter
            filter-placeholder="Search rigs…"
            size="small"
            class="context-select"
            :disabled="!hasRigs"
            @update:model-value="onRigChange"
          />
        </label>
        <label class="context-field">
          <span class="context-label">Well</span>
          <Select
            :model-value="wellSelectorValue"
            :options="wellOptions"
            option-label="display"
            option-value="id"
            placeholder="Select well"
            filter
            filter-placeholder="Search wells…"
            size="small"
            class="context-select"
            :disabled="selectedRigId == null || !hasWellsForRig"
            @update:model-value="onWellChange"
          />
        </label>
        <div v-if="selectedRig && selectedWell" class="context-summary">
          <i class="pi pi-check-circle" />
          <span>
            Entering sub activities for
            <strong>{{ selectedWell.well_code }} - {{ selectedWell.well_name }}</strong>
            under <strong>{{ selectedRig.display_name }}</strong>
          </span>
        </div>
      </div>
      <Message v-if="!hasRigs" severity="warn" :closable="false" class="context-message">
        No rigs yet — create a rig in Rig &amp; Well Management first, then return here.
      </Message>
      <Message v-else-if="selectedRigId != null && !hasWellsForRig" severity="warn" :closable="false" class="context-message">
        No wells under this rig yet — create the wells in Rig &amp; Well Management first.
      </Message>
      <Message v-else-if="selectedWellId == null" severity="info" :closable="false" class="context-message">
        Select the rig and the corresponding well above to start entering sub activities.
      </Message>
    </section>

    <Message v-if="lookupError" severity="warn" :closable="false" class="no-print">{{ lookupError }}</Message>
    <Message v-if="selectedWellId != null && !hasActivities" severity="warn" :closable="false" class="no-print">
      No Activities defined yet — the Activity dropdown is controlled by Master Data; define the activities on the Master Data page first.
    </Message>

    <template v-if="selectedWellId != null">
      <div class="tabs no-print">
        <button
          v-for="(tab, index) in tabs"
          :key="tab.label"
          class="tabs__item"
          :class="{ 'tabs__item--active': activeTab === index, 'tabs__item--danger': index === TAB_DELETED }"
          @click="switchTab(index)"
        >
          <i :class="tab.icon" />
          {{ tab.label }}
        </button>
      </div>

      <!-- Sub Activities -->
      <section v-if="activeTab === TAB_ENTRIES" class="grid-card">
        <ExcelGrid
          :key="`${selectedWellId}-${reloadKey}`"
          title="Well Sub Activities"
          singular="sub activity"
          :columns="subActivityColumns"
          code-field="sub_activity_code"
          paste-hint="Paste order: Sub Activity Code → Sub Activity Name → Responsible Party/Company → Description/Remarks. The Activity dropdown is excluded from paste — set it in the grid afterwards."
          :print-subtitle="printSubtitle"
          :load-records="() => api.get(`/well-sub-activities?well_id=${selectedWellId}`)"
          :to-row="subActivityToRow"
          :to-payload="subActivityToPayload"
          :create-record="(payload: Record<string, unknown>) => api.post('/well-sub-activities', payload)"
          :update-record="(id: number, payload: Record<string, unknown>) => api.put(`/well-sub-activities/${id}`, payload)"
          :delete-record="(id: number) => api.delete(`/well-sub-activities/${id}`)"
          @dirty="tabDirty = $event"
        >
          <template #toolbar-extra>
            <Button label="Import" icon="pi pi-upload" size="small" severity="secondary" outlined @click="showImport = true" />
            <Button label="XLSX" icon="pi pi-file-excel" size="small" severity="success" outlined @click="exportSubActivities('xlsx')" />
            <Button label="CSV" icon="pi pi-file" size="small" severity="secondary" outlined @click="exportSubActivities('csv')" />
            <Button label="Print" icon="pi pi-print" size="small" severity="secondary" text @click="printPage" />
          </template>
        </ExcelGrid>
      </section>

      <!-- Deleted Entries -->
      <section v-else-if="activeTab === TAB_DELETED" class="grid-card">
        <div class="trash-head no-print">
          <h3 class="trash-title">
            Deleted Entries (Trash) — {{ deletedRecords.length }} items
          </h3>
          <div class="trash-head__right">
            <div class="trash-search">
              <i class="pi pi-search" />
              <input v-model="trashSearch" type="search" placeholder="Search trash…" class="trash-search__input">
            </div>
            <span class="trash-subtitle">Restore or permanently delete. All actions are audit-logged.</span>
          </div>
        </div>
        <div class="table-scroll">
          <table class="trash-table">
            <thead>
              <tr>
                <th>Sub Activity Code</th>
                <th>Sub Activity Name</th>
                <th>Activity</th>
                <th>Responsible Party</th>
                <th>Deleted At</th>
                <th class="text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              <tr v-if="deletedLoading">
                <td colspan="6" class="empty-cell">
                  <i class="pi pi-spin pi-spinner" /> Loading deleted entries…
                </td>
              </tr>
              <tr v-else-if="filteredTrash.length === 0">
                <td colspan="6" class="empty-cell">
                  {{ deletedRecords.length ? 'No deleted entries match the search.' : 'No deleted entries for this well.' }}
                </td>
              </tr>
              <tr v-for="item in filteredTrash" :key="item.id">
                <td class="mono">{{ item.sub_activity_code }}</td>
                <td class="truncate" :title="item.sub_activity_name">{{ item.sub_activity_name }}</td>
                <td class="truncate" :title="item.activity_display ?? ''">{{ item.activity_display || '—' }}</td>
                <td class="truncate" :title="item.responsible_party">{{ item.responsible_party }}</td>
                <td class="muted">{{ item.deleted_at ? new Date(item.deleted_at).toLocaleString() : '—' }}</td>
                <td class="text-right trash-actions">
                  <Button label="Restore" size="small" severity="success" outlined @click="restoreRecord(item)" />
                  <Button label="Delete" size="small" severity="danger" outlined @click="permanentDelete(item)" />
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </template>

    <ImportDialog
      v-if="selectedWellId != null"
      v-model:visible="showImport"
      title="Bulk Import Sub Activities (CSV / XLSX)"
      :endpoint="importEndpoint"
      template-endpoint="/well-sub-activities/import-template"
      template-filename="well_sub_activities_template.xlsx"
      hint="Headers: sub_activity_code, sub_activity_name, activity, responsible_party, description. All columns are mandatory, rows import into the currently selected well, the activity accepts a Master Data activity code or name, and sub_activity_code must be unique within the well (an existing code is updated, not duplicated)."
      @committed="reloadKey += 1"
    />
  </div>
</template>

<style scoped>
  .sub-activities-page {
    display: grid;
    gap: 14px;
  }

  .grid-card {
    background: var(--app-surface);
    border: 1px solid var(--app-border);
    border-radius: 12px;
    box-shadow: var(--app-shadow);
    padding: 1rem;
  }

  .context-card {
    padding-bottom: 0.8rem;
  }

  .context-fields {
    display: flex;
    flex-wrap: wrap;
    align-items: flex-end;
    gap: 12px;
  }

  .context-field {
    display: grid;
    gap: 4px;
    min-width: 260px;
    flex: 0 1 300px;
  }

  .context-label {
    font-size: .72rem;
    font-weight: 700;
    letter-spacing: .04em;
    text-transform: uppercase;
    color: var(--app-muted);
  }

  .context-select {
    width: 100%;
  }

  .context-summary {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 6px 12px;
    border: 1px solid var(--app-border);
    border-radius: 8px;
    background: color-mix(in srgb, var(--p-primary-color, var(--app-teal)) 8%, var(--app-surface));
    font-size: .78rem;
    color: var(--app-ink);
  }

  .context-summary .pi {
    color: var(--p-primary-color, var(--app-teal));
  }

  .context-message {
    margin-top: 10px;
  }

  .table-scroll {
    overflow: auto;
    max-height: 62vh;
    border: 1px solid var(--app-border);
    border-radius: 10px;
  }

  .trash-table {
    width: 100%;
    border-collapse: collapse;
    font-size: .78rem;
  }

  .trash-table thead th {
    position: sticky;
    top: 0;
    z-index: 1;
    padding: 6px 8px;
    background: var(--app-bg);
    color: var(--app-ink);
    font-size: .68rem;
    font-weight: 750;
    letter-spacing: .04em;
    text-transform: uppercase;
    text-align: left;
    white-space: nowrap;
    border-bottom: 1px solid var(--app-border);
  }

  .trash-table tbody td {
    padding: 5px 8px;
    border-bottom: 1px solid var(--app-border);
    vertical-align: middle;
  }

  .trash-table tbody tr:hover td {
    background: color-mix(in srgb, var(--app-bg) 60%, transparent);
  }

  .trash-head {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
    margin-bottom: 10px;
  }

  .trash-title {
    margin: 0;
    font-size: .9rem;
  }

  .trash-head__right {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 10px;
  }

  .trash-subtitle {
    color: var(--app-muted);
    font-size: .72rem;
  }

  .trash-search {
    position: relative;
  }

  .trash-search i {
    position: absolute;
    top: 50%;
    left: 10px;
    color: var(--app-muted);
    transform: translateY(-50%);
  }

  .trash-search__input {
    padding: 6px 10px 6px 30px;
    border: 1px solid var(--app-border);
    border-radius: 8px;
    background: var(--app-surface);
    color: var(--app-ink);
    font-size: .78rem;
  }

  .trash-actions {
    display: flex;
    justify-content: flex-end;
    gap: 4px;
  }

  .truncate {
    max-width: 220px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .mono {
    font-variant-numeric: tabular-nums;
  }

  .muted {
    color: var(--app-muted);
  }

  .text-right {
    text-align: right;
  }

  .empty-cell {
    padding: 22px 10px;
    color: var(--app-muted);
    text-align: center;
  }

  @media print {
    .context-card,
    .tabs {
      display: none !important;
    }
  }
</style>
