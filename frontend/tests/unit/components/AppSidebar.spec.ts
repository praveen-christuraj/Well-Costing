import { mount } from '@vue/test-utils'
import AppSidebar from '~/components/layout/AppSidebar.vue'

describe('AppSidebar', () => {
  function mountNav() {
    return mount(AppSidebar, {
      global: {
        stubs: {
          NuxtLink: { props: ['to'], template: '<a :href="to"><slot /></a>' },
        },
      },
    })
  }

  it('renders a link for every enabled module', () => {
    const wrapper = mountNav()

    const links = wrapper.findAll('a')
    expect(links).toHaveLength(6)
    expect(links.map(link => link.attributes('href'))).toEqual([
      '/requirements',
      '/cost-builder',
      '/master-data/vendors',
      '/cost-control',
      '/reports',
      '/assurance',
    ])
    expect(wrapper.text()).toContain('Well Intake')
    expect(wrapper.text()).toContain('Cost Builder (AFE)')
    expect(wrapper.text()).toContain('Master Data')
  })

  it('renders no placeholder or hidden links', () => {
    const wrapper = mountNav()

    expect(wrapper.html()).not.toContain('/cost-library/services')
  })
})
