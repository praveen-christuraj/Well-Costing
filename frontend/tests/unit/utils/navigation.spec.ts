import { appNavigation, defaultLandingRoute, enabledNavigation, navigationGroups } from '~/utils/navigation'

describe('application navigation', () => {
  it('only exposes modules that are enabled', () => {
    expect(enabledNavigation.every(item => item.enabled)).toBe(true)
    expect(enabledNavigation.map(item => item.key)).toEqual([
      'dashboard',
      'master-data',
      'afe',
      'cost-builder',
      'daily-cost',
      'well-activities',
      'cost-control',
      'reports',
      'assurance',
      'audit',
      'administration',
      'help',
    ])
  })

  it('keeps every module reachable: no module is hidden or disabled', () => {
    expect(appNavigation.every(item => item.enabled)).toBe(true)
    expect(enabledNavigation.length).toBe(appNavigation.length)
  })

  it('no longer offers a separate well-requirement module', () => {
    expect(appNavigation.some(item => item.to.startsWith('/requirements'))).toBe(false)
    expect(appNavigation.find(item => item.key === 'afe')?.to).toBe('/afe')
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
