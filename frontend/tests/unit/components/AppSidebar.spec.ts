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
    expect(links).toHaveLength(1)
    expect(links[0]?.attributes('href')).toBe('/master-data/vendors')
    expect(wrapper.text()).toContain('Master Data')
  })

  it('does not render modules that are not enabled yet', () => {
    const wrapper = mountNav()

    expect(wrapper.text()).not.toContain('Well Intake')
    expect(wrapper.html()).not.toContain('/requirements')
    expect(wrapper.html()).not.toContain('/cost-library')
  })
})
