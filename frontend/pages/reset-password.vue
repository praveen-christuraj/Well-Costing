<script setup lang="ts">
import Message from 'primevue/message'

definePageMeta({ layout: false })
</script>

<template>
  <div class="login-page">
    <div class="login-card">
      <div class="app-mark">DC</div>
      <div class="login-card__intro">
        <p class="page-header__eyebrow">Authentication placeholder</p>
        <h1>Reset password</h1>
        <p>Token-based password reset is not active in the application yet.</p>
      </div>
      <Message severity="warn" :closable="false">
        Keep this route as a placeholder only. Later it can be connected to Google-based authentication or an approved reset workflow.
      </Message>
      <div class="login-card__footer">
        <div class="login-card__note">
          No reset tokens are issued by the backend today, and no self-service user registration is exposed in the app.
        </div>
        <NuxtLink to="/login">Back to sign in</NuxtLink>
      </div>
    </div>
  </div>
</template>