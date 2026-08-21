<script setup lang="ts">
import Button from 'primevue/button'
import Message from 'primevue/message'
import Tag from 'primevue/tag'
import type { EstimateAfeStatus } from '~/types/afeSnapshots'

defineProps<{
  status: EstimateAfeStatus | null
  loading: boolean
  requestMessage: string | null
}>()
const emit = defineEmits<{ 'create-baseline': [] }>()

function formatDate(value: string): string {
  return new Date(value).toLocaleString()
}
</script>

<template>
  <section class="afe-panel">
    <div class="afe-panel__header">
      <div>
        <span class="eyebrow">Phase 7 control</span>
        <h2>Immutable AFE baseline</h2>
      </div>
      <Tag :value="status?.afe_status ?? 'loading'" :severity="status?.afe_status === 'issued' ? 'success' : 'warn'" />
    </div>

    <Message v-if="status?.afe_status === 'policy_pending'" severity="warn" :closable="false">
      AFE policy pending. An immutable baseline cannot be issued until estimate eligibility, numbering, snapshot contents, and authorization rules are approved.
    </Message>
    <Message v-if="requestMessage" severity="error" :closable="false">{{ requestMessage }}</Message>

    <div v-if="status?.baseline_snapshot" class="afe-issued-card">
      <span>Issued baseline</span>
      <strong>{{ status.baseline_snapshot.afe_number }}</strong>
      <span>{{ status.baseline_snapshot.grand_total }} {{ status.baseline_snapshot.currency_code }}</span>
    </div>
    <div v-else class="afe-empty-state">
      <i class="pi pi-lock" />
      <div><strong>No AFE issued</strong><p>The explicit request below is audited but cannot create a snapshot while policy is pending.</p></div>
      <Button label="Create baseline AFE snapshot" icon="pi pi-lock" :loading="loading" @click="emit('create-baseline')" />
    </div>

    <details v-if="status?.pending_requirements.length" class="pending-rules">
      <summary>Pending AFE policy ({{ status.pending_requirements.length }})</summary>
      <ul><li v-for="item in status.pending_requirements" :key="item">{{ item }}</li></ul>
    </details>

    <div v-if="status?.creation_attempts.length" class="afe-attempts">
      <h3>Snapshot attempts</h3>
      <div v-for="attempt in status.creation_attempts" :key="attempt.id" class="afe-attempt">
        <Tag :value="attempt.status" :severity="attempt.status === 'completed' ? 'success' : 'warn'" />
        <span>{{ attempt.requested_reference ?? 'Explicit baseline request' }}</span>
        <time>{{ formatDate(attempt.created_at) }}</time>
      </div>
    </div>
  </section>
</template>
