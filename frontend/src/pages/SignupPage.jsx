// frontend/src/pages/SignupPage.jsx
// ─────────────────────────────────────────────────────────────────────────────
// Multi-Step B2B SaaS Workspace Onboarding Wizard
// Supports:
//   • Step 1: Company Website (with Next & optional Skip)
//   • Step 2: Tell Us About Your Company (with Back, Next / Create my account, & Other custom tag)
//   • Step 3: Administrator Credentials (with Back & Create my account for Email Signups)
// ─────────────────────────────────────────────────────────────────────────────
import { useState, useEffect } from 'react'
import { Link, useNavigate, useLocation } from 'react-router-dom'
import { Eye, EyeOff, AlertCircle, Loader2, ChevronDown } from 'lucide-react'
import { useAuth } from '../contexts/AuthContext'
import { createApiClient } from '../api/client'
import { createAuthService } from '../api/services/auth.service'

const INDUSTRY_OPTIONS = [
  { label: 'SaaS / Technology', value: 'saas' },
  { label: 'Healthcare & Life Sciences', value: 'healthcare' },
  { label: 'E-commerce & Retail', value: 'ecommerce' },
  { label: 'Financial Services & FinTech', value: 'finance' },
  { label: 'Education & EdTech', value: 'education' },
  { label: 'Marketing & Creative Agency', value: 'marketing' },
  { label: 'Professional & Legal Services', value: 'services' },
  { label: 'Manufacturing & Logistics', value: 'logistics' },
  { label: 'Real Estate & Construction', value: 'realestate' },
  { label: 'Other (Specify below)', value: 'other' },
]

const COMPANY_SIZE_OPTIONS = [
  { label: '1-10 employees', value: '1-10' },
  { label: '11-50 employees', value: '11-50' },
  { label: '51-200 employees', value: '51-200' },
  { label: '201-500 employees', value: '201-500' },
  { label: '500+ employees', value: '500+' },
]

function classifySignupError(err) {
  const status = err?.status
  const msg = String(err?.message || err?.error_description || '')
  if (status === 409 || /already registered|already exists|user_already_exists/i.test(msg)) {
    return 'An account with that email already exists. Please sign in instead.'
  }
  if (status === 422) return 'Please check all required fields and try again.'
  if (status >= 500) return 'Something went wrong on our end. Please try again in a moment.'
  if (/network error/i.test(msg)) {
    return 'Unable to reach the server. Check your connection and try again.'
  }
  return msg || 'Unable to complete your onboarding right now. Please try again.'
}

