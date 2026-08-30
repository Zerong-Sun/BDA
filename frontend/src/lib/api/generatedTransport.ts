import {
  ApiError,
  API_BASE,
  authToken,
  notifyUnauthorized,
  refreshAccessToken,
  setUnauthorizedHandler,
  type ProblemDetails,
} from './client'
import { client } from './generated/client.gen'

function generatedBaseUrl(): string {
  const suffix = '/api/v2'
  const baseUrl = API_BASE.endsWith(suffix) ? API_BASE.slice(0, -suffix.length) : API_BASE
  return baseUrl || window.location.origin
}

async function generatedFetch(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
  // The generated SDK uses a relative base URL in browsers. Resolve it here as
  // well so the same transport works under jsdom/Node contract tests, where the
  // native Request constructor rejects relative URLs.
  const resolvedInput = typeof input === 'string' && input.startsWith('/')
    ? new URL(input, window.location.origin)
    : input
  const original = new Request(resolvedInput, { ...init, credentials: 'include' })
  const headers = new Headers(original.headers)
  const token = authToken()
  if (token) headers.set('Authorization', `Bearer ${token}`)
  let request = new Request(original, { headers })
  let response = await fetch(request.clone())
  if (response.status === 401 && !request.url.endsWith('/auth/refresh')) {
    try {
      const nextToken = await refreshAccessToken()
      headers.set('Authorization', `Bearer ${nextToken}`)
      request = new Request(original, { headers })
      response = await fetch(request)
    } catch {
      sessionStorage.removeItem('bda_token')
      notifyUnauthorized()
    }
  }
  return response
}

client.setConfig({
  baseUrl: generatedBaseUrl(),
  credentials: 'include',
  fetch: generatedFetch,
  responseStyle: 'fields',
  throwOnError: true,
})

client.interceptors.error.use((error, response) => {
  const problem = error as Partial<ProblemDetails> | undefined
  throw new ApiError(problem?.detail ?? `Request failed (${response?.status ?? 0})`, response?.status ?? 0, error)
})

export function configureGeneratedUnauthorizedHandler(handler: () => void): void {
  setUnauthorizedHandler(handler)
}

export { client as generatedClient }
