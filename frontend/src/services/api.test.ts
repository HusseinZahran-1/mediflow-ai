import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from './api'

describe('ApiClient session refresh', () => {
  const fetchMock = vi.fn<typeof fetch>()

  beforeEach(() => {
    localStorage.clear()
    api.setToken('expired-access')
    localStorage.setItem('mediflow_refresh', 'valid-refresh')
    vi.stubGlobal('fetch', fetchMock)
  })

  afterEach(() => {
    fetchMock.mockReset()
    api.setToken(null)
    vi.unstubAllGlobals()
  })

  it('refreshes once and retries the failed request with the new access token', async () => {
    fetchMock
      .mockResolvedValueOnce(new Response('', { status: 401 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({
        access_token: 'fresh-access',
        refresh_token: 'fresh-refresh',
        token_type: 'bearer',
        expires_in: 1800,
        user: { id: 1, email: 'doctor@example.com', full_name: 'Doctor Test', role: 'DOCTOR', is_active: true },
      }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify([{ visit_id: 7 }]), { status: 200, headers: { 'Content-Type': 'application/json' } }))

    await expect(api.get<Array<{ visit_id: number }>>('/queue')).resolves.toEqual([{ visit_id: 7 }])

    expect(fetchMock).toHaveBeenCalledTimes(3)
    expect(new Headers(fetchMock.mock.calls[2][1]?.headers).get('Authorization')).toBe('Bearer fresh-access')
    expect(localStorage.getItem('mediflow_refresh')).toBe('fresh-refresh')
  })

  it('refreshes an expired session while restoring the current user', async () => {
    const user = { id: 1, email: 'doctor@example.com', full_name: 'Doctor Test', role: 'DOCTOR' as const, is_active: true }
    fetchMock
      .mockResolvedValueOnce(new Response('', { status: 401 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({
        access_token: 'fresh-access',
        refresh_token: 'fresh-refresh',
        token_type: 'bearer',
        expires_in: 1800,
        user,
      }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(user), { status: 200, headers: { 'Content-Type': 'application/json' } }))

    await expect(api.get('/auth/me')).resolves.toEqual(user)

    expect(fetchMock).toHaveBeenCalledTimes(3)
    expect(new Headers(fetchMock.mock.calls[2][1]?.headers).get('Authorization')).toBe('Bearer fresh-access')
  })
})
