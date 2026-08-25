/**
 * Shared catalogue maintenance grid.
 *
 * Every catalogue item — service, tangible, mud chemical, cement additive — is
 * classified with the one Primary → Secondary → Tertiary hierarchy held in
 * master data. The item's *category* is its Secondary Category and its *sub
 * category* is its Tertiary Category; there is no separate item-category list
 * any more. The three pickers cascade, so a tertiary category can only ever be
 * one that belongs to the chosen secondary.
 */
<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import Button from 'primevue/button'
import Dialog from 'primevue/dialog'
import Message from 'primevue/message'
import EnterpriseGrid from '~/components/data-grid/EnterpriseGrid.vue'
import type { EditableRow, GridColumn, GridFilterDefinition, GridSelectOption } from '~/types/grid'
import type { DeleteImpact, MasterDataRecord, PageResponse } from '~/types/masterData'
import { SLOT } from '~/types/reference'
import { SERVICE_RATE_BASES as RATE_BASES } from '~/types/afe'
import { DeleteCancelledError } from '~/utils/deleteCancelled'

const props = defineProps<{
  entity: string
  title: string
  singular: string
  /** Label for the identifier column, e.g. 'Material number'. */
  identifierLabel?: string
  /** Show specification and manufacturer columns. */
  showEquipmentDetail?: boolean
  /** Show the Rate type picker (daily / per section / per service / fixed). */
  showRateBasis?: boolean
  /** Show the item type column — only the unified catalogue register needs it. */
  showItemType?: boolean
  /**
   * Restrict the classification pickers to one primary category, by code.
   * Tangibles, mud chemicals, and cement additives each pin their own.
   */
  primaryCategoryCode?: string
}>()

const api = useMasterData()
const references = useReferenceOptions()

const primaryOptions = ref<GridSelectOption[]>([])
const secondaryOptions = ref<GridSelectOption[]>([])
const tertiaryOptions = ref<GridSelectOption[]>([])
/** Primary category pinned by the page, when it declared one. */
const pinnedPrimaryId = ref<string>('')

const ITEM_TYPES: GridSelectOption[] = [
  { label: 'Service', value: 'service' },
  { label: 'Tangible', value: 'tangible' },
  { label: 'Mud chemical', value: 'mud_chemical' },
  { label: 'Cement additive', value: 'cement_additive' },
  { label: 'Material', value: 'material' },
  { label: 'Equipment', value: 'equipment' },
]

const columns = computed<GridColumn[]>(() => {
  const base: GridColumn[] = [
    { field: 'code', header: 'Code', required: true, sortable: true, width: '170px' },
    { field: 'name', header: 'Name', required: true, sortable: true, width: '250px' },
  ]
  if (props.showItemType) {
    base.push({ field: 'item_type', header: 'Item type', type: 'select', options: ITEM_TYPES, required: true, width: '160px' })
  }
  if (!pinnedPrimaryId.value) {
    base.push({ field: 'primary_category_id', header: 'Primary Category', type: 'select', options: primaryOptions.value, width: '200px' })
  }
  base.push(
    { field: 'secondary_category_id', header: 'Category (Secondary)', type: 'select', options: secondaryOptions.value, width: '210px' },
    { field: 'tertiary_category_id', header: 'Sub category (Tertiary)', type: 'select', options: tertiaryOptions.value, width: '210px' },
    { field: 'default_unit_id', header: 'UOM', type: 'select', options: references.units.value, width: '150px' },
    { field: 'material_number', header: props.identifierLabel ?? 'Material number', width: '170px' },
  )
  if (props.showRateBasis) {
    base.push({ field: 'rate_basis', header: 'Rate type', type: 'select', options: RATE_BASES, width: '170px' })
  }
  if (props.showEquipmentDetail) {
    base.push(
      { field: 'specification', header: 'Specification', width: '170px' },
      { field: 'manufacturer', header: 'Manufacturer', width: '170px' },
    )
  }
  base.push(
    { field: 'description', header: 'Description', type: 'textarea', width: '220px' },
    { field: 'is_active', header: 'Status', type: 'checkbox', width: '110px' },
  )
  return base
})

