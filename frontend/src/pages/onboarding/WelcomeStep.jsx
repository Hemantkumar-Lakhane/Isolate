// frontend/src/pages/onboarding/WelcomeStep.jsx
// ─────────────────────────────────────────────────────────────────────────────
// Step 2 — Welcome screen shown immediately after account registration.
// Clean, centered layout inspired by HubSpot's welcome screen.
// No back button (first post-registration step).
// ─────────────────────────────────────────────────────────────────────────────
import { Sparkles, ArrowRight } from 'lucide-react'
import { useOnboarding } from '../../contexts/OnboardingContext'
import { useAuth } from '../../contexts/AuthContext'

export default function WelcomeStep() {
  const { goNext } = useOnboarding()
  const { user } = useAuth()

  const firstName = user?.full_name?.split(' ')[0] || 'there'

  return (
    <div className="w-full max-w-md text-center animate-fade-in">
      {/* Icon */}
      <div className="flex justify-center mb-6">
        <div className="w-16 h-16 rounded-2xl bg-blue-50 border border-blue-100 flex items-center justify-center shadow-sm">
          <Sparkles className="w-8 h-8 text-blue-600" strokeWidth={1.5} />
        </div>
      </div>

      {/* Heading */}
      <h1 className="text-2xl font-semibold text-slate-900 mb-3">
        Welcome to SMBFlow, {firstName}!
      </h1>

      {/* Description */}
      <p className="text-slate-500 text-sm leading-relaxed mb-8 max-w-sm mx-auto">
        Let's set up your workspace with a few quick questions. It takes about
        two minutes and helps us tailor your experience.
      </p>

      {/* Steps preview */}
      <div className="bg-white border border-slate-200 rounded-2xl p-5 mb-8 text-left shadow-sm">
        <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">
          What we'll cover
        </p>
        <ul className="space-y-2.5">
          {[
            'A bit about you',
            'Your workspace details',
            'What you want to accomplish',
          ].map((item, i) => (
            <li key={i} className="flex items-center gap-2.5 text-sm text-slate-700">
              <span className="w-5 h-5 rounded-full bg-blue-600 text-white text-[10px] font-bold flex items-center justify-center flex-shrink-0">
                {i + 1}
              </span>
              {item}
            </li>
          ))}
        </ul>
      </div>

      {/* CTA */}
      <button
        onClick={goNext}
        className="w-full py-3 px-6 bg-blue-600 hover:bg-blue-700 active:scale-[0.98] text-white text-sm font-semibold rounded-xl transition-all duration-150 flex items-center justify-center gap-2 shadow-sm"
      >
        Get started
        <ArrowRight size={16} strokeWidth={2.5} />
      </button>
    </div>
  )
}
