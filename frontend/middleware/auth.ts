export default defineNuxtRouteMiddleware(async (to) => {
  if (import.meta.server) return
  const auth = useAuth()
  if (!auth.initialized.value) await auth.loadCurrentUser()
  if (!auth.isAuthenticated.value) {
    return navigateTo({ path: '/login', query: { redirect: to.fullPath } })
  }
})