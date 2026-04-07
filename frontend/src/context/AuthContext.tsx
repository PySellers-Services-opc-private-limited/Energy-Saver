import { createContext, useContext, useState, useEffect, ReactNode } from 'react'
import type { UserResponse } from '../api/types'

interface AuthState {
  token: string | null
  user: UserResponse | null
  isAuthenticated: boolean
  login: (token: string, user: UserResponse) => void
  logout: () => void
}

const AuthContext = createContext<AuthState>({
  token: null,
  user: null,
  isAuthenticated: false,
  login: () => {},
  logout: () => {},
})

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(
    () => localStorage.getItem('esai_token')
  )
  const [user, setUser] = useState<UserResponse | null>(() => {
    try {
      const raw = localStorage.getItem('esai_user')
      return raw ? (JSON.parse(raw) as UserResponse) : null
    } catch {
      return null
    }
  })

  // Validate the stored token on mount — clear stale tokens automatically
  useEffect(() => {
    if (!token) return
    fetch('/api/v1/auth/me', {
      headers: { Authorization: `Bearer ${token}` },
    }).then((res) => {
      if (!res.ok) {
        localStorage.removeItem('esai_token')
        localStorage.removeItem('esai_user')
        setToken(null)
        setUser(null)
      }
    }).catch(() => {
      // Network error — keep token, let retries handle it
    })
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  function login(t: string, u: UserResponse) {
    localStorage.setItem('esai_token', t)
    localStorage.setItem('esai_user', JSON.stringify(u))
    setToken(t)
    setUser(u)
  }

  function logout() {
    localStorage.removeItem('esai_token')
    localStorage.removeItem('esai_user')
    setToken(null)
    setUser(null)
  }

  return (
    <AuthContext.Provider value={{ token, user, isAuthenticated: !!token, login, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export const useAuth = () => useContext(AuthContext)
