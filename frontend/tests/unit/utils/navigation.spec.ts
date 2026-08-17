import { appNavigation, defaultLandingRoute, enabledNavigation } from '~/utils/navigation'

describe('application navigation', () => {
  it('only exposes modules that are enabled', () => {
    expect(enabledNavigation.every(item => item.enabled)).toBe(true)
    expect(enabledNavigation.map(item => item.key)).toEqual(['master-data'])
  })

  it('keeps unreleased modules out of the navigation bar', () => {
    const wellIntake = appNavigation.find(item => item.key === 'requirements')

    expect(wellIntake?.enabled).toBe(false)
    expect(enabledNavigation).not.toContain(wellIntake)
  })

  it('lands on the first enabled module, never a locked one', () => {
    expect(defaultLandingRoute).toBe('/master-data/vendors')
    expect(defaultLandingRoute.startsWith('/cost-library')).toBe(false)
    expect(enabledNavigation.some(item => item.to === defaultLandingRoute)).toBe(true)
  })
})
