export function useAccessTokenCookie() {
  return useCookie<string | null>('drilling-costing-access-token', {
    sameSite: 'lax',
    secure: import.meta.env.PROD,
    path: '/',
  })
}
