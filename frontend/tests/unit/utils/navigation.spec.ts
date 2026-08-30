import { appNavigation, defaultLandingRoute, enabledNavigation, navigationGroups } from '~/utils/navigation'

describe('application navigation', () => {
  it('only exposes modules that are enabled', () => {
    expect(enabledNavigation.every(item => item.enabled)).toBe(true)
    expect(enabledNavigation.map(item => item.key)).toEqual([
      'dashboard',
      'rig-well-management',
      'well-sub-activities',
      'afe-management',
      'daily-costs',
      'cost-analytics',
      'cost-reports',
      'master-data',
      'audit-logs',
    ])
  })

  it('keeps every module reachable: no module is hidden or disabled', () => {
    expect(appNavigation.every(item => item.enabled)).toBe(true)
    expect(enabledNavigation.length).toBe(appNavigation.length)
  })

  it('offers no removed business module', () => {
    // '/afe-management' is the rebuilt AFE module and '/daily-costs',
    // '/cost-analytics' and '/cost-reports' are the rebuilt costing modules;
    // only the removed modules' own paths stay on the forbidden list.
    const removedPrefixes = [
      '/afe-cost-estimates',
      '/cost-control',
      '/reports',
      '/assurance',
      '/administration',
      '/help',
    ]
    // audit-logs is valid, not removed; only generic /audit without -logs should be considered removed
    const removedAuditExact = ['/audit', '/audit/', '/afe']
    const filtered = appNavigation.filter(item => {
      if (removedPrefixes.some(prefix => item.to.startsWith(prefix))) return true
      if (removedAuditExact.includes(item.to)) return true
      return false
    })
    expect(filtered).toEqual([])
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
