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
    expect(links).toHaveLength(3)
    expect(links.map(link => link.attributes('href'))).toEqual(['/dashboard', '/master-data', '/audit-logs'])
    expect(wrapper.text()).toContain('Dashboard')
    expect(wrapper.text()).toContain('Master Data')
    expect(wrapper.text()).toContain('Audit Log')
  })

  it('groups the modules under section headings', () => {
    const wrapper = mountNav()

    const headings = wrapper.findAll('.layout-menuitem-root-text').map(node => node.text())
    expect(headings).toEqual(['Home', 'Master Data & Auditing'])
  })

  it('renders no link to a removed business module', () => {
    const wrapper = mountNav()

    for (const removed of ['/afe', '/daily-cost', '/cost-control', '/reports', '/assurance', '/administration', '/help']) {
      expect(wrapper.html()).not.toContain(`href="${removed}`)
    }
    const html = wrapper.html()
    expect(html).toContain('href="/audit-logs"')
  })
})
