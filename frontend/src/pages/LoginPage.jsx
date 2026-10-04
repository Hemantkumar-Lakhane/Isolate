// frontend/src/pages/LoginPage.jsx
// ─────────────────────────────────────────────────────────────────────────────
// Approved Figma login presentation, wired to the REAL backend & Supabase Auth.
//   • Supports direct email/password sign-in and Supabase Google OAuth.
//   • Role authority is the backend: super_admin / platform_admin → /admin, org_user → /dashboard.
// ─────────────────────────────────────────────────────────────────────────────
import { useState, useEffect } from 'react'
import { Link, useNavigate, useLocation } from 'react-router-dom'
import { Eye, EyeOff, AlertCircle, Info, Loader2 } from 'lucide-react'
import { useAuth } from '../contexts/AuthContext'
import { createApiClient } from '../api/client'
import { createAuthService } from '../api/services/auth.service'

function classifyLoginError(err) {
  const status = err?.status
  const msg = String(err?.message || '')
  if (status === 401 && /disabled|deactivat/i.test(msg)) {
    return 'This account has been deactivated. Contact your administrator for access.'
  }
  if (status === 401) return 'Incorrect email or password. Please try again.'
  if (status === 422) return 'Please enter a valid email and password.'
  if (status >= 500) return 'Something went wrong on our end. Please try again in a moment.'
  if (/network error/i.test(msg)) {
    return 'Unable to reach the server. Check your connection and try again.'
  }
  return msg || 'Unable to sign in right now. Please try again.'
}

function GoogleIcon() {
  return (
    <svg className="w-4 h-4" viewBox="0 0 24 24" aria-hidden="true">
      <path
        fill="#4285F4"
        d="M23.745 12.27c0-.7-.06-1.4-.19-2.07H12v4.51h6.6c-.29 1.52-1.14 2.82-2.4 3.68v3.05h3.88c2.27-2.09 3.665-5.17 3.665-9.17z"
      />
      <path
        fill="#34A853"
        d="M12 24c3.24 0 5.95-1.08 7.93-2.91l-3.88-3.05c-1.08.72-2.45 1.16-4.05 1.16-3.12 0-5.77-2.1-6.72-4.93H1.29v3.14C3.26 21.3 7.31 24 12 24z"
      />
      <path
        fill="#FBBC05"
        d="M5.28 14.27c-.25-.72-.38-1.49-.38-2.27s.13-1.55.38-2.27V6.59H1.29C.47 8.22 0 10.06 0 12s.47 3.78 1.29 5.41l3.99-3.14z"
      />
      <path
        fill="#EA4335"
        d="M12 4.75c1.77 0 3.35.61 4.6 1.8l3.42-3.42C17.95 1.19 15.24 0 12 0 7.31 0 3.26 2.7 1.29 6.59l3.99 3.14c.95-2.83 3.6-4.98 6.72-4.98z"
      />
    </svg>
  )
}

