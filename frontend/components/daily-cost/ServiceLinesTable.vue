<script setup lang="ts">
/**
 * The Services block of a daily cost sheet.
 *
 * The charging basis and the unit rate are never typed by the user: they come
 * from the service's line on the selected AFE (the AFE cost estimation page
 * owns the rate card). The daily page adds what the AFE cannot know — which
 * charge category the day is charged against, the section / phase / well sub
 * activity the cost belongs to, and the hours (0-24) or days (0-1) worked.
 *
 * Mobilization, demobilization and fixed charges are one-time amounts: the
 * hours/days are recorded for the record but never multiply the rate.
 * A per-service or per-section service pulls its lump sum automatically, and
 * the same service can appear several times for different sub activities.
 * An override unit rate bypasses the captured rate when the day was charged
 * differently, and the amount column always shows the server-priced value.
 */
import { computed } from 'vue'
import Button from 'primevue/button'
import Select from 'primevue/select'
import {
  blankServiceRow,
  chargeCategoriesFor,
  formatMoney,
  formatQuantity,
  isOneTimeCategory,
  quantityError,
  rateForCategory,
  rateSourceLabel,
  sectionRateFor,
  subActivityLabel,
  textOf,
} from '~/utils/dailyCost'
import type {
  RateCardService,
  ServiceOption,
  WellConfigurationSection,
  DailyCostSubActivity,
} from '~/types/dailyCost'
import type { GridSelectOption } from '~/types/grid'

const props = defineProps<{
  rows: Record<string, unknown>[]
  rateCard: RateCardService[]
  services: ServiceOption[]
  sections: WellConfigurationSection[]
  subActivities: DailyCostSubActivity[]
  /** Server-priced amounts, index-aligned with `rows`. */
  amounts: string[]
  /** Per-line warnings from the same preview, index-aligned with `rows`. */
  lineWarnings?: string[][]
  disabled?: boolean
}>()

const emit = defineEmits<{
  (event: 'update:rows', rows: Record<string, unknown>[]): void
  (event: 'change'): void
}>()

const serviceOptions = computed<GridSelectOption[]>(() =>
  props.services.map(service => ({
    label: `${service.service_code} - ${service.service_name}`,
    value: service.id,
  })),
)

const sectionOptions = computed<GridSelectOption[]>(() =>
  props.sections.map(section => ({
    label: `${section.section_code} — ${section.section_name}`,
    value: section.section_id,
  })),
)

const subActivityOptions = computed<GridSelectOption[]>(() =>
  props.subActivities.map(sub => ({ label: subActivityLabel(sub), value: sub.id })),
)

function phaseOptionsFor(sectionId: unknown): GridSelectOption[] {
  const section = props.sections.find(item => item.section_id === sectionId)
  if (!section) return []
  return section.phases.map(phase => ({
    label: `${phase.phase_code} — ${phase.phase_name} (${formatQuantity(phase.days)} days)`,
    value: phase.phase_id,
  }))
}

/** A row's id field as `number | null` — templates cannot carry type casts. */
function idOf(row: Record<string, unknown>, field: string): number | null {
  const value = row[field]
  return value == null || value === '' ? null : Number(value)
}

function cardFor(row: Record<string, unknown>): RateCardService | null {
  return props.rateCard.find(card => card.service_id === row.service_id) ?? null
}

/** The unit rate the day would be charged at, from the AFE rate card. */
function capturedRateOf(row: Record<string, unknown>): string {
  const card = cardFor(row)
  if (!card) return textOf(row, 'captured_rate')
  if (card.charging_basis === 'Per Service Rate') return card.per_service_amount
  if (card.charging_basis === 'Per Section Rate') {
    return sectionRateFor(card, row.section_id as number | null, row.phase_id as number | null) ?? '0'
  }
  return rateForCategory(card, textOf(row, 'charge_category')) ?? '0'
}

function basisLabel(row: Record<string, unknown>): string {
  const card = cardFor(row)
  return card?.charging_basis ?? 'Daily Rate'
}

function categoryOptions(row: Record<string, unknown>): GridSelectOption[] {
  return chargeCategoriesFor(basisLabel(row) as never).map(category => ({
    label: category,
    value: category,
  }))
}

