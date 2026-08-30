import {
  blankConsumableRow,
  blankServiceRow,
  blankTangibleRow,
  chargeCategoriesFor,
  decimalOf,
  formatMoney,
  formatQuantity,
  isOneTimeCategory,
  previewAmounts,
  quantityError,
  quantityLimitFor,
  rateForCategory,
  rateSourceLabel,
  resetRowKeys,
  sectionRateFor,
  subActivityLabel,
  textOf,
  todayIso,
} from '~/utils/dailyCost'
import type { RateCardService } from '~/types/dailyCost'

function makeCard(overrides: Partial<RateCardService> = {}): RateCardService {
  return {
    service_id: 1,
    afe_line_id: 11,
    service_code: 'SVC-0001',
    service_name: 'Directional Drilling',
    provider_type: '3rd Party',
    charging_basis: 'Daily Rate',
    per_service_amount: '0',
    section_id: null,
    phase_id: null,
    rates: [
      { category: 'Operation', unit_rate: '1000.00' },
      { category: 'Mobilization', unit_rate: '5000.00' },
      { category: 'Standby', unit_rate: '200.00' },
    ],
    section_rates: [
      { section_id: 2, phase_id: null, amount: '18000.00' },
      { section_id: 3, phase_id: 7, amount: '9000.00' },
    ],
    ...overrides,
  }
}

describe('daily cost helpers', () => {
  beforeEach(() => {
    resetRowKeys()
  })

  it('formats money and quantities for the compact grids', () => {
    expect(formatMoney('1234.5')).toBe('1,234.50')
    expect(formatMoney(null)).toBe('0.00')
    expect(formatMoney('not-a-number')).toBe('not-a-number')
    expect(formatQuantity('12.0000')).toBe('12')
    expect(formatQuantity('0.5000')).toBe('0.5')
    expect(formatQuantity('')).toBe('')
    expect(todayIso(new Date('2026-08-01T12:00:00Z'))).toMatch(/^\d{4}-\d{2}-\d{2}$/)
  })

  it('offers the eight charge categories only for a daily-rate service', () => {
    expect(chargeCategoriesFor('Daily Rate')).toEqual([
      'Mobilization',
      'Demobilization',
      'Operation',
      'Standby',
      'Personnel-Operation',
      'Personnel-Standby',
      'Fixed Charge',
      'Others',
    ])
    expect(chargeCategoriesFor(null)).toHaveLength(8)
    expect(chargeCategoriesFor('Per Service Rate')).toEqual(['Per Service Rate'])
    expect(chargeCategoriesFor('Per Section Rate')).toEqual(['Per Section Rate'])
  })

  it('never multiplies the one-time charge categories', () => {
    expect(isOneTimeCategory('Mobilization')).toBe(true)
    expect(isOneTimeCategory('Demobilization')).toBe(true)
    expect(isOneTimeCategory('Fixed Charge')).toBe(true)
    expect(isOneTimeCategory('Operation')).toBe(false)
    expect(isOneTimeCategory(null)).toBe(false)
  })

  it('enforces the 0-24 hours and 0-1 days ranges', () => {
    expect(quantityLimitFor('hours')).toBe(24)
    expect(quantityLimitFor('days')).toBe(1)
    expect(quantityError('12', 'hours')).toBeNull()
    expect(quantityError('24', 'hours')).toBeNull()
    expect(quantityError('24.5', 'hours')).toContain('cannot exceed 24')
    expect(quantityError('1', 'days')).toBeNull()
    expect(quantityError('1.5', 'days')).toContain('cannot exceed 1')
    expect(quantityError('-1', 'hours')).toContain('cannot be negative')
    expect(quantityError('', 'hours')).toContain('between 0 and 24')
    expect(quantityError('abc', 'hours')).toContain('must be a number')
  })

  it('captures the rate of the relevant charge category from the AFE card', () => {
    const card = makeCard()
    expect(rateForCategory(card, 'Operation')).toBe('1000.00')
    expect(rateForCategory(card, 'Standby')).toBe('200.00')
    expect(rateForCategory(card, 'Demobilization')).toBeNull()
    expect(rateForCategory(null, 'Operation')).toBeNull()
    expect(rateSourceLabel(card, 'Operation')).toBe('AFE unit rate')
    expect(rateSourceLabel(card, 'Mobilization')).toBe('AFE one-time amount')
    expect(rateSourceLabel(null, 'Operation')).toContain('Not on the selected AFE')
    expect(rateSourceLabel(makeCard({ charging_basis: 'Per Service Rate' }), 'Per Service Rate'))
      .toBe('AFE per-service amount')
    expect(rateSourceLabel(makeCard({ charging_basis: 'Per Section Rate' }), 'Per Section Rate'))
      .toBe('AFE section amount')
  })

  it('finds the section rate for the selected section, then falls back to the section row', () => {
    const card = makeCard({ charging_basis: 'Per Section Rate' })
    expect(sectionRateFor(card, 2, null)).toBe('18000.00')
    expect(sectionRateFor(card, 2, 9)).toBe('18000.00')
    expect(sectionRateFor(card, 3, 7)).toBe('9000.00')
    expect(sectionRateFor(card, 4, null)).toBeNull()
    expect(sectionRateFor(card, null, null)).toBeNull()
  })

  it('reads a sub activity the way the page shows it', () => {
    expect(
      subActivityLabel({
        id: 1,
        sub_activity_code: 'RIH-01',
        sub_activity_name: 'Run in hole with tubing',
        activity_id: 1,
        activity_code: 'DRL',
      }),
    ).toBe('RIH-01 - Run in hole with tubing (DRL)')
    expect(subActivityLabel(null)).toBe('')
  })

  it('keeps the preview amounts in the order the rows were sent', () => {
    expect(previewAmounts([{ amount: '500.00' }, { amount: '5000.00' }])).toEqual([
      '500.00',
      '5000.00',
    ])
    expect(previewAmounts([])).toEqual([])
  })

  it('builds blank rows for each block, with distinct keys', () => {
    const service = blankServiceRow()
    const consumable = blankConsumableRow('fuel')
    const tangible = blankTangibleRow()
    expect(service._key).not.toBe(consumable._key)
    expect(service.quantity_unit).toBe('hours')
    expect(consumable.category).toBe('fuel')
    expect(consumable.item_code).toBe('FUEL')
    expect(blankConsumableRow('cement_additive').item_code).toBe('CEM-ADD')
    expect(blankConsumableRow('mud_chemical').item_code).toBe('')
    expect(tangible.quantity).toBe('1')
  })

  it('reads row values the way the save payload needs them', () => {
    const row = { service_id: 4, quantity: ' 12 ', override_rate: '', captured_rate: '1000.00' }
    expect(textOf(row, 'quantity')).toBe('12')
    expect(textOf(row, 'remarks')).toBe('')
    expect(decimalOf(row, 'override_rate')).toBeNull()
    expect(decimalOf(row, 'captured_rate')).toBe('1000')
    expect(decimalOf(row, 'quantity')).toBe('12')
  })
})
