<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import Button from 'primevue/button'
import Column from 'primevue/column'
import DataTable from 'primevue/datatable'
import InputText from 'primevue/inputtext'
import Message from 'primevue/message'
import Select from 'primevue/select'
import Tag from 'primevue/tag'
import PageHeader from '~/components/design-system/PageHeader.vue'
import type { AuditFilters, AuditLogRecord } from '~/services/audit'
import { downloadBlob } from '~/utils/download'
import { escapeHtml, printDocument } from '~/utils/printDocument'

definePageMeta({ middleware: 'auth' })

const audit = useAudit()

const logs = ref<AuditLogRecord[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(25)
const search = ref('')
const actionFilter = ref<string | null>(null)
const entityFilter = ref<string | null>(null)
const loading = ref(false)
const exporting = ref(false)
const printing = ref(false)
const error = ref<string | null>(null)

const actionOptions = [
  { label: 'All actions', value: null },
  { label: 'Login', value: 'login' },
  { label: 'Create', value: 'create' },
  { label: 'Update', value: 'update' },
  { label: 'Save rates', value: 'save_rates' },
  { label: 'Submit', value: 'submitted' },
  { label: 'Reopen', value: 'reopen' },
  { label: 'Resubmit', value: 'resubmitted' },
  { label: 'Soft delete', value: 'soft_delete' },
  { label: 'Recover', value: 'recover' },
  { label: 'Hard delete', value: 'hard_delete' },
  { label: 'Bulk create', value: 'bulk_create' },
  { label: 'Import preview', value: 'import_preview' },
  { label: 'Import commit', value: 'import_commit' },
  { label: 'Export', value: 'export' },
]

const entityOptions = [
  { label: 'All entities', value: null },
  { label: 'User', value: 'user' },
  { label: 'Project', value: 'project' },
  { label: 'Well', value: 'well' },
  { label: 'AFE', value: 'afe' },
  { label: 'AFE line', value: 'afe_line' },
  { label: 'AFE cost estimate', value: 'afe_cost_estimate' },
  { label: 'Daily cost entry', value: 'daily_cost_entry' },
  { label: 'Well activity', value: 'well_activity' },
  { label: 'Report', value: 'report' },
  { label: 'Audit log', value: 'audit_log' },
  { label: 'Primary category', value: 'primary-categories' },
  { label: 'Secondary category', value: 'secondary-categories' },
  { label: 'Tertiary category', value: 'tertiary-categories' },
  { label: 'Cost category', value: 'cost-categories' },
  { label: 'Cost code', value: 'cost-codes' },
  { label: 'Unit', value: 'units' },
  { label: 'Currency', value: 'currencies' },
  { label: 'Hole section', value: 'hole-sections' },
  { label: 'Vendor', value: 'vendors' },
  { label: 'Catalogue item', value: 'catalog_item' },
  { label: 'Drilling phase', value: 'drilling_phase' },
  { label: 'Dropdown binding', value: 'dropdown_binding' },
  { label: 'Import batch', value: 'import_batch' },
  { label: 'AFE import batch', value: 'afe_import_batch' },
]

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize.value)))
const firstRecord = computed(() => total.value === 0 ? 0 : (page.value - 1) * pageSize.value + 1)
const lastRecord = computed(() => Math.min(page.value * pageSize.value, total.value))

function severityFor(action: string): string {
  if (action === 'login') return 'info'
  if (action === 'create' || action === 'bulk_create') return 'success'
  if (action === 'update' || action === 'reopen' || action === 'recover' || action === 'submitted' || action === 'resubmitted') return 'warn'
  if (action === 'soft_delete' || action === 'hard_delete') return 'danger'
  return 'secondary'
}

async function load(): Promise<void> {
  loading.value = true
  error.value = null
  try {
    const res = await audit.list({
      page: page.value,
      page_size: pageSize.value,
      search: search.value.trim() || undefined,
      action: actionFilter.value || undefined,
      entity_type: entityFilter.value || undefined,
    })
    logs.value = res.items as unknown as AuditLogRecord[]
    total.value = res.total
  } catch (caught: unknown) {
    error.value = caught instanceof Error ? caught.message : 'Audit log could not be loaded'
  } finally {
    loading.value = false
  }
}

