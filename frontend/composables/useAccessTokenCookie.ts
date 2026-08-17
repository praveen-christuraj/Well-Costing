export function useAccessTokenCookie() {
  const config = useRuntimeConfig()
  return useCookie<string | null>('drilling-costing-access-token', {
    sameSite: 'lax',
    // Only mark the cookie Secure when the app is actually served over HTTPS.
    // Browsers drop Secure cookies on plain-HTTP LAN origins (e.g. http://192.168.x.x),
    // which previously caused "Authentication is required" on other devices.
    secure: config.public.secureCookie,
    path: '/',
  })
}
