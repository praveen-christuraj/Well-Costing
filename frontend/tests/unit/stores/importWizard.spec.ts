import { createPinia, setActivePinia } from 'pinia'
import { useImportWizardStore } from '~/stores/importWizard'
import type { ImportPreview } from '~/types/imports'

describe('import wizard state machine', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('moves from file selection through validated commit', () => {
    const store = useImportWizardStore()
    store.selectFile(new File(['data'], 'vendors.xlsx'))
    expect(store.step).toBe('file-selected')
    store.startUpload()
    expect(store.step).toBe('uploading')
    store.setPreview({
      batch_id: 'batch', entity_type: 'vendors', status: 'validated', mapping_profile: 'vendors-default', mapping_version: '1.0', detected_columns: ['code', 'name'], applied_mapping: { code: 'code', name: 'name' }, total_rows: 1, valid_rows: 1, error_rows: 0, errors: [], sample: [],
    } satisfies ImportPreview)
    expect(store.canCommit).toBe(true)
    store.startCommit()
    store.complete('1 row imported')
    expect(store.step).toBe('complete')
  })

  it('blocks invalid batches from commit', () => {
    const store = useImportWizardStore()
    store.selectFile(new File(['data'], 'bad.xlsx'))
    store.startUpload()
    store.setPreview({
      batch_id: 'batch', entity_type: 'vendors', status: 'invalid', mapping_profile: 'vendors-default', mapping_version: '1.0', detected_columns: [], applied_mapping: {}, total_rows: 1, valid_rows: 0, error_rows: 1, errors: [], sample: [],
    })
    expect(store.canCommit).toBe(false)
    expect(() => store.startCommit()).toThrow('not ready')
  })
})
