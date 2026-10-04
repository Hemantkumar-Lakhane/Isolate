// frontend/src/pages/onboarding/OnboardingPage.jsx
// ─────────────────────────────────────────────────────────────────────────────
// Main onboarding orchestrator.
// Wraps all step components in OnboardingLayout + OnboardingProvider, seeds
// initial data from the authenticated user, and renders the correct step based
// on currentIndex from context.
//
// Guard logic:
//   • Unauthenticated → /auth
//   • Already completed onboarding (requires_onboarding: false + has org) → /dashboard
//   • Auth still loading → spinner
// ─────────────────────────────────────────────────────────────────────────────
import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Loader2 } from 'lucide-react'
import { useAuth } from '../../contexts/AuthContext'
import { OnboardingProvider, useOnboarding } from '../../contexts/OnboardingContext'
import OnboardingLayout from './OnboardingLayout'
import WelcomeStep      from './WelcomeStep'
import ProfileStep      from './ProfileStep'
import WorkspaceStep    from './WorkspaceStep'
import WorkflowGoalsStep from './WorkflowGoalsStep'
import CompletionStep   from './CompletionStep'

// ── Step renderer — reads context for currentStep.id ─────────────────────────
function StepRenderer() {
  const { currentStep } = useOnboarding()

  switch (currentStep?.id) {
    case 'welcome':   return <WelcomeStep />
    case 'profile':   return <ProfileStep />
    case 'workspace': return <WorkspaceStep />
    case 'goals':     return <WorkflowGoalsStep />
    case 'complete':  return <CompletionStep />
    default:          return <WelcomeStep />
  }
}

// ── Inner component (has access to OnboardingProvider) ───────────────────────
function OnboardingInner() {
  return (
    <OnboardingLayout>
      <StepRenderer />
    </OnboardingLayout>
  )
}

// ── Page guard + seed ─────────────────────────────────────────────────────────
export default function OnboardingPage() {
  const { user, token, loading: authLoading } = useAuth()
  const navigate = useNavigate()

  useEffect(() => {
    if (authLoading) return

    // Not authenticated — send to login
    if (!token || !user) {
      navigate('/auth', { replace: true })
      return
    }

    // Admin users don't go through onboarding
    const isAdmin = user.role === 'super_admin' || user.role === 'platform_admin'
    if (isAdmin) {
      navigate('/admin', { replace: true })
      return
    }

    // If onboarding is already done and the user somehow lands here, go to dashboard
    if (!user.requires_onboarding && user.organization_id) {
      navigate('/dashboard', { replace: true })
    }
  }, [authLoading, token, user, navigate])

  // Loading spinner while auth resolves
  if (authLoading || !token || !user) {
    return (
      <div className="min-h-screen bg-slate-50 flex flex-col items-center justify-center p-4">
        <div className="flex items-center gap-2.5 mb-4">
          <div className="w-9 h-9 rounded-xl bg-blue-600 flex items-center justify-center shadow-sm">
            <span className="text-white font-bold text-sm">S</span>
          </div>
          <span className="text-xl font-semibold text-slate-900">SMBFlow</span>
        </div>
        <div className="flex items-center gap-2 text-slate-500 text-sm">
          <Loader2 className="w-4 h-4 text-blue-600 animate-spin" />
          <span>Preparing your setup…</span>
        </div>
      </div>
    )
  }

  // Seed initial data from the auth profile so steps can pre-populate fields.
  // The OnboardingProvider merges this with any persisted localStorage state.
  const initialData = {
    preferredName: user.full_name?.split(' ')[0] || '',
    // workspaceName may already be set if user filled it in during email/password
    // signup — carried over via Supabase user_metadata.workspace_name
    workspaceName: user.organization_name && user.organization_name !== 'Pending Workspace Setup'
      ? user.organization_name
      : '',
    industry: user.industry || 'saas',
  }

  return (
    <OnboardingProvider initialData={initialData}>
      <OnboardingInner />
    </OnboardingProvider>
  )
}
