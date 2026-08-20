/** Grouped navigation across every master-data maintenance page. */
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
    label: 'Configuration',
    items: [
      { key: 'units', label: 'Units of Measure', to: '/master-data/units' },
      { key: 'currencies', label: 'Currencies', to: '/master-data/currencies' },
      { key: 'item-categories', label: 'Item Categories', to: '/master-data/item-categories' },
      { key: 'hole-sections', label: 'Hole Sections', to: '/master-data/hole-sections' },
    ],
  },
  {
    label: 'Partners',
    items: [
      { key: 'vendors', label: 'Vendors', to: '/master-data/vendors' },
      { key: 'service-orders', label: 'Service Orders', to: '/master-data/service-orders' },
      { key: 'purchase-orders', label: 'Purchase Orders', to: '/master-data/purchase-orders' },
    ],
  },
  {
    label: 'Services',
    items: [
      { key: 'services', label: 'Services', to: '/master-data/services' },
      { key: 'service-rates', label: 'Service Rates', to: '/master-data/service-rates' },
    ],
  },
  {
    label: 'Tangibles',
    items: [
      { key: 'tangibles', label: 'Tangibles', to: '/master-data/tangibles' },
    ],
  },
  {
    label: 'Consumables',
    items: [
      { key: 'mud-chemicals', label: 'Mud Chemicals', to: '/master-data/mud-chemicals' },
      { key: 'cement-additives', label: 'Cement Additives', to: '/master-data/cement-additives' },
    ],
  },
  {
    label: 'Pricing',
    items: [{ key: 'item-prices', label: 'Item Prices', to: '/master-data/item-prices' }],
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