function currentFilters(): AuditFilters {
  return {
    search: search.value.trim() || undefined,
    action: actionFilter.value || undefined,
    entity_type: entityFilter.value || undefined,
  }
}

async function exportAudit(): Promise<void> {
  exporting.value = true
  error.value = null
  try {
    downloadBlob(await audit.export(currentFilters()), 'audit-log.xlsx')
  }
  catch (caught: unknown) {
    error.value = caught instanceof Error ? caught.message : 'Audit log export failed.'
  }
  finally { exporting.value = false }
}

async function printAudit(): Promise<void> {
  printing.value = true
  error.value = null
  try {
    const records = await audit.listAll(currentFilters())
    const body = records.map(record => `<tr>
      <td>${escapeHtml(new Date(record.created_at).toLocaleString())}</td>
      <td>${escapeHtml(record.actor_email ?? '—')}</td><td>${escapeHtml(record.action)}</td>
      <td>${escapeHtml(record.entity_type)}</td><td>${escapeHtml(record.entity_code ?? record.entity_id ?? '—')}</td>
      <td>${escapeHtml(record.details ?? '—')}</td></tr>`).join('')
    printDocument('Audit Log', `<h1>AUDIT LOG</h1><p class="doc-subtitle">Immutable user-action trail · ${records.length} filtered entries</p><table><thead><tr><th>Timestamp</th><th>Actor</th><th>Action</th><th>Entity</th><th>Entity code</th><th>Details</th></tr></thead><tbody>${body || '<tr><td colspan="6">No entries match the selected filters.</td></tr>'}</tbody></table><p class="print-footer">Printed ${new Date().toLocaleString()}.</p>`)
  }
  catch (caught: unknown) {
    error.value = caught instanceof Error ? caught.message : 'Audit log print data could not be loaded.'
  }
  finally { printing.value = false }
}

function goToPage(target: number): void {
  page.value = Math.min(Math.max(1, target), totalPages.value)
  void load()
}

function changePageSize(value: number): void {
  pageSize.value = value
  page.value = 1
  void load()
}

function resetFilters(): void {
  search.value = ''
  actionFilter.value = null
  entityFilter.value = null
  page.value = 1
  void load()
}

let searchTimer: ReturnType<typeof setTimeout> | undefined
watch(search, () => {
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    page.value = 1
    void load()
  }, 400)
})
watch([actionFilter, entityFilter], () => {
  page.value = 1
  void load()
})

onMounted(() => void load())
</script>

