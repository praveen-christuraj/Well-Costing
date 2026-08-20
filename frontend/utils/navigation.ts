/**
 * Single source of truth for the application's top-level modules.
 *
 * Every module is enabled and reachable from the navigation bar. The post-login
 * landing stays on Master Data (the established entry point the full-stack
 * regression test asserts); Well Intake, the AFE builder, Cost Control,
 * Reports, and Assurance are one click away.
 */
export interface AppNavigationItem {
  key: string
  label: string
  icon: string
  to: string
  enabled: boolean
}

export const appNavigation: AppNavigationItem[] = [
  { key: 'requirements', label: 'Well Intake', icon: 'pi pi-clipboard', to: '/requirements', enabled: true },
  { key: 'cost-builder', label: 'Cost Builder (AFE)', icon: 'pi pi-calculator', to: '/cost-builder', enabled: true },
  { key: 'master-data', label: 'Master Data', icon: 'pi pi-book', to: '/master-data/vendors', enabled: true },
  { key: 'cost-control', label: 'Cost Control', icon: 'pi pi-arrow-right-arrow-left', to: '/cost-control', enabled: true },
  { key: 'reports', label: 'Reports', icon: 'pi pi-chart-bar', to: '/reports', enabled: true },
  { key: 'assurance', label: 'Assurance', icon: 'pi pi-shield', to: '/assurance', enabled: true },
]

/** Modules the user can actually open today. */
export const enabledNavigation: AppNavigationItem[] = appNavigation.filter(item => item.enabled)

/**
 * Landing route after sign-in. Kept on Master Data for continuity with the
 * established app flow and the full-stack regression suite.
 */
export const defaultLandingRoute: string = '/master-data/vendors'

