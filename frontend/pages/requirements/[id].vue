<script setup lang="ts">
import PageHeader from '~/components/design-system/PageHeader.vue'
import Message from 'primevue/message'

definePageMeta({ middleware: 'auth' })
</script>

<template>
  <div class="library-page">
    <PageHeader
      title="Requirement Detail"
      description="View and manage requirement line items."
    />
    <div class="feature-disabled-card">
      <i class="pi pi-info-circle" style="font-size: 3rem; color: var(--p-primary-color)" />
      <h2>Well Intake — Coming Soon</h2>
      <Message severity="warn" :closable="false">
        <strong>This feature is not yet enabled.</strong>
        The well intake module will be configured and activated in a future release.
        Use <strong>Master Data</strong> to manage vendors, services, tangibles,
        consumables, pricing, and configuration in the meantime.
      </Message>
      <NuxtLink to="/master-data/vendors" class="p-button p-button-outlined" style="margin-top: 1rem; display: inline-flex; align-items: center; gap: 0.5rem;">
        <i class="pi pi-arrow-right" />
        Go to Master Data
      </NuxtLink>
    </div>
  </div>
</template>

<style scoped>
.feature-disabled-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 1rem;
  padding: 3rem 2rem;
  text-align: center;
  max-width: 600px;
  margin: 3rem auto;
  background: var(--p-surface-50);
  border-radius: var(--p-border-radius-lg);
  box-shadow: var(--p-card-shadow);
}
.feature-disabled-card h2 {
  margin: 0;
  color: var(--p-text-color);
}
</style>