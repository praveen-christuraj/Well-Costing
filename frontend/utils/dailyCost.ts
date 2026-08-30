/**
 * Pure helpers shared by the Daily Costs page and its panels.
 *
 * Nothing here calculates money — the server prices a day (POST
 * `/daily-cost/preview` for the live totals, the same engine on save). These
 * helpers only format what came back, validate the quantity ranges the engine
 * enforces, and build the blank rows the panels edit.
 */

import { ONE_TIME_CATEGORIES, type ChargingBasis, type QuantityUnit } from '~/types/afe'
import {
  MAX_DAYS,
  MAX_HOURS,
  type ConsumableCategory,
  type DailyCostSubActivity,
  type RateCardService,
} from '~/types/dailyCost'

/** `1234.5` → `1,234.50`; anything unparsable comes back unchanged. */
export function formatMoney(value: string | number | null | undefined): string {
  if (value == null || value === '') return '0.00'
  const numeric = typeof value === 'number' ? value : Number(value)
  if (!Number.isFinite(numeric)) return String(value)
  return numeric.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

/** Quantity without trailing zeros: `12.0000` → `12`, `0.5000` → `0.5`. */
export function formatQuantity(value: string | number | null | undefined): string {
  if (value == null || value === '') return ''
  const numeric = typeof value === 'number' ? value : Number(value)
  if (!Number.isFinite(numeric)) return String(value)
  return String(numeric)
}

/** `2026-08-01` → today's local ISO date when called without an argument. */
export function todayIso(reference: Date = new Date()): string {
  const offset = reference.getTimezoneOffset()
  return new Date(reference.getTime() - offset * 60_000).toISOString().slice(0, 10)
}

/** The single date of a date-picker value (ranges and nulls are ignored). */
export function toDate(
  value: Date | Date[] | (Date | null)[] | null | undefined,
): Date | null {
  if (value == null) return null
  if (Array.isArray(value)) {
    const first = value.find(item => item instanceof Date)
    return first instanceof Date ? first : null
  }
  return value instanceof Date ? value : null
}

/** A date-picker value as the `YYYY-MM-DD` the API expects. */
export function isoOf(value: Date | Date[] | (Date | null)[] | null | undefined): string {
  return todayIso(toDate(value) ?? new Date())
}

/** `2026-08-01` → `01-Aug-2026`, the way the daily sheet reads it. */
export function formatDateLabel(value: string | null | undefined): string {
  if (!value) return '—'
  const parsed = new Date(`${value}T00:00:00`)
  if (Number.isNaN(parsed.getTime())) return value
  return parsed.toLocaleDateString(undefined, { day: '2-digit', month: 'short', year: 'numeric' })
}

/** The charge category a service line is priced from, for its charging basis. */
export function chargeCategoriesFor(basis: ChargingBasis | null | undefined): string[] {
  if (basis == null || basis === 'Daily Rate') {
    return [
      'Mobilization',
      'Demobilization',
      'Operation',
      'Standby',
      'Personnel-Operation',
      'Personnel-Standby',
      'Fixed Charge',
      'Others',
    ]
  }
  // Per service / per section are lump sums — the basis is its own category.
  return [basis]
}

/** Mobilization, demobilization and fixed charges are never multiplied. */
export function isOneTimeCategory(category: string | null | undefined): boolean {
  return category != null && (ONE_TIME_CATEGORIES as readonly string[]).includes(category)
}

/** Hours (0–24) or days (0–1), depending on the entered unit. */
export function quantityLimitFor(unit: QuantityUnit | null | undefined): number {
  return unit === 'days' ? MAX_DAYS : MAX_HOURS
}

/**
 * The engine's quantity rule, checked before the row is sent so the user sees
 * the reason immediately. Returns `null` when the value is acceptable.
 */
export function quantityError(
  value: string | number | null | undefined,
  unit: QuantityUnit | null | undefined,
): string | null {
  const limit = quantityLimitFor(unit)
  if (value == null || String(value).trim() === '') return `Enter a quantity between 0 and ${limit}`
  const numeric = Number(value)
  if (!Number.isFinite(numeric)) return 'The quantity must be a number'
  if (numeric < 0) return 'The quantity cannot be negative'
  if (numeric > limit) {
    return unit === 'days'
      ? 'Days cannot exceed 1 — enter a fraction of a day (e.g. 0.5)'
      : `Hours cannot exceed ${MAX_HOURS}`
  }
  return null
}

/** The AFE unit rate for one charge category of a rate-card service. */
export function rateForCategory(card: RateCardService | null, category: string | null): string | null {
  if (!card || !category) return null
  const match = card.rates.find(rate => rate.category === category)
  return match ? match.unit_rate : null
}

/** The AFE section amount for a per-section service, at the chosen scope. */
export function sectionRateFor(
  card: RateCardService | null,
  sectionId: number | null,
  phaseId: number | null,
): string | null {
  if (!card || sectionId == null) return null
  const exact = card.section_rates.find(
    rate => rate.section_id === sectionId && rate.phase_id === phaseId,
  )
  if (exact) return exact.amount
  const sectionOnly = card.section_rates.find(
    rate => rate.section_id === sectionId && rate.phase_id == null,
  )
  return sectionOnly ? sectionOnly.amount : null
}

/** What a service line of the day is charged from, in one short phrase. */
export function rateSourceLabel(card: RateCardService | null, chargeCategory: string): string {
  if (!card) return 'Not on the selected AFE — enter the rate'
  if (card.charging_basis === 'Per Service Rate') return 'AFE per-service amount'
  if (card.charging_basis === 'Per Section Rate') return 'AFE section amount'
  return isOneTimeCategory(chargeCategory) ? 'AFE one-time amount' : 'AFE unit rate'
}

/** Sub activities read as `RIH-01 - Run in hole with tubing (DRL)`. */
export function subActivityLabel(sub: DailyCostSubActivity | null | undefined): string {
  if (!sub) return ''
  const activity = sub.activity_code || sub.activity_name
  return `${sub.sub_activity_code} - ${sub.sub_activity_name}${activity ? ` (${activity})` : ''}`
}

/** The server prices the rows in the order they were sent — index is the key. */
export function previewAmounts(lines: { amount: string }[]): string[] {
  return lines.map(line => line.amount)
}

/** A blank service row of the day. */
export function blankServiceRow(): Record<string, unknown> {
  return {
    _key: nextRowKey(),
    service_id: null,
    charging_basis: null,
    charge_category: '',
    afe_line_id: null,
    section_id: null,
    phase_id: null,
    sub_activity_id: null,
    quantity: '',
    quantity_unit: 'hours',
    captured_rate: null,
    override_rate: '',
    remarks: '',
  }
}

/** A blank consumable row for one of the four categories. */
export function blankConsumableRow(category: ConsumableCategory): Record<string, unknown> {
  return {
    _key: nextRowKey(),
    category,
    item_id: null,
    item_code: category === 'fuel' ? 'FUEL' : category === 'cement_additive' ? 'CEM-ADD' : '',
    item_name: '',
    quantity: '',
    uom: '',
    currency: '',
    captured_rate: null,
    override_rate: '',
    manual_amount: '',
    section_id: null,
    phase_id: null,
    sub_activity_id: null,
    remarks: '',
  }
}

/** A blank tangible row — the list always comes from Master Data. */
export function blankTangibleRow(): Record<string, unknown> {
  return {
    _key: nextRowKey(),
    tangible_id: null,
    quantity: '1',
    uom: '',
    currency: '',
    captured_rate: null,
    override_rate: '',
    remarks: '',
  }
}

let rowKeyCounter = 0

/** Stable in-page row identity (rows are not saved until the day is). */
export function nextRowKey(): string {
  rowKeyCounter += 1
  return `row-${rowKeyCounter}`
}

/** Reset the row counter — used by the tests so keys are predictable. */
export function resetRowKeys(): void {
  rowKeyCounter = 0
}

/** Text value of a row field, trimmed, as the API expects it. */
export function textOf(row: Record<string, unknown>, field: string): string {
  const value = row[field]
  return value == null ? '' : String(value).trim()
}

/** Decimal value of a row field, or `null` when the user left it blank. */
export function decimalOf(row: Record<string, unknown>, field: string): string | null {
  const text = textOf(row, field)
  if (text === '') return null
  const numeric = Number(text)
  return Number.isFinite(numeric) ? String(numeric) : null
}
