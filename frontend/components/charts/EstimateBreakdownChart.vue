<script setup lang="ts">
import { nextTick, onBeforeUnmount, ref, watch } from 'vue'
import EmptyState from '~/components/design-system/EmptyState.vue'

const props = defineProps<{ categories: Record<string, unknown>[] }>()
const chartElement = ref<HTMLElement | null>(null)
let chart: { dispose: () => void, setOption: (option: object) => void } | null = null

async function render(): Promise<void> {
  if (!props.categories.length || !chartElement.value || !import.meta.client) return
  const echarts = await import('echarts')
  chart?.dispose()
  chart = echarts.init(chartElement.value)
  chart.setOption({
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'category', data: props.categories.map(item => String(item.cost_category_code ?? 'Uncategorized')) },
    yAxis: { type: 'value' },
    series: [{ name: 'Total', type: 'bar', data: props.categories.map(item => Number(item.grand_total ?? 0)), itemStyle: { color: '#0f766e' } }],
  })
}
watch(() => props.categories, async () => { await nextTick(); await render() }, { deep: true, immediate: true })
onBeforeUnmount(() => chart?.dispose())
</script>
<template><div class="chart-shell"><div v-if="categories.length" ref="chartElement" class="estimate-chart" /><EmptyState v-else title="No calculated breakdown" description="Category totals will appear only after confirmed Phase 5 rules are implemented and a calculation completes." icon="pi pi-chart-bar" /></div></template>
