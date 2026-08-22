import type { ApiClient } from '~/services/apiClient'
import type { AfeLineRecord, AfeRecord, DrillingPhaseRecord, ProjectRecord, WellRecord } from '~/types/afe'
import type { ImportCommitResult, ImportPreview } from '~/types/imports'
import type { BulkValidationResult, PageResponse } from '~/types/masterData'

export class AfeApi {
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

  recoverProject(id: string): Promise<ProjectRecord> {
    return this.api.post(`/projects/${id}/recover`, {})
  }

  hardDeleteProject(id: string): Promise<undefined> {
    return this.api.delete(`/projects/${id}/hard`)
  }

  listWells(projectId?: string, isActive: boolean | null = null): Promise<PageResponse<WellRecord>> {
    const params = new URLSearchParams({ page: '1', page_size: '500' })
    if (projectId) params.set('project_id', projectId)
    if (isActive !== null) params.set('is_active', String(isActive))
    return this.api.get(`/wells?${params}`)
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

  recoverWell(id: string): Promise<WellRecord> {
    return this.api.post(`/wells/${id}/recover`, {})
  }

  hardDeleteWell(id: string): Promise<undefined> {
    return this.api.delete(`/wells/${id}/hard`)
  }

  listAfes(wellId?: string, status?: string, isActive: boolean | null = true): Promise<PageResponse<AfeRecord>> {
    const query = new URLSearchParams({ page: '1', page_size: '500' })
    if (wellId) query.set('well_id', wellId)
    if (status) query.set('status', status)
    if (isActive !== null) query.set('is_active', String(isActive))
    return this.api.get(`/afes?${query}`)
  }

  listDeletedAfes(): Promise<PageResponse<AfeRecord>> {
    return this.listAfes(undefined, undefined, false)
  }

  getAfe(id: string): Promise<AfeRecord> {
    return this.api.get(`/afes/${id}`)
  }

  createAfe(payload: Record<string, unknown>): Promise<AfeRecord> {
    return this.api.post('/afes', payload)
  }

  updateAfe(id: string, payload: Record<string, unknown>): Promise<AfeRecord> {
    return this.api.patch(`/afes/${id}`, payload)
  }

  deleteAfe(id: string): Promise<undefined> {
    return this.api.delete(`/afes/${id}`)
  }

  recoverAfe(id: string): Promise<AfeRecord> {
    return this.api.post(`/afes/${id}/recover`, {})
  }

  hardDeleteAfe(id: string): Promise<undefined> {
    return this.api.delete(`/afes/${id}/hard`)
  }

  reopen(id: string, remarks: string): Promise<AfeRecord> {
    return this.api.post(`/afes/${id}/reopen`, { remarks })
  }

  listDrillingPhases(): Promise<DrillingPhaseRecord[]> {
    return this.api.get('/drilling-phases')
  }

  createDrillingPhase(payload: Record<string, unknown>): Promise<DrillingPhaseRecord> {
    return this.api.post('/drilling-phases', payload)
  }

  updateDrillingPhase(id: string, payload: Record<string, unknown>): Promise<DrillingPhaseRecord> {
    return this.api.patch(`/drilling-phases/${id}`, payload)
  }

  deleteDrillingPhase(id: string): Promise<undefined> {
    return this.api.delete(`/drilling-phases/${id}`)
  }

  validateLines(afeId: string, rows: Record<string, unknown>[]): Promise<BulkValidationResult> {
    return this.api.post(`/afes/${afeId}/lines/bulk/validate`, { rows })
  }

  bulkCreateLines(afeId: string, rows: Record<string, unknown>[]): Promise<AfeLineRecord[]> {
    return this.api.post(`/afes/${afeId}/lines/bulk/create`, { rows })
  }

  bulkUpdateLines(rows: Record<string, unknown>[]): Promise<AfeLineRecord[]> {
    return this.api.patch('/afe-lines/bulk/update', { rows })
  }

  deactivateLine(id: string): Promise<undefined> {
    return this.api.delete(`/afe-lines/${id}`)
  }

  recoverLine(id: string): Promise<AfeLineRecord> {
    return this.api.post(`/afe-lines/${id}/recover`, {})
  }

  listRemovedLines(afeId: string): Promise<AfeLineRecord[]> {
    return this.api.get(`/afes/${afeId}/lines/removed`)
  }

  submit(id: string): Promise<AfeRecord> {
    return this.api.post(`/afes/${id}/submit`, {})
  }

  previewImport(id: string, file: File): Promise<ImportPreview> {
    const body = new FormData()
    body.append('file', file)
    return this.api.postForm(`/afes/${id}/import/preview`, body)
  }

  commitImport(id: string, batchId: string): Promise<ImportCommitResult> {
    return this.api.post(`/afes/${id}/import/commit`, { batch_id: batchId })
  }

  template(id: string): Promise<Blob> {
    return this.api.download(`/afes/${id}/import/template`)
  }

  export(id: string): Promise<Blob> {
    return this.api.download(`/afes/${id}/export`)
  }
}
