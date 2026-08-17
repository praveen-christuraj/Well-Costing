/**
 * Shared catalogue maintenance grid for services, tangibles, and consumables.
 * All four share the same shape: code, name, category, unit, and identifiers.
 */
<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import EnterpriseGrid from '~/components/data-grid/EnterpriseGrid.vue'
import type { EditableRow, GridColumn, GridFilterDefinition } from '~/types/grid'
import type { MasterDataRecord, PageResponse } from '~/types/masterData'

const props = defineProps<{
  entity: string
  title: string
  singular: string
  /** Restrict the category picker to categories declared for this scope. */
  categoryScope: string
  /** Label for the identifier column, e.g. 'Material number'. */
  identifierLabel?: string
  /** Show specification and manufacturer columns. */
  showEquipmentDetail?: boolean
}>()

const api = useMasterData()
const references = useReferenceOptions()
const categoryOptions = ref<{ label: string, value: string }[]>([])

const columns = computed<GridColumn[]>(() => {
  const base: GridColumn[] = [
    { field: 'code', header: 'Code', required: true, sortable: true, width: '170px' },
    { field: 'name', header: 'Name', required: true, sortable: true, width: '250px' },
    { field: 'item_category_id', header: 'Category', type: 'select', options: categoryOptions.value, width: '200px' },
    { field: 'default_unit_id', header: 'UOM', type: 'select', options: references.units.value, width: '150px' },
    { field: 'material_number', header: props.identifierLabel ?? 'Material number', width: '170px' },
  ]
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

const filters = computed<GridFilterDefinition[]>(() => [
  { key: 'item_category_id', label: 'Category', type: 'select', options: categoryOptions.value },
  { key: 'default_unit_id', label: 'UOM', type: 'select', options: references.units.value, width: '150px' },
])

onMounted(async () => {
  await references.load(['units', 'item-categories'])
  try {
    const page = await api.listPage('item-categories', {
      page: 1,
      page_size: 500,
      applies_to: props.categoryScope,
      is_active: true,
    })
    categoryOptions.value = page.items.map(item => ({ label: `${item.code} — ${item.name}`, value: item.id }))
  }
  catch {
    categoryOptions.value = []
  }
})

function fetchPage(params: Record<string, unknown>): Promise<PageResponse<Record<string, unknown>>> {
  return api.listPage(props.entity, params as Record<string, string>) as unknown as Promise<PageResponse<Record<string, unknown>>>
}

function toRow(record: Record<string, unknown>) {
  const item = record as unknown as MasterDataRecord
  return {
    id: item.id,
    code: item.code,
    name: item.name,
    item_category_id: item.item_category_id ?? '',
    default_unit_id: item.default_unit_id ?? '',
    material_number: item.material_number ?? '',
    specification: item.specification ?? '',
    manufacturer: item.manufacturer ?? '',
    description: item.description ?? '',
    is_active: item.is_active,
  }
}

function toPayload(row: EditableRow) {
  return {
    code: String(row.code ?? '').trim(),
    name: String(row.name ?? '').trim(),
    item_category_id: row.item_category_id || null,
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
  item_category_id: '',
  default_unit_id: '',
  material_number: '',
  specification: '',
  manufacturer: '',
  description: '',
  is_active: true,
})
</script>

<template>
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
    :remove-record="(id, hard) => (hard ? api.remove(entity, id) : api.deactivate(entity, id))"
    :import-entity="entity"
    :export-entity="entity"
    default-sort="code"
    :search-placeholder="`Search by code, name, or material number…`"
  />
</template>
