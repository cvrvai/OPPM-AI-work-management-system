/**
 * Token utility — localStorage helpers for access/refresh tokens.
 * Tokens are stored in localStorage and managed by authStore.
 */

export function getAccessToken(): string | null {
  return localStorage.getItem('access_token')
}

export function getRefreshToken(): string | null {
  return localStorage.getItem('refresh_token')
}

export function clearTokens(): void {
  localStorage.removeItem('access_token')
  localStorage.removeItem('refresh_token')
}
