<script setup lang="ts">
/**
 * Placeholder for Consumables subcategories whose item-entry workflow is
 * scoped for a later release (Cement Additives, Fuel). The subcategory is
 * declared (with its own code) so it appears in the directory and audit trail;
 * rate entry will be configured in a subsequent release.
 */
defineProps<{
  code: string
  name: string
  description?: string
  note?: string
}>()
</script>

<template>
  <div class="placeholder">
    <i class="pi pi-clock placeholder__icon" />
    <h3 class="placeholder__title">{{ name }} <span class="placeholder__code">({{ code }})</span></h3>
    <p class="placeholder__text">
      {{ description || 'This consumable subcategory is registered in the master data directory.' }}
      {{ note || 'Item-level rate entry will be configured in a later release — the same bulk-entry grid, rate revisions, import/export and audit workflow used for Mud Chemicals and Drill Bits will apply.' }}
    </p>
    <p class="placeholder__hint">
      <i class="pi pi-info-circle" />
      Rates for this subcategory are currently tracked through PO/SO orders on the Master Data tab.
    </p>
  </div>
</template>

<style scoped>
.placeholder {
  border: 2px dashed var(--app-border);
  border-radius: 12px;
  padding: 3rem 2rem;
  text-align: center;
  color: var(--app-muted);
  background: var(--app-bg);
}

.placeholder__icon {
  font-size: 2rem;
  color: var(--app-teal);
  opacity: 0.6;
}

.placeholder__title {
  font-size: 1.05rem;
  color: var(--app-ink);
  margin: 0.75rem 0 0.5rem;
}

.placeholder__code {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 0.8rem;
  color: var(--app-muted);
}

.placeholder__text {
  max-width: 46rem;
  margin: 0 auto 0.75rem;
  font-size: 0.85rem;
  line-height: 1.5;
}

.placeholder__hint {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 0.75rem;
  background: var(--app-surface);
  border: 1px solid var(--app-border);
  border-radius: 999px;
  padding: 0.35rem 0.9rem;
  margin: 0;
}
</style>
