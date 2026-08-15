<script setup lang="ts">
interface NavigationItem {
  label: string
  icon: string
  enabled: boolean
  to?: string
}

const navigation: NavigationItem[] = [
  { label: 'Well Intake', icon: 'pi pi-clipboard', enabled: true, to: '/requirements' },
  { label: 'Master Data', icon: 'pi pi-book', enabled: true, to: '/master-data/vendors' },
]
</script>

<template>
  <nav class="app-topnav" aria-label="Primary navigation">
    <ul class="app-topnav__list">
      <li v-for="item in navigation" :key="item.label">
        <NuxtLink
          v-if="item.enabled && item.to"
          :to="item.to"
          class="app-topnav__item"
        >
          <i :class="item.icon" aria-hidden="true" />
          <span>{{ item.label }}</span>
        </NuxtLink>
      </li>
    </ul>
  </nav>
</template>
