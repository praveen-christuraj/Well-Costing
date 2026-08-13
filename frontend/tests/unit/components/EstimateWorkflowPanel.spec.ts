import { mount } from '@vue/test-utils'
import EstimateWorkflowPanel from '~/components/workflow/EstimateWorkflowPanel.vue'
import type { EstimateWorkflowStatus } from '~/types/workflow'

const pendingStatus: EstimateWorkflowStatus = {
  estimate_id: 'estimate-1',
  estimate_version_id: 'version-1',
  version_number: 1,
  workflow_status: 'profile_pending',
  profile: null,
  current_state_key: null,
  available_actions: [],
  transition_attempts: [],
  review_comments: [],
  pending_requirements: ['approved states', 'role mappings'],
}

describe('EstimateWorkflowPanel', () => {
  it('shows pending policy without inventing approval actions', () => {
    const wrapper = mount(EstimateWorkflowPanel, {
      props: { status: pendingStatus, note: '', saving: false },
    })

    expect(wrapper.text()).toContain('Workflow profile pending')
    expect(wrapper.text()).toContain('Pending workflow policy (2)')
    expect(wrapper.text()).toContain('No transition attempts yet')
    expect(wrapper.findAll('button').map(button => button.text())).not.toContain('Approve')
  })
})
