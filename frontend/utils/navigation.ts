/**
 * Single source of truth for the application's navigation.
 *
 * The sidebar renders these groups in order. `appNavigation` keeps the flat
 * list of top-level modules that other code (and the tests) rely on.
 *
 * The application was restructured down to its shell: authentication plus a
 * Master Data stub. Add modules back here as they are rebuilt.
 */
export interface AppNavigationItem {
  key: string
  label: string
  icon: string
  to: string
  enabled: boolean
}

export interface AppNavigationGroup {
  key: string
  label: string
  items: AppNavigationItem[]
}

export const appNavigation: AppNavigationItem[] = [
  { key: 'dashboard', label: 'Dashboard', icon: 'pi pi-home', to: '/dashboard', enabled: true },
  { key: 'master-data', label: 'Master Data', icon: 'pi pi-book', to: '/master-data', enabled: true },
]

/** Modules the user can actually open today. */
export const enabledNavigation: AppNavigationItem[] = appNavigation.filter(item => item.enabled)

const GROUPS: { key: string, label: string, keys: string[] }[] = [
  { key: 'home', label: 'Home', keys: ['dashboard'] },
  { key: 'foundation', label: 'Master Data', keys: ['master-data'] },
]

/** Sidebar model: the enabled modules arranged into labelled groups. */
export const navigationGroups: AppNavigationGroup[] = GROUPS
  .map(group => ({
    key: group.key,
    label: group.label,
    items: group.keys
      .map(key => enabledNavigation.find(item => item.key === key))
      .filter((item): item is AppNavigationItem => Boolean(item)),
  }))
  .filter(group => group.items.length > 0)

/** Landing route after sign-in: the dashboard is the app's overview. */
export const defaultLandingRoute: string = '/dashboard'
