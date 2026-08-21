<script setup lang="ts">
/**
 * Sidebar navigation, modelled on the PrimeVue Sakai shell.
 *
 * An open overlay or mobile menu closes when the user clicks away from it; the
 * menu items close it themselves when a destination is chosen.
 */
import { onBeforeUnmount, useTemplateRef, watch } from 'vue'
import AppMenu from '~/components/layout/AppMenu.vue'
import { useLayout } from '~/composables/useLayout'

const { layoutState, hasOpenOverlay } = useLayout()
const sidebarRef = useTemplateRef<HTMLElement>('sidebarRef')
let outsideClickListener: ((event: MouseEvent) => void) | null = null

function isOutsideClicked(event: MouseEvent): boolean {
  const sidebar = sidebarRef.value
  const toggle = document.querySelector('.layout-menu-button')
  const target = event.target as Node | null
  if (!sidebar || !target) return false
  return !(sidebar.contains(target) || toggle?.contains(target))
}

function bindOutsideClickListener(): void {
  if (outsideClickListener) return
  outsideClickListener = (event: MouseEvent) => {
    if (!isOutsideClicked(event)) return
    layoutState.overlayMenuActive = false
    layoutState.mobileMenuActive = false
  }
  document.addEventListener('click', outsideClickListener)
}

function unbindOutsideClickListener(): void {
  if (!outsideClickListener) return
  document.removeEventListener('click', outsideClickListener)
  outsideClickListener = null
}

watch(hasOpenOverlay, (open) => {
  if (open) bindOutsideClickListener()
  else unbindOutsideClickListener()
})

onBeforeUnmount(unbindOutsideClickListener)
</script>

<template>
  <aside ref="sidebarRef" class="layout-sidebar" aria-label="Primary navigation">
    <AppMenu />
  </aside>
</template>
