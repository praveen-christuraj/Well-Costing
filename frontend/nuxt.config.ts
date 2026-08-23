import Aura from '@primeuix/themes/aura'

const configuredProxyTimeout = Number.parseInt(
  process.env.NUXT_API_PROXY_TIMEOUT_MS || '90000',
  10,
)
const apiProxyTimeoutMs = Number.isFinite(configuredProxyTimeout) && configuredProxyTimeout > 0
  ? configuredProxyTimeout
  : 90000

// Default: Secure auth cookie in production builds only. Explicitly set
// NUXT_PUBLIC_SECURE_COOKIE=true|false to override — e.g. 'false' when serving
// the production build over plain HTTP on a LAN (http://192.168.x.x:3000),
// because browsers refuse Secure cookies from non-localhost HTTP origins.
const secureCookieOverride = process.env.NUXT_PUBLIC_SECURE_COOKIE
const secureCookie = secureCookieOverride === 'true' || secureCookieOverride === 'false'
  ? secureCookieOverride === 'true'
  : process.env.NODE_ENV === 'production'

export default defineNuxtConfig({
  compatibilityDate: '2025-05-15',
  devtools: { enabled: process.env.NODE_ENV !== 'production' },
  modules: ['@pinia/nuxt', '@primevue/nuxt-module', '@nuxt/eslint'],
  css: ['primeicons/primeicons.css', '~/assets/css/main.css'],
  typescript: {
    strict: true,
    // typeCheck runs vue-tsc during every build — very slow on low-memory devices
    // (phone/CI). Run `npm run typecheck` separately when needed.
    typeCheck: false,
  },
  runtimeConfig: {
    apiInternalBase: process.env.NUXT_API_INTERNAL_BASE || 'http://127.0.0.1:8000',
    apiProxyTimeoutMs,
    public: {
      apiBase: process.env.NUXT_PUBLIC_API_BASE || '/api/v1',
      secureCookie,
    },
  },
  routeRules: {
    '/**': {
      headers: {
        'X-Content-Type-Options': 'nosniff',
        // Clickjacking protection stays on for every built artefact. It is
        // omitted only while running `nuxt dev`, because remote development
        // previews render the dev server inside an iframe on another origin.
        ...(process.env.NODE_ENV === 'production' ? { 'X-Frame-Options': 'DENY' } : {}),
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