const filters = computed<GridFilterDefinition[]>(() => {
  const result: GridFilterDefinition[] = [
    { key: 'secondary_category_id', label: 'Category', type: 'select', options: secondaryOptions.value, width: '200px' },
    { key: 'tertiary_category_id', label: 'Sub category', type: 'select', options: tertiaryOptions.value, width: '200px' },
  ]
  if (props.showItemType) {
    result.unshift({ key: 'item_type', label: 'Item type', type: 'select', options: ITEM_TYPES, width: '170px' })
  }
  result.push({ key: 'default_unit_id', label: 'UOM', type: 'select', options: references.units.value, width: '150px' })
  return result
})

/** Load the secondary categories under the pinned or selected primary. */
async function loadSecondaries(primaryId: string): Promise<void> {
  secondaryOptions.value = await references.cascade(SLOT.catalogueItemSecondary, primaryId)
}

/**
 * Load the tertiary categories, each labelled with the secondary it belongs to.
 *
 * The grid renders one option list for the whole column, so rather than hide
 * the parent the label carries it: "BITS › PDC — PDC bits". Picking a tertiary
 * fills in its parents on save, and a tertiary that contradicts an explicitly
 * chosen secondary is rejected by the API with a plain-language message.
 */
async function loadTertiaries(): Promise<void> {
  const options = await references.slot(SLOT.catalogueItemTertiary)
  const secondaryLabels = new Map(secondaryOptions.value.map(option => [option.value, option.label]))
  tertiaryOptions.value = options.map((option) => {
    const parent = option.parent_id ? secondaryLabels.get(option.parent_id) : undefined
    const parentCode = parent?.split(' — ')[0]
    return {
      label: parentCode ? `${parentCode} › ${option.label}` : option.label,
      value: option.value,
    }
  })
}

onMounted(async () => {
  await references.load(['units'])
  const primaries = await references.slot(SLOT.catalogueItemPrimary)
  primaryOptions.value = primaries.map(option => ({ label: option.label, value: option.value }))

  if (props.primaryCategoryCode) {
    const match = primaries.find(option => option.code === props.primaryCategoryCode)
    pinnedPrimaryId.value = match?.value ?? ''
  }
  if (pinnedPrimaryId.value) {
    await loadSecondaries(pinnedPrimaryId.value)
  }
  else {
    // No pinned primary: offer every secondary, cascading is per row instead.
    secondaryOptions.value = (await references.slot(SLOT.catalogueItemSecondary))
      .map(option => ({ label: option.label, value: option.value }))
  }
  await loadTertiaries()
})

function fetchPage(params: Record<string, unknown>): Promise<PageResponse<Record<string, unknown>>> {
  const scoped = pinnedPrimaryId.value
    ? { ...params, primary_category_id: pinnedPrimaryId.value }
    : params
  return api.listPage(props.entity, scoped as Record<string, string>) as unknown as Promise<PageResponse<Record<string, unknown>>>
}

function toRow(record: Record<string, unknown>) {
  const item = record as unknown as MasterDataRecord
  return {
    id: item.id,
    code: item.code,
    name: item.name,
    item_type: item.item_type ?? '',
    primary_category_id: item.primary_category_id ?? '',
    secondary_category_id: item.secondary_category_id ?? '',
    tertiary_category_id: item.tertiary_category_id ?? '',
    rate_basis: item.rate_basis ?? 'daily',
    default_unit_id: item.default_unit_id ?? '',
    material_number: item.material_number ?? '',
    specification: item.specification ?? '',
    manufacturer: item.manufacturer ?? '',
    description: item.description ?? '',
    is_active: item.is_active,
  }
}

function toPayload(row: EditableRow) {
  const tertiary = row.tertiary_category_id || null
  return {
    code: String(row.code ?? '').trim(),
    name: String(row.name ?? '').trim(),
    ...(props.showItemType ? { item_type: row.item_type || 'tangible' } : {}),
    // The backend derives the parents from the deepest level supplied, so send
    // the primary only when nothing narrower was chosen.
    primary_category_id: (pinnedPrimaryId.value || row.primary_category_id || null),
    secondary_category_id: row.secondary_category_id || null,
    tertiary_category_id: tertiary,
    ...(props.showRateBasis ? { rate_basis: row.rate_basis || 'daily' } : {}),
    default_unit_id: row.default_unit_id || null,
    material_number: row.material_number || null,
    specification: row.specification || null,
    manufacturer: row.manufacturer || null,
    description: row.description || null,
    is_active: row.is_active !== false,
  }
}

