import { mount } from '@vue/test-utils'
import AfeBaselinePanel from '~/components/afe/AfeBaselinePanel.vue'
import type { EstimateAfeStatus } from '~/types/afeSnapshots'

const pending: EstimateAfeStatus = {
  estimate_id: 'estimate-1',
  estimate_version_id: 'version-1',
  version_number: 1,
  afe_status: 'policy_pending',
  baseline_snapshot: null,
  creation_attempts: [],
  pending_requirements: ['eligibility gate', 'numbering policy'],
}

describe('AfeBaselinePanel', () => {
  it('shows an explicit but fail-closed baseline request shell', async () => {
    const wrapper = mount(AfeBaselinePanel, {
      props: { status: pending, loading: false, requestMessage: null },
    })

    expect(wrapper.text()).toContain('No AFE issued')
    expect(wrapper.text()).toContain('Pending AFE policy (2)')
    await wrapper.get('button').trigger('click')
    expect(wrapper.emitted('create-baseline')).toHaveLength(1)
  })
})
