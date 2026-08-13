import Aura from '@primeuix/themes/aura'

const configuredProxyTimeout = Number.parseInt(
  process.env.NUXT_API_PROXY_TIMEOUT_MS || '90000',
  10,
)
const apiProxyTimeoutMs = Number.isFinite(configuredProxyTimeout) && configuredProxyTimeout > 0
  ? configuredProxyTimeout
  : 90000

export default defineNuxtConfig({
  compatibilityDate: '2025-05-15',
  devtools: { enabled: process.env.NODE_ENV !== 'production' },
  modules: ['@pinia/nuxt', '@primevue/nuxt-module', '@nuxt/eslint'],
  css: ['primeicons/primeicons.css', '~/assets/css/main.css'],
  typescript: {
    strict: true,
    typeCheck: true,
  },
  runtimeConfig: {
    apiInternalBase: process.env.NUXT_API_INTERNAL_BASE || 'http://127.0.0.1:8000',
    apiProxyTimeoutMs,
    public: {
      apiBase: process.env.NUXT_PUBLIC_API_BASE || '/api/v1',
    },
  },
  routeRules: {
    '/**': {
      headers: {
        'X-Content-Type-Options': 'nosniff',
        'X-Frame-Options': 'DENY',
        'Referrer-Policy': 'strict-origin-when-cross-origin',
        'Permissions-Policy': 'camera=(), microphone=(), geolocation=()',
      },
    },
  },
  primevue: {
    options: {
      ripple: true,
      theme: {
        preset: Aura,
        options: {
          darkModeSelector: '.app-dark',
          cssLayer: {
            name: 'primevue',
            order: 'theme, base, primevue, app',
          },
        },
      },
    },
  },
  app: {
    head: {
      title: 'Drilling Costing',
      meta: [
        {
          name: 'description',
          content: 'Auditable, bulk-first drilling cost management',
        },
      ],
    },
  },
})
