/**
 * Dropdown Sources — the super-admin console for the reference registry.
 *
 * Every picker in the application is a *slot* with a stable code. The slot
 * catalogue and the sources it may read from are declared in the backend, so
 * this page cannot invent a binding the application will not understand; it
 * chooses between the options the backend already permits and shows what is in
 * effect right now.
 */
<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import Button from 'primevue/button'
import Column from 'primevue/column'
import DataTable from 'primevue/datatable'
import Dialog from 'primevue/dialog'
import InputText from 'primevue/inputtext'
import Message from 'primevue/message'
import Select from 'primevue/select'
import Tag from 'primevue/tag'
import ToggleSwitch from 'primevue/toggleswitch'
import PageHeader from '~/components/design-system/PageHeader.vue'
import type { DropdownRegistry, DropdownSlot, ReferenceSource } from '~/types/reference'

definePageMeta({ middleware: 'auth' })

const api = useReference()

const registry = ref<DropdownRegistry | null>(null)
const usage = ref<Record<string, number>>({})
const moduleFilter = ref<string>('all')
const search = ref<string>('')
const loading = ref(false)
const saving = ref(false)
const error = ref<string | null>(null)
const success = ref<string | null>(null)

const editing = ref<DropdownSlot | null>(null)
const dialogVisible = ref(false)
const form = ref({ source_code: '', label_template: '{code} — {name}', include_inactive: false, notes: '' })

const LABEL_TEMPLATES = [
  { label: 'CODE — Name', value: '{code} — {name}' },
  { label: 'Name only', value: '{name}' },
  { label: 'Code only', value: '{code}' },
  { label: 'Name (CODE)', value: '{name} ({code})' },
]

const moduleOptions = computed(() => [
  { label: 'All modules', value: 'all' },
  ...(registry.value?.modules ?? []).map(entry => ({ label: entry.label, value: entry.key })),
])

const sourcesByCode = computed<Record<string, ReferenceSource>>(() => {
  const map: Record<string, ReferenceSource> = {}
  for (const source of registry.value?.sources ?? []) map[source.code] = source
  return map
})

const visibleSlots = computed<DropdownSlot[]>(() => {
  const term = search.value.trim().toLowerCase()
  return (registry.value?.slots ?? []).filter((slot) => {
    if (moduleFilter.value !== 'all' && slot.module !== moduleFilter.value) return false
    if (!term) return true
    return `${slot.label} ${slot.code} ${slot.description}`.toLowerCase().includes(term)
  })
})

const overriddenCount = computed(() => (registry.value?.slots ?? []).filter(slot => slot.is_overridden).length)

function sourceLabel(code: string): string {
  return sourcesByCode.value[code]?.label ?? code
}

function rowCount(code: string): number | null {
  const value = usage.value[code]
  return value === undefined ? null : value
}

function sourceOptionsFor(slot: DropdownSlot) {
  return slot.allowed_sources.map(code => ({
    label: `${sourceLabel(code)}${rowCount(code) !== null ? ` · ${rowCount(code)} rows` : ''}`,
    value: code,
  }))
}

async function load(): Promise<void> {
  loading.value = true
  error.value = null
  try {
    const [registryData, usageData] = await Promise.all([api.registry(), api.usage()])
    registry.value = registryData
    usage.value = usageData
  }
  catch (caught: unknown) {
    error.value = caught instanceof Error ? caught.message : 'The dropdown registry could not be loaded.'
  }
  finally { loading.value = false }
}

function openEditor(slot: DropdownSlot): void {
  if (slot.locked) return
  editing.value = slot
  form.value = {
    source_code: slot.effective_source,
    label_template: slot.label_template,
    include_inactive: slot.binding?.include_inactive ?? false,
    notes: slot.binding?.notes ?? '',
  }
  dialogVisible.value = true
}

async function save(): Promise<void> {
  if (!editing.value) return
  saving.value = true
  error.value = null
  success.value = null
  try {
    await api.bind(editing.value.code, {
      source_code: form.value.source_code,
      label_template: form.value.label_template,
      include_inactive: form.value.include_inactive,
      notes: form.value.notes.trim() || null,
    })
    success.value = `${editing.value.label} now reads from ${sourceLabel(form.value.source_code)}.`
    dialogVisible.value = false
    await load()
  }
  catch (caught: unknown) {
    error.value = caught instanceof Error ? caught.message : 'The binding could not be saved.'
  }
  finally { saving.value = false }
}

async function reset(slot: DropdownSlot): Promise<void> {
  error.value = null
  success.value = null
  try {
    await api.reset(slot.code)
    success.value = `${slot.label} restored to its default source.`
    await load()
  }
  catch (caught: unknown) {
    error.value = caught instanceof Error ? caught.message : 'The binding could not be reset.'
  }
}

onMounted(() => void load())
</script>

