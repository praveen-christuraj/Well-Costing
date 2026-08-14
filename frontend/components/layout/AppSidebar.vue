<script setup lang="ts">
interface NavigationItem {
  label: string
  icon: string
  enabled: boolean
  to?: string
  phase?: number
}

const navigation: NavigationItem[] = [
  { label: 'Dashboard', icon: 'pi pi-chart-bar', enabled: true, to: '/' },
  { label: 'Requirements', icon: 'pi pi-clipboard', enabled: true, to: '/requirements' },
  { label: 'Master Data', icon: 'pi pi-book', enabled: true, to: '/master-data/vendors' },
  { label: 'Cost Library', icon: 'pi pi-database', enabled: true, to: '/cost-library/services' },
  { label: 'Cost Builder', icon: 'pi pi-table', enabled: true, to: '/cost-builder' },
  { label: 'Estimates', icon: 'pi pi-calculator', enabled: false, phase: 5 },
  { label: 'AFE', icon: 'pi pi-file-check', enabled: false, phase: 7 },
  { label: 'Cost Control', icon: 'pi pi-receipt', enabled: true, to: '/cost-control' },
  { label: 'Reports', icon: 'pi pi-chart-pie', enabled: true, to: '/reports' },
  { label: 'Enterprise Setup', icon: 'pi pi-sitemap', enabled: true, to: '/administration/enterprise' },
  { label: 'Assurance', icon: 'pi pi-shield', enabled: true, to: '/assurance' },
]
</script>

<template>
  <aside class="app-sidebar" aria-label="Primary navigation">
    <div class="app-sidebar__section-label">
      Workspace
    </div>
    <nav>
      <ul class="app-nav">
        <li v-for="item in navigation" :key="item.label">
          <NuxtLink
            v-if="item.enabled && item.to"
            :to="item.to"
            class="app-nav__item app-nav__item--active"
          >
            <i :class="item.icon" aria-hidden="true" />
            <span>{{ item.label }}</span>
          </NuxtLink>
          <div v-else class="app-nav__item app-nav__item--disabled" aria-disabled="true">
            <i :class="item.icon" aria-hidden="true" />
            <span>{{ item.label }}</span>
            <small v-if="item.phase">P{{ item.phase }}</small>
          </div>
        </li>
      </ul>
    </nav>
    <div class="app-sidebar__footer">
      <i class="pi pi-lock" aria-hidden="true" />
      <div>
        <strong>Audit-ready foundation</strong>
        <span>Business calculations are intentionally deferred.</span>
      </div>
    </div>
  </aside>
</template>
