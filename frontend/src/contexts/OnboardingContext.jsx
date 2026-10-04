// frontend/src/contexts/OnboardingContext.jsx
// ─────────────────────────────────────────────────────────────────────────────
// Multi-step onboarding state management.
// Tracks the current step, all collected data, validation state, and
// persistence helpers. Data is flushed to localStorage so a browser refresh
// during onboarding resumes where the user left off.
// ─────────────────────────────────────────────────────────────────────────────
import { createContext, useContext, useState, useCallback, useMemo, useEffect } from 'react'

const OnboardingContext = createContext(null)

const STORAGE_KEY = 'smbflow_onboarding_state'

// Step IDs – used as route-like keys inside the wizard.
export const ONBOARDING_STEPS = [
  { id: 'welcome',   label: 'Welcome',   optional: false },
  { id: 'profile',   label: 'About You', optional: false },
  { id: 'workspace', label: 'Workspace', optional: false },
  { id: 'goals',     label: 'Goals',     optional: true  },
  { id: 'complete',  label: 'All Done',  optional: false },
]

// Total "progress" steps shown in the indicator (excluding welcome + complete)
export const PROGRESS_STEPS = ONBOARDING_STEPS.filter(
  (s) => s.id !== 'welcome' && s.id !== 'complete',
)

function loadPersistedState() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

function persistState(state) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state))
  } catch (_) {}
}

export function OnboardingProvider({ children, initialData = {} }) {
  // Index into ONBOARDING_STEPS — restored from localStorage on mount to
  // allow resuming after a browser refresh mid-flow.
  const [currentIndex, setCurrentIndex] = useState(() => {
    const saved = loadPersistedState()
    const idx = saved?._step
    if (typeof idx === 'number' && idx > 0 && idx < ONBOARDING_STEPS.length - 1) {
      return idx
    }
    return 0
  })

  // All form data accumulated across steps
  const [data, setData] = useState(() => {
    const saved = loadPersistedState()
    return {
      // Step 3 – profile
      preferredName: '',
      jobRole: '',
      // Step 4 – workspace
      workspaceName: '',
      industry: 'saas',
      teamSize: '',
      // Step 5 – goals
      goals: [],
      // Seeded from registration / auth context (lowest priority)
      ...initialData,
      // Persisted session data overrides defaults
      ...(saved ? { ...saved, _step: undefined } : {}),
      // initialData fields that are explicitly set always win over stale
      // localStorage (e.g. preferred name from a freshly created account)
      ...(initialData.preferredName ? { preferredName: initialData.preferredName } : {}),
      ...(initialData.workspaceName ? { workspaceName: initialData.workspaceName } : {}),
      ...(initialData.industry ? { industry: initialData.industry } : {}),
    }
  })

  // Saving / error state (used on the completion step)
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState('')

  // Persist data + step to localStorage whenever they change
  useEffect(() => {
    persistState({ ...data, _step: currentIndex })
  }, [data, currentIndex])

  const currentStep = ONBOARDING_STEPS[currentIndex]

  const updateData = useCallback((partial) => {
    setData((prev) => ({ ...prev, ...partial }))
    setSaveError('')
  }, [])

  const goNext = useCallback(() => {
    setCurrentIndex((i) => Math.min(i + 1, ONBOARDING_STEPS.length - 1))
  }, [])

  const goBack = useCallback(() => {
    setCurrentIndex((i) => Math.max(i - 1, 0))
  }, [])

  const goToStep = useCallback((id) => {
    const idx = ONBOARDING_STEPS.findIndex((s) => s.id === id)
    if (idx !== -1) setCurrentIndex(idx)
  }, [])

  const clearPersistedState = useCallback(() => {
    try { localStorage.removeItem(STORAGE_KEY) } catch (_) {}
  }, [])

  const value = useMemo(
    () => ({
      currentIndex,
      currentStep,
      totalSteps: ONBOARDING_STEPS.length,
      steps: ONBOARDING_STEPS,
      progressSteps: PROGRESS_STEPS,
      data,
      saving,
      saveError,
      setSaving,
      setSaveError,
      updateData,
      goNext,
      goBack,
      goToStep,
      clearPersistedState,
    }),
    [currentIndex, currentStep, data, saving, saveError, updateData, goNext, goBack, goToStep, clearPersistedState],
  )

  return <OnboardingContext.Provider value={value}>{children}</OnboardingContext.Provider>
}

export function useOnboarding() {
  const ctx = useContext(OnboardingContext)
  if (!ctx) throw new Error('useOnboarding must be used inside <OnboardingProvider>')
  return ctx
}
