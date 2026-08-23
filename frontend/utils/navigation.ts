/**
 * Single source of truth for the application's navigation.
 *
 * The sidebar renders these groups in order. `appNavigation` keeps the flat
 * list of top-level modules that other code (and the tests) rely on.
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
  { key: 'master-data', label: 'Master Data', icon: 'pi pi-book', to: '/master-data/primary-categories', enabled: true },
  { key: 'afe', label: 'AFE', icon: 'pi pi-clipboard', to: '/afe', enabled: true },
  { key: 'cost-builder', label: 'Cost Builder', icon: 'pi pi-calculator', to: '/cost-builder', enabled: true },
  { key: 'daily-cost', label: 'Daily Cost', icon: 'pi pi-calendar-plus', to: '/daily-cost', enabled: true },
  { key: 'well-activities', label: 'Well Activities', icon: 'pi pi-list-check', to: '/daily-cost/well-activities', enabled: true },
  { key: 'cost-control', label: 'Cost Control', icon: 'pi pi-arrow-right-arrow-left', to: '/cost-control', enabled: true },
  { key: 'reports', label: 'Reports', icon: 'pi pi-chart-bar', to: '/reports', enabled: true },
  { key: 'assurance', label: 'Assurance', icon: 'pi pi-shield', to: '/assurance', enabled: true },
  { key: 'audit', label: 'Audit Log', icon: 'pi pi-history', to: '/audit', enabled: true },
  { key: 'administration', label: 'Administration', icon: 'pi pi-cog', to: '/administration/enterprise', enabled: true },
  { key: 'dropdown-sources', label: 'Dropdown Sources', icon: 'pi pi-sliders-h', to: '/administration/dropdowns', enabled: true },
  { key: 'help', label: 'Help', icon: 'pi pi-question-circle', to: '/help', enabled: true },
]

/** Modules the user can actually open today. */
export const enabledNavigation: AppNavigationItem[] = appNavigation.filter(item => item.enabled)

const GROUPS: { key: string, label: string, keys: string[] }[] = [
  { key: 'home', label: 'Home', keys: ['dashboard'] },
  { key: 'foundation', label: 'Master Data', keys: ['master-data'] },
  { key: 'planning', label: 'Planning', keys: ['afe', 'cost-builder'] },
  { key: 'execution', label: 'Execution', keys: ['daily-cost', 'well-activities', 'cost-control', 'reports', 'assurance', 'audit'] },
  { key: 'configuration', label: 'Configuration', keys: ['administration', 'dropdown-sources'] },
  { key: 'support', label: 'Support', keys: ['help'] },
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
