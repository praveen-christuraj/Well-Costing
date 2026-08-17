/** Primary navigation. Only modules enabled in `utils/navigation` are shown. */
<script setup lang="ts">
import { enabledNavigation } from '~/utils/navigation'
</script>

<template>
  <nav class="app-topnav" aria-label="Primary navigation">
    <ul class="app-topnav__list">
      <li v-for="item in enabledNavigation" :key="item.key">
        <NuxtLink
          :to="item.to"
          class="app-topnav__item"
        >
          <i :class="item.icon" aria-hidden="true" />
          <span>{{ item.label }}</span>
        </NuxtLink>
      </li>
    </ul>
  </nav>
</template>