export default function LoginPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const { user, token, loading: authLoading, login, sessionExpired, clearSessionExpired, supabase } = useAuth()

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [loading, setLoading] = useState(false)
  const [googleLoading, setGoogleLoading] = useState(false)
  const [error, setError] = useState('')
  const [touched, setTouched] = useState({ email: false, password: false })

  useEffect(() => {
    if (!authLoading && token && user) {
      if (user.requires_onboarding) {
        navigate('/auth/signup', { replace: true })
        return
      }
      const from = location.state?.from?.pathname
      const isAdmin = user.role === 'super_admin' || user.role === 'platform_admin'
      navigate(from || (isAdmin ? '/admin/copilot' : '/dashboard'), { replace: true })
    }
  }, [token, user, authLoading, navigate, location.state])

  if (authLoading) {
    return (
      <div className="min-h-screen bg-slate-50 flex flex-col items-center justify-center p-4">
        <div className="flex items-center gap-2.5 mb-4">
          <div className="w-9 h-9 rounded-xl bg-blue-600 flex items-center justify-center">
            <span className="text-white font-bold text-sm">S</span>
          </div>
          <span className="text-xl font-semibold text-slate-900">SMBFlow</span>
        </div>
        <div className="flex items-center gap-2 text-slate-500 text-sm">
          <Loader2 className="w-4 h-4 text-blue-600 animate-spin" />
          <span>Verifying authentication...</span>
        </div>
      </div>
    )
  }

  const emailValid = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)
  const passwordValid = password.length >= 6
  const canSubmit = emailValid && passwordValid && !loading && !googleLoading

  const roleHome = (role) =>
    role === 'super_admin' || role === 'platform_admin' ? '/admin/copilot' : '/dashboard'

  async function handleGoogleLogin() {
    if (!supabase) {
      setError('Supabase authentication client is not configured. Please check your setup.')
      return
    }
    setGoogleLoading(true)
    setError('')
    clearSessionExpired()
    try {
      const { error: oauthError } = await supabase.auth.signInWithOAuth({
        provider: 'google',
        options: {
          redirectTo: `${window.location.origin}/auth/callback`,
        },
      })
      if (oauthError) throw oauthError
    } catch (err) {
      setError(classifyLoginError(err))
      setGoogleLoading(false)
    }
  }

  async function handleSubmit(e) {
    e.preventDefault()
    setTouched({ email: true, password: true })
    if (!canSubmit) return

    setLoading(true)
    setError('')
    clearSessionExpired()
    try {
      const authApi = createAuthService(createApiClient(null))
      const { access_token, user } = await authApi.login(email.trim(), password)

      const bound = createAuthService(createApiClient(access_token))
      const profile = await bound.me().catch(() => user)

      login(access_token, profile)

      const from = location.state?.from?.pathname
      navigate(from || roleHome(profile.role), { replace: true })
    } catch (err) {
      setError(classifyLoginError(err))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center p-4">
      <div className="w-full max-w-sm">
        {/* Logo */}
        <div className="flex items-center gap-2.5 justify-center mb-8">
          <div className="w-9 h-9 rounded-xl bg-blue-600 flex items-center justify-center">
            <span className="text-white font-bold text-sm">S</span>
          </div>
          <span className="text-xl font-semibold text-slate-900">SMBFlow</span>
        </div>

        <div className="bg-white border border-slate-200 rounded-2xl p-8 shadow-sm">
          <h1 className="text-lg font-semibold text-slate-900 mb-1">Sign in to SMBFlow</h1>
          <p className="text-sm text-slate-500 mb-6">
            Access your workspace using your account credentials.
          </p>

          {/* Session-expiry notice */}
          {sessionExpired && !error && (
            <div
              role="status"
              className="flex items-start gap-2.5 bg-blue-50 border border-blue-200 rounded-lg px-4 py-3 mb-4"
            >
              <Info size={15} className="text-blue-500 shrink-0 mt-0.5" />
              <p className="text-sm text-blue-700">Your session has expired. Please sign in again.</p>
            </div>
          )}

          {/* Error banner */}
          {error && (
            <div
              role="alert"
              className="flex items-start gap-2.5 bg-red-50 border border-red-200 rounded-lg px-4 py-3 mb-4"
            >
              <AlertCircle size={15} className="text-red-500 shrink-0 mt-0.5" />
              <p className="text-sm text-red-700">{error}</p>
            </div>
          )}

          {/* Google OAuth Button */}
          <button
            type="button"
            onClick={handleGoogleLogin}
            disabled={googleLoading || loading}
            aria-label="Continue with Google"
            className="w-full py-2.5 px-4 bg-white border border-slate-200 rounded-lg text-slate-700 text-sm font-medium hover:bg-slate-50 hover:border-slate-300 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center justify-center gap-2 mb-5 shadow-2xs"
          >
            {googleLoading ? (
              <>
                <Loader2 size={16} className="animate-spin text-slate-500" />
                <span>Connecting to Google...</span>
              </>
            ) : (
              <>
                <GoogleIcon />
                <span>Continue with Google</span>
              </>
            )}
          </button>

          {/* Divider */}
          <div className="relative flex items-center justify-center mb-5">
            <div className="border-t border-slate-200 w-full" />
            <span className="bg-white px-3 text-xs text-slate-400 font-medium uppercase tracking-wider absolute">
              or
            </span>
          </div>

          <form onSubmit={handleSubmit} noValidate className="space-y-4">
            {/* Email */}
            <div>
              <label htmlFor="login-email" className="block text-xs font-medium text-slate-700 mb-1.5">
                Email address
              </label>
              <input
                id="login-email"
                type="email"
                value={email}
                onChange={e => { setEmail(e.target.value); setError('') }}
                onBlur={() => setTouched(t => ({ ...t, email: true }))}
                placeholder="you@company.com"
                autoComplete="email"
                autoFocus
                aria-invalid={touched.email && !emailValid}
                aria-describedby={touched.email && !emailValid ? 'login-email-error' : undefined}
                className={`w-full px-3 py-2 text-sm border rounded-lg bg-white text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 transition-colors ${
                  touched.email && !emailValid
                    ? 'border-red-300 focus:ring-red-500/20 focus:border-red-400'
                    : 'border-slate-200 focus:ring-blue-500/20 focus:border-blue-500'
                }`}
              />
              {touched.email && !emailValid && (
                <p id="login-email-error" className="mt-1 text-xs text-red-600">Enter a valid email address.</p>
              )}
            </div>

            {/* Password */}
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <label htmlFor="login-password" className="block text-xs font-medium text-slate-700">Password</label>
                <Link to="/auth/forgot-password" className="text-xs font-medium text-blue-600 hover:text-blue-700">
                  Forgot password?
                </Link>
              </div>
              <div className="relative">
                <input
                  id="login-password"
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={e => { setPassword(e.target.value); setError('') }}
                  onBlur={() => setTouched(t => ({ ...t, password: true }))}
                  placeholder="••••••••"
                  autoComplete="current-password"
                  aria-invalid={touched.password && !passwordValid}
                  aria-describedby={touched.password && !passwordValid ? 'login-password-error' : undefined}
                  className={`w-full px-3 py-2 pr-10 text-sm border rounded-lg bg-white text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 transition-colors ${
                    touched.password && !passwordValid
                      ? 'border-red-300 focus:ring-red-500/20 focus:border-red-400'
                      : 'border-slate-200 focus:ring-blue-500/20 focus:border-blue-500'
                  }`}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(v => !v)}
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                  aria-pressed={showPassword}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 transition-colors"
                >
                  {showPassword ? <EyeOff size={15} /> : <Eye size={15} />}
                </button>
              </div>
              {touched.password && !passwordValid && (
                <p id="login-password-error" className="mt-1 text-xs text-red-600">Password must be at least 6 characters.</p>
              )}
            </div>

            <button
              type="submit"
              disabled={!canSubmit}
              className="w-full py-2.5 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center justify-center gap-2"
            >
              {loading ? (
                <>
                  <Loader2 size={15} className="animate-spin" />
                  Signing in...
                </>
              ) : 'Sign in'}
            </button>
          </form>

          <p className="text-center text-sm text-slate-500 mt-6">
            New to SMBFlow?{' '}
            <Link to="/auth/signup" className="font-medium text-blue-600 hover:text-blue-700">
              Create an account
            </Link>
          </p>
        </div>

        <p className="text-center text-xs text-slate-400 mt-4">
          SMBFlow — AI Workflow Orchestration for SMBs
        </p>
      </div>
    </div>
  )
}
