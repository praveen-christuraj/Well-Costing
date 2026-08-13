export interface WorkflowTransition {
  id: string
  action_key: string
  label: string
  from_state_key: string
  to_state_key: string
  sort_order: number
  requires_comment: boolean
  allowed_role_names: string[]
}

export interface WorkflowProfile {
  id: string
  code: string
  name: string
  record_type: string
  version_number: number
  lifecycle_status: string
  description: string | null
  source_reference: string | null
  states: Array<{ state_key: string, label: string, is_initial: boolean, is_terminal: boolean }>
  transitions: WorkflowTransition[]
}

export interface WorkflowTransitionAttempt {
  id: string
  requested_action: string
  from_state_key: string | null
  to_state_key: string | null
  status: 'completed' | 'blocked' | 'denied' | 'failed'
  message: string | null
  created_at: string
  created_by: string | null
}

export interface ReviewComment {
  id: string
  estimate_version_id: string
  body: string
  created_at: string
  created_by: string | null
}

export interface EstimateWorkflowStatus {
  estimate_id: string
  estimate_version_id: string
  version_number: number
  workflow_status: 'profile_pending' | 'not_started' | 'active'
  profile: WorkflowProfile | null
  current_state_key: string | null
  available_actions: WorkflowTransition[]
  transition_attempts: WorkflowTransitionAttempt[]
  review_comments: ReviewComment[]
  pending_requirements: string[]
}
