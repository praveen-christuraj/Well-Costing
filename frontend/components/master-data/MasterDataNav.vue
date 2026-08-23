/**
 * Grouped navigation across the master-data maintenance pages.
 *
 * The classification (Primary → Secondary → Tertiary) leads, because every
 * other page files its records against it. Item categories, item sub
 * categories, and the standalone Services register are gone: they were
 * parallel classifications of the same thing.
 */
<script setup lang="ts">
interface NavItem {
  key: string
  label: string
  to: string
}

interface NavGroup {
  label: string
  items: NavItem[]
}

defineProps<{ active: string }>()

const groups: NavGroup[] = [
  {
    label: 'Classification',
    items: [
      { key: 'primary-categories', label: 'Primary Categories', to: '/master-data/primary-categories' },
      { key: 'secondary-categories', label: 'Secondary Categories', to: '/master-data/secondary-categories' },
      { key: 'tertiary-categories', label: 'Tertiary Categories', to: '/master-data/tertiary-categories' },
    ],
  },
  {
    label: 'Configuration',
    items: [
      { key: 'units', label: 'Units of Measure', to: '/master-data/units' },
      { key: 'currencies', label: 'Currencies', to: '/master-data/currencies' },
      { key: 'hole-sections', label: 'Hole Sections', to: '/master-data/hole-sections' },
      { key: 'phases', label: 'Phases', to: '/master-data/phases' },
      { key: 'activities', label: 'Activities', to: '/master-data/activities' },
    ],
  },
  {
    label: 'Costing',
    items: [
      { key: 'cost-categories', label: 'Cost Categories', to: '/master-data/cost-categories' },
      { key: 'cost-codes', label: 'Cost Codes', to: '/master-data/cost-codes' },
    ],
  },
  {
    label: 'Catalogue',
    items: [
      { key: 'catalogue-items', label: 'All Catalogue Items', to: '/master-data/catalogue-items' },
      { key: 'tangibles', label: 'Tangibles', to: '/master-data/tangibles' },
      { key: 'mud-chemicals', label: 'Mud Chemicals', to: '/master-data/mud-chemicals' },
      { key: 'cement-additives', label: 'Cement Additives', to: '/master-data/cement-additives' },
    ],
  },
  {
    label: 'Partners & References',
    items: [
      { key: 'vendors', label: 'Vendors', to: '/master-data/vendors' },
      { key: 'service-orders', label: 'Service Orders', to: '/master-data/service-orders' },
      { key: 'purchase-orders', label: 'Purchase Orders', to: '/master-data/purchase-orders' },
    ],
  },
  {
    label: 'Rates',
    items: [
      { key: 'item-prices', label: 'Tangible Rates', to: '/master-data/item-prices' },
      { key: 'rate-revisions', label: 'Rate Revisions', to: '/master-data/rate-revisions' },
    ],
  },
]
</script>

<template>
  <nav class="md-nav" aria-label="Master data sections">
    <div v-for="group in groups" :key="group.label" class="md-nav__group">
      <span class="md-nav__label">{{ group.label }}</span>
      <NuxtLink
        v-for="item in group.items"
        :key="item.key"
        :to="item.to"
        :class="['md-nav__item', { 'md-nav__item--active': active === item.key }]"
      >
        {{ item.label }}
      </NuxtLink>
    </div>
  </nav>
</template>
