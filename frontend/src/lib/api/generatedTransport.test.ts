import { afterEach, describe, expect, it, vi } from 'vitest'
import { generatedClient } from './generatedTransport'
import { invalidateAuthRequests, setUnauthorizedHandler } from './client'

afterEach(() => {
  invalidateAuthRequests()
  sessionStorage.clear()
  vi.unstubAllGlobals()
  setUnauthorizedHandler(() => {})
})

const rejected = () => new Response(JSON.stringify({ detail: 'Rejected' }), {
  status: 401, headers: { 'content-type': 'application/json' },
})

describe('generated transport session boundaries', () => {
  it('rejects a successful response from a previous account and aborts its request', async () => {
    let finish!: (response: Response) => void
    let started!: () => void
    const ready = new Promise<void>(resolve => { started = resolve })
    const fetch = vi.fn<(request: RequestInfo | URL) => Promise<Response>>(() => new Promise<Response>(resolve => { finish = resolve; started() }))
    vi.stubGlobal('fetch', fetch)
    const pending = generatedClient.get({ url: '/api/v2/projects' })
    const rejectedRequest = expect(pending).rejects.toBeDefined()
    await ready
    invalidateAuthRequests()
    expect((fetch.mock.calls[0][0] as Request).signal.aborted).toBe(true)
    finish(new Response(JSON.stringify({ private: 'old-account' }), { headers: { 'content-type': 'application/json' } }))
    await rejectedRequest
  })

  it('does not send a bearer token to an absolute URL outside the configured API', async () => {
    sessionStorage.setItem('bda_token', 'access-token')
    const fetch = vi.fn()
    vi.stubGlobal('fetch', fetch)
    await expect(generatedClient.get({ url: 'https://untrusted.example/api/v2/projects' })).rejects.toBeDefined()
    expect(fetch).not.toHaveBeenCalled()
  })

  it('does not sign out a new account when a previous account retry returns 401 late', async () => {
    let finishRetry!: (response: Response) => void
    let retryStarted!: () => void
    const started = new Promise<void>(resolve => { retryStarted = resolve })
    const fetch = vi.fn().mockResolvedValueOnce(rejected())
      .mockResolvedValueOnce(new Response(JSON.stringify({ access_token: 'old-refreshed', user: { id: 'old' } }), {
        headers: { 'content-type': 'application/json' },
      })).mockImplementationOnce(() => new Promise<Response>(resolve => {
        finishRetry = resolve
        retryStarted()
      }))
    vi.stubGlobal('fetch', fetch)
    const unauthorized = vi.fn()
    setUnauthorizedHandler(unauthorized)
    sessionStorage.setItem('bda_user', JSON.stringify({ id: 'old' }))
    const pending = generatedClient.get({ url: '/api/v2/auth/me' })
    const rejectedRequest = expect(pending).rejects.toMatchObject({ status: 401 })
    await started
    invalidateAuthRequests()
    sessionStorage.setItem('bda_user', JSON.stringify({ id: 'new' }))
    sessionStorage.setItem('bda_token', 'new-login')
    finishRetry(rejected())
    await rejectedRequest
    expect(unauthorized).not.toHaveBeenCalled()
    expect(sessionStorage.getItem('bda_token')).toBe('new-login')
  })
  it('does not refresh or retry an explicitly rejected login', async () => {
    const fetch = vi.fn().mockImplementation(rejected)
    const unauthorized = vi.fn()
    setUnauthorizedHandler(unauthorized)
    vi.stubGlobal('fetch', fetch)
    await expect(generatedClient.post({ url: '/api/v2/auth/token', body: {} })).rejects.toMatchObject({ status: 401 })
    expect(fetch).toHaveBeenCalledTimes(1)
    expect(unauthorized).not.toHaveBeenCalled()
  })

  it('ends the session when the single authenticated retry is also rejected', async () => {
    const fetch = vi.fn().mockResolvedValueOnce(rejected())
      .mockResolvedValueOnce(new Response(JSON.stringify({ access_token: 'new-token' }), {
        headers: { 'content-type': 'application/json' },
      })).mockResolvedValueOnce(rejected())
    const unauthorized = vi.fn()
    setUnauthorizedHandler(unauthorized)
    vi.stubGlobal('fetch', fetch)
    await expect(generatedClient.get({ url: '/api/v2/auth/me' })).rejects.toMatchObject({ status: 401 })
    expect(fetch).toHaveBeenCalledTimes(3)
    expect(unauthorized).toHaveBeenCalledTimes(1)
  })

  it('preserves a write body when retrying after refresh', async () => {
    const fetch = vi.fn().mockResolvedValueOnce(rejected())
      .mockResolvedValueOnce(new Response(JSON.stringify({ access_token: 'new-token' }), {
        headers: { 'content-type': 'application/json' },
      })).mockResolvedValueOnce(new Response('{}', { headers: { 'content-type': 'application/json' } }))
    vi.stubGlobal('fetch', fetch)
    await generatedClient.post({ url: '/api/v2/projects', body: { name: 'Review' }, headers: { 'content-type': 'application/json' } })
    expect(await (fetch.mock.calls[0][0] as Request).text()).toEqual('{"name":"Review"}')
    expect(await (fetch.mock.calls[2][0] as Request).text()).toEqual('{"name":"Review"}')
    expect((fetch.mock.calls[2][0] as Request).headers.get('authorization')).toBe('Bearer new-token')
  })
})
