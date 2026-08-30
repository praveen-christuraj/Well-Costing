<script setup lang="ts">
/**
 * The Consumables block of a daily cost sheet — the four categories, with only
 * what was actually consumed entered:
 *
 *   1. Mud chemicals   — picked from the Master Data chemical list; usage ×
 *                        the catalogue unit rate, with an override rate.
 *   2. Fuel            — the user enters the usage only; the unit rate is
 *                        captured from the AFE cost estimate.
 *   3. Cement additives— the total consumption cost is entered by hand for the
 *                        chosen section, phase and well sub activity.
 *   4. Drill bits      — picked from the Master Data bit list; number used ×
 *                        the catalogue unit rate, with an override rate.
 */
import { computed } from 'vue'
import Button from 'primevue/button'
import Select from 'primevue/select'
import {
  blankConsumableRow,
  formatMoney,
  formatQuantity,
  quantityError,
  subActivityLabel,
  textOf,
} from '~/utils/dailyCost'
import {
  CONSUMABLE_CATEGORIES,
  CONSUMABLE_ENTRY_HINTS,
  CONSUMABLE_LABELS,
  type ConsumableCategory,
  type DailyCostSubActivity,
  type DrillBitOption,
  type MudChemicalOption,
  type WellConfigurationSection,
} from '~/types/dailyCost'
import type { GridSelectOption } from '~/types/grid'

const props = defineProps<{
  rows: Record<string, unknown>[]
  chemicals: MudChemicalOption[]
  drillBits: DrillBitOption[]
  sections: WellConfigurationSection[]
  subActivities: DailyCostSubActivity[]
  /** Fuel unit rate captured from the AFE cost estimate. */
  fuelRate: string
  /** Server-priced amounts, index-aligned with `rows`. */
  amounts: string[]
  lineWarnings?: string[][]
  disabled?: boolean
}>()

const emit = defineEmits<{
  (event: 'update:rows', rows: Record<string, unknown>[]): void
  (event: 'change'): void
}>()

const chemicalOptions = computed<GridSelectOption[]>(() =>
  props.chemicals.map(item => ({
    label: `${item.chemical_code} - ${item.chemical_name}`,
    value: item.id,
  })),
)

