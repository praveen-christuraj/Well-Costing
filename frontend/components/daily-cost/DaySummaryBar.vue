<script setup lang="ts">
/**
 * The day's totals and its lifecycle.
 *
 * The totals are the server's: the page posts the rows to `/daily-cost/preview`
 * (debounced) and shows exactly what the pricing engine returned, so what the
 * user sees is what gets saved. Save keeps the day a draft; Submit closes it
 * for the daily cost report, and a submitted day can be reopened as a draft.
 *
 * Reconciliation status is shown read-only: the reconciliation run that will
 * sit between the AFE and the actual cost marks the day reconciled later.
 */
import { computed } from 'vue'
import Button from 'primevue/button'
import { formatMoney } from '~/utils/dailyCost'
import type { DailyStatus, ReconciliationStatus, SummaryRow } from '~/types/dailyCost'

const props = withDefaults(
  defineProps<{
    summary: SummaryRow[]
    grandTotal: string
    status: DailyStatus | null
    warnings: string[]
    reconciliationStatus?: ReconciliationStatus
    /** AFE estimated total for the well, to show what the day leaves behind. */
    afeEstimated?: string | null
    actualToDate?: string | null
    saving?: boolean
    dirty?: boolean
    disabled?: boolean
  }>(),
  {
    reconciliationStatus: 'pending',
    afeEstimated: null,
    actualToDate: null,
    saving: false,
    dirty: false,
    disabled: false,
  },
)

const emit = defineEmits<{
  (event: 'save' | 'submit' | 'reopen'): void
}>()

const groups = computed(() => props.summary.filter(row => row.group !== 'Total'))
const total = computed(() => props.summary.find(row => row.group === 'Total'))

const isDraft = computed(() => props.status === 'draft')
const isSubmitted = computed(() => props.status === 'submitted')

const remaining = computed(() => {
  if (props.afeEstimated == null) return null
  const estimated = Number(props.afeEstimated)
  const actual = Number(props.actualToDate ?? 0)
  if (!Number.isFinite(estimated)) return null
  return formatMoney(estimated - actual)
})
</script>

<template>
  <section class="daybar" data-testid="daily-cost-summary">
    <div class="daybar__totals">
      <div v-for="row in groups" :key="row.group" class="daybar__group">
        <span class="daybar__label">{{ row.group }}</span>
        <span class="daybar__value mono">{{ formatMoney(row.amount) }}</span>
      </div>
      <div class="daybar__group daybar__group--total">
        <span class="daybar__label">Total Cost for the Day</span>
        <span class="daybar__value mono">{{ formatMoney(total?.amount ?? grandTotal) }}</span>
      </div>
      <div v-if="remaining != null" class="daybar__group daybar__group--context">
        <span class="daybar__label">AFE budget left (well to date)</span>
        <span class="daybar__value mono">{{ remaining }}</span>
      </div>
    </div>

    <div class="daybar__side">
      <div class="daybar__flags">
        <span class="daybar__flag" :class="isSubmitted ? 'daybar__flag--done' : 'daybar__flag--draft'">
          <i :class="isSubmitted ? 'pi pi-check-circle' : 'pi pi-pencil'" />
          {{ isSubmitted ? 'Submitted' : 'Draft' }}
        </span>
        <span
          class="daybar__flag"
          :class="reconciliationStatus === 'reconciled' ? 'daybar__flag--done' : 'daybar__flag--muted'"
        >
          <i :class="reconciliationStatus === 'reconciled' ? 'pi pi-lock' : 'pi pi-sync'" />
          {{ reconciliationStatus === 'reconciled' ? 'Reconciled' : 'Reconciliation pending' }}
        </span>
        <span v-if="dirty" class="daybar__flag daybar__flag--dirty">
          <i class="pi pi-circle-fill" /> Unsaved changes
        </span>
      </div>

      <div class="daybar__actions">
        <Button
          v-if="isDraft || status == null"
          label="Save draft"
          icon="pi pi-save"
          size="small"
          severity="secondary"
          outlined
          :loading="saving"
          :disabled="disabled"
          @click="emit('save')"
        />
        <Button
          v-if="isDraft || status == null"
          label="Submit"
          icon="pi pi-check"
          size="small"
          severity="success"
          :loading="saving"
          :disabled="disabled"
          @click="emit('submit')"
        />
        <Button
          v-if="isSubmitted"
          label="Reopen as draft"
          icon="pi pi-undo"
          size="small"
          severity="warn"
          outlined
          :loading="saving"
          :disabled="disabled"
          @click="emit('reopen')"
        />
      </div>
    </div>

    <ul v-if="warnings.length" class="daybar__warnings" data-testid="daily-cost-warnings">
      <li v-for="warning in warnings" :key="warning">
        <i class="pi pi-info-circle" /> {{ warning }}
      </li>
    </ul>
  </section>
</template>

<style scoped>
  .daybar {
    display: grid;
    gap: 8px;
    padding: 10px 12px;
    border: 1px solid var(--app-border, #e3e7ee);
    border-radius: 10px;
    background: var(--app-surface-muted, #f9fbfd);
  }

  .daybar__totals {
    display: flex;
    flex-wrap: wrap;
    gap: 18px;
    align-items: flex-end;
  }

  .daybar__group {
    display: grid;
    gap: 1px;
    min-width: 118px;
  }

  .daybar__label {
    font-size: 0.66rem;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: var(--app-text-muted, #6b7480);
  }

  .daybar__value {
    font-size: 0.95rem;
    font-weight: 650;
    font-variant-numeric: tabular-nums;
  }

  .mono {
    font-family: var(--app-font-mono, ui-monospace, monospace);
  }

  .daybar__group--total {
    border-left: 2px solid var(--app-border-strong, #c8cfda);
    padding-left: 14px;
  }

  .daybar__group--total .daybar__value {
    font-size: 1.15rem;
  }

  .daybar__group--context .daybar__value {
    font-size: 0.85rem;
    color: var(--app-text-muted, #4b5563);
  }

  .daybar__side {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    flex-wrap: wrap;
  }

  .daybar__flags {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
  }

  .daybar__flag {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    font-size: 0.7rem;
    padding: 2px 8px;
    border-radius: 999px;
    background: var(--app-surface, #fff);
    border: 1px solid var(--app-border, #e3e7ee);
    color: var(--app-text-muted, #5b6472);
  }

  .daybar__flag--draft {
    color: #92400e;
    background: #fef3c7;
    border-color: #fde68a;
  }

  .daybar__flag--done {
    color: #166534;
    background: #dcfce7;
    border-color: #bbf7d0;
  }

  .daybar__flag--dirty {
    color: #1d4ed8;
    background: #dbeafe;
    border-color: #bfdbfe;
  }

  .daybar__flag--dirty :deep(.pi-circle-fill) {
    font-size: 0.4rem;
  }

  .daybar__actions {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
  }

  .daybar__warnings {
    margin: 0;
    padding: 0;
    list-style: none;
    display: grid;
    gap: 3px;
  }

  .daybar__warnings li {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 0.7rem;
    color: #b45309;
  }
</style>
