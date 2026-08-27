<script setup lang="ts">
/**
 * Manage a user-configurable dropdown list (bit types, manufacturers,
 * tangible categories/subcategories). Add single values, bulk-paste a list,
 * rename via inline prompt, and soft-delete values — all audited on the
 * server. Soft-deleted values can be restored from the Master Data → Deleted
 * Entries tab.
 *
 * Dependent lists: pass `parent-config-type` (e.g. tangible subcategories
 * depend on tangible categories). The dialog then makes the user pick the
 * parent first — values are listed, added and bulk-added per parent, and
 * legacy parent-less values can be moved under a parent.
 */
import { computed, ref, watch } from 'vue'
import Button from 'primevue/button'
import Dialog from 'primevue/dialog'
import InputText from 'primevue/inputtext'
import Select from 'primevue/select'
import Textarea from 'primevue/textarea'

interface ConfigValue {
  id: number
  value: string
  parent_value?: string | null
  is_active: boolean
  system_seeded: boolean
}

const UNASSIGNED = '__unassigned__'

const props = defineProps<{
  visible: boolean
  configType: string
  title: string
  /** Config type of the parent list for dependent dropdowns. */
  parentConfigType?: string
  /** Label of the parent, e.g. "Category". */
  parentLabel?: string
}>()

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void
  (e: 'changed'): void
}>()

const api = useApi()

const values = ref<ConfigValue[]>([])
const parents = ref<ConfigValue[]>([])
const selectedParent = ref<string | null>(null)
const loading = ref(false)
const newValues = ref('')
const singleValue = ref('')
const error = ref<string | null>(null)
const busy = ref(false)
const moveTarget = ref<Record<number, string>>({})

const dialogVisible = computed({
  get: () => props.visible,
  set: (v: boolean) => emit('update:visible', v),
})

const parentLabel = computed(() => props.parentLabel ?? 'Parent')
const isParented = computed(() => !!props.parentConfigType)

const singularTitle = computed(() => props.title.replace(/s$/, '').toLowerCase())

const parentOptions = computed(() => {
  const options = parents.value.map(parent => ({ label: parent.value, value: parent.value }))
  if (unassignedValues.value.length) {
    options.push({ label: 'Unassigned (legacy — move under a category)', value: UNASSIGNED })
  }
  return options
})

const visibleValues = computed(() => {
  if (!isParented.value) return values.value
  if (selectedParent.value === UNASSIGNED) {
    return values.value.filter(item => item.parent_value == null)
  }
  return values.value.filter(item => item.parent_value === selectedParent.value)
})

const unassignedValues = computed(() => values.value.filter(item => item.parent_value == null))

const activeParent = computed(() => {
  if (!isParented.value) return null
  return selectedParent.value && selectedParent.value !== UNASSIGNED ? selectedParent.value : null
})

async function load(): Promise<void> {
  loading.value = true
  error.value = null
  try {
    const parentType = props.parentConfigType
    const [configValues, parentValues] = await Promise.all([
      api.get<ConfigValue[]>(`/catalogue/configs/${props.configType}`),
      parentType ? api.get<ConfigValue[]>(`/catalogue/configs/${parentType}`) : Promise.resolve([]),
    ])
    values.value = configValues
    parents.value = parentValues
    if (isParented.value) {
      // Keep the selection; fall back to the first parent when none is set.
      if (!selectedParent.value || ![...parents.value.map(p => p.value), UNASSIGNED].includes(selectedParent.value)) {
        selectedParent.value = parents.value[0]?.value ?? null
      }
    }
  }
  catch (caught: unknown) {
    error.value = caught instanceof Error ? caught.message : 'Could not load the list'
  }
  finally {
    loading.value = false
  }
}

watch(dialogVisible, (open) => {
  if (open) {
    newValues.value = ''
    singleValue.value = ''
    error.value = null
    selectedParent.value = null
    moveTarget.value = {}
    void load()
  }
})

function parentSuffix(): string {
  return activeParent.value ? ` under '${activeParent.value}'` : ''
}

async function addSingle(): Promise<void> {
  const value = singleValue.value.trim()
  if (!value || !activeParent.value) return
  busy.value = true
  error.value = null
  try {
    await api.post(`/catalogue/configs/${props.configType}`, { value, parent_value: activeParent.value })
    singleValue.value = ''
    await load()
    emit('changed')
  }
  catch (caught: unknown) {
    error.value = caught instanceof Error ? caught.message : 'Add failed'
  }
  finally {
    busy.value = false
  }
}

