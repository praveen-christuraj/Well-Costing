import { mount } from '@vue/test-utils'
import EstimateBreakdownChart from '~/components/charts/EstimateBreakdownChart.vue'

describe('EstimateBreakdownChart', () => {
  it('shows a safe empty state while calculation rules are pending', () => {
    const wrapper = mount(EstimateBreakdownChart, {
      props: { categories: [] },
    })

    expect(wrapper.text()).toContain('No calculated breakdown')
    expect(wrapper.text()).toContain('confirmed Phase 5 rules')
  })
})
