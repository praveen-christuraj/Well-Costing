<script setup lang="ts">
/** The sidebar menu model: navigation groups from `utils/navigation`. */
import AppMenuItem from '~/components/layout/AppMenuItem.vue'
import { navigationGroups } from '~/utils/navigation'
</script>

<template>
  <ul class="layout-menu">
    <template v-for="group in navigationGroups" :key="group.key">
      <li class="layout-root-menuitem">
        <div class="layout-menuitem-root-text">{{ group.label }}</div>
        <ul class="layout-submenu">
          <AppMenuItem v-for="item in group.items" :key="item.key" :item="item" />
        </ul>
      </li>
    </template>
  </ul>
</template>
