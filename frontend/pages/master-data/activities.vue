/** Activity master data — Planned, NPT, UPA classification.

These are the top-level activity types. Well-scoped sub-activities (e.g.
NPT-1, NPT-2, UPA-1) are configured inside the well after AFE creation.
*/
<script setup lang="ts">
import EnterpriseGrid from '~/components/data-grid/EnterpriseGrid.vue'
import MasterDataNav from '~/components/master-data/MasterDataNav.vue'
import PageHeader from '~/components/design-system/PageHeader.vue'
import type { EditableRow, GridColumn } from '~/types/grid'
import type { MasterDataRecord, PageResponse } from '~/types/masterData'

definePageMeta({ middleware: 'auth' })

const api = useMasterData()
const entity = 'activities'

const columns: GridColumn[] = [
  { field: 'code', header: 'Activity code', required: true, sortable: true, width: '140px', placeholder: 'e.g. PLANNED, NPT' },
  { field: 'name', header: 'Activity name', required: true, sortable: true, width: '200px', placeholder: 'e.g. Planned, NPT, UPA' },
  { field: 'sequence', header: 'Sequence', type: 'number', width: '100px' },
  { field: 'description', header: 'Description', type: 'textarea', width: '300px' },
  { field: 'is_active', header: 'Status', type: 'checkbox', width: '110px' },
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
      title="Activities"
      description="Master activity classification: Planned, NPT (Non Productive Time), and UPA (Unplanned Activity). Well-scoped sub-activities are configured inside each well after AFE creation."
    />
    <MasterDataNav active="activities" />

    <section class="cc-guide">
      <h2>What is an Activity?</h2>
      <p>
        Activities classify daily cost entries into <strong>Planned</strong>, <strong>NPT</strong>
        (Non Productive Time), and <strong>UPA</strong> (Unplanned Activity). Each well then
        configures sub-activities (e.g. NPT-1, NPT-2) linked to one of these primaries, with a
        responsible party for cost accountability.
      </p>
      <div class="cc-guide__grid">
        <article>
          <h3>Planned</h3>
          <p>Normal drilling and operational activities proceeding as scheduled.</p>
        </article>
        <article>
          <h3>NPT — Non Productive Time</h3>
          <p>Time lost due to equipment failure, weather, or other interruptions. Sub-classified
          into NPT-1, NPT-2, etc. per responsible party.</p>
        </article>
        <article>
          <h3>UPA — Unplanned Activity</h3>
          <p>Work that was not in the original plan but is not necessarily unproductive —
          e.g. sidetracks, additional logging runs. Sub-classified per responsible party.</p>
        </article>
        <article>
          <h3>Daily Cost Tracking</h3>
          <p>Each service line on a daily cost entry is tagged with a sub-activity. Costs roll up
          by activity type: X = X<sub>1</sub> (Planned) + X<sub>2</sub> (NPT) + X<sub>3</sub> (UPA).</p>
        </article>
      </div>
    </section>

    <EnterpriseGrid
      title="Activities"
      singular="activity"
      :columns="columns"
      :fetch-page="fetchPage"
      :to-row="toRow"
      :to-payload="toPayload"
      :blank-row="blankRow"
      :validate-rows="rows => api.validate(entity, rows as never)"
      :bulk-create="rows => api.bulkCreate(entity, rows as never)"
      :bulk-update="rows => api.bulkUpdate(entity, rows as never)"
      :remove-record="(id, hard) => (hard ? api.remove(entity, id) : api.deactivate(entity, id))"
      import-entity="activities"
      export-entity="activities"
      default-sort="sequence"
      search-placeholder="Search activities…"
    />
  </div>
</template>

<style scoped>
.cc-guide {
  padding: 16px 18px;
  margin-bottom: 16px;
  border: 1px solid var(--app-border);
  border-radius: 12px;
  background: white;
  box-shadow: var(--app-shadow);
}

.cc-guide h2 {
  margin: 0 0 6px;
  font-size: 1.05rem;
}

.cc-guide > p {
  margin: 0 0 14px;
  color: var(--app-muted);
  line-height: 1.6;
}

.cc-guide__grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.cc-guide article {
  padding: 12px 14px;
  border: 1px solid var(--app-border);
  border-radius: 9px;
  background: #fafcfd;
}

.cc-guide h3 {
  margin: 0 0 8px;
  font-size: .86rem;
}

.cc-guide article p {
  margin: 0;
  color: var(--app-muted);
  font-size: .78rem;
  line-height: 1.6;
}

@media (max-width: 820px) {
  .cc-guide__grid {
    grid-template-columns: 1fr;
  }
}
</style>
