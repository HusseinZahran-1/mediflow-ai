import { createContext, useContext, useEffect, useMemo, useState, type PropsWithChildren } from 'react'
import { api } from '../services/api'
import type { User } from '../types'

interface AuthValue {
  user: User | null
  loading: boolean
  login: (email: string, password: string) => Promise<void>
  logout: () => void
}

const AuthContext = createContext<AuthValue | null>(null)

export function AuthProvider({ children }: PropsWithChildren) {
  const [user, setUser] = useState<User | null>(() => {
    const stored = localStorage.getItem('mediflow_user')
    try { return stored ? JSON.parse(stored) as User : null } catch { return null }
  })
  const [loading, setLoading] = useState(Boolean(localStorage.getItem('mediflow_access')))

  useEffect(() => {
    const expire = () => { setUser(null); setLoading(false) }
    const refreshed = (event: Event) => setUser((event as CustomEvent<User>).detail)
    window.addEventListener('mediflow:session-expired', expire)
    window.addEventListener('mediflow:session-refreshed', refreshed)
    if (!localStorage.getItem('mediflow_access')) {
      setLoading(false)
      return () => {
        window.removeEventListener('mediflow:session-expired', expire)
        window.removeEventListener('mediflow:session-refreshed', refreshed)
      }
    }
    api.get<User>('/auth/me').then((me) => {
      setUser(me)
      localStorage.setItem('mediflow_user', JSON.stringify(me))
    }).catch(() => {
      api.setToken(null)
      localStorage.removeItem('mediflow_user')
      setUser(null)
    }).finally(() => setLoading(false))
    return () => {
      window.removeEventListener('mediflow:session-expired', expire)
      window.removeEventListener('mediflow:session-refreshed', refreshed)
    }
  }, [])

  const value = useMemo<AuthValue>(() => ({
    user,
    loading,
    login: async (email, password) => {
      const result = await api.login(email, password)
      api.setToken(result.access_token)
      localStorage.setItem('mediflow_refresh', result.refresh_token)
      localStorage.setItem('mediflow_user', JSON.stringify(result.user))
      setUser(result.user)
    },
    logout: () => {
      const refreshToken = localStorage.getItem('mediflow_refresh')
      if (refreshToken) void api.post('/auth/logout', { refresh_token: refreshToken }).catch(() => undefined)
      api.setToken(null)
      localStorage.removeItem('mediflow_refresh')
      localStorage.removeItem('mediflow_user')
      setUser(null)
    },
  }), [user, loading])

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const value = useContext(AuthContext)
  if (!value) throw new Error('useAuth must be used inside AuthProvider')
  return value
}
