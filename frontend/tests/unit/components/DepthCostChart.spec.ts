import { mount } from '@vue/test-utils'
import DepthCostChart from '~/components/daily-cost/DepthCostChart.vue'
import type { DepthCostPoint } from '~/types/dailyCost'

const points: DepthCostPoint[] = [
  {
    depth: '1500.00',
    section_id: 1,
    section_label: 'SEC1 — Surface Section',
    estimated_cumulative: '38000.00',
    actual_cumulative: '24000.00',
    estimated_section: '38000.00',
    actual_section: '24000.00',
    variance: '-14000.00',
  },
  {
    depth: '3000',
    section_id: 2,
    section_label: 'SEC2 — Intermediate',
    estimated_cumulative: '42000.00',
    actual_cumulative: '55641.55',
    estimated_section: '4000.00',
    actual_section: '31641.55',
    variance: '13641.55',
  },
]

describe('DepthCostChart', () => {
  it('plots the AFE estimate and the actual cost against depth', () => {
    const wrapper = mount(DepthCostChart, {
      props: { points, depthUnit: 'm', totalEstimated: '73000.00', totalActual: '55641.55' },
    })

    const svg = wrapper.get('[data-testid="depth-cost-chart"] svg')
    const paths = svg.findAll('path.depth-chart__line')
    expect(paths).toHaveLength(2)
    // Both curves start at zero depth / zero cost and end at the last section.
    for (const path of paths) {
      expect(path.attributes('d')).toMatch(/^M92\.00,/)
      expect(path.attributes('d')).toContain('L')
    }
    // One marker per section per series.
    expect(svg.findAll('circle')).toHaveLength(4)
    expect(svg.text()).toContain('1,500 m')
    expect(svg.text()).toContain('3,000 m')

    const table = wrapper.get('.depth-chart__table')
    expect(table.text()).toContain('SEC1 — Surface Section')
    expect(table.text()).toContain('38,000.00')
    expect(table.text()).toContain('55,641.55')
    expect(table.findAll('tbody tr')).toHaveLength(2)
    expect(wrapper.text()).toContain('73,000.00')
  })

  it('flags the section that ran over its estimate', () => {
    const wrapper = mount(DepthCostChart, { props: { points } })
    const variances = wrapper.findAll('tbody td.is-over')
    expect(variances).toHaveLength(1)
    expect(variances[0]?.text()).toBe('13,641.55')
  })

  it('explains itself when the well has no configured sections', () => {
    const wrapper = mount(DepthCostChart, { props: { points: [] } })
    expect(wrapper.find('svg').exists()).toBe(false)
    expect(wrapper.text()).toContain('No hole sections are configured for this well yet')
  })
})
