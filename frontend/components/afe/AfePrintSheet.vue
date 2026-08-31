<script setup lang="ts">
/**
 * Print-only sheet for a complete AFE, portrait A4, two pages.
 *
 *   Page 1 — the estimate at a glance:
 *     1. metadata header — rig / well / type / status
 *     2. well configuration — hole sections, phases, depths, planned days
 *     3. summary — the service list with one cost per service (no section /
 *        phase split), the consumable main categories with their totals, the
 *        tangibles total, and the Total AFE cost (services + consumables +
 *        tangibles)
 *
 *   Page 2 — the list of tangibles going into the well.
 *
 * Rendered invisible on screen — the print stylesheet is what shows it — so
 * the same markup serves the list's row-wise Print button and the cost
 * estimation dialog.
 */
import { computed } from 'vue'
import type { AfeEstimate, ConsumableKind } from '~/types/afe'

const props = defineProps<{
  estimate: AfeEstimate
  printedAt?: string
}>()

function money(value: string | number | null | undefined): string {
  if (value == null || value === '') return '0.00'
  const numeric = Number(value)
  return Number.isFinite(numeric) ? numeric.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : String(value)
}

function quantity(value: string | number | null): string {
  if (value == null || value === '') return '—'
  const numeric = Number(value)
  return Number.isFinite(numeric) ? String(numeric) : String(value)
}

function depth(value: string | number | null): string {
  if (value == null || value === '') return '—'
  return `${Number(value)} ${props.estimate.well_configuration?.depth_unit === 'ft' ? 'ft' : 'm'}`
}

const afe = computed(() => props.estimate.afe)
const well = computed(() => props.estimate.well_configuration)
const statusLabel = computed(() => {
  const map: Record<string, string> = { draft: 'Draft', submitted: 'Submitted', approved: 'Approved' }
  return map[afe.value.status] ?? afe.value.status
})
const meta = computed(() => {
  const parts = [
    afe.value.rig_display || '—',
    afe.value.well_display || '—',
    afe.value.afe_type,
    statusLabel.value,
    `Well total depth ${depth(well.value?.total_depth ?? null)}`,
    `Planned days ${quantity(well.value?.total_days ?? 0)}`,
  ]
  if (afe.value.status_remarks) parts.push(`Status remarks: ${afe.value.status_remarks}`)
  if (props.printedAt) parts.push(`Printed ${props.printedAt}`)
  return parts.join(' · ')
})

// --- page 1 summary figures ------------------------------------------------

/** One row per service with its compiled cost — no section/phase split. */
const serviceRows = computed(() =>
  props.estimate.services.map((line, index) => ({
    key: `svc-${line.id}`,
    label: `${index + 1}. ${line.service_code || ''} ${line.service_name || ''}`.trim(),
    basis: line.charging_basis,
    amount: line.estimate.amount,
  })),
)
const servicesTotal = computed(() =>
  serviceRows.value.reduce((sum, row) => sum + Number(row.amount ?? 0), 0),
)

const CONSUMABLE_CATEGORY_LABELS: Record<ConsumableKind, string> = {
  mud_chemical: 'Mud Chemicals',
  drill_bit: 'Drill Bits',
  cement_additive: 'Cement Additives',
  fuel: 'Fuel',
}
const CONSUMABLE_CATEGORY_ORDER: ConsumableKind[] = ['mud_chemical', 'drill_bit', 'cement_additive', 'fuel']

/** Consumables rolled up to their main category and its cost. */
const consumableCategoryRows = computed(() => {
  const totals = new Map<string, number>()
  const labelOf = (kind: string): string => CONSUMABLE_CATEGORY_LABELS[kind as ConsumableKind] ?? kind
  for (const line of props.estimate.consumables) {
    const label = labelOf(line.item_kind)
    totals.set(label, (totals.get(label) ?? 0) + Number(line.estimate.amount ?? 0))
  }
  // Known categories in display order first, then anything unexpected.
  const labels = [
    ...CONSUMABLE_CATEGORY_ORDER.filter(kind => props.estimate.consumables.some(line => line.item_kind === kind))
      .map(kind => CONSUMABLE_CATEGORY_LABELS[kind]),
    ...[...new Set(props.estimate.consumables.map(line => labelOf(line.item_kind)))]
      .filter(label => !CONSUMABLE_CATEGORY_ORDER.some(kind => CONSUMABLE_CATEGORY_LABELS[kind] === label)),
  ]
  return labels.map(label => ({ key: `con-${label}`, label, amount: totals.get(label) ?? 0 }))
})
const consumablesTotal = computed(() =>
  consumableCategoryRows.value.reduce((sum, row) => sum + row.amount, 0),
)

