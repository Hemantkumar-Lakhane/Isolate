// frontend/src/pages/onboarding/WorkflowGoalsStep.jsx
// ─────────────────────────────────────────────────────────────────────────────
// Step 5 — Workflow goals (optional).
// Presents the actual SMBFlow workflow capabilities as selectable goal chips.
// At least one selection is required, but the step can be skipped entirely.
// ─────────────────────────────────────────────────────────────────────────────
import { ChevronLeft, ArrowRight, Check } from 'lucide-react'
import { useOnboarding } from '../../contexts/OnboardingContext'
import OnboardingProgress from './OnboardingProgress'

// Mapped to real SMBFlow capabilities visible in the app (WorkflowLibrary,
// Dashboard, etc.) — no invented features.
const GOAL_OPTIONS = [
  {
    id: 'automate_workflows',
    label: 'Automate business workflows',
    description: 'Run multi-step automations with AI agents handling repetitive tasks.',
  },
  {
    id: 'manage_tasks',
    label: 'Manage tasks and approvals',
    description: 'Track escalations, human-in-the-loop approvals, and action items.',
  },
  {
    id: 'email_productivity',
    label: 'Improve email productivity',
    description: 'Summarise, categorise, and act on customer emails at scale.',
  },
  {
    id: 'product_launch',
    label: 'Run product launch campaigns',
    description: 'Orchestrate research, content creation, and multi-channel outreach.',
  },
  {
    id: 'monitor_operations',
    label: 'Monitor workflow performance',
    description: 'Track run costs, outcomes, and performance across your operations.',
  },
  {
    id: 'connect_tools',
    label: 'Connect existing tools',
    description: 'Integrate the tools you already use into automated workflows.',
  },
]

function GoalChip({ goal, selected, onToggle }) {
  return (
    <button
      type="button"
      onClick={() => onToggle(goal.id)}
      aria-pressed={selected}
      className={[
        'w-full text-left px-4 py-3.5 rounded-xl border transition-all duration-150',
        'flex items-start gap-3 group',
        selected
          ? 'border-blue-500 bg-blue-50 ring-1 ring-blue-500/30'
          : 'border-slate-200 bg-white hover:border-slate-300 hover:bg-slate-50',
      ].join(' ')}
    >
      {/* Checkbox indicator */}
      <div
        className={[
          'mt-0.5 w-4.5 h-4.5 rounded-md border-2 flex-shrink-0 flex items-center justify-center transition-all',
          selected ? 'bg-blue-600 border-blue-600' : 'border-slate-300 bg-white',
        ].join(' ')}
        style={{ width: '18px', height: '18px', minWidth: '18px' }}
      >
        {selected && <Check size={10} strokeWidth={3} className="text-white" />}
      </div>

      {/* Text */}
      <div>
        <p className={['text-sm font-medium', selected ? 'text-blue-900' : 'text-slate-800'].join(' ')}>
          {goal.label}
        </p>
        <p className={['text-xs mt-0.5 leading-relaxed', selected ? 'text-blue-700/80' : 'text-slate-500'].join(' ')}>
          {goal.description}
        </p>
      </div>
    </button>
  )
}

export default function WorkflowGoalsStep() {
  const { data, updateData, goNext, goBack } = useOnboarding()

  function toggleGoal(id) {
    const current = data.goals || []
    const next = current.includes(id)
      ? current.filter((g) => g !== id)
      : [...current, id]
    updateData({ goals: next })
  }

  const hasSelection = (data.goals || []).length > 0

  return (
    <div className="w-full max-w-md">
      <OnboardingProgress />

      {/* Heading */}
      <div className="mb-6 text-center">
        <h1 className="text-xl font-semibold text-slate-900 mb-2">
          What do you want to accomplish?
        </h1>
        <p className="text-sm text-slate-500 leading-relaxed">
          Choose the areas you want to focus on. Select all that apply.
        </p>
      </div>

      {/* Goal chips */}
      <div className="space-y-2.5 mb-5">
        {GOAL_OPTIONS.map((goal) => (
          <GoalChip
            key={goal.id}
            goal={goal}
            selected={(data.goals || []).includes(goal.id)}
            onToggle={toggleGoal}
          />
        ))}
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

        {/* Skip (this step is optional) */}
        {!hasSelection && (
          <button
            onClick={goNext}
            type="button"
            className="ml-auto text-sm text-slate-400 hover:text-slate-600 transition-colors py-2 px-3"
          >
            Skip for now
          </button>
        )}

        {/* Continue — only shown when something is selected */}
        {hasSelection && (
          <button
            onClick={goNext}
            type="button"
            className="ml-auto flex items-center gap-2 py-2.5 px-6 bg-blue-600 hover:bg-blue-700 active:scale-[0.98] text-white text-sm font-semibold rounded-xl transition-all duration-150 shadow-sm"
          >
            Continue
            <ArrowRight size={15} strokeWidth={2.5} />
          </button>
        )}
      </div>

      {/* Selection count hint */}
      {hasSelection && (
        <p className="text-center text-xs text-slate-400 mt-3">
          {data.goals.length} goal{data.goals.length !== 1 ? 's' : ''} selected
        </p>
      )}
    </div>
  )
}
