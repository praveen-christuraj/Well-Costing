/** Cost code register — the classification attached to every AFE line. */
<script setup lang="ts">
import { computed, onMounted } from 'vue'
import EnterpriseGrid from '~/components/data-grid/EnterpriseGrid.vue'
import MasterDataNav from '~/components/master-data/MasterDataNav.vue'
import PageHeader from '~/components/design-system/PageHeader.vue'
import type { EditableRow, GridColumn } from '~/types/grid'
import type { MasterDataRecord, PageResponse } from '~/types/masterData'

definePageMeta({ middleware: 'auth' })

const api = useMasterData()
const references = useReferenceOptions()
const entity = 'cost-codes'

onMounted(() => {
  void references.load(['cost-categories'])
})

const columns = computed<GridColumn[]>(() => [
  { field: 'code', header: 'Cost code', required: true, sortable: true, width: '150px', placeholder: 'e.g. 1000, 2010, DRILL-01' },
  { field: 'name', header: 'Cost code name', required: true, sortable: true, width: '230px', placeholder: 'e.g. Drilling rig day rate' },
  { field: 'cost_category_id', header: 'Cost category', type: 'select', options: references.costCategories.value, required: true, width: '220px' },
  { field: 'description', header: 'Description', type: 'textarea', width: '280px' },
  { field: 'is_active', header: 'Status', type: 'checkbox', width: '110px' },
])

function fetchPage(params: Record<string, unknown>): Promise<PageResponse<Record<string, unknown>>> {
  return api.listPage(entity, params as Record<string, string>) as unknown as Promise<PageResponse<Record<string, unknown>>>
}

function toRow(record: Record<string, unknown>) {
  const item = record as unknown as MasterDataRecord
  return {
    id: item.id,
    code: item.code,
    name: item.name,
    cost_category_id: item.cost_category_id ?? '',
    description: item.description ?? '',
    is_active: item.is_active,
  }
}

function toPayload(row: EditableRow) {
  return {
    code: String(row.code ?? '').trim(),
    name: String(row.name ?? '').trim(),
    cost_category_id: row.cost_category_id || null,
    description: row.description || null,
    is_active: row.is_active !== false,
  }
}

const blankRow = () => ({ code: '', name: '', cost_category_id: '', description: '', is_active: true })

const description = computed(
  () => 'Define the cost codes every AFE line is charged to. A cost code is a short, stable identifier that groups related spend for reporting — the AFE picks one per line and AFE Cost Estimates, Daily Cost, Cost Control and reports roll up under it.',
)
</script>

<template>
  <div class="library-page">
    <PageHeader title="Cost Codes" :description="description" />
    <MasterDataNav active="cost-codes" />

    <div class="uom-tip">
      <i class="pi pi-info-circle" aria-hidden="true" />
      <span>Cost Codes must be configured before you build an AFE. When you add a line to an AFE, you choose the cost code it is charged to — so have the full code list ready here first.</span>
    </div>

    <section class="cc-guide">
      <h2>What is a cost code?</h2>
      <p>
        A <strong>cost code</strong> is the identifier that tells the system <em>where a cost belongs</em>.
        It is not a price and not a rate — it is the classification that every AFE line carries so that
        spend can be grouped, reported, and controlled consistently from planning through to actuals.
      </p>
      <div class="cc-guide__grid">
        <article>
          <h3>What it is used for</h3>
          <ul>
            <li>Every AFE line is charged to exactly one cost code.</li>
            <li>AFE Cost Estimates roll planned line costs up by cost code and configured category.</li>
            <li>Daily Cost, Reports and Cost Control are filtered and summed by cost code.</li>
            <li>It links the estimate to the actuals so variance is measured like-for-like.</li>
          </ul>
        </article>
        <article>
          <h3>How it is structured</h3>
          <ul>
            <li><strong>Cost code</strong> — the short identifier you enter here (e.g. <em>2010</em>).</li>
            <li><strong>Cost category</strong> — the group the code belongs to (e.g. <em>Drilling</em>).</li>
            <li>Categories roll codes up for summary reporting; codes stay at line level.</li>
          </ul>
        </article>
        <article>
          <h3>How to configure it</h3>
          <ol>
            <li>Open <strong>Master Data › Cost Categories</strong> and create the groups first.</li>
            <li>Come back here and add each code, choosing its category from the dropdown.</li>
            <li>Activate the codes you want available on new AFE lines.</li>
            <li>Optionally attach a default code to a catalogue item so AFE lines pre-fill it.</li>
          </ol>
        </article>
        <article>
          <h3>Rules to remember</h3>
          <ul>
            <li>A code must belong to a category — the dropdown is mandatory.</li>
            <li>Codes are unique; you cannot reuse an existing code.</li>
            <li>Deactivating a code hides it from new lines but keeps history intact.</li>
            <li>An in-use code cannot be permanently deleted — deactivate it instead.</li>
          </ul>
        </article>
      </div>
    </section>

    <EnterpriseGrid
      title="Cost codes"
      singular="cost code"
      :columns="columns"
      :fetch-page="fetchPage"
      :to-row="toRow"
      :to-payload="toPayload"
      :blank-row="blankRow"
      :validate-rows="rows => api.validate(entity, rows as never)"
      :bulk-create="rows => api.bulkCreate(entity, rows as never)"
      :bulk-update="rows => api.bulkUpdate(entity, rows as never)"
      :remove-record="(id, hard) => (hard ? api.remove(entity, id) : api.deactivate(entity, id))"
      import-entity="cost-codes"
      export-entity="cost-codes"
      default-sort="code"
      search-placeholder="Search by cost code or name…"
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

.cc-guide ul,
.cc-guide ol {
  margin: 0;
  padding-left: 18px;
  color: var(--app-muted);
  font-size: .78rem;
  line-height: 1.6;
}

.cc-guide li {
  margin-bottom: 4px;
}

@media (max-width: 820px) {
  .cc-guide__grid {
    grid-template-columns: 1fr;
  }
}
</style>
