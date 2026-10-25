import {
  ApiError,
  API_BASE,
  authToken,
  notifyUnauthorized,
  refreshAccessToken,
  setUnauthorizedHandler,
  type ProblemDetails,
  currentAuthGeneration,
  captureAuthSession,
  apiAuthorizationHeaders,
} from './client'
import { client } from './generated/client.gen'

function generatedBaseUrl(): string {
  const suffix = '/api/v2'
  const baseUrl = API_BASE.endsWith(suffix) ? API_BASE.slice(0, -suffix.length) : API_BASE
  return baseUrl || window.location.origin
}

async function generatedFetch(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
  const generation = currentAuthGeneration()
  const session = captureAuthSession()
  // The generated SDK uses a relative base URL in browsers. Resolve it here as
  // well so the same transport works under jsdom/Node contract tests, where the
  // native Request constructor rejects relative URLs.
  const resolvedInput = typeof input === 'string' && input.startsWith('/')
    ? new URL(input, window.location.origin)
    : input
  const source = new Request(resolvedInput, init)
  const original = new Request(source, {
    credentials: 'include',
    signal: AbortSignal.any([source.signal, session.signal]),
  })
  const headers = new Headers(original.headers)
  const token = authToken()
  if (token) {
    const authorization = apiAuthorizationHeaders(original.url)
    if (!authorization.Authorization) throw new ApiError('Untrusted API URL', 400)
    headers.set('Authorization', authorization.Authorization)
  }
  // Keep the original body available: constructing a Request transfers its
  // stream, so reusing that consumed Request made authenticated POST retries fail.
  let request = new Request(original.clone(), { headers })
  let response = await fetch(request.clone())
  session.assertCurrent()
  const pathname = new URL(request.url).pathname.replace(/\/$/, '')
  const isCredentialRequest = ['/auth/refresh', '/auth/token', '/auth/register', '/auth/logout', '/auth/password', '/auth/password/reset'].some(path => pathname.endsWith(path))
  if (response.status === 401 && !isCredentialRequest && generation === currentAuthGeneration()) {
    let nextToken: string
    try {
      nextToken = await refreshAccessToken()
    } catch {
      if (generation === currentAuthGeneration()) notifyUnauthorized()
      return response
    }
    if (generation !== currentAuthGeneration()) return response
    headers.set('Authorization', `Bearer ${nextToken}`)
    request = new Request(original, { headers })
    response = await fetch(request)
    session.assertCurrent()
    if (response.status === 401 && generation === currentAuthGeneration()) notifyUnauthorized()
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
  if (error instanceof ApiError) throw error
  const problem = error as Partial<ProblemDetails> | undefined
  throw new ApiError(problem?.detail ?? `Request failed (${response?.status ?? 0})`, response?.status ?? 0, error)
})

export function configureGeneratedUnauthorizedHandler(handler: () => void): void {
  setUnauthorizedHandler(handler)
}

export { client as generatedClient }
