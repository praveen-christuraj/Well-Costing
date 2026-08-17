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
  { key: 'requirements', label: 'Well Intake', icon: 'pi pi-clipboard', to: '/requirements', enabled: false },
  { key: 'master-data', label: 'Master Data', icon: 'pi pi-book', to: '/master-data/vendors', enabled: true },
]

/** Modules the user can actually open today. */
export const enabledNavigation: AppNavigationItem[] = appNavigation.filter(item => item.enabled)

/** Landing route: the first enabled module, never a locked or unreleased one. */
export const defaultLandingRoute: string = enabledNavigation[0]?.to ?? '/login'
