import type { ApiClient } from '~/services/apiClient'
import type { ImportBatch, ImportCommitResult, ImportPreview } from '~/types/imports'
import type {
  BulkValidationResult,
  MasterDataRecord,
  PageResponse,
  RateRecord,
} from '~/types/masterData'

export interface MasterDataWrite {
  id?: string
  code: string
  name: string
  description?: string | null
  is_active?: boolean
  symbol?: string | null
  parent_id?: string | null
  cost_category_id?: string | null
  cost_code_id?: string | null
  default_unit_id?: string | null
}

export class MasterDataApi {
  constructor(private readonly api: ApiClient) {}

  list(entity: string, search = ''): Promise<PageResponse<MasterDataRecord>> {
    const query = new URLSearchParams({ page: '1', page_size: '500', sort_by: 'code' })
    if (search) query.set('search', search)
    return this.api.get(`/master-data/${entity}?${query.toString()}`)
  }

  validate(entity: string, rows: MasterDataWrite[]): Promise<BulkValidationResult> {
    return this.api.post(`/master-data/${entity}/bulk/validate`, { rows })
  }

  bulkCreate(entity: string, rows: MasterDataWrite[]): Promise<MasterDataRecord[]> {
    return this.api.post(`/master-data/${entity}/bulk/create`, { rows })
  }

  bulkUpdate(entity: string, rows: MasterDataWrite[]): Promise<MasterDataRecord[]> {
    return this.api.patch(`/master-data/${entity}/bulk/update`, { rows })
  }

  deactivate(entity: string, id: string): Promise<undefined> {
    return this.api.delete(`/master-data/${entity}/${id}`)
  }

  listRates(): Promise<PageResponse<RateRecord>> {
    return this.api.get('/master-data/rates?page=1&page_size=500')
  }

  bulkCreateRates(rows: Record<string, unknown>[]): Promise<RateRecord[]> {
    return this.api.post('/master-data/rates/bulk/create', { rows })
  }

  bulkUpdateRates(rows: Record<string, unknown>[]): Promise<RateRecord[]> {
    return this.api.patch('/master-data/rates/bulk/update', { rows })
  }

  deactivateRate(id: string): Promise<undefined> {
    return this.api.delete(`/master-data/rates/${id}`)
  }

  previewImport(entity: string, file: File, mappingJson?: string): Promise<ImportPreview> {
    const body = new FormData()
    body.append('file', file)
    if (mappingJson?.trim()) body.append('mapping_json', mappingJson.trim())
    return this.api.postForm(`/import/${entity}/preview`, body)
  }

  commitImport(entity: string, batchId: string): Promise<ImportCommitResult> {
    return this.api.post(`/import/${entity}/commit`, { batch_id: batchId })
  }

  importHistory(): Promise<PageResponse<ImportBatch>> {
    return this.api.get('/imports/batches?page=1&page_size=100')
  }

  downloadTemplate(entity: string): Promise<Blob> {
    return this.api.download(`/import/${entity}/template`)
  }

  export(entity: string): Promise<Blob> {
    return this.api.download(`/export/${entity}`)
  }
}
