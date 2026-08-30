<script setup lang="ts">
/**
 * Depth vs Cost — the AFE estimated cost and the actual cost incurred, plotted
 * against depth. Depth comes from the well configuration, the estimated cost
 * from the AFE cost estimates and the actual cost from the saved daily costs,
 * so both curves share one depth axis.
 *
 * Hand-built SVG on purpose: the project has no charting dependency and a
 * two-series cumulative curve with value labels does not need one.
 */
import { computed } from 'vue'
import type { DepthCostPoint } from '~/types/dailyCost'
import { formatMoney } from '~/utils/dailyCost'

const props = withDefaults(
  defineProps<{
    points: DepthCostPoint[]
    depthUnit?: string
    totalEstimated?: string | null
    totalActual?: string | null
    /** Chart height in CSS pixels (the SVG scales horizontally). */
    height?: number
  }>(),
  { depthUnit: 'm', height: 300, totalEstimated: null, totalActual: null },
)

const WIDTH = 860
const PAD_LEFT = 92
const PAD_RIGHT = 24
const PAD_TOP = 18
const PAD_BOTTOM = 46

/** The prop is defaulted, but the template must not see it as optional. */
const chartHeight = computed(() => props.height)

const innerWidth = WIDTH - PAD_LEFT - PAD_RIGHT
const innerHeight = computed(() => chartHeight.value - PAD_TOP - PAD_BOTTOM)

const numericPoints = computed(() =>
  props.points
    .map(point => ({
      depth: Number(point.depth),
      label: point.section_label,
      estimated: Number(point.estimated_cumulative),
      actual: Number(point.actual_cumulative),
      variance: Number(point.variance),
    }))
    .filter(point => Number.isFinite(point.depth)),
)

const maxDepth = computed(() => {
  const deepest = Math.max(0, ...numericPoints.value.map(point => point.depth))
  return deepest > 0 ? deepest : 1
})

const maxCost = computed(() => {
  const highest = Math.max(
    0,
    ...numericPoints.value.flatMap(point => [point.estimated, point.actual]),
    Number(props.totalEstimated ?? 0) || 0,
    Number(props.totalActual ?? 0) || 0,
  )
  return highest > 0 ? highest * 1.08 : 1
})

function x(depth: number): number {
  return PAD_LEFT + (depth / maxDepth.value) * innerWidth
}

function y(cost: number): number {
  return PAD_TOP + innerHeight.value - (cost / maxCost.value) * innerHeight.value
}

/** A cumulative curve: it starts at zero depth / zero cost. */
function toPath(values: { depth: number, cost: number }[]): string {
  const all = [{ depth: 0, cost: 0 }, ...values]
  return all
    .map((point, index) => `${index === 0 ? 'M' : 'L'}${x(point.depth).toFixed(2)},${y(point.cost).toFixed(2)}`)
    .join(' ')
}

const estimatedPath = computed(() =>
  toPath(numericPoints.value.map(point => ({ depth: point.depth, cost: point.estimated }))),
)
const actualPath = computed(() =>
  toPath(numericPoints.value.map(point => ({ depth: point.depth, cost: point.actual }))),
)

/** Cost axis ticks: five evenly spaced values, formatted as money. */
const costTicks = computed(() => {
  const steps = 5
  return Array.from({ length: steps + 1 }, (_unused, index) => {
    const value = (maxCost.value / steps) * index
    return { value, y: y(value), label: formatMoney(value) }
  })
})

const depthTicks = computed(() =>
  numericPoints.value.map(point => ({
    depth: point.depth,
    x: x(point.depth),
    label: `${point.depth.toLocaleString()} ${props.depthUnit}`,
  })),
)

const hasData = computed(() => numericPoints.value.length > 0)
</script>

