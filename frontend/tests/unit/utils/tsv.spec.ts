import { parseTsv } from '~/utils/tsv'

describe('parseTsv', () => {
  it('maps pasted Excel rows to configured grid columns', () => {
    expect(parseTsv('S-01\tMud logging\tDaily service\nS-02\tWireline\tPer run', [
      { field: 'code' }, { field: 'name' }, { field: 'description' },
    ])).toEqual([
      { code: 'S-01', name: 'Mud logging', description: 'Daily service' },
      { code: 'S-02', name: 'Wireline', description: 'Per run' },
    ])
  })
})
