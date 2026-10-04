// frontend/src/pages/onboarding/ProfileStep.jsx
// ─────────────────────────────────────────────────────────────────────────────
// Step 3 — Personal information.
// Collects: Preferred Name, Job Role.
// Full Name is pre-populated from registration and shown read-only to avoid
// asking for it twice.
// ─────────────────────────────────────────────────────────────────────────────
import { useState } from 'react'
import { ChevronLeft, ArrowRight } from 'lucide-react'
import { useOnboarding } from '../../contexts/OnboardingContext'
import { useAuth } from '../../contexts/AuthContext'
import OnboardingProgress from './OnboardingProgress'

const JOB_ROLES = [
  { label: 'Select your role', value: '' },
  { label: 'Business Owner / Founder', value: 'owner' },
  { label: 'Operations Manager', value: 'operations' },
  { label: 'Product Manager', value: 'product' },
  { label: 'Marketing Manager', value: 'marketing' },
  { label: 'Sales Manager', value: 'sales' },
  { label: 'Finance / Accounting', value: 'finance' },
  { label: 'Customer Success', value: 'customer_success' },
  { label: 'IT / Technical Lead', value: 'it' },
  { label: 'Individual Contributor', value: 'individual' },
  { label: 'Other', value: 'other' },
]

export default function ProfileStep() {
  const { data, updateData, goNext, goBack } = useOnboarding()
  const { user } = useAuth()

  const [touched, setTouched] = useState({})

  const preferredNameValid = data.preferredName.trim().length > 0
  const jobRoleValid = data.jobRole.length > 0

  const canContinue = preferredNameValid && jobRoleValid

  function handleContinue() {
    setTouched({ preferredName: true, jobRole: true })
    if (!canContinue) return
    goNext()
  }

  function touch(k) {
    return () => setTouched((t) => ({ ...t, [k]: true }))
  }

  return (
    <div className="w-full max-w-md">
      <OnboardingProgress />

      {/* Heading */}
      <div className="mb-7 text-center">
        <h1 className="text-xl font-semibold text-slate-900 mb-2">Tell us about yourself</h1>
        <p className="text-sm text-slate-500 leading-relaxed">
          Help us personalise your SMBFlow experience.
        </p>
      </div>

      {/* Form card */}
      <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm space-y-5">

        {/* Registered name — read-only context */}
        {user?.full_name && (
          <div>
            <label className="block text-xs font-medium text-slate-500 mb-1.5">
              Registered as
            </label>
            <div className="px-3 py-2.5 bg-slate-50 border border-slate-200 rounded-lg text-sm text-slate-600 select-none">
              {user.full_name}
            </div>
          </div>
        )}

        {/* Preferred name */}
        <div>
          <label htmlFor="ob-preferred-name" className="block text-xs font-medium text-slate-700 mb-1.5">
            What should we call you? <span className="text-red-500">*</span>
          </label>
          <input
            id="ob-preferred-name"
            type="text"
            value={data.preferredName}
            onChange={(e) => updateData({ preferredName: e.target.value })}
            onBlur={touch('preferredName')}
            placeholder="e.g. Alex"
            autoFocus
            autoComplete="nickname"
            aria-invalid={touched.preferredName && !preferredNameValid}
            aria-describedby={touched.preferredName && !preferredNameValid ? 'ob-pn-err' : undefined}
            className={[
              'w-full px-3 py-2.5 text-sm border rounded-lg bg-white text-slate-900 placeholder:text-slate-400',
              'focus:outline-none focus:ring-2 transition-colors',
              touched.preferredName && !preferredNameValid
                ? 'border-red-300 focus:ring-red-500/20 focus:border-red-400'
                : 'border-slate-200 focus:ring-blue-500/20 focus:border-blue-500',
            ].join(' ')}
          />
          {touched.preferredName && !preferredNameValid && (
            <p id="ob-pn-err" className="mt-1 text-xs text-red-600">Please enter your preferred name.</p>
          )}
        </div>

        {/* Job role */}
        <div>
          <label htmlFor="ob-job-role" className="block text-xs font-medium text-slate-700 mb-1.5">
            What's your role? <span className="text-red-500">*</span>
          </label>
          <div className="relative">
            <select
              id="ob-job-role"
              value={data.jobRole}
              onChange={(e) => { updateData({ jobRole: e.target.value }); touch('jobRole')() }}
              onBlur={touch('jobRole')}
              aria-invalid={touched.jobRole && !jobRoleValid}
              className={[
                'w-full px-3 py-2.5 text-sm border rounded-lg bg-white text-slate-900 appearance-none',
                'focus:outline-none focus:ring-2 transition-colors pr-9',
                touched.jobRole && !jobRoleValid
                  ? 'border-red-300 focus:ring-red-500/20 focus:border-red-400'
                  : 'border-slate-200 focus:ring-blue-500/20 focus:border-blue-500',
                !data.jobRole && 'text-slate-400',
              ].join(' ')}
            >
              {JOB_ROLES.map((r) => (
                <option key={r.value} value={r.value} disabled={r.value === ''}>
                  {r.label}
                </option>
              ))}
            </select>
            <div className="pointer-events-none absolute inset-y-0 right-3 flex items-center">
              <svg className="w-4 h-4 text-slate-400" viewBox="0 0 20 20" fill="currentColor">
                <path fillRule="evenodd" d="M5.23 7.21a.75.75 0 011.06.02L10 11.168l3.71-3.938a.75.75 0 111.08 1.04l-4.25 4.5a.75.75 0 01-1.08 0l-4.25-4.5a.75.75 0 01.02-1.06z" clipRule="evenodd" />
              </svg>
            </div>
          </div>
          {touched.jobRole && !jobRoleValid && (
            <p className="mt-1 text-xs text-red-600">Please select your role.</p>
          )}
        </div>
      </div>

      {/* Navigation */}
      <div className="flex items-center gap-3 mt-5">
        <button
          onClick={goBack}
          className="flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-700 transition-colors px-1 py-2"
          type="button"
        >
          <ChevronLeft size={16} strokeWidth={2} />
          Back
        </button>

        <button
          onClick={handleContinue}
          type="button"
          className="ml-auto flex items-center gap-2 py-2.5 px-6 bg-blue-600 hover:bg-blue-700 active:scale-[0.98] text-white text-sm font-semibold rounded-xl transition-all duration-150 shadow-sm disabled:opacity-50 disabled:cursor-not-allowed"
        >
          Continue
          <ArrowRight size={15} strokeWidth={2.5} />
        </button>
      </div>
    </div>
  )
}