function GoogleIcon() {
  return (
    <svg className="w-4 h-4 shrink-0" viewBox="0 0 24 24" aria-hidden="true">
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

function inferCompanyNameFromWebsite(url) {
  if (!url) return ''
  try {
    let clean = url.replace(/^https?:\/\//i, '').replace(/^www\./i, '').split('/')[0]
    let domain = clean.split('.')[0]
    if (domain && domain.length > 1) {
      return domain.charAt(0).toUpperCase() + domain.slice(1)
    }
  } catch (_) {}
  return ''
}

export default function SignupPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const { user, token, loading: authLoading, login, provisionWorkspace, supabase, clearSessionExpired } = useAuth()

  // Google first-login onboarding state detection
  const isGoogleOnboarding = Boolean(token && user && user.requires_onboarding)

  // Steps: 1 (Website) -> 2 (Company Details) -> 3 (Credentials if email signup)
  const [step, setStep] = useState(1)

  const [form, setForm] = useState({
    website: '',
    workspace: '',
    companySize: '11-50',
    industry: 'saas',
    customIndustry: '',
    fullName: user?.full_name || '',
    email: location.state?.email || user?.email || '',
    password: '',
  })

  useEffect(() => {
    if (!authLoading && token && user && !user.requires_onboarding) {
      const isAdmin = user.role === 'super_admin' || user.role === 'platform_admin'
      navigate(isAdmin ? '/admin' : '/dashboard', { replace: true })
    }
  }, [token, user, authLoading, navigate])

  useEffect(() => {
    if (user?.full_name && !form.fullName) {
      setForm(f => ({ ...f, fullName: user.full_name }))
    }
    if (user?.email && !form.email) {
      setForm(f => ({ ...f, email: user.email }))
    }
  }, [user, form.fullName, form.email])

  const [showPassword, setShowPassword] = useState(false)
  const [loading, setLoading] = useState(false)
  const [googleLoading, setGoogleLoading] = useState(false)
  const [error, setError] = useState('')
  const [fieldErrors, setFieldErrors] = useState({})

  const set = (k) => (e) => {
    setForm(f => ({ ...f, [k]: e.target.value }))
    setError('')
    setFieldErrors(fe => ({ ...fe, [k]: false }))
  }

  const resolvedIndustry = form.industry === 'other'
    ? (form.customIndustry.trim() || 'other')
    : (form.industry || 'saas')

  // Step 1 -> Step 2
  const handleStep1Next = (e) => {
    if (e) e.preventDefault()
    if (!form.website.trim()) {
      setError('Please enter your company website.')
      setFieldErrors({ website: true })
      return
    }
    setError('')
    setFieldErrors({})
    if (!form.workspace.trim()) {
      const inferred = inferCompanyNameFromWebsite(form.website)
      if (inferred) {
        setForm(f => ({ ...f, workspace: inferred }))
      }
    }
    setStep(2)
  }

  // Skip Step 1 (allow continuing directly to company details)
  const handleSkipStep1 = () => {
    setError('')
    setFieldErrors({})
    setStep(2)
  }

  // Step 2 Next or Create Account (if Google user)
  const handleStep2Submit = async (e) => {
    e.preventDefault()
    const errs = {}
    if (!form.workspace.trim()) errs.workspace = true
    if (!form.companySize) errs.companySize = true
    if (!form.industry) errs.industry = true
    if (form.industry === 'other' && !form.customIndustry.trim()) errs.customIndustry = true

    if (Object.keys(errs).length > 0) {
      setFieldErrors(errs)
      setError('Please fill in the required company details.')
      return
    }
    setError('')
    setFieldErrors({})

    if (isGoogleOnboarding) {
      setLoading(true)
      try {
        const payload = {
          full_name: form.fullName.trim() || user.full_name || 'Admin',
          workspace_name: form.workspace.trim(),
          industry: resolvedIndustry,
          website: form.website.trim() || null,
          company_size: form.companySize || null,
        }
        await provisionWorkspace(payload)
        navigate('/dashboard', { replace: true })
      } catch (err) {
        setError(classifySignupError(err))
      } finally {
        setLoading(false)
      }
    } else {
      setStep(3)
    }
  }

  // Step 3 (Email Signup) -> Complete Registration & open Dashboard
  async function handleEmailSignupSubmit(e) {
    e.preventDefault()
    const errs = {}
    if (!form.fullName.trim()) errs.fullName = true
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email)) errs.email = true
    if (form.password.length < 6) errs.password = true

    if (Object.keys(errs).length > 0) {
      setFieldErrors(errs)
      setError('Please enter valid administrator credentials.')
      return
    }

    setLoading(true)
    setError('')
    setFieldErrors({})

    try {
      const authApi = createAuthService(createApiClient(null))
      const res = await authApi.signup({
        email: form.email.trim(),
        password: form.password,
        full_name: form.fullName.trim(),
        tenant_name: form.workspace.trim(),
        industry: resolvedIndustry,
        website: form.website.trim() || null,
        company_size: form.companySize || null,
      })

      const { access_token, user: signedUpUser } = res
      const bound = createAuthService(createApiClient(access_token))
      const profile = await bound.me().catch(() => signedUpUser)

      login(access_token, profile)
      navigate('/dashboard', { replace: true })
    } catch (err) {
      setError(classifySignupError(err))
    } finally {
      setLoading(false)
    }
  }

  // Google 1-Click OAuth
  async function handleGoogleSignup() {
    if (!supabase) {
      setError('Supabase authentication client is not configured.')
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
      setError(classifySignupError(err))
      setGoogleLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-[#fafafa] flex flex-col items-center justify-center p-4 font-sans text-slate-800 antialiased selection:bg-blue-100 selection:text-blue-900">
      
      {/* ── Brand Indicator ──────────────────────────────────────────────── */}
      <div className="mb-6 flex items-center gap-2.5">
        <div className="w-8 h-8 rounded-xl bg-slate-900 text-white flex items-center justify-center font-bold text-sm shadow-sm">
          S
        </div>
        <span className="text-lg font-bold text-slate-900 tracking-tight">SMBFlow</span>
      </div>

      <div className="w-full max-w-md">

        {/* ── Global Error Notification ──────────────────────────────────── */}
        {error && (
          <div className="mb-5 p-3.5 bg-rose-50 border border-rose-200 text-rose-800 rounded-2xl text-xs flex items-start gap-2.5 shadow-sm">
            <AlertCircle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
            <div className="flex-1 font-medium">{error}</div>
          </div>
        )}

        {/* ══════════════════════════════════════════════════════════════════
            STEP 1: COMPANY WEBSITE
            ══════════════════════════════════════════════════════════════════ */}
        {step === 1 && (
          <div className="flex flex-col items-center text-center">
            <h1 className="text-3xl font-extrabold text-slate-900 tracking-tight mb-3">
              Company website
            </h1>
            <p className="text-sm text-slate-500 mb-8 max-w-xs leading-relaxed">
              We'll analyze your website to speed up your sign-up.
            </p>

            <form onSubmit={handleStep1Next} className="w-full space-y-4">
              <div>
                <input
                  type="text"
                  value={form.website}
                  onChange={set('website')}
                  placeholder="www.website.com"
                  autoFocus
                  required
                  className={`w-full px-5 py-3.5 text-base rounded-2xl border ${
                    fieldErrors.website ? 'border-rose-400 bg-rose-50/20 ring-2 ring-rose-100' : 'border-slate-300 focus:border-blue-600 focus:ring-4 focus:ring-blue-100'
                  } transition-all text-slate-900 placeholder:text-slate-400 bg-white shadow-sm outline-none`}
                />
              </div>

              <button
                type="submit"
                className="w-full py-3.5 px-6 rounded-full bg-[#f1f3f5] hover:bg-slate-900 hover:text-white text-slate-700 font-semibold text-sm transition-all duration-200 cursor-pointer shadow-sm active:scale-[0.99]"
              >
                Next
              </button>

              <div className="text-center pt-1">
                <button
                  type="button"
                  onClick={handleSkipStep1}
                  className="text-xs text-slate-500 hover:text-slate-800 font-medium transition-colors cursor-pointer"
                >
                  Skip for now
                </button>
              </div>
            </form>

            {!isGoogleOnboarding && (
              <div className="w-full mt-6 pt-6 border-t border-slate-200/80">
                <button
                  type="button"
                  onClick={handleGoogleSignup}
                  disabled={googleLoading}
                  className="w-full py-3 px-4 rounded-full border border-slate-300 hover:bg-white hover:border-slate-400 bg-white text-slate-700 font-medium text-xs transition-all flex items-center justify-center gap-2.5 shadow-sm cursor-pointer"
                >
                  {googleLoading ? <Loader2 className="w-4 h-4 animate-spin text-blue-600" /> : <GoogleIcon />}
                  <span>Continue with Google</span>
                </button>

                <p className="text-xs text-slate-500 mt-5">
                  Already have an account?{' '}
                  <Link to="/auth" className="text-slate-900 font-bold hover:underline">
                    Sign in
                  </Link>
                </p>
              </div>
            )}
          </div>
        )}

        {/* ══════════════════════════════════════════════════════════════════
            STEP 2: TELL US ABOUT YOUR COMPANY
            ══════════════════════════════════════════════════════════════════ */}
        {step === 2 && (
          <div>
            <div className="text-center mb-6">
              <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 tracking-tight mb-2">
                Tell us about your company
              </h1>
              <p className="text-xs sm:text-sm text-slate-500 max-w-sm mx-auto leading-relaxed">
                Help us personalize your account and setup by providing a few details about where you work.
              </p>
            </div>

            <div className="bg-white border border-slate-200/90 rounded-3xl p-6 sm:p-7 shadow-sm">
              <form onSubmit={handleStep2Submit} className="space-y-4">
                
                {/* Company Name */}
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                    Company name <span className="text-rose-500">*</span>
                  </label>
                  <input
                    type="text"
                    value={form.workspace}
                    onChange={set('workspace')}
                    placeholder="Company name"
                    autoFocus
                    required
                    className={`w-full px-4 py-2.5 text-sm rounded-xl border ${
                      fieldErrors.workspace ? 'border-rose-400 bg-rose-50/20 ring-2 ring-rose-100' : 'border-slate-300 focus:border-blue-600 focus:ring-2 focus:ring-blue-100'
                    } transition-all text-slate-900 bg-white placeholder:text-slate-400 outline-none`}
                  />
                </div>

                {/* Company Website */}
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                    Company website
                  </label>
                  <input
                    type="text"
                    value={form.website}
                    onChange={set('website')}
                    placeholder="https://yourcompany.com"
                    className="w-full px-4 py-2.5 text-sm rounded-xl border border-slate-300 focus:border-blue-600 focus:ring-2 focus:ring-blue-100 transition-all text-slate-900 bg-white placeholder:text-slate-400 outline-none"
                  />
                </div>

                {/* Company Size */}
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                    Company size <span className="text-rose-500">*</span>
                  </label>
                  <div className="relative">
                    <select
                      value={form.companySize}
                      onChange={set('companySize')}
                      required
                      className={`w-full px-4 py-2.5 text-sm rounded-xl border ${
                        fieldErrors.companySize ? 'border-rose-400 bg-rose-50/20 ring-2 ring-rose-100' : 'border-slate-300 focus:border-blue-600 focus:ring-2 focus:ring-blue-100'
                      } transition-all text-slate-900 bg-white appearance-none pr-10 cursor-pointer outline-none`}
                    >
                      <option value="" disabled>Select</option>
                      {COMPANY_SIZE_OPTIONS.map(opt => (
                        <option key={opt.value} value={opt.value}>{opt.label}</option>
                      ))}
                    </select>
                    <ChevronDown className="w-4 h-4 text-slate-500 absolute right-3.5 top-1/2 -translate-y-1/2 pointer-events-none" />
                  </div>
                </div>

                {/* Industry Dropdown */}
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                    Industry <span className="text-rose-500">*</span>
                  </label>
                  <div className="relative">
                    <select
                      value={form.industry}
                      onChange={set('industry')}
                      required
                      className={`w-full px-4 py-2.5 text-sm rounded-xl border ${
                        fieldErrors.industry ? 'border-rose-400 bg-rose-50/20 ring-2 ring-rose-100' : 'border-slate-300 focus:border-blue-600 focus:ring-2 focus:ring-blue-100'
                      } transition-all text-slate-900 bg-white appearance-none pr-10 cursor-pointer outline-none`}
                    >
                      <option value="" disabled>Select industry</option>
                      {INDUSTRY_OPTIONS.map(opt => (
                        <option key={opt.value} value={opt.value}>{opt.label}</option>
                      ))}
                    </select>
                    <ChevronDown className="w-4 h-4 text-slate-500 absolute right-3.5 top-1/2 -translate-y-1/2 pointer-events-none" />
                  </div>
                </div>

                {/* Custom 'Other' Industry Tag Field */}
                {form.industry === 'other' && (
                  <div className="pt-1 animate-in fade-in slide-in-from-top-1 duration-150">
                    <label className="block text-xs font-semibold text-blue-700 mb-1.5">
                      Specify Industry / Tag <span className="text-rose-500">*</span>
                    </label>
                    <input
                      type="text"
                      value={form.customIndustry}
                      onChange={set('customIndustry')}
                      placeholder="e.g. EdTech, Biotech, Clean Energy, Legal Services..."
                      autoFocus
                      required
                      className={`w-full px-4 py-2.5 text-sm rounded-xl border ${
                        fieldErrors.customIndustry ? 'border-rose-400 bg-rose-50/20 ring-2 ring-rose-100' : 'border-blue-300 focus:border-blue-600 focus:ring-2 focus:ring-blue-100'
                      } transition-all text-slate-900 bg-blue-50/20 placeholder:text-slate-400 outline-none`}
                    />
                  </div>
                )}

                <div className="pt-2 flex items-center gap-3">
                  <button
                    type="button"
                    onClick={() => setStep(1)}
                    className="py-3.5 px-6 rounded-full bg-slate-100 hover:bg-slate-200 text-slate-700 font-semibold text-sm transition-all cursor-pointer"
                  >
                    Back
                  </button>

                  <button
                    type="submit"
                    disabled={loading}
                    className="flex-1 py-3.5 px-6 rounded-full bg-[#f1f3f5] hover:bg-slate-900 hover:text-white text-slate-700 font-semibold text-sm transition-all duration-200 cursor-pointer flex items-center justify-center gap-2 shadow-sm active:scale-[0.99]"
                  >
                    {loading ? (
                      <>
                        <Loader2 className="w-4 h-4 animate-spin" />
                        <span>{isGoogleOnboarding ? 'Completing setup...' : 'Saving...'}</span>
                      </>
                    ) : (
                      <span>{isGoogleOnboarding ? 'Complete setup' : 'Next'}</span>
                    )}
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}

        {/* ══════════════════════════════════════════════════════════════════
            STEP 3: ADMINISTRATOR ACCOUNT (Direct Email Registration only)
            ══════════════════════════════════════════════════════════════════ */}
        {step === 3 && (
          <div>
            <div className="text-center mb-6">
              <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 tracking-tight mb-2">
                Administrator Account
              </h1>
              <p className="text-xs sm:text-sm text-slate-500 max-w-sm mx-auto leading-relaxed">
                Create your primary administrative login to manage {form.workspace || 'your organization'}.
              </p>
            </div>

            <div className="bg-white border border-slate-200/90 rounded-3xl p-6 sm:p-7 shadow-sm">
              <form onSubmit={handleEmailSignupSubmit} className="space-y-4">
                {/* Full Name */}
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                    Your full name <span className="text-rose-500">*</span>
                  </label>
                  <input
                    type="text"
                    value={form.fullName}
                    onChange={set('fullName')}
                    placeholder="e.g. Alex Morgan"
                    autoFocus
                    required
                    className={`w-full px-4 py-2.5 text-sm rounded-xl border ${
                      fieldErrors.fullName ? 'border-rose-400 bg-rose-50/20 ring-2 ring-rose-100' : 'border-slate-300 focus:border-blue-600 focus:ring-2 focus:ring-blue-100'
                    } transition-all text-slate-900 bg-white placeholder:text-slate-400 outline-none`}
                  />
                </div>

                {/* Work Email */}
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                    Work email <span className="text-rose-500">*</span>
                  </label>
                  <input
                    type="email"
                    value={form.email}
                    onChange={set('email')}
                    placeholder="alex@company.com"
                    required
                    className={`w-full px-4 py-2.5 text-sm rounded-xl border ${
                      fieldErrors.email ? 'border-rose-400 bg-rose-50/20 ring-2 ring-rose-100' : 'border-slate-300 focus:border-blue-600 focus:ring-2 focus:ring-blue-100'
                    } transition-all text-slate-900 bg-white placeholder:text-slate-400 outline-none`}
                  />
                </div>

                {/* Password */}
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                    Password <span className="text-rose-500">*</span>
                  </label>
                  <div className="relative">
                    <input
                      type={showPassword ? 'text' : 'password'}
                      value={form.password}
                      onChange={set('password')}
                      placeholder="At least 6 characters"
                      required
                      className={`w-full px-4 py-2.5 pr-10 text-sm rounded-xl border ${
                        fieldErrors.password ? 'border-rose-400 bg-rose-50/20 ring-2 ring-rose-100' : 'border-slate-300 focus:border-blue-600 focus:ring-2 focus:ring-blue-100'
                      } transition-all text-slate-900 bg-white placeholder:text-slate-400 outline-none`}
                    />
                    <button
                      type="button"
                      onClick={() => setShowPassword(v => !v)}
                      className="absolute right-3.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 cursor-pointer"
                    >
                      {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                    </button>
                  </div>
                </div>

                <div className="pt-2 flex items-center gap-3">
                  <button
                    type="button"
                    onClick={() => setStep(2)}
                    className="py-3.5 px-6 rounded-full bg-slate-100 hover:bg-slate-200 text-slate-700 font-semibold text-sm transition-all cursor-pointer"
                  >
                    Back
                  </button>

                  <button
                    type="submit"
                    disabled={loading}
                    className="flex-1 py-3.5 px-6 rounded-full bg-slate-900 hover:bg-slate-800 text-white font-semibold text-sm transition-all duration-200 cursor-pointer flex items-center justify-center gap-2 shadow-sm active:scale-[0.99]"
                  >
                    {loading ? (
                      <>
                        <Loader2 className="w-4 h-4 animate-spin" />
                        <span>Creating account...</span>
                      </>
                    ) : (
                      <span>Create my account</span>
                    )}
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}

      </div>
    </div>
  )
}
