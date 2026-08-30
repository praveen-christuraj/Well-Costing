<script setup lang="ts">
/**
 * Print-only sheet for one daily cost day: the rig / well / date header, the
 * group totals, then the services, consumables and tangibles that were charged,
 * each with the rate it was captured at and the section / phase / sub activity
 * the cost belongs to. Hidden on screen — the print stylesheet shows it.
 */
import { computed } from 'vue'
import { formatMoney, formatDateLabel, formatQuantity } from '~/utils/dailyCost'
import { CONSUMABLE_LABELS, type ConsumableCategory, type DailyCostDay } from '~/types/dailyCost'

const props = withDefaults(
  defineProps<{
    day: DailyCostDay
    rigDisplay?: string
    wellDisplay?: string
    printedAt?: string
  }>(),
  { rigDisplay: '', wellDisplay: '', printedAt: '' },
)

const entry = computed(() => props.day.entry)
const total = computed(
  () => props.day.summary.find(row => row.group === 'Total')?.amount ?? props.day.grand_total,
)

function scopeOf(
  row: { section_id: number | null, phase_id: number | null, sub_activity_display: string | null },
): string {
  const section = props.day.well_configuration?.sections.find(
    item => item.section_id === row.section_id,
  )
  const phase = section?.phases.find(item => item.phase_id === row.phase_id)
  return (
    [section?.section_code, phase?.phase_code, row.sub_activity_display].filter(Boolean).join(' / ')
    || '—'
  )
}

function consumableLabel(category: string): string {
  return CONSUMABLE_LABELS[category as ConsumableCategory] ?? category
}
</script>

<template>
  <div class="print-sheet" data-testid="daily-cost-print-sheet">
    <header class="ps-head">
      <div>
        <h1>Daily Cost Sheet</h1>
        <p class="ps-code">{{ entry.daily_cost_code }}</p>
      </div>
      <dl class="ps-meta">
        <div><dt>Rig</dt><dd>{{ rigDisplay || entry.rig_display || '—' }}</dd></div>
        <div><dt>Well</dt><dd>{{ wellDisplay || entry.well_display || '—' }}</dd></div>
        <div><dt>Cost Date</dt><dd>{{ formatDateLabel(entry.cost_date) }}</dd></div>
        <div><dt>AFE</dt><dd>{{ entry.afe_code || '—' }}</dd></div>
        <div><dt>Status</dt><dd>{{ entry.status === 'submitted' ? 'Submitted' : 'Draft' }}</dd></div>
        <div><dt>Printed</dt><dd>{{ printedAt }}</dd></div>
      </dl>
    </header>

    <table class="ps-totals">
      <tbody>
        <tr>
          <th>Services</th>
          <td class="num">{{ formatMoney(entry.service_total) }}</td>
          <th>Consumables</th>
          <td class="num">{{ formatMoney(entry.consumable_total) }}</td>
          <th>Tangibles</th>
          <td class="num">{{ formatMoney(entry.tangible_total) }}</td>
          <th>Total Cost for the Day</th>
          <td class="num ps-grand">{{ formatMoney(total) }}</td>
        </tr>
      </tbody>
    </table>

    <p v-if="entry.remarks" class="ps-remarks"><strong>Remarks:</strong> {{ entry.remarks }}</p>

    <section class="ps-block">
      <h2>Services</h2>
      <table class="ps-table">
        <thead>
          <tr>
            <th>#</th>
            <th>Service</th>
            <th>Charge Category</th>
            <th>Basis</th>
            <th>Section / Phase / Sub Activity</th>
            <th class="num">Qty</th>
            <th>Unit</th>
            <th class="num">Unit Rate</th>
            <th class="num">Override</th>
            <th class="num">Amount</th>
            <th>Remarks</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="day.services.length === 0">
            <td colspan="11" class="ps-empty">No services charged on this day.</td>
          </tr>
          <tr v-for="(line, index) in day.services" :key="line.id">
            <td>{{ index + 1 }}</td>
            <td>{{ line.service_code }} - {{ line.service_name }}</td>
            <td>{{ line.charge_category }}</td>
            <td>{{ line.charging_basis }}</td>
            <td>{{ scopeOf(line) }}</td>
            <td class="num">{{ formatQuantity(line.quantity) }}</td>
            <td>{{ line.quantity_unit }}</td>
            <td class="num">{{ formatMoney(line.captured_rate) }}</td>
            <td class="num">{{ line.override_rate == null ? '—' : formatMoney(line.override_rate) }}</td>
            <td class="num">{{ formatMoney(line.amount) }}</td>
            <td>{{ line.remarks || '' }}</td>
          </tr>
        </tbody>
      </table>
    </section>

    <section class="ps-block">
      <h2>Consumables</h2>
      <table class="ps-table">
        <thead>
          <tr>
            <th>#</th>
            <th>Category</th>
            <th>Item</th>
            <th class="num">Usage</th>
            <th>UOM</th>
            <th class="num">Unit Rate</th>
            <th class="num">Override</th>
            <th class="num">Total Cost</th>
            <th class="num">Amount</th>
            <th>Section / Phase / Sub Activity</th>
            <th>Remarks</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="day.consumables.length === 0">
            <td colspan="11" class="ps-empty">No consumables used on this day.</td>
          </tr>
          <tr v-for="(line, index) in day.consumables" :key="line.id">
            <td>{{ index + 1 }}</td>
            <td>{{ consumableLabel(line.category) }}</td>
            <td>{{ line.item_code }} - {{ line.item_name }}</td>
            <td class="num">{{ formatQuantity(line.quantity) }}</td>
            <td>{{ line.uom || '—' }}</td>
            <td class="num">{{ formatMoney(line.captured_rate) }}</td>
            <td class="num">{{ line.override_rate == null ? '—' : formatMoney(line.override_rate) }}</td>
            <td class="num">
              {{ line.manual_amount == null ? '—' : formatMoney(line.manual_amount) }}
            </td>
            <td class="num">{{ formatMoney(line.amount) }}</td>
            <td>{{ scopeOf(line) }}</td>
            <td>{{ line.remarks || '' }}</td>
          </tr>
        </tbody>
      </table>
    </section>

    <section class="ps-block">
      <h2>Tangibles</h2>
      <table class="ps-table">
        <thead>
          <tr>
            <th>#</th>
            <th>Tangible</th>
            <th class="num">Quantity</th>
            <th>UOM</th>
            <th class="num">Unit Rate</th>
            <th class="num">Override</th>
            <th class="num">Amount</th>
            <th>Remarks</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="day.tangibles.length === 0">
            <td colspan="8" class="ps-empty">No tangibles entered for this day.</td>
          </tr>
          <tr v-for="(line, index) in day.tangibles" :key="line.id">
            <td>{{ index + 1 }}</td>
            <td>{{ line.tangible_code }} - {{ line.tangible_name }}</td>
            <td class="num">{{ formatQuantity(line.quantity) }}</td>
            <td>{{ line.uom || '—' }}</td>
            <td class="num">{{ formatMoney(line.captured_rate) }}</td>
            <td class="num">{{ line.override_rate == null ? '—' : formatMoney(line.override_rate) }}</td>
            <td class="num">{{ formatMoney(line.amount) }}</td>
            <td>{{ line.remarks || '' }}</td>
          </tr>
        </tbody>
      </table>
    </section>

    <ul v-if="day.warnings.length" class="ps-warnings">
      <li v-for="warning in day.warnings" :key="warning">{{ warning }}</li>
    </ul>

    <footer class="ps-foot">
      <span>Daily cost {{ entry.daily_cost_code }} — priced by the cost engine at save time.</span>
      <span>Prepared by: ____________________  ·  Verified by: ____________________</span>
    </footer>
  </div>
