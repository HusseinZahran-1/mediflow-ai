import type { AuthResponse } from '../types'

const API_URL = import.meta.env.VITE_API_URL || '/api/v1'

class ApiClient {
  private accessToken = localStorage.getItem('mediflow_access')
  private refreshPromise: Promise<boolean> | null = null

  setToken(token: string | null) {
    this.accessToken = token
    if (token) localStorage.setItem('mediflow_access', token)
    else localStorage.removeItem('mediflow_access')
  }

  getToken() { return this.accessToken }

  private clearSession() {
    this.setToken(null)
    localStorage.removeItem('mediflow_refresh')
    localStorage.removeItem('mediflow_user')
    window.dispatchEvent(new Event('mediflow:session-expired'))
  }

  private refreshAccessToken(): Promise<boolean> {
    if (this.refreshPromise) return this.refreshPromise
    const refreshToken = localStorage.getItem('mediflow_refresh')
    if (!refreshToken) return Promise.resolve(false)
    this.refreshPromise = fetch(`${API_URL}/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refreshToken }),
    }).then(async (response) => {
      if (!response.ok) throw new Error('Session refresh failed')
      const result = await response.json() as AuthResponse
      this.setToken(result.access_token)
      localStorage.setItem('mediflow_refresh', result.refresh_token)
      localStorage.setItem('mediflow_user', JSON.stringify(result.user))
      window.dispatchEvent(new CustomEvent('mediflow:session-refreshed', { detail: result.user }))
      return true
    }).catch(() => {
      this.clearSession()
      return false
    }).finally(() => { this.refreshPromise = null })
    return this.refreshPromise
  }

  async request<T>(path: string, options: RequestInit = {}, retryAfterRefresh = true): Promise<T> {
    const headers = new Headers(options.headers)
    if (!headers.has('Content-Type') && options.body) headers.set('Content-Type', 'application/json')
    if (this.accessToken) headers.set('Authorization', `Bearer ${this.accessToken}`)
    const response = await fetch(`${API_URL}${path}`, { ...options, headers })
    const canRefresh = path === '/auth/me' || !path.startsWith('/auth/')
    if (response.status === 401 && retryAfterRefresh && canRefresh) {
      if (await this.refreshAccessToken()) return this.request<T>(path, options, false)
    }
    if (!response.ok) {
      const body = await response.json().catch(() => ({ detail: response.statusText }))
      throw new Error(typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail))
    }
    if (response.status === 204) return undefined as T
    return response.json() as Promise<T>
  }

  get<T>(path: string) { return this.request<T>(path) }
  post<T>(path: string, body?: unknown) { return this.request<T>(path, { method: 'POST', body: body === undefined ? undefined : JSON.stringify(body) }) }
  patch<T>(path: string, body: unknown) { return this.request<T>(path, { method: 'PATCH', body: JSON.stringify(body) }) }
  login(email: string, password: string) { return this.post<AuthResponse>('/auth/login', { email, password }) }

  websocketUrl(path: string) {
    const url = new URL(API_URL, window.location.origin)
    url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:'
    url.pathname = `${url.pathname.replace(/\/$/, '')}/${path.replace(/^\//, '')}`
    url.search = ''
    return url.toString()
  }
}

export const api = new ApiClient()
