<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import Button from 'primevue/button'
import InputText from 'primevue/inputtext'
import Message from 'primevue/message'
import Password from 'primevue/password'
import { NormalizedApiError } from '~/types/api'

definePageMeta({ layout: false })

const defaultRedirectPath = '/cost-library/services'

const email = ref('')
const password = ref('')
const loading = ref(false)
const error = ref<string | null>(null)
const route = useRoute()
const { login, loadCurrentUser, initialized, isAuthenticated } = useAuth()

const redirectPath = computed(() => {
  const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : defaultRedirectPath
  return redirect.startsWith('/') ? redirect : defaultRedirectPath
})
const showRedirectMessage = computed(() => redirectPath.value !== defaultRedirectPath)
const canSubmit = computed(() => email.value.trim().length > 0 && password.value.length > 0 && !loading.value)

onMounted(async () => {
  if (!initialized.value) await loadCurrentUser()
  if (isAuthenticated.value) await navigateTo(redirectPath.value)
})

function normalizeLoginError(caught: unknown): string {
  const apiError = caught instanceof NormalizedApiError
    ? caught
    : caught instanceof Error && 'code' in caught && typeof caught.code === 'string'
      ? caught
      : null

  if (apiError) {
    if (apiError.code === 'authentication_failed') return 'Invalid email or password.'
    if (apiError.code === 'network_error') {
      return 'Unable to reach the sign-in service. Check the backend deployment and try again.'
    }
    return apiError.message
  }

  return caught instanceof Error ? caught.message : 'Login failed'
}

async function submit(): Promise<void> {
  if (!canSubmit.value) return

  loading.value = true
  error.value = null

  try {
    await login({ email: email.value.trim().toLowerCase(), password: password.value })
    await navigateTo(redirectPath.value)
  }
  catch (caught: unknown) {
    error.value = normalizeLoginError(caught)
  }
  finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="login-page">
    <form class="login-card" @submit.prevent="submit">
      <div class="app-mark">DC</div>
      <div class="login-card__intro">
        <p class="page-header__eyebrow">Secure workspace</p>
        <h1>Sign in</h1>
        <p>Use your drilling costing account to manage the cost library and enterprise setup.</p>
      </div>
      <Message v-if="showRedirectMessage" severity="info" :closable="false">
        Sign in to continue to your requested page.
      </Message>
      <Message v-if="error" severity="error" :closable="false">{{ error }}</Message>
      <label>
        Email
        <InputText v-model="email" type="email" autocomplete="username" fluid required autofocus />
        <small class="login-help">Use the named account provisioned for this environment.</small>
      </label>
      <label>
        Password
        <Password
          v-model="password"
          :feedback="false"
          toggle-mask
          fluid
          input-class="w-full"
          autocomplete="current-password"
          required
        />
      </label>
      <Button
        type="submit"
        label="Sign in"
        icon="pi pi-arrow-right"
        :loading="loading"
        :disabled="!canSubmit"
        fluid
      />
      <div class="login-card__footer">
        <div class="login-card__note">
          Cloud deployments keep the same login flow for development, UAT, and production-like testing.
        </div>
        <NuxtLink to="/">Return to dashboard</NuxtLink>
      </div>
    </form>
  </div>
</template>