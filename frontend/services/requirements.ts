import type { ApiClient } from '~/services/apiClient'
import type { ImportCommitResult, ImportPreview } from '~/types/imports'
import type { BulkValidationResult, PageResponse } from '~/types/masterData'
import type {
  ProjectRecord,
  RequirementItemRecord,
  RequirementRecord,
  WellRecord,
} from '~/types/requirements'

export class RequirementApi {
  constructor(private readonly api: ApiClient) {}

  listProjects(search = ''): Promise<PageResponse<ProjectRecord>> {
    return this.api.get(`/projects?page=1&page_size=500&search=${encodeURIComponent(search)}`)
  }

  createProject(payload: Record<string, unknown>): Promise<ProjectRecord> {
    return this.api.post('/projects', payload)
  }

  updateProject(id: string, payload: Record<string, unknown>): Promise<ProjectRecord> {
    return this.api.patch(`/projects/${id}`, payload)
  }

  deleteProject(id: string): Promise<undefined> {
    return this.api.delete(`/projects/${id}`)
  }

  listWells(projectId?: string): Promise<PageResponse<WellRecord>> {
    const query = projectId ? `&project_id=${projectId}` : ''
    return this.api.get(`/wells?page=1&page_size=500${query}`)
  }

  createWell(payload: Record<string, unknown>): Promise<WellRecord> {
    return this.api.post('/wells', payload)
  }

  updateWell(id: string, payload: Record<string, unknown>): Promise<WellRecord> {
    return this.api.patch(`/wells/${id}`, payload)
  }

  deleteWell(id: string): Promise<undefined> {
    return this.api.delete(`/wells/${id}`)
  }

  listRequirements(wellId?: string, status?: string): Promise<PageResponse<RequirementRecord>> {
    const query = new URLSearchParams({ page: '1', page_size: '500' })
    if (wellId) query.set('well_id', wellId)
    if (status) query.set('status', status)
    return this.api.get(`/requirements?${query}`)
  }

  getRequirement(id: string): Promise<RequirementRecord> {
    return this.api.get(`/requirements/${id}`)
  }

  createRequirement(payload: Record<string, unknown>): Promise<RequirementRecord> {
    return this.api.post('/requirements', payload)
  }

  updateRequirement(id: string, payload: Record<string, unknown>): Promise<RequirementRecord> {
    return this.api.patch(`/requirements/${id}`, payload)
  }

  deleteRequirement(id: string): Promise<undefined> {
    return this.api.delete(`/requirements/${id}`)
  }

  validateItems(requirementId: string, rows: Record<string, unknown>[]): Promise<BulkValidationResult> {
    return this.api.post(`/requirements/${requirementId}/items/bulk/validate`, { rows })
  }

  bulkCreateItems(requirementId: string, rows: Record<string, unknown>[]): Promise<RequirementItemRecord[]> {
    return this.api.post(`/requirements/${requirementId}/items/bulk/create`, { rows })
  }

  bulkUpdateItems(rows: Record<string, unknown>[]): Promise<RequirementItemRecord[]> {
    return this.api.patch('/requirement-items/bulk/update', { rows })
  }

  deactivateItem(id: string): Promise<undefined> {
    return this.api.delete(`/requirement-items/${id}`)
  }

  submit(id: string): Promise<RequirementRecord> {
    return this.api.post(`/requirements/${id}/submit`, {})
  }

  previewImport(id: string, file: File): Promise<ImportPreview> {
    const body = new FormData()
    body.append('file', file)
    return this.api.postForm(`/requirements/${id}/import/preview`, body)
  }

  commitImport(id: string, batchId: string): Promise<ImportCommitResult> {
    return this.api.post(`/requirements/${id}/import/commit`, { batch_id: batchId })
  }

  template(id: string): Promise<Blob> {
    return this.api.download(`/requirements/${id}/import/template`)
  }

  export(id: string): Promise<Blob> {
    return this.api.download(`/requirements/${id}/export`)
  }
}
