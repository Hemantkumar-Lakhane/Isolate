// frontend/src/pages/VerifyEmailPage.jsx
// ─────────────────────────────────────────────────────────────────────────────
// Enterprise Email Verification Screen for SMBFlow
// Features:
//   • Dual-theme support (light slate / dark obsidian)
//   • Real-time verification listener & auto-redirect
//   • Resend verification link with cooldown timer & rate limiting
//   • Seamless integration with Supabase Auth & platform backend
// ─────────────────────────────────────────────────────────────────────────────

import { useState, useEffect, useCallback } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { Mail, ArrowRight, RefreshCw, CheckCircle2, AlertCircle, ShieldCheck } from 'lucide-react'
import { useAuth } from '../contexts/AuthContext'
import { createApiClient } from '../api/client'

export default function VerifyEmailPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const { user, token, supabase } = useAuth()

  // Get email from URL params, auth context, or fallback
  const emailParam = searchParams.get('email') || user?.email || 'your-email@company.com'

  const [resending, setResending] = useState(false)
  const [resendSuccess, setResendSuccess] = useState(false)
  const [resendError, setResendError] = useState('')
  const [cooldown, setCooldown] = useState(0)

  // Redirect if user is already authenticated & verified
  useEffect(() => {
    if (token && user && !user.requires_onboarding) {
      navigate('/dashboard', { replace: true })
    }
  }, [token, user, navigate])

  // Cooldown countdown timer for resending
  useEffect(() => {
    if (cooldown <= 0) return
    const timer = setInterval(() => {
      setCooldown(prev => Math.max(0, prev - 1))
    }, 1000)
    return () => clearInterval(timer)
  }, [cooldown])

  // Real-time polling to detect verification from other tab/device
  useEffect(() => {
    if (!supabase) return

    const checkInterval = setInterval(async () => {
      try {
        const { data: { session } } = await supabase.auth.getSession()
        if (session && session.user && session.user.email_confirmed_at) {
          navigate('/dashboard', { replace: true })
        }
      } catch (_) {}
    }, 4000)

    const { data: { subscription } } = supabase.auth.onAuthStateChange((event, session) => {
      if (event === 'SIGNED_IN' && session?.user) {
        navigate('/dashboard', { replace: true })
      }
    })

    return () => {
      clearInterval(checkInterval)
      subscription?.unsubscribe()
    }
  }, [supabase, navigate])

  // Handle Resend Verification Email
  const handleResend = useCallback(async () => {
    if (cooldown > 0 || resending) return

    setResending(true)
    setResendError('')
    setResendSuccess(false)

    try {
      // 1. Try Supabase Auth resend if client is configured
      if (supabase) {
        const { error } = await supabase.auth.resend({
          type: 'signup',
          email: emailParam,
          options: {
            emailRedirectTo: `${window.location.origin}/auth/callback`,
          },
        })
        if (error) throw error
      } else {
        // 2. Fallback to SMBFlow platform API
        const api = createApiClient(null)
        await api.post('/auth/resend-verification', { email: emailParam })
      }

      setResendSuccess(true)
      setCooldown(60) // 60s cooldown
    } catch (err) {
      console.error('Failed to resend verification email:', err)
      setResendError(err.message || 'Unable to resend verification email. Please try again in a moment.')
    } finally {
      setResending(false)
    }
  }, [cooldown, resending, supabase, emailParam])

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-[#0b0f17] flex flex-col items-center justify-center p-4 font-sans text-slate-900 dark:text-slate-100 transition-colors">
      {/* ── Brand Logo ──────────────────────────────────────────────────────── */}
      <div className="flex items-center gap-2.5 mb-8">
        <div className="w-10 h-10 rounded-2xl bg-blue-600 flex items-center justify-center shadow-md shadow-blue-500/20">
          <span className="text-white font-bold text-base">S</span>
        </div>
        <div className="flex flex-col">
          <span className="text-xl font-bold tracking-tight text-slate-900 dark:text-white">SMBFlow</span>
          <span className="text-[10px] font-medium text-slate-400 -mt-1 tracking-wide uppercase font-mono">Autonomous Engine</span>
        </div>
      </div>

      {/* ── Main Verification Card ────────────────────────────────────────── */}
      <div className="w-full max-w-md bg-white dark:bg-[#121826] border border-slate-200 dark:border-[#233048] rounded-3xl p-8 sm:p-10 shadow-xl dark:shadow-2xl relative overflow-hidden animate-in fade-in zoom-in-95 duration-200">
        {/* Decorative subtle header glow */}
        <div className="absolute -top-12 left-1/2 -translate-x-1/2 w-40 h-40 bg-blue-500/10 rounded-full blur-2xl pointer-events-none" />

        {/* Mail Icon Badge */}
        <div className="flex justify-center mb-6">
          <div className="w-16 h-16 rounded-2xl bg-blue-50 dark:bg-blue-950/50 border border-blue-200 dark:border-blue-900/60 flex items-center justify-center shadow-inner">
            <Mail className="w-8 h-8 text-blue-600 dark:text-blue-400" />
          </div>
        </div>

        {/* Text Header */}
        <div className="text-center space-y-2 mb-8">
          <h1 className="text-2xl font-bold text-slate-900 dark:text-white tracking-tight">
            Verify your account
          </h1>
          <p className="text-sm text-slate-500 dark:text-slate-400 leading-relaxed max-w-xs mx-auto">
            We have sent you an email with a link to verify your email address. Please check your inbox and click on the link to verify your email.
          </p>
        </div>

        {/* Highlighted Email Target Pill */}
        <div className="mb-6 p-3 bg-slate-50 dark:bg-[#182234] border border-slate-200 dark:border-[#233048] rounded-2xl flex items-center justify-between gap-3 text-xs">
          <div className="flex items-center gap-2 min-w-0">
            <ShieldCheck className="w-4 h-4 text-emerald-500 shrink-0" />
            <span className="font-mono text-slate-700 dark:text-slate-300 font-semibold truncate">
              {emailParam}
            </span>
          </div>
          <Link
            to="/auth/signup"
            className="text-blue-600 dark:text-blue-400 hover:underline font-medium text-[11px] shrink-0"
          >
            Change
          </Link>
        </div>

        {/* Feedback Alerts */}
        {resendSuccess && (
          <div className="mb-5 p-3.5 bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-900 rounded-2xl text-xs text-emerald-700 dark:text-emerald-300 flex items-center gap-2.5 animate-fade-in">
            <CheckCircle2 className="w-4 h-4 shrink-0 text-emerald-600" />
            <span>A fresh verification link was dispatched to your inbox.</span>
          </div>
        )}

        {resendError && (
          <div className="mb-5 p-3.5 bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-900 rounded-2xl text-xs text-rose-700 dark:text-rose-300 flex items-center gap-2.5 animate-fade-in">
            <AlertCircle className="w-4 h-4 shrink-0 text-rose-600" />
            <span>{resendError}</span>
          </div>
        )}

        {/* Resend Action Section */}
        <div className="space-y-4">
          <p className="text-xs text-center text-slate-500 dark:text-slate-400">
            Didn't receive the email? Click the button below to resend the email.
          </p>

          <button
            type="button"
            onClick={handleResend}
            disabled={resending || cooldown > 0}
            className="w-full py-3.5 px-5 rounded-2xl bg-blue-600 hover:bg-blue-500 disabled:bg-slate-200 dark:disabled:bg-slate-800 disabled:text-slate-400 text-white font-semibold text-sm transition-all duration-150 flex items-center justify-center gap-2 shadow-sm shadow-blue-500/20 cursor-pointer disabled:cursor-not-allowed"
          >
            {resending ? (
              <>
                <RefreshCw className="w-4 h-4 animate-spin" />
                <span>Sending verification link...</span>
              </>
            ) : cooldown > 0 ? (
              <span>Resend email in {cooldown}s</span>
            ) : (
              <span>Resend verification email</span>
            )}
          </button>
        </div>

        {/* Footer Navigation */}
        <div className="mt-8 pt-6 border-t border-slate-100 dark:border-[#1a2336] text-center text-xs text-slate-500 dark:text-slate-400">
          <span>Already verified? </span>
          <Link
            to={`/auth?verified=true&email=${encodeURIComponent(emailParam)}`}
            className="font-semibold text-blue-600 dark:text-blue-400 hover:underline inline-flex items-center gap-1"
          >
            <span>Sign In</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </Link>
        </div>
      </div>

      {/* Security note footer */}
      <p className="text-xs text-slate-400 dark:text-slate-500 mt-6 text-center font-mono">
        Secured with End-to-End Tenant Isolation · SMBFlow Auth Vault
      </p>
    </div>
  )
}
