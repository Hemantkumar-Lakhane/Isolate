// frontend/src/pages/onboarding/OnboardingProgress.jsx
// ─────────────────────────────────────────────────────────────────────────────
// Step-progress indicator shown above every onboarding step (except Welcome
// and Completion, which handle their own visual treatment).
//
// Renders a row of labelled dots connected by lines.  Completed steps are
// filled blue; the active step has a ring; future steps are muted grey.
// ─────────────────────────────────────────────────────────────────────────────
import { Check } from 'lucide-react'
import { useOnboarding } from '../../contexts/OnboardingContext'

export default function OnboardingProgress() {
  const { currentStep, progressSteps, currentIndex, steps } = useOnboarding()

  // Map the global step index to a progress-bar position (0-based among
  // progress steps, which excludes 'welcome' and 'complete').
  const progressIndex = progressSteps.findIndex((s) => s.id === currentStep?.id)

  // Hide the bar on welcome / complete screens
  if (progressIndex === -1) return null

  return (
    <div className="w-full max-w-md mx-auto mb-8" aria-label="Onboarding progress">
      <div className="flex items-center">
        {progressSteps.map((step, idx) => {
          const isCompleted = idx < progressIndex
          const isActive    = idx === progressIndex
          const isFuture    = idx > progressIndex

          return (
            <div key={step.id} className="flex items-center flex-1 last:flex-none">
              {/* Dot */}
              <div className="flex flex-col items-center">
                <div
                  aria-current={isActive ? 'step' : undefined}
                  className={[
                    'w-7 h-7 rounded-full flex items-center justify-center transition-all duration-300 text-xs font-semibold',
                    isCompleted
                      ? 'bg-blue-600 text-white shadow-sm'
                      : isActive
                      ? 'bg-white border-2 border-blue-600 text-blue-600 shadow-sm ring-4 ring-blue-100'
                      : 'bg-white border-2 border-slate-200 text-slate-400',
                  ].join(' ')}
                >
                  {isCompleted ? (
                    <Check size={13} strokeWidth={2.5} />
                  ) : (
                    <span>{idx + 1}</span>
                  )}
                </div>
                {/* Label */}
                <span
                  className={[
                    'mt-1.5 text-[10px] font-medium whitespace-nowrap',
                    isCompleted || isActive ? 'text-slate-700' : 'text-slate-400',
                  ].join(' ')}
                >
                  {step.label}
                </span>
              </div>

              {/* Connector line — skip after the last dot */}
              {idx < progressSteps.length - 1 && (
                <div
                  className={[
                    'h-0.5 flex-1 mx-1 mb-4 rounded-full transition-all duration-500',
                    isCompleted ? 'bg-blue-500' : 'bg-slate-200',
                  ].join(' ')}
                />
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
