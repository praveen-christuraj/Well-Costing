# Frontend services

`apiClient.ts` is the single transport boundary for browser-to-backend calls. Feature code should use `useApi()` rather than calling `$fetch` directly.
