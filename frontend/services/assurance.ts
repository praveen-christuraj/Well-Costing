import type { ApiClient } from '~/services/apiClient'
import type { AssuranceStatus } from '~/types/assurance'
export class AssuranceApi { constructor(private readonly api: ApiClient) {} status(): Promise<AssuranceStatus> { return this.api.get('/assurance/status') } }
