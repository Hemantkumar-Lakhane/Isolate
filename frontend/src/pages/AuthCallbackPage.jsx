// frontend/src/pages/AuthCallbackPage.jsx
// ─────────────────────────────────────────────────────────────────────────────
// Dedicated OAuth Callback Page for Supabase Google Authentication.
//   • Waits for Supabase Auth session hydration and FastAPI /auth/me profile loading.
//   • Prevents premature redirection to /auth while authentication hydrates.
//   • Directs new users to /auth/signup, completed users to /dashboard or /admin.
// ─────────────────────────────────────────────────────────────────────────────
import React, { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Loader2, AlertCircle } from 'lucide-react'
import { useAuth } from '../contexts/AuthContext'

export default function AuthCallbackPage() {
  const navigate = useNavigate()
  const { user, token, loading: authLoading } = useAuth()
  const [error, setError] = useState(null)

  useEffect(() => {
    // 1. Wait until AuthContext finishes session hydration & /auth/me loading
    if (authLoading) return

    // 2. If session and user profile exist, route according to role and onboarding state
    if (token && user) {
      if (user.requires_onboarding) {
        navigate('/auth/signup', { replace: true })
      } else if (user.role === 'super_admin' || user.role === 'platform_admin') {
        navigate('/admin', { replace: true })
      } else {
        navigate('/dashboard', { replace: true })
      }
      return
    }

    // 3. Handle error or unauthenticated state
    const params = new URLSearchParams(window.location.search)
    const errorDesc = params.get('error_description') || params.get('error')
    if (errorDesc) {
      setError(errorDesc)
      const timer = setTimeout(() => navigate('/auth', { replace: true }), 3000)
      return () => clearTimeout(timer)
    }

    // Safety timeout to allow async PKCE token exchange to settle
    const safetyTimer = setTimeout(() => {
      if (!token) {
        navigate('/auth', { replace: true })
      }
    }, 2500)

    return () => clearTimeout(safetyTimer)
  }, [token, user, authLoading, navigate])

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col items-center justify-center p-4">
      <div className="flex items-center gap-2.5 mb-4">
        <div className="w-9 h-9 rounded-xl bg-blue-600 flex items-center justify-center">
          <span className="text-white font-bold text-sm">S</span>
        </div>
        <span className="text-xl font-semibold text-slate-900">SMBFlow</span>
      </div>

      {error ? (
        <div className="flex items-center gap-2 text-red-600 text-sm bg-red-50 border border-red-200 rounded-lg p-4 max-w-md">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span>{error}</span>
        </div>
      ) : (
        <div className="flex items-center gap-2 text-slate-500 text-sm">
          <Loader2 className="w-4 h-4 text-blue-600 animate-spin" />
          <span>Completing authentication...</span>
        </div>
      )}
    </div>
  )
}