<template>
  <div class="library-page">
    <PageHeader
      title="Audit Log"
      description="Complete immutable trail across Master Data, AFE, AFE Cost Estimates, Daily Cost, Well Activities and report exports. Print or export the complete filtered result."
    >
      <template #actions>
        <Button label="Print" icon="pi pi-print" outlined :loading="printing" @click="printAudit" />
        <Button label="Export Excel" icon="pi pi-file-excel" outlined :loading="exporting" @click="exportAudit" />
        <Button label="Refresh" icon="pi pi-refresh" :loading="loading" @click="load" />
      </template>
    </PageHeader>

    <Message v-if="error" severity="error" :closable="true" @close="error = null">{{ error }}</Message>

    <section class="audit-filters">
      <div class="audit-filters__search">
        <i class="pi pi-search" aria-hidden="true" />
        <InputText v-model="search" placeholder="Search by actor, entity, code, or details…" />
      </div>
      <Select v-model="actionFilter" :options="actionOptions" option-label="label" option-value="value" placeholder="All actions" show-clear style="width: 190px" />
      <Select v-model="entityFilter" :options="entityOptions" option-label="label" option-value="value" placeholder="All entities" show-clear style="width: 190px" />
      <Button v-if="search || actionFilter || entityFilter" label="Clear filters" icon="pi pi-filter-slash" text severity="secondary" @click="resetFilters" />
    </section>

    <DataTable :value="logs" :loading="loading" data-key="id" striped-rows show-gridlines size="small" scrollable scroll-height="560px" class="audit-table">
      <Column header="Timestamp" style="min-width: 170px">
        <template #body="{ data }">{{ new Date(data.created_at).toLocaleString() }}</template>
      </Column>
      <Column header="Actor" style="min-width: 180px">
        <template #body="{ data }">
          <div class="audit-actor">
            <strong>{{ data.actor_email || '—' }}</strong>
            <small v-if="data.actor_id" class="audit-actor__id">{{ data.actor_id.slice(0, 8) }}…</small>
          </div>
        </template>
      </Column>
      <Column header="Action" style="width: 140px">
        <template #body="{ data }">
          <Tag :value="data.action" :severity="severityFor(data.action) as any" />
        </template>
      </Column>
      <Column field="entity_type" header="Entity" style="width: 130px" />
      <Column header="Entity code" style="min-width: 150px">
        <template #body="{ data }">{{ data.entity_code || (data.entity_id ? data.entity_id.slice(0, 8) + '…' : '—') }}</template>
      </Column>
      <Column header="Details" style="min-width: 300px">
        <template #body="{ data }">
          <span class="audit-details" :title="data.details || ''">{{ data.details ? (data.details.length > 120 ? data.details.slice(0, 120) + '…' : data.details) : '—' }}</span>
        </template>
      </Column>
      <template #empty>
        <div class="audit-empty">
          <i class="pi pi-history" aria-hidden="true" />
          <p><strong>No audit entries match the current filters.</strong></p>
          <p>Actions are logged from login onward — create, update, submit, reopen, soft-delete, recover, and hard-delete across master data and AFEs.</p>
        </div>
      </template>
    </DataTable>

    <div class="audit-pager">
      <span class="audit-pager__info">Showing <strong>{{ firstRecord }}</strong>–<strong>{{ lastRecord }}</strong> of <strong>{{ total }}</strong> entries</span>
      <div class="audit-pager__controls">
        <label for="audit-page-size">Rows</label>
        <Select id="audit-page-size" :model-value="pageSize" :options="[10, 25, 50, 100]" style="width: 92px" @update:model-value="changePageSize" />
        <Button icon="pi pi-angle-double-left" text :disabled="page === 1" aria-label="First page" @click="goToPage(1)" />
        <Button icon="pi pi-angle-left" text :disabled="page === 1" aria-label="Previous page" @click="goToPage(page - 1)" />
        <span class="audit-pager__page">Page {{ page }} of {{ totalPages }}</span>
        <Button icon="pi pi-angle-right" text :disabled="page >= totalPages" aria-label="Next page" @click="goToPage(page + 1)" />
        <Button icon="pi pi-angle-double-right" text :disabled="page >= totalPages" aria-label="Last page" @click="goToPage(totalPages)" />
      </div>
    </div>
  </div>
</template>

<style scoped>
.audit-filters {
  display: flex;
  gap: 0.75rem;
  align-items: center;
  flex-wrap: wrap;
  margin: 1rem 0 0.75rem;
  padding: 0.75rem;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
}
.audit-filters__search {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex: 1;
  min-width: 240px;
}
.audit-filters__search :deep(input) {
  flex: 1;
}
.audit-table {
  margin-top: 0.5rem;
}
.audit-actor {
  display: flex;
  flex-direction: column;
  line-height: 1.2;
}
.audit-actor__id {
  color: #64748b;
  font-size: 0.7rem;
}
.audit-details {
  font-size: 0.8rem;
  color: #334155;
  word-break: break-word;
}
.audit-empty {
  text-align: center;
  padding: 2rem 1rem;
  color: #64748b;
}
.audit-empty i {
  font-size: 1.8rem;
  margin-bottom: 0.5rem;
  display: block;
}
.audit-pager {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 0.75rem;
  flex-wrap: wrap;
  gap: 0.75rem;
  font-size: 0.85rem;
}
.audit-pager__controls {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}
.audit-pager__page {
  min-width: 110px;
  text-align: center;
}
</style>
