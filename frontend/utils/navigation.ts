/**
 * Single source of truth for the application's top-level modules.
 *
 * Only modules flagged `enabled` are reachable from the navigation bar, and the
 * first enabled module is where the application lands after sign-in. Keeping the
 * flag here means enabling a future module is a one-line change that updates the
 * navigation bar, the post-login redirect, and the `/` landing route together.
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

/** Landing route: the first enabled module, never a locked or unreleased one. */
export const defaultLandingRoute: string = enabledNavigation[0]?.to ?? '/login'