function oneTime(row: Record<string, unknown>): boolean {
  return isOneTimeCategory(textOf(row, 'charge_category'))
}

function rowError(row: Record<string, unknown>): string | null {
  if (row.service_id == null) return 'Select the service'
  if (!textOf(row, 'charge_category')) return 'Select the charge category'
  const limit = quantityError(textOf(row, 'quantity'), row.quantity_unit as 'days' | 'hours')
  if (limit) return limit
  if (cardFor(row) == null && !textOf(row, 'captured_rate') && !textOf(row, 'override_rate')) {
    return 'This service is not on the selected AFE — enter its unit rate'
  }
  return null
}

function onServiceChange(row: Record<string, unknown>, serviceId: number | null): void {
  row.service_id = serviceId
  const card = cardFor(row)
  if (!card) {
    // Not on the AFE: the user prices it by hand, charged per day by default.
    row.charging_basis = null
    row.afe_line_id = null
    row.charge_category = textOf(row, 'charge_category') || 'Operation'
    row.quantity_unit = 'hours'
    row.captured_rate = null
  }
  else {
    row.charging_basis = card.charging_basis
    row.afe_line_id = card.afe_line_id
    row.charge_category
      = card.charging_basis === 'Daily Rate'
        ? (textOf(row, 'charge_category') || 'Operation')
        : card.charging_basis
    row.quantity_unit = card.charging_basis === 'Daily Rate' ? 'hours' : 'days'
    row.quantity = textOf(row, 'quantity') || '1'
    row.section_id = card.section_id ?? row.section_id
    row.phase_id = card.phase_id ?? row.phase_id
    row.captured_rate = capturedRateOf(row)
  }
  changed()
}

function onCategoryChange(row: Record<string, unknown>, category: string | null): void {
  row.charge_category = category
  const card = cardFor(row)
  if (card && card.charging_basis === 'Daily Rate') {
    row.captured_rate = rateForCategory(card, category) ?? '0'
    // One-time categories are recorded in days; the rest are normally hours.
    row.quantity_unit = isOneTimeCategory(category) ? 'days' : 'hours'
    if (!textOf(row, 'quantity')) row.quantity = '1'
  }
  changed()
}

function onSectionChange(row: Record<string, unknown>, value: unknown): void {
  row.section_id = value == null ? null : Number(value)
  row.phase_id = null
  onScopeChange(row)
}

function onPhaseChange(row: Record<string, unknown>, value: unknown): void {
  row.phase_id = value == null ? null : Number(value)
  onScopeChange(row)
}

function onSubActivityChange(row: Record<string, unknown>, value: unknown): void {
  row.sub_activity_id = value == null ? null : Number(value)
  changed()
}

function onScopeChange(row: Record<string, unknown>): void {
  const card = cardFor(row)
  if (card && card.charging_basis === 'Per Section Rate') {
    row.captured_rate = sectionRateFor(card, row.section_id as number | null, row.phase_id as number | null) ?? '0'
  }
  changed()
}

function addRow(): void {
  emit('update:rows', [...props.rows, blankServiceRow()])
  emit('change')
}

function removeRow(index: number): void {
  const rows = [...props.rows]
  rows.splice(index, 1)
  emit('update:rows', rows)
  emit('change')
}

function changed(): void {
  emit('change')
}
</script>

