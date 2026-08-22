/** Drilling Phases — user-configurable operational phases.

Like hole sections, phases are configured once in master data and referenced
throughout AFE sections and daily cost entries.
*/
<script setup lang="ts">
import EnterpriseGrid from '~/components/data-grid/EnterpriseGrid.vue'
import MasterDataNav from '~/components/master-data/MasterDataNav.vue'
import PageHeader from '~/components/design-system/PageHeader.vue'
import type { EditableRow, GridColumn } from '~/types/grid'
import type { MasterDataRecord, PageResponse } from '~/types/masterData'

definePageMeta({ middleware: 'auth' })

const api = useMasterData()
const entity = 'phases'

const columns: GridColumn[] = [
  { field: 'code', header: 'Phase code', required: true, sortable: true, width: '150px', placeholder: 'e.g. DRILL, COMP, ABAND' },
  { field: 'name', header: 'Phase name', required: true, sortable: true, width: '220px', placeholder: 'e.g. Drilling, Completion' },
  { field: 'sequence', header: 'Sequence', type: 'number', width: '100px' },
  { field: 'description', header: 'Description', type: 'textarea', width: '300px' },
  { field: 'is_active', header: 'Active', type: 'checkbox', width: '110px' },
]

function fetchPage(params: Record<string, unknown>): Promise<PageResponse<Record<string, unknown>>> {
  return api.listPage(entity, params as Record<string, string>) as unknown as Promise<PageResponse<Record<string, unknown>>>
}

function toRow(record: Record<string, unknown>) {
  const item = record as unknown as MasterDataRecord
  return {
    id: item.id,
    code: item.code,
    name: item.name,
    sequence: item.sequence ?? 1,
    description: item.description ?? '',
    is_active: item.is_active,
  }
}

function toPayload(row: EditableRow) {
  return {
    code: String(row.code ?? '').trim(),
    name: String(row.name ?? '').trim(),
    sequence: Number(row.sequence) || 1,
    description: row.description || null,
    is_active: row.is_active !== false,
  }
}

const blankRow = () => ({ code: '', name: '', sequence: 1, description: '', is_active: true })
</script>

<template>
  <div class="library-page">
    <PageHeader
      title="Phases"
      description="Configure the drilling and completion operational phases available for AFE section planning and daily cost tracking — Drilling, Completion, Abandonment, etc."
    />
    <MasterDataNav active="phases" />
    <EnterpriseGrid
      title="Phases"
      singular="phase"
      :columns="columns"
      :fetch-page="fetchPage"
      :to-row="toRow"
      :to-payload="toPayload"
      :blank-row="blankRow"
      :bulk-create="rows => api.bulkCreate(entity, rows as never)"
      :bulk-update="rows => api.bulkUpdate(entity, rows as never)"
      :remove-record="(id, hard) => (hard ? api.remove(entity, id) : api.deactivate(entity, id))"
      default-sort="sequence"
      search-placeholder="Search phases…"
    />
  </div>
</template>
