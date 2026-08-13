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
        <h1>Forgot password</h1>
        <p>Password recovery is reserved for a later release.</p>
      </div>
      <Message severity="info" :closable="false">
        For now, bootstrap admin is created during deployment and any additional users are provisioned directly in the hosted PostgreSQL database. Contact your system administrator for password assistance.
      </Message>
      <div class="login-card__footer">
        <div class="login-card__note">
          This page is intentionally a placeholder until the future password-recovery and Google-auth roadmap is approved.
        </div>
        <NuxtLink to="/login">Back to sign in</NuxtLink>
      </div>
    </div>
  </div>
</template>