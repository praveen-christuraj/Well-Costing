import { mount } from '@vue/test-utils'
import AppSidebar from '~/components/layout/AppSidebar.vue'

describe('AppSidebar', () => {
  function mountNav() {
    return mount(AppSidebar, {
      global: {
        stubs: {
          NuxtLink: { props: ['to'], template: '<a :href="to"><slot /></a>' },
        },
        mocks: {
          $route: { path: '/dashboard' },
        },
      },
    })
  }

  it('renders a link for every enabled module', () => {
    const wrapper = mountNav()

    const links = wrapper.findAll('a')
    expect(links).toHaveLength(13)
    expect(links.map(link => link.attributes('href'))).toEqual([
      '/dashboard',
      '/master-data/primary-categories',
      '/afe',
      '/cost-builder',
      '/daily-cost',
      '/daily-cost/well-activities',
      '/cost-control',
      '/reports',
      '/assurance',
      '/audit',
      '/administration/enterprise',
      '/administration/dropdowns',
      '/help',
    ])
    expect(wrapper.text()).toContain('Dashboard')
    expect(wrapper.text()).toContain('AFE')
    expect(wrapper.text()).toContain('Daily Cost')
    expect(wrapper.text()).toContain('Master Data')
    expect(wrapper.text()).toContain('Help')
  })

  it('groups the modules under section headings', () => {
    const wrapper = mountNav()

    const headings = wrapper.findAll('.layout-menuitem-root-text').map(node => node.text())
    expect(headings).toEqual(['Home', 'Master Data', 'Planning', 'Execution', 'Configuration', 'Support'])
  })

  it('renders no placeholder or hidden links', () => {
    const wrapper = mountNav()

    expect(wrapper.html()).not.toContain('/cost-library/services')
    expect(wrapper.html()).not.toContain('/requirements')
  })
})
