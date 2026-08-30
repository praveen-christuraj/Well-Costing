<script setup lang="ts">
/**
 * The Tangibles block — entered in bulk at well completion, not daily.
 *
 * The list always comes from Master Data, never from the AFE: a planned
 * tangible can be damaged and a different one used on the day. Selecting the
 * tangible captures its rate, the user enters the quantity, and an override
 * unit rate bypasses the captured rate when the day was charged differently.
 */
import { computed } from 'vue'
import Button from 'primevue/button'
import Select from 'primevue/select'
import { blankTangibleRow, formatMoney, textOf } from '~/utils/dailyCost'
import type { TangibleOption } from '~/types/dailyCost'
import type { GridSelectOption } from '~/types/grid'

const props = defineProps<{
  rows: Record<string, unknown>[]
  tangibles: TangibleOption[]
  /** Server-priced amounts, index-aligned with `rows`. */
  amounts: string[]
  lineWarnings?: string[][]
  disabled?: boolean
}>()

const emit = defineEmits<{
  (event: 'update:rows', rows: Record<string, unknown>[]): void
  (event: 'change'): void
}>()

const tangibleOptions = computed<GridSelectOption[]>(() =>
  props.tangibles.map(item => ({
    label: `${item.tangible_code} - ${item.tangible_name}`,
    value: item.id,
  })),
)

/** A row's id field as `number | null` — templates cannot carry type casts. */
function idOf(row: Record<string, unknown>, field: string): number | null {
  const value = row[field]
  return value == null || value === '' ? null : Number(value)
}

function capturedRateOf(row: Record<string, unknown>): string {
  const rate = textOf(row, 'captured_rate')
  if (rate) return rate
  return String(props.tangibles.find(item => item.id === row.tangible_id)?.final_cost ?? '0')
}

function uomOf(row: Record<string, unknown>): string {
  if (textOf(row, 'uom')) return textOf(row, 'uom')
  return String(props.tangibles.find(item => item.id === row.tangible_id)?.uom ?? '')
}

function rowError(row: Record<string, unknown>): string | null {
  if (row.tangible_id == null) return 'Select the tangible used'
  if (!textOf(row, 'quantity')) return 'Enter the quantity used'
  if (Number(textOf(row, 'quantity')) < 0) return 'The quantity cannot be negative'
  if (!textOf(row, 'override_rate') && Number(capturedRateOf(row)) === 0) {
    return 'No unit rate captured — enter an override unit rate'
  }
  return null
}

function onTangibleChange(row: Record<string, unknown>, tangibleId: number | null): void {
  row.tangible_id = tangibleId
  const item = props.tangibles.find(candidate => candidate.id === tangibleId)
  row.captured_rate = item?.final_cost ?? null
  row.uom = item?.uom ?? ''
  row.currency = item?.currency ?? ''
  emit('change')
}

function addRow(): void {
  emit('update:rows', [...props.rows, blankTangibleRow()])
  emit('change')
}

function removeRow(index: number): void {
  const rows = [...props.rows]
  rows.splice(index, 1)
  emit('update:rows', rows)
  emit('change')
}
</script>

