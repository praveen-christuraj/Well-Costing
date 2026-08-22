/** Well-scoped Sub-Activities — configure Planned, NPT-1, NPT-2, UPA-1, etc.

After selecting a well, the user configures sub-activities linked to a primary
activity (Planned, NPT, UPA) from master data. Each sub-activity has a
responsible party for cost accountability.
*/
<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import Button from 'primevue/button'
import Column from 'primevue/column'
import DataTable from 'primevue/datatable'
import InputText from 'primevue/inputtext'
import Message from 'primevue/message'
import Select from 'primevue/select'
import Textarea from 'primevue/textarea'
import PageHeader from '~/components/design-system/PageHeader.vue'
import type { WellRecord } from '~/types/afe'
import type { ActivityRecord, WellActivityRecord } from '~/types/dailyCost'
import type { MasterDataRecord } from '~/types/masterData'

definePageMeta({ middleware: 'auth' })

const afeApi = useAfe()
const wellActApi = useWellActivities()
const master = useMasterData()

const wells = ref<WellRecord[]>([])
const selectedWellId = ref<string>('')
const activities = ref<ActivityRecord[]>([])

const loading = ref(false)
const error = ref<string | null>(null)
const success = ref<string | null>(null)

// Inline editing state
interface EditableRow {
  id?: string
  activity_id: string
  name: string
  responsible_party: string
  description: string
  is_active: boolean
  _state: 'clean' | 'new' | 'dirty'
}

const rows = ref<EditableRow[]>([])

const selectedWell = computed(() => wells.value.find(w => w.id === selectedWellId.value))
const activityOptions = computed(() =>
  activities.value.map(a => ({ label: `${a.code} — ${a.name}`, value: a.id })),
)

async function loadWells(): Promise<void> {
  try {
    const result = await afeApi.listWells()
    wells.value = result.items || []
  }
  catch (e: any) {
    error.value = e?.message || 'Failed to load wells'
  }
}

async function loadActivities(): Promise<void> {
  try {
    const result = await master.list('activities')
    activities.value = (result.items || []) as ActivityRecord[]
  }
  catch (e: any) {
    error.value = e?.message || 'Failed to load activities'
  }
}

async function loadWellActivities(): Promise<void> {
  if (!selectedWellId.value) {
    rows.value = []
    return
  }
  loading.value = true
  error.value = null
  try {
    await wellActApi.loadForWell(selectedWellId.value)
    rows.value = wellActApi.wellActivities.value.map(r => ({
      id: r.id,
      activity_id: r.activity_id,
      name: r.name,
      responsible_party: r.responsible_party ?? '',
      description: r.description ?? '',
      is_active: r.is_active,
      _state: 'clean',
    }))
  }
  catch (e: any) {
    error.value = e?.message || 'Failed to load well activities'
    rows.value = []
  }
  finally {
    loading.value = false
  }
}

function addRow(): void {
  rows.value.push({
    activity_id: activities.value[0]?.id ?? '',
    name: '',
    responsible_party: '',
    description: '',
    is_active: true,
    _state: 'new',
  })
}

function removeRow(index: number): void {
  rows.value.splice(index, 1)
}

async function saveAll(): Promise<void> {
  if (!selectedWellId.value) return
  error.value = null
  success.value = null
  loading.value = true

  let saved = 0
  let failed = 0

  for (const row of rows.value) {
    try {
      if (row._state === 'new') {
        const result = await wellActApi.createActivity({
          well_id: selectedWellId.value,
          activity_id: row.activity_id,
          name: row.name,
          responsible_party: row.responsible_party || null,
          description: row.description || null,
        })
        if (result) {
          row.id = result.id
          row._state = 'clean'
          saved++
        }
        else {
          failed++
        }
      }
      else if (row._state === 'dirty' && row.id) {
        const result = await wellActApi.updateActivity(row.id, {
          activity_id: row.activity_id,
          name: row.name,
          responsible_party: row.responsible_party || null,
          description: row.description || null,
          is_active: row.is_active,
        })
        if (result) {
          row._state = 'clean'
          saved++
        }
        else {
          failed++
        }
      }
    }
    catch (e: any) {
      failed++
      error.value = e?.message || 'Save failed'
    }
  }

  if (saved > 0) {
    success.value = `Saved ${saved} sub-activit${saved === 1 ? 'y' : 'ies'}.`
  }
  if (failed > 0) {
    error.value = `${failed} sub-activit${failed === 1 ? 'y' : 'ies'} failed to save.`
  }

  loading.value = false
  await loadWellActivities()
}

function markDirty(row: EditableRow): void {
  if (row._state === 'clean') row._state = 'dirty'
}

onMounted(async () => {
  await Promise.all([loadWells(), loadActivities()])
})

watch(selectedWellId, () => {
  void loadWellActivities()
})
</script>