</template>

<style scoped>
  .print-sheet {
    display: none;
  }

  @media print {
    .print-sheet {
      display: block;
      font-size: 9px;
      color: #000;
    }

    .ps-head {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      border-bottom: 2px solid #000;
      padding-bottom: 6px;
      margin-bottom: 8px;
    }

    .ps-head h1 {
      margin: 0;
      font-size: 15px;
      letter-spacing: 0.02em;
    }

    .ps-code {
      margin: 2px 0 0;
      font-size: 10px;
      font-family: ui-monospace, monospace;
    }

    .ps-meta {
      margin: 0;
      display: grid;
      grid-template-columns: repeat(3, auto);
      gap: 1px 14px;
    }

    .ps-meta div {
      display: flex;
      gap: 4px;
    }

    .ps-meta dt {
      font-weight: 600;
    }

    .ps-meta dd {
      margin: 0;
    }

    .ps-totals {
      width: 100%;
      border-collapse: collapse;
      margin-bottom: 8px;
    }

    .ps-totals th,
    .ps-totals td {
      border: 1px solid #999;
      padding: 3px 5px;
      font-size: 9px;
    }

    .ps-totals th {
      background: #eee;
      text-align: left;
    }

    .num {
      text-align: right;
      font-variant-numeric: tabular-nums;
    }

    .ps-grand {
      font-weight: 700;
      font-size: 10px;
    }

    .ps-remarks {
      margin: 0 0 6px;
    }

    .ps-block {
      margin-bottom: 10px;
      break-inside: avoid;
    }

    .ps-block h2 {
      margin: 0 0 3px;
      font-size: 10px;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      border-bottom: 1px solid #000;
      padding-bottom: 1px;
    }

    .ps-table {
      width: 100%;
      border-collapse: collapse;
    }

    .ps-table th,
    .ps-table td {
      border: 1px solid #bbb;
      padding: 2px 4px;
      text-align: left;
      vertical-align: top;
    }

    .ps-table th {
      background: #f2f2f2;
      font-weight: 600;
      white-space: nowrap;
    }

    .ps-empty {
      text-align: center;
      color: #555;
    }

    .ps-warnings {
      margin: 0 0 8px;
      padding-left: 14px;
      font-size: 8px;
      color: #333;
    }

    .ps-foot {
      display: flex;
      justify-content: space-between;
      border-top: 1px solid #000;
      padding-top: 4px;
      font-size: 8px;
      color: #333;
    }
  }
</style>
