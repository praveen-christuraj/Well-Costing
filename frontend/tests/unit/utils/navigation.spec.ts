import { appNavigation, defaultLandingRoute, enabledNavigation, navigationGroups } from '~/utils/navigation'

describe('application navigation', () => {
  it('only exposes modules that are enabled', () => {
    expect(enabledNavigation.every(item => item.enabled)).toBe(true)
    expect(enabledNavigation.map(item => item.key)).toEqual(['dashboard', 'master-data'])
  })

  it('keeps every module reachable: no module is hidden or disabled', () => {
    expect(appNavigation.every(item => item.enabled)).toBe(true)
    expect(enabledNavigation.length).toBe(appNavigation.length)
  })

  it('offers no removed business module', () => {
    const removedPrefixes = [
      '/afe',
      '/afe-cost-estimates',
      '/daily-cost',
      '/cost-control',
      '/reports',
      '/assurance',
      '/audit',
      '/administration',
      '/help',
    ]
    expect(appNavigation.filter(item => removedPrefixes.some(prefix => item.to.startsWith(prefix))))
      .toEqual([])
  })

  it('lands on the dashboard after sign-in', () => {
    expect(defaultLandingRoute).toBe('/dashboard')
    expect(enabledNavigation.some(item => item.to === defaultLandingRoute)).toBe(true)
  })

  it('groups every enabled module into exactly one sidebar group', () => {
    const grouped = navigationGroups.flatMap(group => group.items.map(item => item.key))
    expect([...grouped].sort()).toEqual([...enabledNavigation.map(item => item.key)].sort())
    expect(new Set(grouped).size).toBe(grouped.length)
  })
})
