import { computed, reactive } from 'vue'
import type { ComputedRef } from 'vue'

/**
 * Shell state shared by the topbar, sidebar, and theme configurator.
 *
 * Modelled on the PrimeVue Sakai layout: a static or overlay menu, a dark-mode
 * toggle driven by the `.app-dark` class the PrimeVue theme is configured with,
 * and a preset/palette selection the user can change at runtime. The choice is
 * persisted so it survives a reload.
 */

export type MenuMode = 'static' | 'overlay'

export interface LayoutConfig {
  preset: string
  primary: string
  surface: string | null
  darkTheme: boolean
  menuMode: MenuMode
}

export interface LayoutState {
  staticMenuInactive: boolean
  overlayMenuActive: boolean
  mobileMenuActive: boolean
  configSidebarVisible: boolean
  menuHoverActive: boolean
  activePath: string | null
}

const STORAGE_KEY = 'drilling-costing.layout'

const layoutConfig = reactive<LayoutConfig>({
  preset: 'Aura',
  primary: 'teal',
  surface: null,
  darkTheme: false,
  menuMode: 'static',
})

const layoutState = reactive<LayoutState>({
  staticMenuInactive: false,
  overlayMenuActive: false,
  mobileMenuActive: false,
  configSidebarVisible: false,
  menuHoverActive: false,
  activePath: null,
})

/** Desktop breakpoint; below it the menu behaves as a mobile drawer. */
export function isDesktop(): boolean {
  return typeof window === 'undefined' || window.innerWidth > 991
}

function persist(): void {
  if (typeof window === 'undefined') return
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(layoutConfig))
  }
  catch {
    // A full or blocked storage quota must never break the shell.
  }
}

/** Read the saved preferences, if any, and apply the dark-mode class. */
export function restoreLayoutConfig(): LayoutConfig {
  if (typeof window === 'undefined') return layoutConfig
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY)
    if (raw) Object.assign(layoutConfig, JSON.parse(raw) as Partial<LayoutConfig>)
  }
  catch {
    // Ignore unreadable or corrupt preferences and keep the defaults.
  }
  document.documentElement.classList.toggle('app-dark', layoutConfig.darkTheme)
  return layoutConfig
}

export function useLayout() {
  function executeDarkModeToggle(): void {
    layoutConfig.darkTheme = !layoutConfig.darkTheme
    document.documentElement.classList.toggle('app-dark', layoutConfig.darkTheme)
    persist()
  }

  function toggleDarkMode(): void {
    const startViewTransition = (document as Document & {
      startViewTransition?: (callback: () => void) => void
    }).startViewTransition
    if (typeof startViewTransition !== 'function') {
      executeDarkModeToggle()
      return
    }
    startViewTransition.call(document, executeDarkModeToggle)
  }

  function toggleMenu(): void {
    if (!isDesktop()) {
      layoutState.mobileMenuActive = !layoutState.mobileMenuActive
      return
    }
    if (layoutConfig.menuMode === 'static') {
      layoutState.staticMenuInactive = !layoutState.staticMenuInactive
    }
    else {
      layoutState.overlayMenuActive = !layoutState.overlayMenuActive
    }
  }

  function hideMobileMenu(): void {
    layoutState.mobileMenuActive = false
    layoutState.overlayMenuActive = false
  }

  function toggleConfigurator(): void {
    layoutState.configSidebarVisible = !layoutState.configSidebarVisible
  }

  function changeMenuMode(mode: MenuMode): void {
    layoutConfig.menuMode = mode
    layoutState.staticMenuInactive = false
    layoutState.mobileMenuActive = false
    layoutState.overlayMenuActive = false
    layoutState.menuHoverActive = false
    persist()
  }

  function setPreset(preset: string): void {
    layoutConfig.preset = preset
    persist()
  }

  function setPrimary(color: string): void {
    layoutConfig.primary = color
    persist()
  }

  function setSurface(surface: string | null): void {
    layoutConfig.surface = surface
    persist()
  }

  const isDarkTheme: ComputedRef<boolean> = computed(() => layoutConfig.darkTheme)
  const hasOpenOverlay: ComputedRef<boolean> = computed(
    () => layoutState.overlayMenuActive || layoutState.mobileMenuActive,
  )

  return {
    layoutConfig,
    layoutState,
    isDarkTheme,
    hasOpenOverlay,
    isDesktop,
    toggleDarkMode,
    toggleMenu,
    hideMobileMenu,
    toggleConfigurator,
    changeMenuMode,
    setPreset,
    setPrimary,
    setSurface,
  }
}
