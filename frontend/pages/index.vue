/**
 * Landing route. The application must always open on an enabled module, so this
 * route forwards to the first entry in the enabled navigation (Master Data
 * today) rather than rendering a module that is not released yet.
 */
<script setup lang="ts">
import { defaultLandingRoute } from '~/utils/navigation'

definePageMeta({
  middleware: [
    'auth',
    () => navigateTo(defaultLandingRoute, { replace: true }),
  ],
})
</script>

<template>
  <div class="library-page" />
</template>
