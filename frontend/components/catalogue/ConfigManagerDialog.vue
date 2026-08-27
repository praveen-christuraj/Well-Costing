<script setup lang="ts">
/**
 * Manage a user-configurable dropdown list (bit types, manufacturers,
 * tangible categories/subcategories). Add single values, bulk-paste a list,
 * rename via double-click style inline flow, and soft-delete values — all
 * audited on the server. Soft-deleted values can be restored from the Master
 * Data → Deleted Entries tab.
 */
import { computed, ref, watch } from 'vue'
import Button from 'primevue/button'
import Dialog from 'primevue/dialog'
import InputText from 'primevue/inputtext'
import Textarea from 'primevue/textarea'

interface ConfigValue {
  id: number
  value: string
  is_active: boolean
  system_seeded: boolean
}

const props = defineProps<{
  visible: boolean
  configType: string
  title: string
}>()

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void
  (e: 'changed'): void
}>()

const api = useApi()

const values = ref<ConfigValue[]>([])
const loading = ref(false)
const newValues = ref('')
const singleValue = ref('')
const error = ref<string | null>(null)
const busy = ref(false)

const dialogVisible = computed({
  get: () => props.visible,
  set: (v: boolean) => emit('update:visible', v),
})

async function load(): Promise<void> {
  loading.value = true
  error.value = null
  try {
    values.value = await api.get<ConfigValue[]>(`/catalogue/configs/${props.configType}`)
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
    void load()
  }
})

async function addSingle(): Promise<void> {
  const value = singleValue.value.trim()
  if (!value) return
  busy.value = true
  error.value = null
  try {
    await api.post(`/catalogue/configs/${props.configType}`, { value })
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
  if (!items.length) return
  busy.value = true
  error.value = null
  try {
    const result = await api.post<{ imported_count: number, errors: string[] }>(
      `/catalogue/configs/${props.configType}/bulk`,
      { values: items },
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
</script>

<template>
  <Dialog v-model:visible="dialogVisible" modal :header="`Manage — ${title}`" :style="{ width: '38rem' }">
    <div class="cfg">
      <p v-if="error" class="cfg__error">{{ error }}</p>

      <div class="cfg__add">
        <InputText v-model="singleValue" fluid size="small" :placeholder="`Add a new ${title.replace(/s$/, '').toLowerCase()}…`" @keyup.enter="addSingle" />
        <Button label="Add" icon="pi pi-plus" size="small" :loading="busy" :disabled="!singleValue.trim()" @click="addSingle" />
      </div>

      <div class="cfg__list" data-testid="config-values">
        <div v-if="loading" class="cfg__hint"><i class="pi pi-spin pi-spinner" /> Loading…</div>
        <div v-else-if="!values.length" class="cfg__hint">No values yet — add one above or bulk-paste below.</div>
        <div v-for="item in values" :key="item.id" class="cfg__item">
          <span class="cfg__value">{{ item.value }}</span>
          <span class="cfg__actions">
            <button class="cfg__icon" title="Rename" :disabled="busy" @click="rename(item)"><i class="pi pi-pencil" /></button>
            <button class="cfg__icon cfg__icon--danger" title="Remove (soft delete)" :disabled="busy" @click="remove(item)"><i class="pi pi-trash" /></button>
          </span>
        </div>
      </div>

      <div class="cfg__bulk">
        <label class="cfg__bulk-label">Bulk add — one value per line (or comma separated)</label>
        <Textarea v-model="newValues" rows="3" fluid placeholder="PDC&#10;Tricone&#10;Diamond Impregnated" />
        <div class="cfg__bulk-actions">
          <Button
label="Bulk Add" icon="pi pi-list" size="small" severity="secondary" outlined
                  :disabled="!newValues.trim() || busy" @click="bulkAdd" />
        </div>
      </div>
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
  padding: 0.35rem 0.6rem;
  border-bottom: 1px solid var(--app-border);
}

.cfg__item:last-child {
  border-bottom: none;
}

.cfg__value {
  font-size: 0.8rem;
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
