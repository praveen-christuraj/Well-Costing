import { describe, expect, it } from 'vitest'
import { parseTsv } from '~/utils/tsv'

describe('parseTsv', () => {
  it('maps tab-separated lines onto the given columns in order', () => {
    const rows = parseTsv('M\tMetre\tlength\nBBL\tBarrel\tvolume', [
      { field: 'code' },
      { field: 'name' },
      { field: 'description' },
    ])
    expect(rows).toEqual([
      { code: 'M', name: 'Metre', description: 'length' },
      { code: 'BBL', name: 'Barrel', description: 'volume' },
    ])
  })

  it('normalises Windows line endings and trailing whitespace', () => {
    const rows = parseTsv('A\tOne\r\nB\tTwo\r\n', [{ field: 'code' }, { field: 'name' }])
    expect(rows).toEqual([
      { code: 'A', name: 'One' },
      { code: 'B', name: 'Two' },
    ])
  })

  it('fills missing trailing cells with empty strings', () => {
    const rows = parseTsv('A', [{ field: 'code' }, { field: 'name' }])
    expect(rows).toEqual([{ code: 'A', name: '' }])
  })

  it('returns an empty list for blank input', () => {
    expect(parseTsv('   \n\t', [{ field: 'code' }])).toEqual([])
  })
})