const tangiblesTotal = computed(() =>
  props.estimate.tangibles.reduce((sum, line) => sum + Number(line.estimate.amount ?? 0), 0),
)
/** The engine's compiled total is authoritative for the bottom line. */
const grandTotal = computed(() => money(props.estimate.grand_total))

const tangibleRows = computed(() =>
  props.estimate.tangibles.map((line, index) => ({
    key: `tan-${line.id}`,
    index: index + 1,
    code: line.tangible_code || '—',
    name: line.tangible_name || '—',
    quantity: quantity(line.quantity),
    uom: line.uom || '—',
    rate: line.override_rate == null || line.override_rate === '' ? line.captured_rate : line.override_rate,
    amount: line.estimate.amount,
  })),
)
</script>

<template>
  <div class="print-sheet afe-print" aria-hidden="true" data-testid="afe-print-sheet">
    <header class="print-sheet__header">
      <p class="print-sheet__eyebrow">Drilling Costing — AFE Cost Estimate</p>
      <h1>{{ afe.afe_code }} — {{ afe.afe_name }}</h1>
      <p class="print-sheet__meta">{{ meta }}</p>
      <p v-if="afe.remarks" class="print-sheet__meta">Remarks: {{ afe.remarks }}</p>
    </header>

    <!-- 1 — well configuration metadata -->
    <h2 class="afe-print__title">Well configuration</h2>
    <table class="print-sheet__table">
      <thead>
        <tr>
          <th>#</th>
          <th>Hole Section</th>
          <th>From</th>
          <th>To</th>
          <th>Phase</th>
          <th>Planned Days</th>
        </tr>
      </thead>
      <tbody>
        <tr v-if="!well || !well.sections.length">
          <td colspan="6" class="print-sheet__empty">
            No configuration saved for this well — day-based estimates cannot be calculated.
          </td>
        </tr>
        <template v-for="(section, sIndex) in (well?.sections ?? [])" :key="`s-${section.id}`">
          <tr v-if="!section.phases.length">
            <td>{{ sIndex + 1 }}</td>
            <td>{{ section.section_code || '—' }}{{ section.section_name ? ` — ${section.section_name}` : '' }}</td>
            <td>{{ depth(section.from_depth) }}</td>
            <td>{{ depth(section.to_depth) }}</td>
            <td>—</td>
            <td>{{ quantity(section.total_days) }}</td>
          </tr>
          <tr v-for="(phase, pIndex) in section.phases" :key="`p-${section.id}-${phase.id}`">
            <td>{{ pIndex === 0 ? sIndex + 1 : '' }}</td>
            <td>{{ pIndex === 0 ? `${section.section_code || '—'}${section.section_name ? ` — ${section.section_name}` : ''}` : '' }}</td>
            <td>{{ pIndex === 0 ? depth(section.from_depth) : '' }}</td>
            <td>{{ pIndex === 0 ? depth(section.to_depth) : '' }}</td>
            <td>{{ phase.phase_code || '—' }}{{ phase.phase_name ? ` — ${phase.phase_name}` : '' }}</td>
            <td>{{ quantity(phase.days) }}</td>
          </tr>
        </template>
      </tbody>
    </table>

    <!-- 2 — summary: services, consumable categories, tangibles, total -->
    <h2 class="afe-print__title">AFE cost estimate summary</h2>

    <table class="print-sheet__table afe-print__services">
      <thead>
        <tr>
          <th>Service</th>
          <th>Charging Basis</th>
          <th class="afe-print__num">Cost</th>
        </tr>
      </thead>
      <tbody>
        <tr v-if="!serviceRows.length">
          <td colspan="3" class="print-sheet__empty">No services configured.</td>
        </tr>
        <tr v-for="row in serviceRows" :key="row.key">
          <td>{{ row.label }}</td>
          <td>{{ row.basis }}</td>
          <td class="afe-print__num">{{ money(row.amount) }}</td>
        </tr>
      </tbody>
      <tfoot>
        <tr>
          <th colspan="2">Services total</th>
          <th class="afe-print__num">{{ money(servicesTotal) }}</th>
        </tr>
      </tfoot>
    </table>

    <table class="print-sheet__table afe-print__categories">
      <thead>
        <tr>
          <th>Consumables</th>
          <th class="afe-print__num">Cost</th>
        </tr>
      </thead>
      <tbody>
        <tr v-if="!consumableCategoryRows.length">
          <td colspan="2" class="print-sheet__empty">No consumables configured.</td>
        </tr>
        <tr v-for="row in consumableCategoryRows" :key="row.key">
          <td>{{ row.label }}</td>
          <td class="afe-print__num">{{ money(row.amount) }}</td>
        </tr>
      </tbody>
      <tfoot>
        <tr>
          <th>Consumables total</th>
          <th class="afe-print__num">{{ money(consumablesTotal) }}</th>
        </tr>
      </tfoot>
    </table>

    <table class="print-sheet__table afe-print__totals">
      <tbody>
        <tr>
          <td>Services total</td>
          <td class="afe-print__num">{{ money(servicesTotal) }}</td>
        </tr>
        <tr>
          <td>Consumables total</td>
          <td class="afe-print__num">{{ money(consumablesTotal) }}</td>
        </tr>
        <tr>
          <td>Tangibles total ({{ estimate.tangibles.length }} item(s) — listed on page 2)</td>
          <td class="afe-print__num">{{ money(tangiblesTotal) }}</td>
        </tr>
      </tbody>
      <tfoot>
        <tr>
          <th>Total AFE cost</th>
          <th class="afe-print__num">{{ grandTotal }}</th>
        </tr>
      </tfoot>
    </table>

    <!-- 3 — page 2: the tangibles going into the well -->
    <div v-if="estimate.tangibles.length" class="afe-print__page2">
      <h2 class="afe-print__title">Tangibles to be used</h2>
      <table class="print-sheet__table">
        <thead>
          <tr>
            <th>#</th>
            <th>Code</th>
            <th>Tangible</th>
            <th>Qty</th>
            <th>UOM</th>
            <th>Rate</th>
            <th>Amount</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in tangibleRows" :key="row.key">
            <td>{{ row.index }}</td>
            <td>{{ row.code }}</td>
            <td>{{ row.name }}</td>
            <td>{{ row.quantity }}</td>
            <td>{{ row.uom }}</td>
            <td class="afe-print__num">{{ money(row.rate) }}</td>
            <td class="afe-print__num">{{ money(row.amount) }}</td>
          </tr>
        </tbody>
        <tfoot>
          <tr>
            <th colspan="6">Tangibles total</th>
            <th class="afe-print__num">{{ money(tangiblesTotal) }}</th>
          </tr>
        </tfoot>
      </table>
    </div>

    <p v-if="estimate.warnings.length" class="afe-print__warnings">
      Notes: {{ estimate.warnings.join(' · ') }}
    </p>
  </div>
