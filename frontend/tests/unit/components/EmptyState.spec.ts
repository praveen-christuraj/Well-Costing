import { mount } from '@vue/test-utils'
import EmptyState from '~/components/design-system/EmptyState.vue'

describe('EmptyState', () => {
  it('renders guidance and an optional action', () => {
    const wrapper = mount(EmptyState, {
      props: {
        title: 'No estimates',
        description: 'Create an estimate after requirements are approved.',
      },
      slots: { action: '<button>Start</button>' },
    })

    expect(wrapper.get('h3').text()).toBe('No estimates')
    expect(wrapper.text()).toContain('Create an estimate')
    expect(wrapper.get('button').text()).toBe('Start')
  })
})