<template>
  <section class="svc" data-testid="daily-service-lines">
    <header class="svc__head">
      <div>
        <h3 class="svc__title">
          <i class="pi pi-cog" /> Services
          <span class="svc__count">{{ rows.length }}</span>
        </h3>
        <p class="svc__hint">
          Charging basis and unit rate follow the service's configuration on the AFE cost
          estimation page. Mobilization, demobilization and fixed charges are one-time amounts.
        </p>
      </div>
      <Button
        label="Add service"
        icon="pi pi-plus"
        size="small"
        severity="primary"
        outlined
        :disabled="disabled"
        @click="addRow"
      />
    </header>

    <div class="svc__scroll">
      <table class="svc__table">
        <thead>
          <tr>
            <th class="svc__num">#</th>
            <th>Service</th>
            <th>Charge Category</th>
            <th>Section</th>
            <th>Phase</th>
            <th>Well Sub Activity</th>
            <th class="num">Qty</th>
            <th>Unit</th>
            <th class="num">Unit Rate</th>
            <th class="num">Override</th>
            <th class="num">Amount</th>
            <th>Remarks</th>
            <th class="svc__action" />
          </tr>
        </thead>
        <tbody>
          <tr v-if="rows.length === 0">
            <td colspan="13" class="svc__empty">
              No services entered for this day — add the services that ran, one line per charge
              category, section / phase and well sub activity.
            </td>
          </tr>
          <template v-for="(row, index) in rows" :key="row._key as string">
            <tr :class="{ 'is-invalid': rowError(row) }">
              <td class="svc__num">{{ index + 1 }}</td>
              <td>
                <Select
                  :model-value="idOf(row, 'service_id')"
                  :options="serviceOptions"
                  option-label="label"
                  option-value="value"
                  placeholder="Select service"
                  filter
                  size="small"
                  class="svc__cell svc__cell--service"
                  :disabled="disabled"
                  @update:model-value="onServiceChange(row, $event as number | null)"
                />
                <small class="svc__basis">{{ basisLabel(row) }} · {{ rateSourceLabel(cardFor(row), textOf(row, 'charge_category')) }}</small>
              </td>
              <td>
                <Select
                  :model-value="textOf(row, 'charge_category')"
                  :options="categoryOptions(row)"
                  option-label="label"
                  option-value="value"
                  placeholder="Category"
                  size="small"
                  class="svc__cell"
                  :disabled="disabled || row.service_id == null"
                  @update:model-value="onCategoryChange(row, $event as string | null)"
                />
                <small v-if="oneTime(row)" class="svc__flag">One-time — not multiplied</small>
              </td>
              <td>
                <Select
                  :model-value="idOf(row, 'section_id')"
                  :options="sectionOptions"
                  option-label="label"
                  option-value="value"
                  placeholder="Section"
                  show-clear
                  size="small"
                  class="svc__cell"
                  :disabled="disabled"
                  @update:model-value="onSectionChange(row, $event)"
                />
              </td>
              <td>
                <Select
                  :model-value="idOf(row, 'phase_id')"
                  :options="phaseOptionsFor(row.section_id)"
                  option-label="label"
                  option-value="value"
                  placeholder="Phase"
                  show-clear
                  size="small"
                  class="svc__cell"
                  :disabled="disabled || row.section_id == null"
                  @update:model-value="onPhaseChange(row, $event)"
                />
              </td>
              <td>
                <Select
                  :model-value="idOf(row, 'sub_activity_id')"
                  :options="subActivityOptions"
                  option-label="label"
                  option-value="value"
                  placeholder="Sub activity"
                  filter
                  show-clear
                  size="small"
                  class="svc__cell"
                  :disabled="disabled"
                  @update:model-value="onSubActivityChange(row, $event)"
                />
              </td>
              <td class="num">
                <input
                  v-model="row.quantity"
                  type="text"
                  inputmode="decimal"
                  class="svc__input svc__input--num"
                  :placeholder="row.quantity_unit === 'days' ? '0-1' : '0-24'"
                  :disabled="disabled"
                  @change="changed"
                >
              </td>
              <td>
                <Select
                  v-model="row.quantity_unit"
                  :options="[{ label: 'hours', value: 'hours' }, { label: 'days', value: 'days' }]"
                  option-label="label"
                  option-value="value"
                  size="small"
                  class="svc__cell svc__cell--unit"
                  :disabled="disabled"
                  @update:model-value="changed"
                />
              </td>
              <td class="num mono">{{ formatMoney(capturedRateOf(row)) }}</td>
              <td class="num">
                <input
                  v-model="row.override_rate"
                  type="text"
                  inputmode="decimal"
                  class="svc__input svc__input--num"
                  placeholder="—"
                  :disabled="disabled"
                  @change="changed"
                >
              </td>
              <td class="num mono svc__amount">{{ formatMoney(amounts[index] ?? '0') }}</td>
              <td>
                <input
                  v-model="row.remarks"
                  type="text"
                  class="svc__input"
                  placeholder="Optional remarks"
                  :disabled="disabled"
                  @change="changed"
                >
              </td>
              <td class="svc__action">
                <Button
                  icon="pi pi-times"
                  size="small"
                  severity="danger"
                  text
                  aria-label="Remove service line"
                  :disabled="disabled"
                  @click="removeRow(index)"
                />
              </td>
            </tr>
            <tr v-if="rowError(row) || (lineWarnings?.[index]?.length ?? 0) > 0" class="svc__notes">
              <td :colspan="13">
                <span v-if="rowError(row)" class="svc__note svc__note--error">
                  <i class="pi pi-exclamation-circle" /> {{ rowError(row) }}
                </span>
                <span
                  v-for="warning in lineWarnings?.[index] ?? []"
                  :key="warning"
                  class="svc__note"
                >
                  <i class="pi pi-info-circle" /> {{ warning }}
                </span>
              </td>
            </tr>
          </template>
        </tbody>
      </table>
    </div>
  </section>
