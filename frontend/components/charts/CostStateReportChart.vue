<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import EmptyState from '~/components/design-system/EmptyState.vue'
import type { StateSummary } from '~/types/reporting'
const props = defineProps<{ states: StateSummary[] }>()
const chartElement = ref<HTMLElement | null>(null)
const hasAmounts = computed(() => props.states.length > 0 && props.states.every(item => item.amount !== null))
let chart: { dispose: () => void, setOption: (option: object) => void } | null = null
async function render() { if (!hasAmounts.value || !chartElement.value || !import.meta.client) return; const echarts = await import('echarts'); chart?.dispose(); chart = echarts.init(chartElement.value); chart.setOption({ tooltip: { trigger: 'axis' }, xAxis: { type: 'category', data: props.states.map(item => item.cost_state.replace('_', ' ')) }, yAxis: { type: 'value' }, series: [{ type: 'bar', data: props.states.map(item => Number(item.amount)), itemStyle: { color: '#0f766e' } }] }) }
watch(() => props.states, async () => { await nextTick(); await render() }, { deep: true, immediate: true })
onBeforeUnmount(() => chart?.dispose())
</script>
<template><div><div v-if="hasAmounts" ref="chartElement" class="estimate-chart" /><EmptyState v-else title="Financial metrics pending" description="Cost-state totals and comparison charts require approved reporting currency, overlap, variance, forecast, and rounding rules." icon="pi pi-chart-bar" /></div></template>
