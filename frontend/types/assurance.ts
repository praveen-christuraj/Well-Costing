export interface AssuranceCheck { key: string; label: string; status: 'passed' | 'failed'; violations: number; detail: string }
export interface AssuranceBlocker { key: string; status: 'blocked'; detail: string }
export interface AssuranceStatus { status: 'framework_ready' | 'failed'; migration_head: string; reporting_contract_version: string; checks: AssuranceCheck[]; blockers: AssuranceBlocker[] }
