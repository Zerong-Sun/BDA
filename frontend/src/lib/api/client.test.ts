import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  ApiError,
  invalidateAuthRequests,
  apiAuthorizationHeaders,
  notifyUnauthorized,
  refreshAccessToken,
  setUnauthorizedHandler,
} from './client'

afterEach(() => {
  invalidateAuthRequests()
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


describe('session isolation', () => {
  it('starts a new refresh after an account switch and keeps its single flight when the old request settles', async () => {
    let finishOld!: (response: Response) => void
    let finishNew!: (response: Response) => void
    const fetch = vi.fn()
      .mockImplementationOnce(() => new Promise<Response>(resolve => { finishOld = resolve }))
      .mockImplementationOnce(() => new Promise<Response>(resolve => { finishNew = resolve }))
    vi.stubGlobal('fetch', fetch)
    sessionStorage.setItem('bda_user', JSON.stringify({ id: 'old' }))
    const oldRequest = refreshAccessToken()
    const rejected = expect(oldRequest).rejects.toThrow('Session ended')
    invalidateAuthRequests()
    sessionStorage.setItem('bda_user', JSON.stringify({ id: 'new' }))
    sessionStorage.setItem('bda_token', 'new-login')
    const newRequest = refreshAccessToken()
    expect(fetch).toHaveBeenCalledTimes(2)
    expect((fetch.mock.calls[0][1] as RequestInit).signal?.aborted).toBe(true)
    finishOld(new Response(JSON.stringify({ access_token: 'stale', user: { id: 'old' } })))
    await rejected
    expect(sessionStorage.getItem('bda_token')).toBe('new-login')
    expect(refreshAccessToken()).toBe(newRequest)
    finishNew(new Response(JSON.stringify({ access_token: 'new-refresh', user: { id: 'new' } })))
    await expect(newRequest).resolves.toBe('new-refresh')
    expect(fetch).toHaveBeenCalledTimes(2)
  })
  it('does not resurrect browser credentials when an in-flight refresh finishes after logout', async () => {
    let finish!: (response: Response) => void
    vi.stubGlobal('fetch', vi.fn(() => new Promise<Response>(resolve => { finish = resolve })))
    const pending = refreshAccessToken()
    const rejected = expect(pending).rejects.toThrow('Session ended')
    invalidateAuthRequests()
    finish(new Response(JSON.stringify({ access_token: 'stale', user: { id: 'old' } })))
    await rejected
    expect(sessionStorage.getItem('bda_token')).toBeNull()
  })
  it('does not silently switch to the account whose cookie was set in another tab', async () => {
    sessionStorage.setItem('bda_user', JSON.stringify({ id: 'first' }))
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ access_token: 'other', user: { id: 'second' } }))))
    await expect(refreshAccessToken()).rejects.toThrow('Account changed')
    expect(sessionStorage.getItem('bda_token')).toBeNull()
    expect(JSON.parse(sessionStorage.getItem('bda_user')!).id).toBe('first')
  })
})
