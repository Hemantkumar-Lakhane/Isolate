// frontend/src/contexts/AuthContext.jsx
// ─────────────────────────────────────────────────────────────────────────────
// Supabase Auth + SMBFlow Canonical Profile Context
// Handles token, user, role, organization hydration & session listeners.
// ─────────────────────────────────────────────────────────────────────────────
import { createContext, useContext, useState, useCallback, useMemo, useEffect } from 'react'
import { createClient } from '@supabase/supabase-js'
import { createApiClient } from '../api/client'
import { createServices } from '../api/services'
import { createAuthService } from '../api/services/auth.service'
import { onSessionExpired } from '../api/authEvents'

const AuthContext = createContext(null)

const USER_STORAGE_KEY = 'smbflow_user_profile'

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL || ''
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY || ''
export const supabase = (supabaseUrl && supabaseAnonKey && !supabaseAnonKey.startsWith('YOUR_'))
  ? createClient(supabaseUrl, supabaseAnonKey)
  : null

function loadStoredUser() {
  try {
    return JSON.parse(localStorage.getItem(USER_STORAGE_KEY) || 'null')
  } catch {
    return null
  }
}

export function AuthProvider({ children }) {
  const [token, setToken] = useState(null)
  const [user, setUser] = useState(() => loadStoredUser())
  const [loading, setLoading] = useState(true)
  const [sessionExpired, setSessionExpired] = useState(false)

  const login = useCallback((newToken, newUser) => {
    setToken(newToken)
    setUser(newUser)
    setSessionExpired(false)
    try {
      localStorage.setItem(USER_STORAGE_KEY, JSON.stringify(newUser))
    } catch (_) {}
  }, [])

  const logout = useCallback(async () => {
    if (supabase) {
      try { await supabase.auth.signOut() } catch (_) {}
    }
    setToken(null)
    setUser(null)
    try {
      localStorage.removeItem(USER_STORAGE_KEY)
    } catch (_) {}
  }, [])

  const clearSessionExpired = useCallback(() => setSessionExpired(false), [])

  // Hydrate profile via FastAPI /auth/me or fallback to session metadata
  const processSession = useCallback(async (session) => {
    if (!session) {
      setToken(null)
      setUser(null)
      try { localStorage.removeItem(USER_STORAGE_KEY) } catch (_) {}
      setLoading(false)
      return
    }

    setToken(session.access_token)
    try {
      const authApi = createAuthService(createApiClient(session.access_token))
      const profile = await authApi.me().catch(() => null)

      const u = {
        id: profile?.id || session.user.id,
        email: profile?.email || session.user.email,
        role: profile?.role || session.user.user_metadata?.role || 'org_user',
        organization_id: profile?.organization_id || profile?.tenant_id || session.user.user_metadata?.organization_id || null,
        tenant_id: profile?.organization_id || profile?.tenant_id || session.user.user_metadata?.organization_id || null,
        full_name: profile?.full_name || session.user.user_metadata?.full_name || session.user.user_metadata?.name || null,
        organization_name: profile?.organization_name || profile?.tenant_name || null,
        industry: profile?.industry || 'saas',
        requires_onboarding: profile?.requires_onboarding ?? false,
        enabled_modules: [profile?.industry || 'saas'],
        is_email_confirmed: Boolean(session.user.email_confirmed_at || session.user.confirmed_at),
      }
      setUser(u)
      try { localStorage.setItem(USER_STORAGE_KEY, JSON.stringify(u)) } catch (_) {}
    } catch (_) {
      const u = {
        id: session.user.id,
        email: session.user.email,
        role: session.user.user_metadata?.role || 'org_user',
        organization_id: session.user.user_metadata?.organization_id || null,
        requires_onboarding: false,
        enabled_modules: ['saas'],
        is_email_confirmed: Boolean(session.user.email_confirmed_at || session.user.confirmed_at),
      }
      setUser(u)
    } finally {
      setLoading(false)
    }
  }, [])

  const provisionWorkspace = useCallback(async (payload) => {
    if (!token) throw new Error('No active authentication token')
    const authApi = createAuthService(createApiClient(token))
    const profile = await authApi.provision(payload)
    const u = {
      id: profile.id,
      email: profile.email,
      role: profile.role || 'org_user',
      organization_id: profile.organization_id || profile.tenant_id,
      tenant_id: profile.organization_id || profile.tenant_id,
      full_name: profile.full_name,
      organization_name: profile.organization_name || profile.tenant_name,
      industry: profile.industry || 'saas',
      requires_onboarding: false,
      enabled_modules: [profile.industry || 'saas'],
    }
    setUser(u)
    try { localStorage.setItem(USER_STORAGE_KEY, JSON.stringify(u)) } catch (_) {}
    return u
  }, [token])

  // Supabase Auth listener — INITIAL_SESSION fires on mount for existing sessions
  useEffect(() => {
    if (!supabase) {
      setLoading(false)
      return
    }

    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, session) => {
      processSession(session)
    })

    return () => subscription.unsubscribe()
  }, [processSession])

  useEffect(() => {
    return onSessionExpired(() => {
      setToken((prev) => {
        if (prev) setSessionExpired(true)
        return null
      })
      setUser(null)
      try {
        localStorage.removeItem(USER_STORAGE_KEY)
      } catch (_) {}
    })
  }, [])

  const api = useMemo(() => createApiClient(token), [token])
  const services = useMemo(() => createServices(api), [api])

  const isAdmin = user?.role === 'platform_admin' || user?.role === 'super_admin'

  const value = useMemo(
    () => ({
      user, token, loading, isAdmin, login, logout, provisionWorkspace, api, services,
      sessionExpired, clearSessionExpired, supabase,
    }),
    [user, token, loading, isAdmin, login, logout, provisionWorkspace, api, services, sessionExpired, clearSessionExpired],
  )


  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>')
  return ctx
}