<template>
  <div class="library-page">
    <PageHeader
      title="Well Sub-Activities"
      description="Configure well-scoped sub-activities (Planned, NPT-1, NPT-2, UPA-1, etc.) after creating a well. Each sub-activity belongs to a primary activity and has a responsible party for cost accountability."
    />

    <div class="selector-bar">
      <div class="selector-field">
        <label>Select Well</label>
        <Select
          v-model="selectedWellId"
          :options="wells"
          option-label="name"
          option-value="id"
          filter
          placeholder="Choose a well…"
          style="min-width: 300px"
        >
          <template #option="{ option }">
            {{ option.code }} — {{ option.name }}
          </template>
        </Select>
      </div>
      <div v-if="selectedWell" class="well-info">
        <span class="well-badge">{{ selectedWell.code }}</span>
        <span class="well-status">{{ selectedWell.status }}</span>
      </div>
    </div>

    <Message v-if="error" severity="error" :closable="false" class="mb-3">{{ error }}</Message>
    <Message v-if="success" severity="success" :closable="false" class="mb-3">{{ success }}</Message>

    <div v-if="selectedWellId" class="wa-panel">
      <div class="wa-toolbar">
        <strong>Sub-Activities for {{ selectedWell?.name }}</strong>
        <div class="wa-actions">
          <Button label="Add Sub-Activity" icon="pi pi-plus" size="small" @click="addRow" />
          <Button label="Save All" icon="pi pi-save" size="small" severity="success" :loading="loading" @click="saveAll" />
        </div>
      </div>

      <DataTable :value="rows" size="small" striped-rows show-gridlines edit-mode="cell" class="mt-2">
        <Column header="#" style="width: 50px">
          <template #body="{ index }">{{ index + 1 }}</template>
        </Column>
        <Column header="Primary Activity" style="min-width: 200px">
          <template #body="{ data }">
            <Select
              v-model="data.activity_id"
              :options="activityOptions"
              option-label="label"
              option-value="value"
              filter
              fluid
              size="small"
              @change="markDirty(data)"
            />
          </template>
        </Column>
        <Column header="Sub-Activity Name" style="min-width: 200px">
          <template #body="{ data }">
            <InputText v-model="data.name" fluid size="small" placeholder="e.g. NPT-1, UPA-1" @input="markDirty(data)" />
          </template>
        </Column>
        <Column header="Responsible Party" style="min-width: 200px">
          <template #body="{ data }">
            <InputText v-model="data.responsible_party" fluid size="small" placeholder="Company or 3rd party" @input="markDirty(data)" />
          </template>
        </Column>
        <Column header="Remarks / Description" style="min-width: 250px">
          <template #body="{ data }">
            <InputText v-model="data.description" fluid size="small" placeholder="Optional remarks" @input="markDirty(data)" />
          </template>
        </Column>
        <Column header="" style="width: 50px">
          <template #body="{ index }">
            <Button icon="pi pi-trash" size="small" text severity="danger" @click="removeRow(index)" />
          </template>
        </Column>
        <template #empty>
          <div class="empty-hint">No sub-activities configured yet. Click "Add Sub-Activity" to begin.</div>
        </template>
      </DataTable>

      <section class="wa-guide">
        <h3>How Sub-Activities Work</h3>
        <div class="wa-guide__grid">
          <article>
            <p><strong>Planned</strong> — Sub-activities like "Planned" linked to the Planned primary activity. Costs posted here are normal operational spend.</p>
          </article>
          <article>
            <p><strong>NPT-1, NPT-2</strong> — Non Productive Time sub-classified by responsible party. For example NPT-1 (Rig Contractor), NPT-2 (Operator).</p>
          </article>
          <article>
            <p><strong>UPA-1, UPA-2</strong> — Unplanned Activities sub-classified similarly. Each carries a responsible party for cost accountability.</p>
          </article>
          <article>
            <p><strong>Cost Tracking</strong> — During daily cost entry, each service line is tagged with a sub-activity. Costs roll up: Total = Planned + NPT + UPA.</p>
          </article>
        </div>
      </section>
    </div>

    <div v-else class="empty-hint" style="padding: 3rem; text-align: center">
      Select a well above to configure its sub-activities.
    </div>
  </div>
</template>

<style scoped>
.selector-bar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 1.5rem;
  padding: 1rem 1.25rem;
  background: white;
  border: 1px solid var(--surface-border, #e2e8f0);
  border-radius: 10px;
}

.selector-field {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.selector-field label {
  font-size: 0.78rem;
  font-weight: 600;
  color: var(--text-color-secondary, #64748b);
  text-transform: uppercase;
  letter-spacing: 0.03em;
}

.well-info {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.well-badge {
  padding: 0.25rem 0.75rem;
  background: #e0f2fe;
  color: #0369a1;
  border-radius: 6px;
  font-weight: 600;
  font-size: 0.85rem;
}

.well-status {
  font-size: 0.8rem;
  color: #64748b;
  text-transform: capitalize;
}

.wa-panel {
  background: white;
  border: 1px solid var(--surface-border, #e2e8f0);
  border-radius: 10px;
  padding: 1rem 1.25rem;
}

.wa-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.75rem;
}

.wa-actions {
  display: flex;
  gap: 0.5rem;
}

.mt-2 {
  margin-top: 0.5rem;
}

.mb-3 {
  margin-bottom: 0.75rem;
}

.empty-hint {
  text-align: center;
  padding: 2rem;
  color: #64748b;
  font-style: italic;
}

.wa-guide {
  margin-top: 1.5rem;
  padding: 1rem;
  border: 1px solid var(--surface-border, #e2e8f0);
  border-radius: 8px;
  background: #fafcfd;
}

.wa-guide h3 {
  margin: 0 0 0.75rem;
  font-size: 0.95rem;
}

.wa-guide__grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.75rem;
}

.wa-guide article {
  padding: 0.75rem;
  border: 1px solid var(--surface-border, #e2e8f0);
  border-radius: 6px;
  background: white;
}

.wa-guide article p {
  margin: 0;
  font-size: 0.8rem;
  line-height: 1.5;
  color: #475569;
}

@media (max-width: 820px) {
  .wa-guide__grid {
    grid-template-columns: 1fr;
  }
}
</style>