async function bulkAdd(): Promise<void> {
  const items = newValues.value.split(/[\n,;]+/).map(v => v.trim()).filter(Boolean)
  if (!items.length || !activeParent.value) return
  busy.value = true
  error.value = null
  try {
    const result = await api.post<{ imported_count: number, errors: string[] }>(
      `/catalogue/configs/${props.configType}/bulk`,
      { values: items, parent_value: activeParent.value },
    )
    newValues.value = ''
    if (result.errors?.length) error.value = result.errors.join('; ')
    await load()
    emit('changed')
  }
  catch (caught: unknown) {
    error.value = caught instanceof Error ? caught.message : 'Bulk add failed'
  }
  finally {
    busy.value = false
  }
}

async function rename(item: ConfigValue): Promise<void> {
  const next = window.prompt(`Rename "${item.value}" to:`, item.value)
  if (!next || next.trim() === item.value) return
  busy.value = true
  error.value = null
  try {
    await api.put(`/catalogue/configs/${props.configType}/${item.id}`, { value: next.trim() })
    await load()
    emit('changed')
  }
  catch (caught: unknown) {
    error.value = caught instanceof Error ? caught.message : 'Rename failed'
  }
  finally {
    busy.value = false
  }
}

async function remove(item: ConfigValue): Promise<void> {
  if (!window.confirm(`Remove "${item.value}" from this list? Existing entries keep the value; it moves to Deleted Entries.`)) return
  busy.value = true
  error.value = null
  try {
    await api.delete(`/catalogue/configs/${props.configType}/${item.id}`)
    await load()
    emit('changed')
  }
  catch (caught: unknown) {
    error.value = caught instanceof Error ? caught.message : 'Remove failed'
  }
  finally {
    busy.value = false
  }
}

/** Move a legacy unassigned value under the chosen parent. */
async function moveToParent(item: ConfigValue): Promise<void> {
  const target = moveTarget.value[item.id]
  if (!target) return
  busy.value = true
  error.value = null
  try {
    await api.put(`/catalogue/configs/${props.configType}/${item.id}`, {
      value: item.value,
      parent_value: target,
    })
    moveTarget.value[item.id] = ''
    await load()
    emit('changed')
  }
  catch (caught: unknown) {
    error.value = caught instanceof Error ? caught.message : 'Move failed'
  }
  finally {
    busy.value = false
  }
}
</script>

