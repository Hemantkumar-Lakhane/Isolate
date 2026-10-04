// frontend/src/pages/ResetPasswordPage.jsx
// ─────────────────────────────────────────────────────────────────────────────
// Set a new password using a single-use token from the reset link
// (?token=...). Security/UX notes:
//   • The token comes from the query string; it is a single-use reset
//     credential, never a password, and is never persisted by the client.
//   • The backend returns ONE generic error for any invalid / expired / used
//     token, so we don't try to distinguish those states (doing so would leak
//     token state). We show that single message.
//   • Missing/empty token → immediate invalid state without calling the API.
//   • Password policy mirrors the backend: minimum 8 characters + confirm match.
// Uses an UNAUTHENTICATED client (no token) — errors are handled inline and
// never trip the session-expiry path.
// ─────────────────────────────────────────────────────────────────────────────
import { useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { Eye, EyeOff, AlertCircle, CheckCircle2, Loader2, Check } from 'lucide-react'
import { createApiClient } from '../api/client'
import { createAuthService } from '../api/services/auth.service'

const MIN_LEN = 8

export default function ResetPasswordPage() {
  const [params] = useSearchParams()
  const token = (params.get('token') || '').trim()

  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [showPw, setShowPw] = useState(false)
  const [touched, setTouched] = useState({ password: false, confirm: false })
  const [loading, setLoading] = useState(false)
  const [done, setDone] = useState(false)
  const [error, setError] = useState('')

  const lengthOk = password.length >= MIN_LEN
  const matchOk = confirm.length > 0 && password === confirm
  const canSubmit = !!token && lengthOk && matchOk && !loading

  async function handleSubmit(e) {
    e.preventDefault()
    setTouched({ password: true, confirm: true })
    if (!canSubmit) return

    setLoading(true)
    setError('')
    try {
      const auth = createAuthService(createApiClient(null))
      await auth.resetPassword(token, password)
      setDone(true)
    } catch (err) {
      const status = err?.status
      const msg = String(err?.message || '')
      if (status === 400) {
        // Generic invalid/expired/used — matches backend wording, no state leak.
        setError('This reset link is invalid or has expired. Request a new one to continue.')
      } else if (status === 422) {
        setError(`Password must be at least ${MIN_LEN} characters.`)
      } else if (/network error/i.test(msg)) {
        setError('Unable to reach the server. Check your connection and try again.')
      } else if (status >= 500) {
        setError('Something went wrong on our end. Please try again in a moment.')
      } else {
        setError('Unable to reset your password right now. Please try again.')
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center p-4">
      <div className="w-full max-w-sm">
        <div className="flex items-center gap-2.5 justify-center mb-8">
          <div className="w-9 h-9 rounded-xl bg-blue-600 flex items-center justify-center">
            <span className="text-white font-bold text-sm">S</span>
          </div>
          <span className="text-xl font-semibold text-slate-900">SMBFlow</span>
        </div>

        <div className="bg-white border border-slate-200 rounded-2xl p-8 shadow-sm">
          {done ? (
            <>
              <div className="flex items-center gap-2.5 mb-3">
                <CheckCircle2 size={18} className="text-green-500 shrink-0" />
                <h1 className="text-lg font-semibold text-slate-900">Password updated</h1>
              </div>
              <p role="status" className="text-sm text-slate-600 leading-relaxed">
                Your password has been updated.
              </p>
              <Link
                to="/auth"
                className="mt-6 block w-full text-center py-2.5 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 transition-colors"
              >
                Return to sign in
              </Link>
            </>
          ) : !token ? (
            <>
              <div className="flex items-center gap-2.5 mb-3">
                <AlertCircle size={18} className="text-red-500 shrink-0" />
                <h1 className="text-lg font-semibold text-slate-900">Invalid reset link</h1>
              </div>
              <p className="text-sm text-slate-600 leading-relaxed">
                This reset link is invalid or has expired. Request a new one to continue.
              </p>
              <Link
                to="/auth/forgot-password"
                className="mt-6 block w-full text-center py-2.5 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 transition-colors"
              >
                Request a new link
              </Link>
            </>
          ) : (
            <>
              <h1 className="text-lg font-semibold text-slate-900 mb-1">Choose a new password</h1>
              <p className="text-sm text-slate-500 mb-6">
                Enter a new password for your account.
              </p>

              {error && (
                <div
                  role="alert"
                  className="flex items-start gap-2.5 bg-red-50 border border-red-200 rounded-lg px-4 py-3 mb-4"
                >
                  <AlertCircle size={15} className="text-red-500 shrink-0 mt-0.5" />
                  <p className="text-sm text-red-700">{error}</p>
                </div>
              )}

              <form onSubmit={handleSubmit} noValidate className="space-y-4">
                {/* New password */}
                <div>
                  <label htmlFor="rp-password" className="block text-xs font-medium text-slate-700 mb-1.5">
                    New password
                  </label>
                  <div className="relative">
                    <input
                      id="rp-password"
                      type={showPw ? 'text' : 'password'}
                      value={password}
                      onChange={e => { setPassword(e.target.value); setError('') }}
                      onBlur={() => setTouched(t => ({ ...t, password: true }))}
                      placeholder="••••••••"
                      autoComplete="new-password"
                      autoFocus
                      aria-invalid={touched.password && !lengthOk}
                      aria-describedby="rp-password-req"
                      className={`w-full px-3 py-2 pr-10 text-sm border rounded-lg bg-white text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 transition-colors ${
                        touched.password && !lengthOk
                          ? 'border-red-300 focus:ring-red-500/20 focus:border-red-400'
                          : 'border-slate-200 focus:ring-blue-500/20 focus:border-blue-500'
                      }`}
                    />
                    <button
                      type="button"
                      onClick={() => setShowPw(v => !v)}
                      aria-label={showPw ? 'Hide password' : 'Show password'}
                      aria-pressed={showPw}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 transition-colors"
                    >
                      {showPw ? <EyeOff size={15} /> : <Eye size={15} />}
                    </button>
                  </div>
                  <p id="rp-password-req" className="mt-1.5 text-xs flex items-center gap-1.5">
                    <Check size={12} className={lengthOk ? 'text-green-500' : 'text-slate-300'} />
                    <span className={lengthOk ? 'text-slate-600' : 'text-slate-400'}>
                      At least {MIN_LEN} characters
                    </span>
                  </p>
                </div>

                {/* Confirm */}
                <div>
                  <label htmlFor="rp-confirm" className="block text-xs font-medium text-slate-700 mb-1.5">
                    Confirm new password
                  </label>
                  <input
                    id="rp-confirm"
                    type={showPw ? 'text' : 'password'}
                    value={confirm}
                    onChange={e => { setConfirm(e.target.value); setError('') }}
                    onBlur={() => setTouched(t => ({ ...t, confirm: true }))}
                    placeholder="••••••••"
                    autoComplete="new-password"
                    aria-invalid={touched.confirm && !matchOk}
                    aria-describedby={touched.confirm && !matchOk ? 'rp-confirm-error' : undefined}
                    className={`w-full px-3 py-2 text-sm border rounded-lg bg-white text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 transition-colors ${
                      touched.confirm && !matchOk
                        ? 'border-red-300 focus:ring-red-500/20 focus:border-red-400'
                        : 'border-slate-200 focus:ring-blue-500/20 focus:border-blue-500'
                    }`}
                  />
                  {touched.confirm && !matchOk && (
                    <p id="rp-confirm-error" className="mt-1 text-xs text-red-600">Passwords do not match.</p>
                  )}
                </div>

                <button
                  type="submit"
                  disabled={!canSubmit}
                  className="w-full py-2.5 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center justify-center gap-2"
                >
                  {loading ? (<><Loader2 size={15} className="animate-spin" />Updating...</>) : 'Update password'}
                </button>
              </form>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
