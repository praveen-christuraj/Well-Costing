<script setup lang="ts">
import { computed } from 'vue'
import DataTable from 'primevue/datatable'
import EmptyState from '~/components/design-system/EmptyState.vue'

const props = withDefaults(defineProps<{
  rows: Record<string, unknown>[]
  loading?: boolean
  pageSize?: number
  totalRecords?: number
  lazy?: boolean
  emptyTitle?: string
}>(), {
  loading: false,
  pageSize: 25,
  totalRecords: 0,
  lazy: false,
  emptyTitle: 'No records found',
})

const resolvedEmptyTitle = computed(() => props.emptyTitle ?? 'No records found')
</script>

<template>
  <DataTable
    :value="rows"
    :loading="loading"
    :rows="pageSize"
    :total-records="totalRecords"
    :lazy="lazy"
    paginator
    striped-rows
    removable-sort
    show-gridlines
    size="small"
    scrollable
    scroll-height="flex"
    data-key="id"
    class="data-table-wrapper"
  >
    <slot />
    <template #empty>
      <slot name="empty">
        <EmptyState :title="resolvedEmptyTitle" />
      </slot>
    </template>
  </DataTable>
</template>
