<script setup lang="ts">
/**
 * Print-only sheet for a complete AFE: the well configuration in the metadata
 * header, then the service, consumable and tangible costs with the compiled
 * group totals. Rendered invisible on screen — the print stylesheet is what
 * shows it — so the same markup serves the list's row-wise Print button and
 * the cost estimation dialog.
 */
import { computed } from 'vue'
import type { AfeEstimate } from '~/types/afe'

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
const summaryTotal = computed(() => money(props.estimate.grand_total))
</script>

<template>
  <div class="print-sheet" aria-hidden="true" data-testid="afe-print-sheet">
    <header class="print-sheet__header">
      <p class="print-sheet__eyebrow">Drilling Costing — AFE Cost Estimate</p>
      <h1>{{ afe.afe_code }} — {{ afe.afe_name }}</h1>
      <p class="print-sheet__meta">{{ meta }}</p>
      <p v-if="afe.remarks" class="print-sheet__meta">Remarks: {{ afe.remarks }}</p>
    </header>

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

    <h2 class="afe-print__title">Services</h2>
    <table class="print-sheet__table">
      <thead>
        <tr>
          <th>Service</th>
          <th>Provider</th>
          <th>Charging Basis</th>
          <th>Section / Phase</th>
          <th>Charge Category</th>
          <th>Qty</th>
          <th>Rate</th>
          <th>Amount</th>
        </tr>
      </thead>
      <tbody>
        <tr v-if="!estimate.services.length">
          <td colspan="8" class="print-sheet__empty">No services configured.</td>
        </tr>
        <template v-for="line in estimate.services" :key="`svc-${line.id}`">
          <tr v-for="(component, cIndex) in (line.estimate.components.length ? line.estimate.components : [null])" :key="`svc-${line.id}-${cIndex}`">
            <td>{{ cIndex === 0 ? `${line.service_code || ''} ${line.service_name || ''}` : '' }}</td>
            <td>{{ cIndex === 0 ? (line.provider_type || '—') : '' }}</td>
            <td>{{ cIndex === 0 ? line.charging_basis : '' }}</td>
            <td>{{ cIndex === 0 ? [line.estimate.components[0]?.section_label, line.estimate.components[0]?.phase_label].filter(Boolean).join(' / ') || 'Whole well' : '' }}</td>
            <td>{{ component ? component.category : '—' }}</td>
            <td>{{ component ? quantity(component.quantity) : '' }}</td>
            <td>{{ component ? money(component.rate) : '' }}</td>
            <td>{{ component ? money(component.amount) : '0.00' }}</td>
          </tr>
          <tr class="afe-print__subtotal">
            <td colspan="7">{{ line.service_code }} total</td>
            <td>{{ money(line.estimate.amount) }}</td>
          </tr>
        </template>
      </tbody>
    </table>

    <h2 class="afe-print__title">Consumables</h2>
    <table class="print-sheet__table">
      <thead>
        <tr>
          <th>Code</th>
          <th>Consumable</th>
          <th>Section / Phase</th>
          <th>Qty</th>
          <th>Captured Rate</th>
          <th>Override Rate</th>
          <th>Amount</th>
        </tr>
      </thead>
      <tbody>
        <tr v-if="!estimate.consumables.length">
          <td colspan="7" class="print-sheet__empty">No consumables configured.</td>
        </tr>
        <tr v-for="line in estimate.consumables" :key="`con-${line.id}`">
          <td>{{ line.item_code }}</td>
          <td>{{ line.item_name }}</td>
          <td>{{ [line.estimate.components[0]?.section_label, line.estimate.components[0]?.phase_label].filter(Boolean).join(' / ') || '—' }}</td>
          <td>{{ quantity(line.quantity) }} {{ line.uom || '' }}</td>
          <td>{{ money(line.captured_rate) }}</td>
          <td>{{ line.override_rate == null || line.override_rate === '' ? '—' : money(line.override_rate) }}</td>
          <td>{{ money(line.estimate.amount) }}</td>
        </tr>
      </tbody>
    </table>

    <h2 class="afe-print__title">Tangibles</h2>
    <table class="print-sheet__table">
      <thead>
        <tr>
          <th>Code</th>
          <th>Tangible</th>
          <th>Qty</th>
          <th>Captured Rate</th>
          <th>Override Rate</th>
          <th>Amount</th>
        </tr>
      </thead>
      <tbody>
        <tr v-if="!estimate.tangibles.length">
          <td colspan="6" class="print-sheet__empty">No tangibles configured.</td>
        </tr>
        <tr v-for="line in estimate.tangibles" :key="`tan-${line.id}`">
          <td>{{ line.tangible_code || '—' }}</td>
          <td>{{ line.tangible_name || '—' }}</td>
          <td>{{ quantity(line.quantity) }} {{ line.uom || '' }}</td>
          <td>{{ money(line.captured_rate) }}</td>
          <td>{{ line.override_rate == null || line.override_rate === '' ? '—' : money(line.override_rate) }}</td>
          <td>{{ money(line.estimate.amount) }}</td>
        </tr>
      </tbody>
    </table>

    <h2 class="afe-print__title">Compiled AFE cost estimate</h2>
    <table class="print-sheet__table">
      <thead>
        <tr>
          <th>Cost Group</th>
          <th>Lines</th>
          <th>Amount</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in estimate.summary" :key="`sum-${row.group}`">
          <td>{{ row.group }}</td>
          <td>{{ row.line_count }}</td>
          <td>{{ money(row.amount) }}</td>
        </tr>
      </tbody>
      <tfoot>
        <tr>
          <th colspan="2">Total AFE cost estimate</th>
          <th>{{ summaryTotal }}</th>
        </tr>
      </tfoot>
    </table>

    <table v-if="estimate.by_section.length" class="print-sheet__table afe-print__rollup">
      <thead>
        <tr>
          <th>Section</th>
          <th>Planned Days</th>
          <th>Cost</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in estimate.by_section" :key="`roll-${row.section_id ?? 'well'}`">
          <td>{{ row.section_label }}</td>
          <td>{{ quantity(row.planned_days) }}</td>
          <td>{{ money(row.amount) }}</td>
        </tr>
      </tbody>
    </table>

    <p v-if="estimate.warnings.length" class="afe-print__warnings">
      Notes: {{ estimate.warnings.join(' · ') }}
    </p>
  </div>
</template>

<style scoped>
  .afe-print__title {
    margin: 14px 0 4px;
    font-size: .82rem;
    font-weight: 800;
    letter-spacing: .06em;
    text-transform: uppercase;
    color: #333;
  }

  .afe-print__subtotal td {
    background: #f2f6f7;
    font-weight: 700;
  }

  .afe-print__rollup {
    margin-top: 10px;
  }

  .afe-print__warnings {
    margin-top: 10px;
    font-size: .72rem;
    color: #555;
  }
</style>
