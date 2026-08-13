import { mount } from '@vue/test-utils'
import StatusBadge from '~/components/design-system/StatusBadge.vue'

describe('StatusBadge', () => {
  it('renders its label and semantic severity', () => {
    const wrapper = mount(StatusBadge, {
      props: { label: 'Connected', tone: 'success', icon: 'pi pi-check' },
    })

    expect(wrapper.text()).toContain('Connected')
    expect(wrapper.find('.p-tag-success').exists()).toBe(true)
    expect(wrapper.find('.pi-check').exists()).toBe(true)
  })
})