<template>
  <div class="dropdowns-page">
    <PageHeader
      title="Dropdown Sources"
      description="Decide which master-data section feeds each dropdown in the application. Slots and their permitted sources are defined by the system; this page chooses between them and records who changed what."
    >
      <template #actions>
        <Tag value="Super administrator" severity="info" />
      </template>
    </PageHeader>

    <Message severity="info" :closable="false">
      Every dropdown resolves through this registry at runtime. A slot with no override reads the
      source declared in code, so the application always works out of the box — changes here refine
      it rather than switch it on.
    </Message>
    <Message v-if="error" severity="error">{{ error }}</Message>
    <Message v-if="success" severity="success">{{ success }}</Message>

    <section class="dropdowns-summary">
      <article><span>Dropdown slots</span><strong>{{ registry?.slots.length ?? 0 }}</strong></article>
      <article><span>Available sources</span><strong>{{ registry?.sources.length ?? 0 }}</strong></article>
      <article><span>Configured overrides</span><strong>{{ overriddenCount }}</strong></article>
    </section>

    <section class="dropdowns-filters">
      <Select v-model="moduleFilter" :options="moduleOptions" option-label="label" option-value="value" />
      <InputText v-model="search" placeholder="Search dropdowns…" class="dropdowns-search" />
      <Button icon="pi pi-refresh" label="Reload" outlined :loading="loading" @click="load" />
    </section>

    <DataTable :value="visibleSlots" :loading="loading" data-key="code" striped-rows show-gridlines size="small">
      <Column header="Dropdown" :style="{ minWidth: '260px' }">
        <template #body="{ data }">
          <strong>{{ data.label }}</strong>
          <small class="dropdowns-code">{{ data.code }}</small>
          <small class="dropdowns-desc">{{ data.description }}</small>
        </template>
      </Column>
      <Column header="Module" :style="{ width: '130px' }">
        <template #body="{ data }"><Tag :value="data.module" severity="secondary" /></template>
      </Column>
      <Column header="Reads from" :style="{ minWidth: '220px' }">
        <template #body="{ data }">
          {{ sourceLabel(data.effective_source) }}
          <small v-if="rowCount(data.effective_source) !== null" class="dropdowns-desc">
            {{ rowCount(data.effective_source) }} record(s) available
          </small>
        </template>
      </Column>
      <Column header="Cascades from" :style="{ minWidth: '180px' }">
        <template #body="{ data }">
          <span v-if="data.cascades_from" class="dropdowns-cascade">{{ data.cascades_from }}</span>
          <span v-else class="dropdowns-muted">—</span>
        </template>
      </Column>
      <Column header="Status" :style="{ width: '150px' }">
        <template #body="{ data }">
          <Tag v-if="data.locked" value="Structural" severity="warn" />
          <Tag v-else-if="data.is_overridden" value="Configured" severity="success" />
          <Tag v-else value="Default" severity="secondary" />
        </template>
      </Column>
      <Column header="" :style="{ width: '170px' }">
        <template #body="{ data }">
          <Button
            label="Change"
            icon="pi pi-pencil"
            text
            size="small"
            :disabled="data.locked"
            @click="openEditor(data)"
          />
          <Button
            v-if="data.is_overridden"
            label="Reset"
            icon="pi pi-undo"
            text
            size="small"
            severity="secondary"
            @click="reset(data)"
          />
        </template>
      </Column>
      <template #empty>No dropdown slots match this filter.</template>
    </DataTable>

    <Dialog v-model:visible="dialogVisible" modal :header="editing?.label ?? 'Dropdown source'" :style="{ width: '560px' }">
      <p class="dropdowns-desc">{{ editing?.description }}</p>
      <div class="dropdowns-form">
        <label>
          Read options from
          <Select
            v-model="form.source_code"
            :options="editing ? sourceOptionsFor(editing) : []"
            option-label="label"
            option-value="value"
            fluid
          />
        </label>
        <small class="dropdowns-desc">{{ sourcesByCode[form.source_code]?.description }}</small>
        <label>
          Show each option as
          <Select v-model="form.label_template" :options="LABEL_TEMPLATES" option-label="label" option-value="value" fluid />
        </label>
        <label class="dropdowns-switch">
          <ToggleSwitch v-model="form.include_inactive" />
          <span>Include deactivated records in this dropdown</span>
        </label>
        <label>
          Notes
          <InputText v-model="form.notes" placeholder="Why this dropdown was repointed" fluid />
        </label>
      </div>
      <template #footer>
        <Button label="Cancel" severity="secondary" text @click="dialogVisible = false" />
        <Button label="Save binding" icon="pi pi-check" :loading="saving" @click="save" />
      </template>
    </Dialog>
  </div>
</template>

<style scoped>
.dropdowns-page {
  display: grid;
  gap: 1rem;
}

.dropdowns-summary {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 0.75rem;
}

.dropdowns-summary article {
  display: grid;
  gap: 0.25rem;
  padding: 0.75rem 1rem;
  border: 1px solid var(--surface-border, #e2e8f0);
  border-radius: 8px;
  background: var(--surface-card, #fff);
}

.dropdowns-summary span {
  font-size: 0.8rem;
  color: var(--text-color-secondary, #64748b);
}

.dropdowns-summary strong {
  font-size: 1.35rem;
}

.dropdowns-filters {
  display: flex;
  gap: 0.5rem;
  align-items: center;
  flex-wrap: wrap;
}

.dropdowns-search {
  flex: 1;
  min-width: 220px;
}

.dropdowns-code,
.dropdowns-desc {
  display: block;
  font-size: 0.75rem;
  color: var(--text-color-secondary, #64748b);
}

.dropdowns-code {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
}

.dropdowns-cascade {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 0.75rem;
}

.dropdowns-muted {
  color: var(--text-color-secondary, #94a3b8);
}

.dropdowns-form {
  display: grid;
  gap: 0.75rem;
}

.dropdowns-form label {
  display: grid;
  gap: 0.25rem;
  font-size: 0.85rem;
  font-weight: 600;
}

.dropdowns-switch {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-weight: 500;
}
</style>
