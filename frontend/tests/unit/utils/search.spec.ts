import { describe, expect, it } from 'vitest'
import { matchesAdvancedSearch, tokenizeSearch } from '~/utils/search'

describe('tokenizeSearch', () => {
  it('splits on whitespace and lower-cases', () => {
    expect(tokenizeSearch('  Acme  PO-1 ')).toEqual(['acme', 'po-1'])
  })

  it('keeps quoted phrases together', () => {
    expect(tokenizeSearch('"Acme Drilling" SO-9')).toEqual(['acme drilling', 'so-9'])
  })

  it('returns an empty list for blank input', () => {
    expect(tokenizeSearch('   ')).toEqual([])
  })
})

describe('matchesAdvancedSearch', () => {
  const po = {
    po_so_number: 'PO-2024-001',
    vendor: 'VEND001 — Acme Drilling',
    po_type: 'PO',
    remarks: 'Callout for rig 4',
  }

  it('matches any field (vendor name, not only the number)', () => {
    expect(matchesAdvancedSearch(po, 'acme')).toBe(true)
    expect(matchesAdvancedSearch(po, 'PO-2024-001')).toBe(true)
    expect(matchesAdvancedSearch(po, 'rig 4')).toBe(true)
    expect(matchesAdvancedSearch(po, 'missing')).toBe(false)
  })

  it('requires every token to match (AND across fields)', () => {
    expect(matchesAdvancedSearch(po, 'acme po-2024')).toBe(true)
    expect(matchesAdvancedSearch(po, 'acme SO-9')).toBe(false)
  })

  it('does not join adjacent fields into a false positive', () => {
    expect(matchesAdvancedSearch({ a: 'ven', b: 'dor' }, 'vendor')).toBe(false)
  })

  it('flattens nested objects and skips bookkeeping keys', () => {
    const row = { _id: 7, _state: 'clean', name: 'PDC', extra: { code: 'DB-001' } }
    expect(matchesAdvancedSearch(row, 'db-001')).toBe(true)
    expect(matchesAdvancedSearch(row, 'clean')).toBe(false)
  })

  it('treats an empty query as a match', () => {
    expect(matchesAdvancedSearch(po, '  ')).toBe(true)
  })
})
