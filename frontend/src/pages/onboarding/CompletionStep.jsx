// frontend/src/pages/onboarding/CompletionStep.jsx
// ─────────────────────────────────────────────────────────────────────────────
// Step 7 (final) — Completion screen.
// Saves all onboarding data to the backend, then redirects to /dashboard.
// Shows a loading state while saving and a retry-able error if it fails.
// ─────────────────────────────────────────────────────────────────────────────
import { useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { CheckCircle2, AlertCircle, Loader2, ArrowRight } from 'lucide-react'
import { useOnboarding } from '../../contexts/OnboardingContext'
import { useAuth } from '../../contexts/AuthContext'

export default function CompletionStep() {
  const { data, saving, saveError, setSaving, setSaveError, clearPersistedState } = useOnboarding()
  const { user, provisionWorkspace, token, api } = useAuth()
  const navigate = useNavigate()
  const savedRef = useRef(false)

  const firstName = data.preferredName || user?.full_name?.split(' ')[0] || 'there'

  async function save() {
    if (savedRef.current) return
    savedRef.current = true
    setSaving(true)
    setSaveError('')

    try {
      // 1. Provision / update workspace — this is the canonical onboarding
      //    completion call that sets requires_onboarding: false on the backend.
      await provisionWorkspace({
        full_name: user?.full_name || data.preferredName,
        workspace_name: data.workspaceName,
        industry: data.industry,
      })

      // 2. Persist the extra profile fields (preferred name, role, goals,
      //    team size) to org profile_config via the /organizations/me/profile
      //    endpoint that already exists in the backend.
      //    OrgProfileUpdate schema uses: { name, industry, config }
      try {
        await api.put('/organizations/me/profile', {
          name: data.workspaceName,
          industry: data.industry,
          config: {
            preferred_name: data.preferredName,
            job_role: data.jobRole,
            team_size: data.teamSize,
            workflow_goals: data.goals || [],
          },
        })
      } catch (_) {
        // Non-critical — workspace provisioning already completed.
        // The extra profile fields are best-effort.
      }

      // 3. Clean up localStorage and redirect
      clearPersistedState()
      navigate('/dashboard', { replace: true })
    } catch (err) {
      savedRef.current = false
      const msg = err?.message || ''
      if (/already registered|already exists/i.test(msg)) {
        // Workspace already exists — safe to continue
        clearPersistedState()
        navigate('/dashboard', { replace: true })
        return
      }
      setSaveError('We couldn\'t save your setup. Please try again.')
    } finally {
      setSaving(false)
    }
  }

  // Auto-trigger save when the step mounts
  useEffect(() => {
    save()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // ── Saving state ──────────────────────────────────────────────────────────
  if (saving) {
    return (
      <div className="w-full max-w-md text-center">
        <div className="flex justify-center mb-6">
          <div className="w-16 h-16 rounded-2xl bg-blue-50 border border-blue-100 flex items-center justify-center">
            <Loader2 className="w-8 h-8 text-blue-600 animate-spin" strokeWidth={1.5} />
          </div>
        </div>
        <h1 className="text-xl font-semibold text-slate-900 mb-2">Setting up your workspace…</h1>
        <p className="text-sm text-slate-500">Just a moment while we save your preferences.</p>
      </div>
    )
  }

  // ── Error state ───────────────────────────────────────────────────────────
  if (saveError) {
    return (
      <div className="w-full max-w-md text-center">
        <div className="flex justify-center mb-6">
          <div className="w-16 h-16 rounded-2xl bg-red-50 border border-red-100 flex items-center justify-center">
            <AlertCircle className="w-8 h-8 text-red-500" strokeWidth={1.5} />
          </div>
        </div>
        <h1 className="text-xl font-semibold text-slate-900 mb-2">Something went wrong</h1>
        <p className="text-sm text-red-600 mb-6">{saveError}</p>
        <button
          onClick={() => { savedRef.current = false; save() }}
          className="flex items-center gap-2 py-2.5 px-6 bg-blue-600 hover:bg-blue-700 active:scale-[0.98] text-white text-sm font-semibold rounded-xl transition-all duration-150 shadow-sm mx-auto"
        >
          Try again
          <ArrowRight size={15} strokeWidth={2.5} />
        </button>
      </div>
    )
  }

  // ── Success state (brief flash before redirect) ───────────────────────────
  return (
    <div className="w-full max-w-md text-center">
      <div className="flex justify-center mb-6">
        <div className="w-16 h-16 rounded-2xl bg-green-50 border border-green-100 flex items-center justify-center">
          <CheckCircle2 className="w-8 h-8 text-green-500" strokeWidth={1.5} />
        </div>
      </div>
      <h1 className="text-2xl font-semibold text-slate-900 mb-3">
        You're all set, {firstName}!
      </h1>
      <p className="text-sm text-slate-500 leading-relaxed mb-6">
        Your SMBFlow workspace is ready. Taking you to your dashboard…
      </p>
      <div className="flex justify-center">
        <Loader2 className="w-5 h-5 text-blue-500 animate-spin" />
      </div>
    </div>
  )
}
