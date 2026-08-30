import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  ApiError,
  apiAuthorizationHeaders,
  notifyUnauthorized,
  refreshAccessToken,
  setUnauthorizedHandler,
} from './client'

afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
  sessionStorage.clear()
})

describe('ApiError', () => {
  it('stores status and payload', () => {
    const err = new ApiError('invalid_credentials', 401, { detail: 'invalid_credentials' })
    expect(err.name).toBe('ApiError')
    expect(err.status).toBe(401)
    expect(err.message).toBe('invalid_credentials')
    expect(err.payload).toEqual({ detail: 'invalid_credentials' })
  })
})

describe('generated transport authentication helpers', () => {
  it('does not attach the BDA bearer token to presigned object URLs', () => {
    sessionStorage.setItem('bda_token', 'access-token')

    expect(apiAuthorizationHeaders('/api/v2/artifacts/123')).toEqual({
      Authorization: 'Bearer access-token',
    })
    expect(
      apiAuthorizationHeaders('http://localhost:9002/bucket/object?X-Amz-Signature=signed'),
    ).toEqual({})
  })

  it('coalesces concurrent refresh requests and stores the rotated access token', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ access_token: 'rotated-token' }), {
        status: 200,
        headers: { 'content-type': 'application/json' },
      }),
    )
    vi.stubGlobal('fetch', fetchMock)

    await expect(Promise.all([refreshAccessToken(), refreshAccessToken()])).resolves.toEqual([
      'rotated-token',
      'rotated-token',
    ])
    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(sessionStorage.getItem('bda_token')).toBe('rotated-token')
  })

  it('notifies the configured handler when authentication is rejected', () => {
    const handler = vi.fn()
    setUnauthorizedHandler(handler)
    notifyUnauthorized()
    expect(handler).toHaveBeenCalledOnce()
  })
})
