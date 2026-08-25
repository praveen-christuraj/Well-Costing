<script setup lang="ts">
import { onMounted, ref } from 'vue'
import Button from 'primevue/button'
import Message from 'primevue/message'
import Tag from 'primevue/tag'
import PageHeader from '~/components/design-system/PageHeader.vue'
import type { AssuranceStatus } from '~/types/assurance'

definePageMeta({ middleware: 'auth' })
const api = useAssurance()
const status = ref<AssuranceStatus | null>(null)
const loading = ref(false)
const error = ref<string | null>(null)
async function load(): Promise<void> {
  loading.value = true
  error.value = null
  try { status.value = await api.status() }
  catch (caught: unknown) { error.value = caught instanceof Error ? caught.message : 'Assurance check failed' }
  finally { loading.value = false }
}
onMounted(() => void load())
</script>

<template>
  <div class="assurance-page">
    <PageHeader title="Data-chain assurance" description="Integrity checks across AFE classifications, AFE Cost Estimate rates, Daily Cost sources and Well Activity accountability.">
      <template #actions><Tag :value="status?.status ?? 'checking'" :severity="status?.status === 'framework_ready' ? 'success' : 'danger'" /><Button label="Run checks" icon="pi pi-refresh" :loading="loading" @click="load" /></template>
    </PageHeader>
    <Message v-if="error" severity="error">{{ error }}</Message>
    <section class="assurance-meta"><div><span>Migration head</span><strong>{{ status?.migration_head ?? '—' }}</strong></div><div><span>Reporting contract</span><strong>v{{ status?.reporting_contract_version ?? '—' }}</strong></div><div><span>Active source chain</span><strong>AFE → Daily Cost</strong></div></section>
    <section><h2>Structural invariants</h2><div class="assurance-grid"><article v-for="check in status?.checks ?? []" :key="check.key"><Tag :value="check.status" :severity="check.status === 'passed' ? 'success' : 'danger'" /><h3>{{ check.label }}</h3><p>{{ check.detail }}</p><small>{{ check.violations }} violations</small></article></div></section>
  </div>
</template>
