// frontend/src/pages/onboarding/WorkspaceStep.jsx
// ─────────────────────────────────────────────────────────────────────────────
// Step 4 — Business / Workspace setup.
// Collects: Workspace Name, Industry, Team Size.
// Workspace Name is pre-populated from the registration form if the user
// already entered one there (passed via OnboardingContext initialData).
// ─────────────────────────────────────────────────────────────────────────────
import { useState } from 'react'
import { ChevronLeft, ArrowRight } from 'lucide-react'
import { useOnboarding } from '../../contexts/OnboardingContext'
import OnboardingProgress from './OnboardingProgress'

const INDUSTRY_OPTIONS = [
  { label: 'Select your industry', value: '' },
  { label: 'SaaS / Technology', value: 'saas' },
  { label: 'Healthcare / Medical Tourism', value: 'healthcare' },
  { label: 'Professional Services', value: 'services' },
  { label: 'E-commerce / Retail', value: 'ecommerce' },
  { label: 'Financial Services', value: 'finance' },
  { label: 'Marketing / Agency', value: 'marketing' },
  { label: 'Other', value: 'other' },
]

const TEAM_SIZE_OPTIONS = [
  { label: 'Select team size', value: '' },
  { label: 'Just me', value: '1' },
  { label: '2–10 people', value: '2-10' },
  { label: '11–50 people', value: '11-50' },
  { label: '51–200 people', value: '51-200' },
  { label: '201–500 people', value: '201-500' },
  { label: '500+ people', value: '500+' },
]

function SelectField({ id, label, value, onChange, onBlur, options, error, required }) {
  return (
    <div>
      <label htmlFor={id} className="block text-xs font-medium text-slate-700 mb-1.5">
        {label} {required && <span className="text-red-500">*</span>}
      </label>
      <div className="relative">
        <select
          id={id}
          value={value}
          onChange={onChange}
          onBlur={onBlur}
          aria-invalid={!!error}
          className={[
            'w-full px-3 py-2.5 text-sm border rounded-lg bg-white appearance-none',
            'focus:outline-none focus:ring-2 transition-colors pr-9',
            error
              ? 'border-red-300 focus:ring-red-500/20 focus:border-red-400 text-slate-900'
              : 'border-slate-200 focus:ring-blue-500/20 focus:border-blue-500',
            !value && 'text-slate-400',
            value && 'text-slate-900',
          ].join(' ')}
        >
          {options.map((o) => (
            <option key={o.value} value={o.value} disabled={o.value === ''}>
              {o.label}
            </option>
          ))}
        </select>
        <div className="pointer-events-none absolute inset-y-0 right-3 flex items-center">
          <svg className="w-4 h-4 text-slate-400" viewBox="0 0 20 20" fill="currentColor">
            <path fillRule="evenodd" d="M5.23 7.21a.75.75 0 011.06.02L10 11.168l3.71-3.938a.75.75 0 111.08 1.04l-4.25 4.5a.75.75 0 01-1.08 0l-4.25-4.5a.75.75 0 01.02-1.06z" clipRule="evenodd" />
          </svg>
        </div>
      </div>
      {error && <p className="mt-1 text-xs text-red-600">{error}</p>}
    </div>
  )
}

export default function WorkspaceStep() {
  const { data, updateData, goNext, goBack } = useOnboarding()
  const [touched, setTouched] = useState({})

  const workspaceNameValid = data.workspaceName.trim().length > 0
  const industryValid = data.industry.length > 0
  // teamSize is optional — no validation required

  const canContinue = workspaceNameValid && industryValid

  function touch(k) {
    return () => setTouched((t) => ({ ...t, [k]: true }))
  }

  function handleContinue() {
    setTouched({ workspaceName: true, industry: true })
    if (!canContinue) return
    goNext()
  }

  return (
    <div className="w-full max-w-md">
      <OnboardingProgress />

      {/* Heading */}
      <div className="mb-7 text-center">
        <h1 className="text-xl font-semibold text-slate-900 mb-2">Tell us about your business</h1>
        <p className="text-sm text-slate-500 leading-relaxed">
          We'll use this to personalise your workflows and automations.
        </p>
      </div>

      {/* Form card */}
      <div className="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm space-y-5">

        {/* Workspace / Business name */}
        <div>
          <label htmlFor="ob-workspace" className="block text-xs font-medium text-slate-700 mb-1.5">
            Business or workspace name <span className="text-red-500">*</span>
          </label>
          <input
            id="ob-workspace"
            type="text"
            value={data.workspaceName}
            onChange={(e) => updateData({ workspaceName: e.target.value })}
            onBlur={touch('workspaceName')}
            placeholder="e.g. Acme Inc."
            autoFocus
            autoComplete="organization"
            aria-invalid={touched.workspaceName && !workspaceNameValid}
            aria-describedby={touched.workspaceName && !workspaceNameValid ? 'ob-ws-err' : undefined}
            className={[
              'w-full px-3 py-2.5 text-sm border rounded-lg bg-white text-slate-900 placeholder:text-slate-400',
              'focus:outline-none focus:ring-2 transition-colors',
              touched.workspaceName && !workspaceNameValid
                ? 'border-red-300 focus:ring-red-500/20 focus:border-red-400'
                : 'border-slate-200 focus:ring-blue-500/20 focus:border-blue-500',
            ].join(' ')}
          />
          {touched.workspaceName && !workspaceNameValid && (
            <p id="ob-ws-err" className="mt-1 text-xs text-red-600">Workspace name is required.</p>
          )}
        </div>

        {/* Industry */}
        <SelectField
          id="ob-industry"
          label="Industry"
          required
          value={data.industry}
          onChange={(e) => { updateData({ industry: e.target.value }); touch('industry')() }}
          onBlur={touch('industry')}
          options={INDUSTRY_OPTIONS}
          error={touched.industry && !industryValid ? 'Please select your industry.' : ''}
        />

        {/* Team size — optional */}
        <SelectField
          id="ob-team-size"
          label="Team size"
          value={data.teamSize}
          onChange={(e) => updateData({ teamSize: e.target.value })}
          options={TEAM_SIZE_OPTIONS}
        />
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
          className="ml-auto flex items-center gap-2 py-2.5 px-6 bg-blue-600 hover:bg-blue-700 active:scale-[0.98] text-white text-sm font-semibold rounded-xl transition-all duration-150 shadow-sm"
        >
          Continue
          <ArrowRight size={15} strokeWidth={2.5} />
        </button>
      </div>
    </div>
  )
}