</template>

<style scoped>
  .afe-print__title {
    margin: 10px 0 3px;
    font-size: .78rem;
    font-weight: 800;
    letter-spacing: .06em;
    text-transform: uppercase;
    color: #333;
  }

  .afe-print__num {
    text-align: right;
    font-variant-numeric: tabular-nums;
    white-space: nowrap;
  }

  /* Keep the summary compact so well configuration + summary share page 1. */
  .afe-print :deep(.print-sheet__table) {
    font-size: .72rem;
  }

  .afe-print :deep(.print-sheet__table th),
  .afe-print :deep(.print-sheet__table td) {
    padding: 2px 4px;
  }

  .afe-print__services,
  .afe-print__categories,
  .afe-print__totals {
    margin-top: 6px;
  }

  .afe-print__totals td {
    font-weight: 600;
  }

  .afe-print__totals tfoot th {
    background: #e8eef1;
    font-weight: 800;
    font-size: .74rem;
  }

  .afe-print__categories tfoot th,
  .afe-print__services tfoot th,
  .afe-print__page2 tfoot th {
    background: #f2f6f7;
    font-weight: 700;
  }

  /* The tangible list always starts on the second page. */
  .afe-print__page2 {
    break-before: page;
    page-break-before: always;
  }

  .afe-print__warnings {
    margin-top: 10px;
    font-size: .68rem;
    color: #555;
  }
</style>