const blankRow = () => ({
  code: '',
  name: '',
  item_type: props.showItemType ? 'tangible' : '',
  primary_category_id: pinnedPrimaryId.value,
  secondary_category_id: '',
  tertiary_category_id: '',
  rate_basis: 'daily',
  default_unit_id: '',
  material_number: '',
  specification: '',
  manufacturer: '',
  description: '',
  is_active: true,
})

/* ------------------------------------------- cascading delete confirmation */
const impact = ref<DeleteImpact | null>(null)
const impactVisible = ref(false)
const impactError = ref<string | null>(null)
const deleting = ref(false)
let resolveDelete: ((confirmed: boolean) => void) | null = null

function totalDependents(): number {
  return (impact.value?.cascades ?? []).reduce((sum, entry) => sum + entry.count, 0)
}

/**
 * Deactivation is unconditional; a permanent delete first asks the API what
 * else would go — a tangible's master rates and rate revisions — and only
 * proceeds once the user has confirmed those numbers.
 */
async function removeRecord(id: string, hard: boolean): Promise<void> {
  if (!hard) {
    await api.deactivate(props.entity, id)
    return
  }
  impactError.value = null
  let detail: DeleteImpact | null = null
  try {
    detail = await api.deleteImpact(props.entity, id)
  }
  catch {
    detail = null
  }
  if (!detail || !detail.requires_confirmation) {
    await api.remove(props.entity, id)
    return
  }

  impact.value = detail
  impactVisible.value = true
  const confirmed = await new Promise<boolean>((resolve) => { resolveDelete = resolve })
  if (!confirmed) throw new DeleteCancelledError()
  await api.remove(props.entity, id, true)
}

async function confirmCascade(): Promise<void> {
  deleting.value = true
  impactVisible.value = false
  deleting.value = false
  resolveDelete?.(true)
  resolveDelete = null
}

function cancelCascade(): void {
  impactVisible.value = false
  resolveDelete?.(false)
  resolveDelete = null
}
</script>

<template>
  <div>
    <EnterpriseGrid
      :title="title"
      :singular="singular"
      :columns="columns"
      :filters="filters"
      :fetch-page="fetchPage"
      :to-row="toRow"
      :to-payload="toPayload"
      :blank-row="blankRow"
      :validate-rows="rows => api.validate(entity, rows as never)"
      :bulk-create="rows => api.bulkCreate(entity, rows as never)"
      :bulk-update="rows => api.bulkUpdate(entity, rows as never)"
      :remove-record="removeRecord"
      :import-entity="entity"
      :export-entity="entity"
      default-sort="code"
      :search-placeholder="`Search by code, name, or material number…`"
    />

    <Dialog
      v-model:visible="impactVisible"
      modal
      :dismissable-mask="false"
      :close-on-escape="false"
      header="This item has rate history"
      :style="{ width: '520px' }"
      @hide="cancelCascade"
    >
      <Message severity="warn" :closable="false">
        Deleting <strong>{{ impact?.code }} — {{ impact?.name }}</strong> also permanently removes
        {{ totalDependents() }} linked record{{ totalDependents() === 1 ? '' : 's' }}. This cannot be undone.
      </Message>
      <ul class="cascade-list">
        <li v-for="entry in impact?.cascades ?? []" :key="entry.entity">
          <strong>{{ entry.count }}</strong> {{ entry.label.toLowerCase() }}
        </li>
      </ul>
      <p class="cascade-note">
        Cancel leaves the item and all linked rate history unchanged. Linked records must be
        deleted first unless you explicitly confirm the cascade above.
      </p>
      <template #footer>
        <Button label="Cancel" text @click="cancelCascade" />
        <Button
          label="Delete item and its rates"
          severity="danger"
          icon="pi pi-trash"
          :loading="deleting"
          @click="confirmCascade"
        />
      </template>
    </Dialog>
  </div>
</template>

<style scoped>
.cascade-list {
  margin: 0.75rem 0 0;
  padding-left: 1.25rem;
}

.cascade-note {
  margin-top: 0.75rem;
  color: var(--p-text-muted-color, #6b7280);
  font-size: 0.875rem;
}
</style>