<template>
  <div class="depth-chart" data-testid="depth-cost-chart">
    <div class="depth-chart__legend">
      <span class="depth-chart__key depth-chart__key--estimated">
        <i class="depth-chart__swatch depth-chart__swatch--estimated" /> AFE Estimated Cost
        <strong v-if="totalEstimated">{{ formatMoney(totalEstimated) }}</strong>
      </span>
      <span class="depth-chart__key depth-chart__key--actual">
        <i class="depth-chart__swatch depth-chart__swatch--actual" /> Actual Cost at Depth
        <strong v-if="totalActual">{{ formatMoney(totalActual) }}</strong>
      </span>
    </div>

    <p v-if="!hasData" class="depth-chart__empty">
      No hole sections are configured for this well yet — configure the sections and depths in
      Rig &amp; Well Management to plot cost against depth.
    </p>

    <svg
      v-else
      class="depth-chart__svg"
      :view-box="`0 0 ${WIDTH} ${chartHeight}`"
      :style="{ height: `${chartHeight}px` }"
      role="img"
      aria-label="Depth versus cost: AFE estimated cost compared with actual cost incurred"
    >
      <!-- cost grid lines and axis labels -->
      <g class="depth-chart__grid">
        <line
          v-for="tick in costTicks"
          :key="`cost-${tick.value}`"
          :x1="PAD_LEFT"
          :x2="WIDTH - PAD_RIGHT"
          :y1="tick.y"
          :y2="tick.y"
        />
        <text
          v-for="tick in costTicks"
          :key="`cost-label-${tick.value}`"
          :x="PAD_LEFT - 8"
          :y="tick.y + 4"
          text-anchor="end"
        >
          {{ tick.label }}
        </text>
      </g>

      <!-- depth axis labels -->
      <g class="depth-chart__axis">
        <line :x1="PAD_LEFT" :x2="PAD_LEFT" :y1="PAD_TOP" :y2="PAD_TOP + innerHeight" />
        <line
          :x1="PAD_LEFT"
          :x2="WIDTH - PAD_RIGHT"
          :y1="PAD_TOP + innerHeight"
          :y2="PAD_TOP + innerHeight"
        />
        <text
          v-for="tick in depthTicks"
          :key="`depth-${tick.depth}`"
          :x="tick.x"
          :y="PAD_TOP + innerHeight + 20"
          text-anchor="middle"
        >
          {{ tick.label }}
        </text>
        <text :x="PAD_LEFT + innerWidth / 2" :y="chartHeight - 6" text-anchor="middle" class="depth-chart__title">
          Depth ({{ depthUnit }})
        </text>
      </g>

      <path :d="estimatedPath" class="depth-chart__line depth-chart__line--estimated" />
      <path :d="actualPath" class="depth-chart__line depth-chart__line--actual" />

      <g v-for="point in numericPoints" :key="point.depth">
        <circle :cx="x(point.depth)" :cy="y(point.estimated)" r="4" class="depth-chart__dot depth-chart__dot--estimated">
          <title>{{ point.label }} — estimated {{ formatMoney(point.estimated) }}</title>
        </circle>
        <circle :cx="x(point.depth)" :cy="y(point.actual)" r="4" class="depth-chart__dot depth-chart__dot--actual">
          <title>{{ point.label }} — actual {{ formatMoney(point.actual) }}</title>
        </circle>
        <text
          :x="x(point.depth)"
          :y="Math.min(y(point.estimated), y(point.actual)) - 10"
          text-anchor="middle"
          class="depth-chart__value"
        >
          {{ point.label.split(' — ')[0] }}
        </text>
      </g>
    </svg>

    <table v-if="hasData" class="depth-chart__table">
      <thead>
        <tr>
          <th>Hole Section</th>
          <th class="num">Depth ({{ depthUnit }})</th>
          <th class="num">Estimated (cumulative)</th>
          <th class="num">Actual (cumulative)</th>
          <th class="num">Variance</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="point in points" :key="point.section_id">
          <td>{{ point.section_label }}</td>
          <td class="num">{{ Number(point.depth).toLocaleString() }}</td>
          <td class="num">{{ formatMoney(point.estimated_cumulative) }}</td>
          <td class="num">{{ formatMoney(point.actual_cumulative) }}</td>
          <td class="num" :class="{ 'is-over': Number(point.variance) > 0 }">
            {{ formatMoney(point.variance) }}
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<style scoped>
  .depth-chart {
    display: grid;
    gap: 10px;
  }

  .depth-chart__legend {
    display: flex;
    flex-wrap: wrap;
    gap: 16px;
    font-size: 0.78rem;
    color: var(--app-text-muted, #5b6472);
  }

  .depth-chart__key {
    display: inline-flex;
    align-items: center;
    gap: 6px;
  }

  .depth-chart__key strong {
    color: var(--app-text, #1c2430);
  }

  .depth-chart__swatch {
    width: 18px;
    height: 3px;
    border-radius: 2px;
    display: inline-block;
  }

  .depth-chart__swatch--estimated {
    background: #2563eb;
  }

  .depth-chart__swatch--actual {
    background: #d97706;
  }

  .depth-chart__svg {
    width: 100%;
    display: block;
  }

  .depth-chart__grid line {
    stroke: var(--app-border, #e3e7ee);
    stroke-width: 1;
  }

  .depth-chart__grid text,
  .depth-chart__axis text {
    font-size: 10px;
    fill: var(--app-text-muted, #6b7480);
  }

  .depth-chart__axis line {
    stroke: var(--app-border-strong, #c8cfda);
    stroke-width: 1;
  }

  .depth-chart__title {
    font-size: 10px;
    letter-spacing: 0.04em;
    text-transform: uppercase;
  }

  .depth-chart__line {
    fill: none;
    stroke-width: 2.5;
    stroke-linejoin: round;
  }

  .depth-chart__line--estimated {
    stroke: #2563eb;
    stroke-dasharray: 6 4;
  }

  .depth-chart__line--actual {
    stroke: #d97706;
  }

  .depth-chart__dot--estimated {
    fill: #2563eb;
  }

  .depth-chart__dot--actual {
    fill: #d97706;
  }

  .depth-chart__value {
    font-size: 10px;
    fill: var(--app-text, #1c2430);
    font-weight: 600;
  }

  .depth-chart__table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.76rem;
  }

  .depth-chart__table th,
  .depth-chart__table td {
    border-bottom: 1px solid var(--app-border, #e6eaf1);
    padding: 4px 8px;
    text-align: left;
    white-space: nowrap;
  }

  .depth-chart__table th {
    font-weight: 600;
    color: var(--app-text-muted, #5b6472);
    background: var(--app-surface-muted, #f7f9fc);
  }

  .depth-chart__table .num {
    text-align: right;
    font-variant-numeric: tabular-nums;
  }

  .depth-chart__table .is-over {
    color: #b91c1c;
    font-weight: 600;
  }

  .depth-chart__empty {
    margin: 0;
    padding: 18px;
    border: 1px dashed var(--app-border, #dbe1ea);
    border-radius: 10px;
    font-size: 0.8rem;
    color: var(--app-text-muted, #5b6472);
  }
</style>
