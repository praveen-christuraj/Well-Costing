export interface HealthResponse {
  status: 'healthy' | 'degraded'
  database: 'connected' | 'disconnected' | 'schema_outdated'
  environment: string
  version: string
  schema_status?: 'current' | 'outdated' | 'unknown'
  schema_message?: string | null
}