const bitOptions = computed<GridSelectOption[]>(() =>
  props.drillBits.map(item => ({ label: `${item.bit_code} - ${item.bit_name}`, value: item.id })),
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

function categoryOf(row: Record<string, unknown>): ConsumableCategory {
  return (row.category as ConsumableCategory) ?? 'mud_chemical'
}

function labelOf(row: Record<string, unknown>): string {
  return CONSUMABLE_LABELS[categoryOf(row)]
}

function itemOptions(row: Record<string, unknown>): GridSelectOption[] {
  if (categoryOf(row) === 'mud_chemical') return chemicalOptions.value
  if (categoryOf(row) === 'drill_bit') return bitOptions.value
  return []
}

/** Fuel and cement additives have no item list of their own. */
function hasItemPicker(row: Record<string, unknown>): boolean {
  const category = categoryOf(row)
  return category === 'mud_chemical' || category === 'drill_bit'
}

/** Cement additives are entered as one total amount for their scope. */
function isManualAmount(row: Record<string, unknown>): boolean {
  return categoryOf(row) === 'cement_additive'
}

/** Fuel takes the AFE rate; the catalogue kinds take their catalogue rate. */
function capturedRateOf(row: Record<string, unknown>): string {
  const rate = textOf(row, 'captured_rate')
  if (rate) return rate
  if (categoryOf(row) === 'fuel') return props.fuelRate
  if (categoryOf(row) === 'mud_chemical') {
    return String(props.chemicals.find(item => item.id === row.item_id)?.current_rate ?? '0')
  }
  if (categoryOf(row) === 'drill_bit') {
    return String(props.drillBits.find(item => item.id === row.item_id)?.final_cost ?? '0')
  }
  return '0'
}

function rateSourceOf(row: Record<string, unknown>): string {
  if (categoryOf(row) === 'fuel') return 'Unit rate from the AFE cost estimate'
  if (isManualAmount(row)) return 'Total cost entered for the selected scope'
  return 'Unit rate from Master Data'
}

function uomOf(row: Record<string, unknown>): string {
  if (textOf(row, 'uom')) return textOf(row, 'uom')
  if (categoryOf(row) === 'mud_chemical') {
    return String(props.chemicals.find(item => item.id === row.item_id)?.uom ?? '')
  }
  if (categoryOf(row) === 'drill_bit') {
    return String(props.drillBits.find(item => item.id === row.item_id)?.uom ?? '')
  }
  return categoryOf(row) === 'fuel' ? 'Litre' : ''
}

function rowError(row: Record<string, unknown>): string | null {
  if (isManualAmount(row)) {
    if (!textOf(row, 'manual_amount')) return 'Enter the total consumption cost for this scope'
    if (!row.section_id && !row.phase_id && !row.sub_activity_id) {
      return 'Select the section, phase or sub activity this cement cost belongs to'
    }
    return null
  }
  if (hasItemPicker(row) && row.item_id == null) return 'Select the item'
  if (!textOf(row, 'quantity')) return 'Enter the quantity used'
  const limit = quantityError(textOf(row, 'quantity'), 'hours')
  if (limit && Number(textOf(row, 'quantity')) < 0) return 'The quantity cannot be negative'
  if (
    !isManualAmount(row)
    && !textOf(row, 'override_rate')
    && Number(capturedRateOf(row)) === 0
    && categoryOf(row) !== 'cement_additive'
  ) {
    return categoryOf(row) === 'fuel'
      ? 'The AFE has no fuel unit rate — enter an override unit rate'
      : 'No unit rate captured — enter an override unit rate'
  }
  return null
}

function onItemChange(row: Record<string, unknown>, itemId: number | null): void {
  row.item_id = itemId
  if (categoryOf(row) === 'mud_chemical') {
    const item = props.chemicals.find(candidate => candidate.id === itemId)
    row.item_code = item?.chemical_code ?? ''
    row.item_name = item?.chemical_name ?? ''
    row.uom = item?.uom ?? ''
    row.currency = item?.currency ?? ''
    row.captured_rate = item?.current_rate ?? null
  }
  else {
    const item = props.drillBits.find(candidate => candidate.id === itemId)
    row.item_code = item?.bit_code ?? ''
    row.item_name = item?.bit_name ?? ''
    row.uom = item?.uom ?? ''
    row.currency = item?.currency ?? ''
    row.captured_rate = item?.final_cost ?? null
  }
  emit('change')
}

function onSectionChange(row: Record<string, unknown>, value: unknown): void {
  row.section_id = value == null ? null : Number(value)
  row.phase_id = null
  emit('change')
}

function onPhaseChange(row: Record<string, unknown>, value: unknown): void {
  row.phase_id = value == null ? null : Number(value)
  emit('change')
}

function onSubActivityChange(row: Record<string, unknown>, value: unknown): void {
  row.sub_activity_id = value == null ? null : Number(value)
  emit('change')
}

function addRow(category: ConsumableCategory): void {
  const row = blankConsumableRow(category)
  if (category === 'fuel') {
    row.item_name = 'Fuel'
    row.captured_rate = props.fuelRate
  }
  emit('update:rows', [...props.rows, row])
  emit('change')
}

function removeRow(index: number): void {
  const rows = [...props.rows]
  rows.splice(index, 1)
  emit('update:rows', rows)
  emit('change')
}

/** Rows grouped by category, in the fixed order of the four blocks. */
interface IndexedRow { row: Record<string, unknown>, index: number }

const orderedRows = computed<IndexedRow[]>(() =>
  CONSUMABLE_CATEGORIES.flatMap(category =>
    props.rows
      .map((row, index) => ({ row, index }))
      .filter(entry => entry.row.category === category),
  ),
)
</script>

<template>
  <section class="cons" data-testid="daily-consumable-lines">
    <header class="cons__head">
      <div>
        <h3 class="cons__title">
          <i class="pi pi-box" /> Consumables
          <span class="cons__count">{{ rows.length }}</span>
        </h3>
        <p class="cons__hint">
          Only the consumables actually used on the day are entered. Add them per category:
          mud chemicals and drill bits come from Master Data, fuel takes its unit rate from the
          AFE, and cement additives are entered as one total for their section, phase and sub activity.
        </p>
      </div>
      <div class="cons__adds">
        <Button
          v-for="category in CONSUMABLE_CATEGORIES"
          :key="category"
          :label="CONSUMABLE_LABELS[category]"
          icon="pi pi-plus"
          size="small"
          severity="secondary"
          outlined
          :disabled="disabled"
          :title="CONSUMABLE_ENTRY_HINTS[category]"
          @click="addRow(category)"
        />
      </div>
    </header>

    <div class="cons__scroll">
      <table class="cons__table">
        <thead>
          <tr>
            <th class="cons__num">#</th>
            <th>Category</th>
            <th>Item</th>
            <th class="num">Usage</th>
            <th>UOM</th>
            <th class="num">Unit Rate</th>
            <th class="num">Override</th>
            <th class="num">Total Cost</th>
            <th class="num">Amount</th>
            <th>Section</th>
            <th>Phase</th>
            <th>Well Sub Activity</th>
            <th>Remarks</th>
            <th class="cons__action" />
          </tr>
        </thead>
        <tbody>
          <tr v-if="rows.length === 0">
            <td colspan="14" class="cons__empty">
              Nothing consumed yet — add mud chemicals, fuel, cement additives or drill bits with
              the buttons above.
            </td>
          </tr>
          <template v-for="entry in orderedRows" :key="entry.row._key as string">
            <tr :class="{ 'is-invalid': rowError(entry.row) }">
              <td class="cons__num">{{ entry.index + 1 }}</td>
              <td>
                <span class="cons__chip" :data-category="entry.row.category">{{ labelOf(entry.row) }}</span>
                <small class="cons__flag">{{ rateSourceOf(entry.row) }}</small>
              </td>
              <td>
                <Select
                  v-if="hasItemPicker(entry.row)"
                  :model-value="idOf(entry.row, 'item_id')"
                  :options="itemOptions(entry.row)"
                  option-label="label"
                  option-value="value"
                  :placeholder="categoryOf(entry.row) === 'fuel' ? 'Fuel' : 'Select item'"
                  filter
                  size="small"
                  class="cons__cell"
                  :disabled="disabled"
                  @update:model-value="onItemChange(entry.row, $event as number | null)"
                />
                <span v-else class="cons__fixed">{{ textOf(entry.row, 'item_code') || '—' }}</span>
              </td>
              <td class="num">
                <input
                  v-if="!isManualAmount(entry.row)"
                  v-model="entry.row.quantity"
                  type="text"
                  inputmode="decimal"
                  class="cons__input cons__input--num"
                  placeholder="0"
                  :disabled="disabled"
                  @change="emit('change')"
                >
                <span v-else class="cons__fixed">—</span>
              </td>
              <td class="mono cons__uom">{{ uomOf(entry.row) || '—' }}</td>
              <td class="num mono">
                {{ isManualAmount(entry.row) ? '—' : formatMoney(capturedRateOf(entry.row)) }}
              </td>
              <td class="num">
                <input
                  v-if="!isManualAmount(entry.row)"
                  v-model="entry.row.override_rate"
                  type="text"
                  inputmode="decimal"
                  class="cons__input cons__input--num"
                  placeholder="—"
                  :disabled="disabled"
                  @change="emit('change')"
                >
                <span v-else class="cons__fixed">—</span>
              </td>
              <td class="num">
                <input
                  v-if="isManualAmount(entry.row)"
                  v-model="entry.row.manual_amount"
                  type="text"
                  inputmode="decimal"
                  class="cons__input cons__input--num"
                  placeholder="0.00"
                  :disabled="disabled"
                  @change="emit('change')"
                >
                <span v-else class="cons__fixed">—</span>
              </td>
              <td class="num mono cons__amount">{{ formatMoney(amounts[entry.index] ?? '0') }}</td>
              <td>
                <Select
                  :model-value="idOf(entry.row, 'section_id')"
                  :options="sectionOptions"
                  option-label="label"
                  option-value="value"
                  placeholder="Section"
                  show-clear
                  size="small"
                  class="cons__cell"
                  :disabled="disabled"
                  @update:model-value="onSectionChange(entry.row, $event)"
                />
              </td>
              <td>
                <Select
                  :model-value="idOf(entry.row, 'phase_id')"
                  :options="phaseOptionsFor(entry.row.section_id)"
                  option-label="label"
                  option-value="value"
                  placeholder="Phase"
                  show-clear
                  size="small"
                  class="cons__cell"
                  :disabled="disabled || entry.row.section_id == null"
                  @update:model-value="onPhaseChange(entry.row, $event)"
                />
              </td>
              <td>
                <Select
                  :model-value="idOf(entry.row, 'sub_activity_id')"
                  :options="subActivityOptions"
                  option-label="label"
                  option-value="value"
                  placeholder="Sub activity"
                  filter
                  show-clear
                  size="small"
                  class="cons__cell"
                  :disabled="disabled"
                  @update:model-value="onSubActivityChange(entry.row, $event)"
                />
              </td>
              <td>
                <input
                  v-model="entry.row.remarks"
                  type="text"
                  class="cons__input"
                  placeholder="Optional remarks"
                  :disabled="disabled"
                  @change="emit('change')"
                >
              </td>
              <td class="cons__action">
                <Button
                  icon="pi pi-times"
                  size="small"
                  severity="danger"
                  text
                  aria-label="Remove consumable line"
                  :disabled="disabled"
                  @click="removeRow(entry.index)"
                />
              </td>
            </tr>
            <tr v-if="rowError(entry.row) || (lineWarnings?.[entry.index]?.length ?? 0) > 0" class="cons__notes">
              <td :colspan="14">
                <span v-if="rowError(entry.row)" class="cons__note cons__note--error">
                  <i class="pi pi-exclamation-circle" /> {{ rowError(entry.row) }}
                </span>
                <span
                  v-for="warning in lineWarnings?.[entry.index] ?? []"
                  :key="warning"
                  class="cons__note"
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
  .cons {
    display: grid;
    gap: 8px;
  }

  .cons__head {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 12px;
    flex-wrap: wrap;
  }

  .cons__title {
    margin: 0;
    font-size: 0.9rem;
    font-weight: 650;
    display: flex;
    align-items: center;
    gap: 6px;
  }

  .cons__count {
    background: var(--app-surface-muted, #eef2f7);
    border-radius: 999px;
    padding: 0 7px;
    font-size: 0.72rem;
    color: var(--app-text-muted, #5b6472);
  }

  .cons__hint {
    margin: 2px 0 0;
    font-size: 0.72rem;
    color: var(--app-text-muted, #6b7480);
    max-width: 88ch;
  }

  .cons__adds {
    display: flex;
    gap: 6px;
    flex-wrap: wrap;
  }

  .cons__scroll {
    overflow-x: auto;
    border: 1px solid var(--app-border, #e3e7ee);
    border-radius: 10px;
  }

  .cons__table {
    width: 100%;
    border-collapse: separate;
    border-spacing: 0;
    font-size: 0.74rem;
    min-width: 1240px;
  }

  .cons__table thead th {
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

  .cons__table tbody td {
    padding: 4px 6px;
    border-bottom: 1px solid var(--app-border-soft, #eef1f6);
    vertical-align: top;
  }

  .cons__table tbody tr.is-invalid td {
    background: #fff7f7;
  }

  .num {
    text-align: right;
    font-variant-numeric: tabular-nums;
  }

  .mono {
    font-family: var(--app-font-mono, ui-monospace, monospace);
  }

  .cons__num {
    width: 26px;
    color: var(--app-text-muted, #8a929e);
    text-align: right;
  }

  .cons__action {
    width: 34px;
    text-align: center;
  }

  .cons__chip {
    display: inline-block;
    padding: 1px 7px;
    border-radius: 999px;
    font-size: 0.68rem;
    font-weight: 600;
    background: var(--app-surface-muted, #eef2f7);
    color: var(--app-text, #1c2430);
    white-space: nowrap;
  }

  .cons__chip[data-category='fuel'] {
    background: #fef3c7;
    color: #92400e;
  }

  .cons__chip[data-category='mud_chemical'] {
    background: #e0f2fe;
    color: #075985;
  }

  .cons__chip[data-category='cement_additive'] {
    background: #ede9fe;
    color: #5b21b6;
  }

  .cons__chip[data-category='drill_bit'] {
    background: #dcfce7;
    color: #166534;
  }

  .cons__flag {
    display: block;
    font-size: 0.66rem;
    color: var(--app-text-muted, #7c8593);
    margin-top: 2px;
    line-height: 1.2;
  }

  .cons__cell {
    width: 100%;
    min-width: 108px;
  }

  .cons__input {
    width: 100%;
    border: 1px solid var(--app-border, #d8dee7);
    border-radius: 6px;
    padding: 4px 6px;
    font-size: 0.74rem;
    background: var(--app-surface, #fff);
  }

  .cons__input--num {
    text-align: right;
    font-variant-numeric: tabular-nums;
    min-width: 68px;
  }

  .cons__input:disabled {
    background: var(--app-surface-muted, #f4f6fa);
  }

  .cons__fixed {
    color: var(--app-text-muted, #8a929e);
    font-size: 0.72rem;
  }

  .cons__uom {
    white-space: nowrap;
    color: var(--app-text-muted, #6b7480);
  }

  .cons__amount {
    font-weight: 650;
    white-space: nowrap;
  }

  .cons__empty {
    text-align: center;
    color: var(--app-text-muted, #7c8593);
    padding: 18px 10px !important;
    font-size: 0.78rem;
  }

  .cons__notes td {
    padding: 0 6px 6px 26px !important;
    border-bottom: 1px solid var(--app-border-soft, #eef1f6);
  }

  .cons__note {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    font-size: 0.68rem;
    color: #b45309;
    margin-right: 12px;
  }

  .cons__note--error {
    color: #b91c1c;
  }
</style>
