import type { ApiClient } from '~/services/apiClient'
import type { EnterpriseConfigSummary, EnterpriseNode, HierarchyRule, NodeType, ReportingMapping, VersionedConfig } from '~/types/enterpriseConfig'
export class EnterpriseConfigApi {
  constructor(private readonly api: ApiClient) {}
  summary(): Promise<EnterpriseConfigSummary> { return this.api.get('/enterprise-config/summary') }
  createNodeType(body: Record<string, unknown>): Promise<NodeType> { return this.api.post('/enterprise-config/node-types', body) }
  createRule(parentTypeId: string, childTypeId: string): Promise<HierarchyRule> { return this.api.post('/enterprise-config/hierarchy-rules', { parent_type_id: parentTypeId, child_type_id: childTypeId }) }
  createNode(body: Record<string, unknown>): Promise<EnterpriseNode> { return this.api.post('/enterprise-config/nodes', body) }
  createVersioned(kind: 'cost-structures' | 'rate-books' | 'estimate-templates', body: Record<string, unknown>): Promise<VersionedConfig> { return this.api.post(`/enterprise-config/${kind}`, body) }
  createMapping(body: Record<string, unknown>): Promise<ReportingMapping> { return this.api.post('/enterprise-config/reporting-mappings', body) }
}
