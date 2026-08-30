const API_BASE = import.meta.env.VITE_API_BASE ?? '/api/v2'

export interface ProblemDetails {
  type: string
  title: string
  status: number
  detail: string
  instance: string
  error_code: string
  trace_id: string
  errors?: Array<Record<string, unknown>>
}

export class ApiError extends Error {
  status: number
  payload?: unknown

  constructor(message: string, status: number, payload?: unknown) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.payload = payload
  }
}

let onUnauthorized: (() => void) | null = null

export function setUnauthorizedHandler(handler: () => void) {
  onUnauthorized = handler
}

export function notifyUnauthorized(): void {
  onUnauthorized?.()
}

export function authToken(): string | null {
  return sessionStorage.getItem('bda_token')
}

/**
 * Attach the BDA bearer token only to BDA API URLs. MinIO presigned URLs carry
 * their own query-string signature; adding a Bearer Authorization header makes
 * MinIO interpret the request as a conflicting S3 authentication mechanism.
 */
export function apiAuthorizationHeaders(url: string): Record<string, string> {
  const token = authToken()
  if (!token) return {}
  const requestUrl = new URL(url, window.location.origin)
  const apiUrl = new URL(API_BASE, window.location.origin)
  const apiPath = apiUrl.pathname.replace(/\/$/, '')
  const isApiUrl = requestUrl.origin === apiUrl.origin
    && (requestUrl.pathname === apiPath || requestUrl.pathname.startsWith(`${apiPath}/`))
  return isApiUrl ? { Authorization: `Bearer ${token}` } : {}
}

interface RefreshResponse { access_token: string }
let refreshPromise: Promise<string> | null = null

export function refreshAccessToken(): Promise<string> {
  if (!refreshPromise) {
    refreshPromise = fetch(`${API_BASE}/auth/refresh`, {
      method: 'POST', credentials: 'include', headers: { 'content-type': 'application/json' }, body: '{}',
    }).then(async (response) => {
      if (!response.ok) throw new ApiError('Session expired', response.status)
      const payload = await response.json() as RefreshResponse
      sessionStorage.setItem('bda_token', payload.access_token)
      return payload.access_token
    }).finally(() => { refreshPromise = null })
  }
  return refreshPromise
}

/**
 * Normalize a backend-provided structure/preview URL into a browser-loadable URL.
 * Absolute URLs and already-prefixed `/api/` paths pass through unchanged; bare
 * relative paths are prefixed with the configured API base.
 */
export function resolveApiUrl(url: string | null | undefined): string | null {
  if (!url) return null
  if (url.startsWith('http://') || url.startsWith('https://')) return url
  if (url.startsWith('/api/')) return url
  return `${API_BASE}${url.startsWith('/') ? '' : '/'}${url}`
}

export { API_BASE }
