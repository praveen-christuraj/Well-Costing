<script setup lang="ts">
/**
 * Application shell: sidebar + topbar, modelled on the PrimeVue Sakai layout.
 *
 * The wrapper classes drive the CSS — `layout-static` keeps the sidebar docked,
 * `layout-overlay` floats it over the content, and the mobile variants slide it
 * in over a mask.
 */
import { computed, onMounted } from 'vue'
import AppHeader from '~/components/layout/AppHeader.vue'
import AppSidebar from '~/components/layout/AppSidebar.vue'
import { restoreLayoutConfig, useLayout } from '~/composables/useLayout'

const { layoutConfig, layoutState, hideMobileMenu } = useLayout()

const containerClass = computed(() => ({
  'layout-static': layoutConfig.menuMode === 'static',
  'layout-overlay': layoutConfig.menuMode === 'overlay',
  'layout-static-inactive': layoutState.staticMenuInactive,
  'layout-overlay-active': layoutState.overlayMenuActive,
  'layout-mobile-active': layoutState.mobileMenuActive,
}))

onMounted(() => restoreLayoutConfig())
</script>

<template>
  <div class="layout-wrapper" :class="containerClass">
    <AppHeader />
    <AppSidebar />
    <div class="layout-main-container">
      <main class="layout-main">
        <slot />
      </main>
    </div>
    <div class="layout-mask" @click="hideMobileMenu" />
  </div>
</template>
