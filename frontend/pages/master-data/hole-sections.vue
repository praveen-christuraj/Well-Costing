<script setup lang="ts">
import EnterpriseGrid from '~/components/data-grid/EnterpriseGrid.vue'
import MasterDataNav from '~/components/master-data/MasterDataNav.vue'
import PageHeader from '~/components/design-system/PageHeader.vue'
import type { EditableRow, GridColumn } from '~/types/grid'
import type { MasterDataRecord, PageResponse } from '~/types/masterData'
definePageMeta({ middleware: 'auth' })
const api = useMasterData(); const entity = 'hole-sections'
const columns: GridColumn[] = [
  { field: 'code', header: 'Section code', required: true, sortable: true, width: '160px', placeholder: 'e.g. 12-1/4' },
  { field: 'name', header: 'Hole section', required: true, sortable: true, width: '220px', placeholder: 'e.g. 12-1/4 inch hole' },
  { field: 'description', header: 'Notes', type: 'textarea', width: '300px' },
  { field: 'is_active', header: 'Active', type: 'checkbox', width: '110px' },
]
const fetchPage = (params: Record<string, unknown>) => api.listPage(entity, params as Record<string, string>) as unknown as Promise<PageResponse<Record<string, unknown>>>
const toRow = (record: Record<string, unknown>) => { const r = record as unknown as MasterDataRecord; return { id: r.id, code: r.code, name: r.name, description: r.description ?? '', is_active: r.is_active } }
const toPayload = (row: EditableRow) => ({ code: String(row.code ?? '').trim().toUpperCase(), name: String(row.name ?? '').trim(), description: row.description || null, is_active: row.is_active !== false })
const blankRow = () => ({ code: '', name: '', description: '', is_active: true })
</script>
<template><div class="library-page">
  <PageHeader title="Hole Sections" description="Configure the wellbore sections available for section-based service planning, AFE preparation, and daily cost tracking." />
  <MasterDataNav active="hole-sections" />
  <EnterpriseGrid title="Hole sections" singular="hole section" :columns="columns" :fetch-page="fetchPage" :to-row="toRow" :to-payload="toPayload" :blank-row="blankRow" :bulk-create="rows => api.bulkCreate(entity, rows as never)" :bulk-update="rows => api.bulkUpdate(entity, rows as never)" :remove-record="(id, hard) => (hard ? api.remove(entity, id) : api.deactivate(entity, id))" default-sort="code" search-placeholder="Search hole sections…" />
</div></template>
