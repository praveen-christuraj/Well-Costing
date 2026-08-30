/**
 * Single source of truth for the application's navigation.
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
  { key: 'rig-well-management', label: 'Rig & Well Management', icon: 'pi pi-sitemap', to: '/rig-well-management', enabled: true },
  { key: 'well-sub-activities', label: 'Well Sub Activities', icon: 'pi pi-list-check', to: '/well-sub-activities', enabled: true },
  { key: 'afe-management', label: 'AFE Management', icon: 'pi pi-wallet', to: '/afe-management', enabled: true },
  { key: 'daily-costs', label: 'Daily Costs', icon: 'pi pi-calendar-clock', to: '/daily-costs', enabled: true },
  { key: 'cost-analytics', label: 'Cost Analytics', icon: 'pi pi-chart-line', to: '/cost-analytics', enabled: true },
  { key: 'cost-reports', label: 'Cost Reports', icon: 'pi pi-file-export', to: '/cost-reports', enabled: true },
  { key: 'master-data', label: 'Master Data', icon: 'pi pi-book', to: '/master-data', enabled: true },
  { key: 'audit-logs', label: 'Audit Log', icon: 'pi pi-history', to: '/audit-logs', enabled: true },
]

/** Modules the user can actually open today. */
export const enabledNavigation: AppNavigationItem[] = appNavigation.filter(item => item.enabled)

const GROUPS: { key: string, label: string, keys: string[] }[] = [
  { key: 'home', label: 'Home', keys: ['dashboard'] },
  { key: 'wells', label: 'Rig & Well', keys: ['rig-well-management', 'well-sub-activities'] },
  { key: 'costing', label: 'Costing', keys: ['afe-management', 'daily-costs', 'cost-analytics', 'cost-reports'] },
  { key: 'foundation', label: 'Master Data & Auditing', keys: ['master-data', 'audit-logs'] },
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
