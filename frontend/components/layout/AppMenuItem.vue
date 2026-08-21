<script setup lang="ts">
/** One sidebar entry. Highlights the route it points at and closes the drawer. */
import { useLayout } from '~/composables/useLayout'
import type { AppNavigationItem } from '~/utils/navigation'

defineProps<{ item: AppNavigationItem }>()

const { layoutState, isDesktop } = useLayout()

function onNavigate(): void {
  if (!isDesktop()) layoutState.mobileMenuActive = false
  layoutState.overlayMenuActive = false
}
</script>

<template>
  <li>
    <NuxtLink :to="item.to" class="layout-menuitem" active-class="active-route" @click="onNavigate">
      <i :class="item.icon" class="layout-menuitem-icon" aria-hidden="true" />
      <span class="layout-menuitem-text">{{ item.label }}</span>
    </NuxtLink>
  </li>
</template>