<template>
  <section class="tng" data-testid="daily-tangible-lines">
    <header class="tng__head">
      <div>
        <h3 class="tng__title">
          <i class="pi pi-inbox" /> Tangibles
          <span class="tng__count">{{ rows.length }}</span>
        </h3>
        <p class="tng__hint">
          Entered in bulk at well completion, not daily. The list comes from Master Data — not from
          the AFE — so a tangible that was damaged can be replaced by the one actually used.
        </p>
      </div>
      <Button
        label="Add tangible"
        icon="pi pi-plus"
        size="small"
        severity="primary"
        outlined
        :disabled="disabled"
        @click="addRow"
      />
    </header>

    <div class="tng__scroll">
      <table class="tng__table">
        <thead>
          <tr>
            <th class="tng__num">#</th>
            <th>Tangible (Master Data)</th>
            <th class="num">Quantity</th>
            <th>UOM</th>
            <th class="num">Unit Rate</th>
            <th class="num">Override</th>
            <th class="num">Amount</th>
            <th>Remarks</th>
            <th class="tng__action" />
          </tr>
        </thead>
        <tbody>
          <tr v-if="rows.length === 0">
            <td colspan="9" class="tng__empty">
              No tangibles entered — add the tubulars, heads and other tangibles actually used.
            </td>
          </tr>
          <template v-for="(row, index) in rows" :key="row._key as string">
            <tr :class="{ 'is-invalid': rowError(row) }">
              <td class="tng__num">{{ index + 1 }}</td>
              <td>
                <Select
                  :model-value="idOf(row, 'tangible_id')"
                  :options="tangibleOptions"
                  option-label="label"
                  option-value="value"
                  placeholder="Select tangible"
                  filter
                  size="small"
                  class="tng__cell"
                  :disabled="disabled"
                  @update:model-value="onTangibleChange(row, $event as number | null)"
                />
              </td>
              <td class="num">
                <input
                  v-model="row.quantity"
                  type="text"
                  inputmode="decimal"
                  class="tng__input tng__input--num"
                  placeholder="0"
                  :disabled="disabled"
                  @change="emit('change')"
                >
              </td>
              <td class="mono tng__uom">{{ uomOf(row) || '—' }}</td>
              <td class="num mono">{{ formatMoney(capturedRateOf(row)) }}</td>
              <td class="num">
                <input
                  v-model="row.override_rate"
                  type="text"
                  inputmode="decimal"
                  class="tng__input tng__input--num"
                  placeholder="—"
                  :disabled="disabled"
                  @change="emit('change')"
                >
              </td>
              <td class="num mono tng__amount">{{ formatMoney(amounts[index] ?? '0') }}</td>
              <td>
                <input
                  v-model="row.remarks"
                  type="text"
                  class="tng__input"
                  placeholder="Optional remarks"
                  :disabled="disabled"
                  @change="emit('change')"
                >
              </td>
              <td class="tng__action">
                <Button
                  icon="pi pi-times"
                  size="small"
                  severity="danger"
                  text
                  aria-label="Remove tangible line"
                  :disabled="disabled"
                  @click="removeRow(index)"
                />
              </td>
            </tr>
            <tr v-if="rowError(row) || (lineWarnings?.[index]?.length ?? 0) > 0" class="tng__notes">
              <td :colspan="9">
                <span v-if="rowError(row)" class="tng__note tng__note--error">
                  <i class="pi pi-exclamation-circle" /> {{ rowError(row) }}
                </span>
                <span
                  v-for="warning in lineWarnings?.[index] ?? []"
                  :key="warning"
                  class="tng__note"
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
  .tng {
    display: grid;
    gap: 8px;
  }

  .tng__head {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 12px;
    flex-wrap: wrap;
  }

  .tng__title {
    margin: 0;
    font-size: 0.9rem;
    font-weight: 650;
    display: flex;
    align-items: center;
    gap: 6px;
  }

  .tng__count {
    background: var(--app-surface-muted, #eef2f7);
    border-radius: 999px;
    padding: 0 7px;
    font-size: 0.72rem;
    color: var(--app-text-muted, #5b6472);
  }

  .tng__hint {
    margin: 2px 0 0;
    font-size: 0.72rem;
    color: var(--app-text-muted, #6b7480);
    max-width: 90ch;
  }

  .tng__scroll {
    overflow-x: auto;
    border: 1px solid var(--app-border, #e3e7ee);
    border-radius: 10px;
  }

  .tng__table {
    width: 100%;
    border-collapse: separate;
    border-spacing: 0;
    font-size: 0.74rem;
    min-width: 880px;
  }

  .tng__table thead th {
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

  .tng__table tbody td {
    padding: 4px 6px;
    border-bottom: 1px solid var(--app-border-soft, #eef1f6);
    vertical-align: top;
  }

  .tng__table tbody tr.is-invalid td {
    background: #fff7f7;
  }

  .num {
    text-align: right;
    font-variant-numeric: tabular-nums;
  }

  .mono {
    font-family: var(--app-font-mono, ui-monospace, monospace);
  }

  .tng__num {
    width: 26px;
    color: var(--app-text-muted, #8a929e);
    text-align: right;
  }

  .tng__action {
    width: 34px;
    text-align: center;
  }

  .tng__cell {
    width: 100%;
    min-width: 220px;
  }

  .tng__input {
    width: 100%;
    border: 1px solid var(--app-border, #d8dee7);
    border-radius: 6px;
    padding: 4px 6px;
    font-size: 0.74rem;
    background: var(--app-surface, #fff);
  }

  .tng__input--num {
    text-align: right;
    font-variant-numeric: tabular-nums;
    min-width: 70px;
  }

  .tng__input:disabled {
    background: var(--app-surface-muted, #f4f6fa);
  }

  .tng__uom {
    white-space: nowrap;
    color: var(--app-text-muted, #6b7480);
  }

  .tng__amount {
    font-weight: 650;
    white-space: nowrap;
  }

  .tng__empty {
    text-align: center;
    color: var(--app-text-muted, #7c8593);
    padding: 18px 10px !important;
    font-size: 0.78rem;
  }

  .tng__notes td {
    padding: 0 6px 6px 26px !important;
    border-bottom: 1px solid var(--app-border-soft, #eef1f6);
  }

  .tng__note {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    font-size: 0.68rem;
    color: #b45309;
    margin-right: 12px;
  }

  .tng__note--error {
    color: #b91c1c;
  }
</style>