<template>
  <Dialog v-model:visible="dialogVisible" modal :header="`Manage — ${title}`" :style="{ width: '38rem' }">
    <div class="cfg">
      <p v-if="error" class="cfg__error">{{ error }}</p>

      <div v-if="isParented" class="cfg__parent">
        <label class="cfg__parent-label">{{ parentLabel }}</label>
        <Select
          v-model="selectedParent"
          :options="parentOptions"
          option-label="label"
          option-value="value"
          :placeholder="parents.length ? `Select ${parentLabel.toLowerCase()}…` : `No ${parentLabel.toLowerCase()} configured yet`"
          :disabled="!parents.length"
          fluid
          size="small"
          data-testid="config-parent-select"
        />
        <p v-if="!parents.length" class="cfg__parent-warning">
          <i class="pi pi-info-circle" />
          Configure a {{ parentLabel.toLowerCase() }} first — {{ title.toLowerCase() }} depend on it.
        </p>
        <p v-else-if="selectedParent === UNASSIGNED" class="cfg__parent-note">
          These values were created before the {{ parentLabel.toLowerCase() }} link existed.
          Move each one under a {{ parentLabel.toLowerCase() }} so it shows only for that {{ parentLabel.toLowerCase() }}.
        </p>
      </div>

      <template v-if="!isParented || activeParent">
        <div class="cfg__add">
          <InputText
            v-model="singleValue"
            fluid
            size="small"
            :placeholder="`Add a new ${singularTitle}${parentSuffix()}…`"
            data-testid="config-single-input"
            @keyup.enter="addSingle"
          />
          <Button label="Add" icon="pi pi-plus" size="small" :loading="busy" :disabled="!singleValue.trim()" data-testid="config-add-single" @click="addSingle" />
        </div>
      </template>

      <div class="cfg__list" data-testid="config-values">
        <div v-if="loading" class="cfg__hint"><i class="pi pi-spin pi-spinner" /> Loading…</div>
        <div v-else-if="!visibleValues.length" class="cfg__hint">
          No values yet{{ parentSuffix() }} — add one above or bulk-paste below.
        </div>
        <div v-for="item in visibleValues" :key="item.id" class="cfg__item">
          <span class="cfg__value">{{ item.value }}</span>
          <span v-if="isParented && item.parent_value == null" class="cfg__move">
            <Select
              v-model="moveTarget[item.id]"
              :options="parents.map(p => ({ label: p.value, value: p.value }))"
              option-label="label"
              option-value="value"
              :placeholder="`Move to ${parentLabel.toLowerCase()}…`"
              size="small"
              class="cfg__move-select"
            />
            <button class="cfg__icon" title="Save move" :disabled="busy || !moveTarget[item.id]" @click="moveToParent(item)"><i class="pi pi-check" /></button>
          </span>
          <span class="cfg__actions">
            <button class="cfg__icon" title="Rename" :disabled="busy" @click="rename(item)"><i class="pi pi-pencil" /></button>
            <button class="cfg__icon cfg__icon--danger" title="Remove (soft delete)" :disabled="busy" @click="remove(item)"><i class="pi pi-trash" /></button>
          </span>
        </div>
      </div>

      <template v-if="!isParented || activeParent">
        <div class="cfg__bulk">
          <label class="cfg__bulk-label">Bulk add{{ parentSuffix() }} — one value per line (or comma separated)</label>
          <Textarea v-model="newValues" rows="3" fluid placeholder="PDC&#10;Tricone&#10;Diamond Impregnated" />
          <div class="cfg__bulk-actions">
            <Button
              label="Bulk Add" icon="pi pi-list" size="small" severity="secondary" outlined
              :disabled="!newValues.trim() || busy" data-testid="config-bulk-add" @click="bulkAdd" />
          </div>
        </div>
      </template>
    </div>
    <template #footer>
      <Button label="Done" severity="secondary" text size="small" @click="dialogVisible = false" />
    </template>
  </Dialog>
</template>

<style scoped>
.cfg {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  font-size: 0.82rem;
}

.cfg__error {
  color: #e11d48;
  margin: 0;
}

.cfg__parent {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.cfg__parent-label {
  font-size: 0.7rem;
  font-weight: 600;
  text-transform: uppercase;
  color: var(--app-muted);
}

.cfg__parent-warning {
  margin: 0;
  font-size: 0.75rem;
  color: #b45309;
  display: flex;
  align-items: center;
  gap: 0.35rem;
}

.cfg__parent-note {
  margin: 0;
  font-size: 0.72rem;
  color: var(--app-muted);
}

.cfg__add {
  display: flex;
  gap: 0.5rem;
  align-items: center;
}

.cfg__list {
  border: 1px solid var(--app-border);
  border-radius: 8px;
  max-height: 14rem;
  overflow-y: auto;
}

.cfg__hint {
  padding: 0.75rem;
  color: var(--app-muted);
  text-align: center;
  font-size: 0.78rem;
}

.cfg__item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
  padding: 0.35rem 0.6rem;
  border-bottom: 1px solid var(--app-border);
}

.cfg__item:last-child {
  border-bottom: none;
}

.cfg__value {
  font-size: 0.8rem;
}

.cfg__move {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  flex: 1;
  max-width: 16rem;
  justify-content: flex-end;
}

.cfg__move-select {
  width: 11rem;
}

.cfg__actions {
  display: flex;
  gap: 0.15rem;
}

.cfg__icon {
  border: none;
  background: transparent;
  color: var(--app-muted);
  cursor: pointer;
  padding: 0.25rem;
  border-radius: 4px;
}

.cfg__icon:hover:not(:disabled) {
  background: var(--app-bg);
  color: var(--p-primary-color);
}

.cfg__icon:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.cfg__icon--danger:hover:not(:disabled) {
  color: #e11d48;
}

.cfg__bulk {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}

.cfg__bulk-label {
  font-size: 0.7rem;
  font-weight: 600;
  text-transform: uppercase;
  color: var(--app-muted);
}

.cfg__bulk-actions {
  display: flex;
  justify-content: flex-end;
}
</style>
