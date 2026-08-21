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
    expect(links).toHaveLength(8)
    expect(links.map(link => link.attributes('href'))).toEqual([
      '/dashboard',
      '/afe',
      '/cost-builder',
      '/cost-control',
      '/reports',
      '/assurance',
      '/master-data/vendors',
      '/administration/enterprise',
    ])
    expect(wrapper.text()).toContain('Dashboard')
    expect(wrapper.text()).toContain('AFE')
    expect(wrapper.text()).toContain('Master Data')
  })

  it('groups the modules under section headings', () => {
    const wrapper = mountNav()

    const headings = wrapper.findAll('.layout-menuitem-root-text').map(node => node.text())
    expect(headings).toEqual(['Home', 'Planning', 'Execution', 'Configuration'])
  })

  it('renders no placeholder or hidden links', () => {
    const wrapper = mountNav()

    expect(wrapper.html()).not.toContain('/cost-library/services')
    expect(wrapper.html()).not.toContain('/requirements')
  })
})
