export interface HealthResponse {
  status: 'healthy' | 'degraded'
  database: 'connected' | 'disconnected'
  environment: string
  version: string
}
