import { afterEach, describe, expect, it, vi } from 'vitest'
import { generatedClient } from './generatedTransport'
import { setUnauthorizedHandler } from './client'

afterEach(() => {
  sessionStorage.clear()
  vi.unstubAllGlobals()
  setUnauthorizedHandler(() => {})
})

const rejected = () => new Response(JSON.stringify({ detail: 'Rejected' }), {
  status: 401, headers: { 'content-type': 'application/json' },
})

describe('generated transport session boundaries', () => {
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
