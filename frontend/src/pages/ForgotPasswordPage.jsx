// frontend/src/pages/ForgotPasswordPage.jsx
// ─────────────────────────────────────────────────────────────────────────────
// Request a password-reset link. Security-first UX:
//   • The backend ALWAYS returns the same generic message for known and unknown
//     emails, so this page shows an identical confirmation either way and never
//     reveals whether an account exists.
//   • In an explicitly-enabled non-production dev environment with email
//     delivery unconfigured, the backend response may include `dev_reset_url`.
//     We render it in a clearly-labelled "Developer only" panel — never styled
//     as, or described as, a real delivered email.
// Uses an UNAUTHENTICATED client (no token), so its errors are handled inline
// and never trip the session-expiry path.
// ─────────────────────────────────────────────────────────────────────────────
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { AlertCircle, CheckCircle2, Loader2, ArrowLeft } from 'lucide-react'
import { createApiClient } from '../api/client'
import { createAuthService } from '../api/services/auth.service'

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState('')
  const [touched, setTouched] = useState(false)
  const [loading, setLoading] = useState(false)
  const [submitted, setSubmitted] = useState(false)
  const [devResetUrl, setDevResetUrl] = useState('')
  const [error, setError] = useState('')

  const emailValid = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)
  const canSubmit = emailValid && !loading

  async function handleSubmit(e) {
    e.preventDefault()
    setTouched(true)
    if (!canSubmit) return

    setLoading(true)
    setError('')
    try {
      const auth = createAuthService(createApiClient(null))
      const res = await auth.forgotPassword(email.trim())
      // Generic success — identical regardless of whether the account exists.
      setSubmitted(true)
      if (res && res.dev_reset_url) setDevResetUrl(res.dev_reset_url)
    } catch (err) {
      // A failure here is a transport/server problem, not an account signal.
      const msg = String(err?.message || '')
      setError(
        /network error/i.test(msg)
          ? 'Unable to reach the server. Check your connection and try again.'
          : 'Something went wrong. Please try again in a moment.'
      )
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
          {submitted ? (
            <>
              <div className="flex items-center gap-2.5 mb-3">
                <CheckCircle2 size={18} className="text-green-500 shrink-0" />
                <h1 className="text-lg font-semibold text-slate-900">Check your email</h1>
              </div>
              <p role="status" className="text-sm text-slate-600 leading-relaxed">
                If an account exists for that email, you'll receive password reset instructions.
              </p>

              {devResetUrl && (
                <div className="mt-5 rounded-lg border border-amber-300 bg-amber-50 p-3">
                  <p className="text-[11px] font-semibold uppercase tracking-wide text-amber-700 mb-1">
                    Developer only · not a real email
                  </p>
                  <p className="text-xs text-amber-800 mb-2 leading-relaxed">
                    Email delivery isn't configured in this environment, so the reset
                    link is shown here for local testing.
                  </p>
                  <a
                    href={devResetUrl}
                    className="text-xs font-medium text-blue-700 underline break-all"
                  >
                    {devResetUrl}
                  </a>
                </div>
              )}

              <Link
                to="/auth"
                className="mt-6 inline-flex items-center gap-1.5 text-sm font-medium text-blue-600 hover:text-blue-700"
              >
                <ArrowLeft size={14} /> Return to sign in
              </Link>
            </>
          ) : (
            <>
              <h1 className="text-lg font-semibold text-slate-900 mb-1">Reset your password</h1>
              <p className="text-sm text-slate-500 mb-6">
                Enter your account email and we'll send you a reset link.
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
                <div>
                  <label htmlFor="fp-email" className="block text-xs font-medium text-slate-700 mb-1.5">
                    Email address
                  </label>
                  <input
                    id="fp-email"
                    type="email"
                    value={email}
                    onChange={e => { setEmail(e.target.value); setError('') }}
                    onBlur={() => setTouched(true)}
                    placeholder="you@company.com"
                    autoComplete="email"
                    autoFocus
                    aria-invalid={touched && !emailValid}
                    aria-describedby={touched && !emailValid ? 'fp-email-error' : undefined}
                    className={`w-full px-3 py-2 text-sm border rounded-lg bg-white text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 transition-colors ${
                      touched && !emailValid
                        ? 'border-red-300 focus:ring-red-500/20 focus:border-red-400'
                        : 'border-slate-200 focus:ring-blue-500/20 focus:border-blue-500'
                    }`}
                  />
                  {touched && !emailValid && (
                    <p id="fp-email-error" className="mt-1 text-xs text-red-600">Enter a valid email address.</p>
                  )}
                </div>

                <button
                  type="submit"
                  disabled={!canSubmit}
                  className="w-full py-2.5 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center justify-center gap-2"
                >
                  {loading ? (<><Loader2 size={15} className="animate-spin" />Sending...</>) : 'Send reset link'}
                </button>
              </form>

              <Link
                to="/auth"
                className="mt-6 inline-flex items-center gap-1.5 text-sm font-medium text-blue-600 hover:text-blue-700"
              >
                <ArrowLeft size={14} /> Back to sign in
              </Link>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
