import { mount } from '@vue/test-utils'
import CostStateReportChart from '~/components/charts/CostStateReportChart.vue'

describe('CostStateReportChart', () => {
  it('keeps financial charts pending when metric rules are unresolved', () => {
    const wrapper = mount(CostStateReportChart, { props: { states: [{ cost_state: 'actual', transaction_count: 0, amount: null, currency_code: null }] } })
    expect(wrapper.text()).toContain('Financial metrics pending')
    expect(wrapper.text()).toContain('variance')
  })
})
