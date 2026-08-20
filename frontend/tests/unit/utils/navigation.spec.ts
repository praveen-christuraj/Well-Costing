import { appNavigation, defaultLandingRoute, enabledNavigation } from '~/utils/navigation'

describe('application navigation', () => {
  it('only exposes modules that are enabled', () => {
    expect(enabledNavigation.every(item => item.enabled)).toBe(true)
    expect(enabledNavigation.map(item => item.key)).toEqual([
      'requirements',
      'cost-builder',
      'master-data',
      'cost-control',
      'reports',
      'assurance',
    ])
  })

  it('keeps every module reachable: no module is hidden or disabled', () => {
    expect(appNavigation.every(item => item.enabled)).toBe(true)
    expect(enabledNavigation.length).toBe(appNavigation.length)
  })

  it('lands on the first enabled module, never a locked one', () => {
    expect(defaultLandingRoute).toBe('/requirements')
    expect(enabledNavigation.some(item => item.to === defaultLandingRoute)).toBe(true)
  })
})