</template>

<style scoped>
  .svc {
    display: grid;
    gap: 8px;
  }

  .svc__head {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 12px;
    flex-wrap: wrap;
  }

  .svc__title {
    margin: 0;
    font-size: 0.9rem;
    font-weight: 650;
    display: flex;
    align-items: center;
    gap: 6px;
  }

  .svc__count {
    background: var(--app-surface-muted, #eef2f7);
    border-radius: 999px;
    padding: 0 7px;
    font-size: 0.72rem;
    color: var(--app-text-muted, #5b6472);
  }

  .svc__hint {
    margin: 2px 0 0;
    font-size: 0.72rem;
    color: var(--app-text-muted, #6b7480);
    max-width: 90ch;
  }

  .svc__scroll {
    overflow-x: auto;
    border: 1px solid var(--app-border, #e3e7ee);
    border-radius: 10px;
  }

  .svc__table {
    width: 100%;
    border-collapse: separate;
    border-spacing: 0;
    font-size: 0.74rem;
    min-width: 1180px;
  }

  .svc__table thead th {
    position: sticky;
    top: 0;
    z-index: 1;
    background: var(--app-surface-muted, #f7f9fc);
    color: var(--app-text-muted, #5b6472);
    font-weight: 600;
    text-align: left;
    padding: 5px 6px;
    border-bottom: 1px solid var(--app-border, #e3e7ee);
    white-space: nowrap;
  }

  .svc__table tbody td {
    padding: 4px 6px;
    border-bottom: 1px solid var(--app-border-soft, #eef1f6);
    vertical-align: top;
  }

  .svc__table tbody tr.is-invalid td {
    background: #fff7f7;
  }

  .num {
    text-align: right;
    font-variant-numeric: tabular-nums;
  }

  .mono {
    font-family: var(--app-font-mono, ui-monospace, monospace);
  }

  .svc__num {
    width: 26px;
    color: var(--app-text-muted, #8a929e);
    text-align: right;
  }

  .svc__action {
    width: 34px;
    text-align: center;
  }

  .svc__cell {
    width: 100%;
    min-width: 108px;
  }

  .svc__cell--service {
    min-width: 190px;
  }

  .svc__cell--unit {
    min-width: 76px;
  }

  .svc__basis,
  .svc__flag {
    display: block;
    font-size: 0.66rem;
    color: var(--app-text-muted, #7c8593);
    margin-top: 2px;
    line-height: 1.2;
  }

  .svc__flag {
    color: #b45309;
  }

  .svc__input {
    width: 100%;
    border: 1px solid var(--app-border, #d8dee7);
    border-radius: 6px;
    padding: 4px 6px;
    font-size: 0.74rem;
    background: var(--app-surface, #fff);
  }

  .svc__input--num {
    text-align: right;
    font-variant-numeric: tabular-nums;
    min-width: 66px;
  }

  .svc__input:disabled {
    background: var(--app-surface-muted, #f4f6fa);
  }

  .svc__amount {
    font-weight: 650;
    white-space: nowrap;
  }

  .svc__empty {
    text-align: center;
    color: var(--app-text-muted, #7c8593);
    padding: 18px 10px !important;
    font-size: 0.78rem;
  }

  .svc__notes td {
    padding: 0 6px 6px 26px !important;
    border-bottom: 1px solid var(--app-border-soft, #eef1f6);
  }

  .svc__note {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    font-size: 0.68rem;
    color: #b45309;
    margin-right: 12px;
  }

  .svc__note--error {
    color: #b91c1c;
  }
</style>
