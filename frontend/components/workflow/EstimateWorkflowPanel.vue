<script setup lang="ts">
import Button from 'primevue/button'
import Message from 'primevue/message'
import Tag from 'primevue/tag'
import Textarea from 'primevue/textarea'
import type { EstimateWorkflowStatus } from '~/types/workflow'

const props = defineProps<{
  status: EstimateWorkflowStatus | null
  note: string
  saving: boolean
}>()
const emit = defineEmits<{
  'update:note': [value: string]
  'add-comment': []
}>()

function formatDate(value: string): string {
  return new Date(value).toLocaleString()
}
</script>

<template>
  <section class="workflow-panel">
    <div class="workflow-panel__header">
      <div>
        <span class="eyebrow">Phase 6 control</span>
        <h2>Review &amp; approval</h2>
      </div>
      <Tag :value="status?.workflow_status ?? 'loading'" :severity="status?.workflow_status === 'active' ? 'success' : 'warn'" />
    </div>

    <Message v-if="status?.workflow_status === 'profile_pending'" severity="warn" :closable="false">
      Workflow profile pending. Approval transitions are disabled until approved states and role mappings are published.
    </Message>

    <div v-if="status?.profile" class="workflow-current-state">
      <span>Current state</span>
      <strong>{{ status.current_state_key ?? 'Not started' }}</strong>
      <small>{{ status.profile.code }} v{{ status.profile.version_number }}</small>
    </div>

    <details v-if="status?.pending_requirements.length" class="pending-rules">
      <summary>Pending workflow policy ({{ status.pending_requirements.length }})</summary>
      <ul><li v-for="item in status.pending_requirements" :key="item">{{ item }}</li></ul>
    </details>

    <div class="review-note-form">
      <label for="review-note">Add review note</label>
      <Textarea
        id="review-note"
        :model-value="props.note"
        rows="3"
        fluid
        placeholder="Record a review observation without changing approval state"
        @update:model-value="emit('update:note', String($event ?? ''))"
      />
      <Button label="Add review note" icon="pi pi-comment" outlined :loading="saving" :disabled="!note.trim()" @click="emit('add-comment')" />
    </div>

    <div class="workflow-trace-grid">
      <div>
        <h3>Review notes</h3>
        <p v-if="!status?.review_comments.length" class="muted-copy">No review notes yet.</p>
        <article v-for="comment in status?.review_comments ?? []" :key="comment.id" class="review-note">
          <p>{{ comment.body }}</p>
          <small>{{ formatDate(comment.created_at) }} · Actor {{ comment.created_by ?? 'unknown' }}</small>
        </article>
      </div>
      <div>
        <h3>Transition attempts</h3>
        <p v-if="!status?.transition_attempts.length" class="muted-copy">No transition attempts yet.</p>
        <div v-for="attempt in status?.transition_attempts ?? []" :key="attempt.id" class="workflow-attempt">
          <Tag :value="attempt.status" :severity="attempt.status === 'completed' ? 'success' : 'warn'" />
          <span>{{ attempt.requested_action }}</span>
          <time>{{ formatDate(attempt.created_at) }}</time>
        </div>
      </div>
    </div>
  </section>
</template>
