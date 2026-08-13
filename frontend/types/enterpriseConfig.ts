export interface NodeType { id: string; code: string; name: string; level_order: number; description: string | null; is_active: boolean }
export interface HierarchyRule { id: string; parent_type_id: string; child_type_id: string; is_active: boolean }
export interface EnterpriseNode { id: string; node_type_id: string; parent_id: string | null; code: string; name: string; description: string | null; is_active: boolean }
export interface VersionedConfig { id: string; code: string; name: string; version_number: number; description: string | null; lifecycle_status: 'draft' | 'published' | 'retired' }
export interface ReportingMapping { id: string; target_system: string; source_dimension: string; source_value: string; target_value: string; version_number: number; lifecycle_status: string }
export interface EnterpriseConfigSummary { node_types: NodeType[]; hierarchy_rules: HierarchyRule[]; nodes: EnterpriseNode[]; cost_structures: VersionedConfig[]; rate_books: VersionedConfig[]; estimate_templates: VersionedConfig[]; reporting_mappings: ReportingMapping[]; workflow_profile_count: number }
