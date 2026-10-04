// frontend/src/components/workflow/DecisionPortal.jsx
// ─────────────────────────────────────────────────────────────────────────────
// KEY CHANGES vs original:
//  1. All emojis replaced with lucide-react icons
//  2. Agent icons use AGENT_ICON_MAP from helpers (lucide, not emoji)
//  3. Smoother modal entrance animations
//  4. EscModal: prosecutor findings collapsed by default with expand toggle
// ─────────────────────────────────────────────────────────────────────────────
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Bot, ArrowLeftRight, AlertTriangle, ShieldAlert,
  ChevronDown, ChevronUp, CheckCircle2, XCircle,
  Scale, ExternalLink,
} from 'lucide-react'
import { Modal, Button, Alert, cn } from '../ui'
import { fmtCost, AGENT_ICON_MAP, AGENT_ICON_FALLBACK, AGENT_LABELS } from '../../utils/helpers'

// ── Agent Icon Pair — used in A2A flow diagram ────────────────────────────────
function AgentIconPill({ agentKey }) {
  const IconComp = AGENT_ICON_MAP[agentKey] || AGENT_ICON_FALLBACK
  return (
    <div className="flex flex-col items-center gap-1">
      <div className="w-10 h-10 rounded-2xl bg-primary-500/12 border border-primary-500/20 flex items-center justify-center">
        <IconComp className="w-5 h-5 text-primary-400" />
      </div>
      <span className="text-[10px] text-[rgb(var(--text-muted))] font-medium">
        {AGENT_LABELS[agentKey] || agentKey}
      </span>
    </div>
  )
}

// ── A2A Permission Modal ──────────────────────────────────────────────────────
function A2AModal({ req, api, onDone }) {
  const [loading, setLoading] = useState(false)
  const [error,   setError]   = useState('')

  const decide = async (approved) => {
    setLoading(true); setError('')
    try {
      await api.post(`/a2a/${req.a2a_id}/decide`, { approved })
      onDone()
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <Modal
      open
      title={
        <span className="flex items-center gap-2">
          <Bot className="w-4 h-4 text-primary-400" />
          Agent-to-Agent Request
        </span>
      }
    >
      <div className="space-y-4">
        {/* Status chip */}
        <div className="flex items-center gap-2">
          <span className="px-2.5 py-0.5 bg-primary-500/10 border border-primary-500/25 text-primary-400 text-xs rounded-full font-semibold animate-pulse">
            Needs Your Permission
          </span>
          <span className="text-xs text-[rgb(var(--text-muted))]">
            Est. {fmtCost(req.estimated_cost_usd || 0.001)}
          </span>
        </div>

        {/* Flow diagram */}
        <div className="bg-[rgb(var(--bg-base))] rounded-2xl p-4 flex items-center gap-3 border border-[rgb(var(--border))]">
          <AgentIconPill agentKey={req.requesting_agent} />
          <div className="flex-1 flex flex-col items-center gap-1">
            <div className="flex items-center gap-1 w-full">
              <div className="flex-1 h-px bg-primary-500/30" />
              <ArrowLeftRight className="w-3.5 h-3.5 text-primary-400 flex-shrink-0" />
              <div className="flex-1 h-px bg-primary-500/30" />
            </div>
            <span className="text-[10px] text-primary-400 font-medium">requests re-run</span>
          </div>
          <AgentIconPill agentKey={req.target_agent} />
        </div>

        {/* Reason */}
        <div>
          <p className="text-[10px] text-[rgb(var(--text-muted))] uppercase tracking-wider font-semibold mb-1.5">Reason</p>
          <p className="text-sm text-[rgb(var(--text-secondary))] bg-[rgb(var(--bg-base))] rounded-xl p-3 leading-relaxed border border-[rgb(var(--border))]">
            {req.reason}
          </p>
        </div>

        {/* Refinement note */}
        {req.refinement_note && (
          <div>
            <p className="text-[10px] text-[rgb(var(--text-muted))] uppercase tracking-wider font-semibold mb-1.5">
              What to look for
            </p>
            <p className="text-xs text-primary-400 bg-primary-500/8 border border-primary-500/20 rounded-xl p-3 font-mono leading-relaxed">
              {req.refinement_note}
            </p>
          </div>
        )}

        {/* Extra tools */}
        {req.new_tools?.length > 0 && (
          <div>
            <p className="text-[10px] text-[rgb(var(--text-muted))] uppercase tracking-wider font-semibold mb-1.5">
              Extra Tools Requested
            </p>
            <div className="flex flex-wrap gap-1.5">
              {req.new_tools.map(t => (
                <code key={t} className="text-[11px] text-success bg-success/10 border border-success/25 rounded-lg px-2 py-0.5 font-mono">
                  {t}
                </code>
              ))}
            </div>
          </div>
        )}

        <p className="text-xs text-warning flex items-center gap-1.5">
          <AlertTriangle className="w-3.5 h-3.5 flex-shrink-0" />
          Re-runs {AGENT_LABELS[req.target_agent] || req.target_agent} — adds ~{fmtCost(req.estimated_cost_usd || 0.001)} to session.
        </p>

        {error && <Alert type="error">{error}</Alert>}

        <div className="flex gap-3">
          <Button variant="success" loading={loading} onClick={() => decide(true)} className="flex-1"
            icon={<CheckCircle2 className="w-4 h-4" />}>
            Allow Re-run
          </Button>
          <Button variant="danger" loading={loading} onClick={() => decide(false)} className="flex-1"
            icon={<XCircle className="w-4 h-4" />}>
            Reject
          </Button>
        </div>
      </div>
    </Modal>
  )
}

// ── Escalation Decision Modal ─────────────────────────────────────────────────
function EscModal({ esc, api, onDone, onDismiss }) {
  const navigate  = useNavigate()
  const [action,    setAction]    = useState(esc?.recommended_action || '')
  const [decidedBy, setDecidedBy] = useState('')
  const [notes,     setNotes]     = useState('')
  const [loading,   setLoading]   = useState(false)
  const [error,     setError]     = useState('')
  const [showFaults, setShowFaults] = useState(false)

  const faults = esc?.options?.[0]?.prosecutor_faults || []

  const fieldCls =
    'w-full bg-[rgb(var(--bg-input))] border border-[rgb(var(--border))] rounded-xl px-3 py-2 text-[rgb(var(--text-primary))] text-sm focus:outline-none focus:ring-2 focus:ring-primary-500/30 focus:border-primary-500/50 transition-all'

  const submit = async () => {
    if (!action || !decidedBy) { setError('Action and name are required'); return }
    const escId = esc?.id || esc?.escalation_id
    if (!escId) { setError('Escalation ID missing — decide from the Escalations page'); return }
    setLoading(true); setError('')
    try {
      await api.post(`/escalations/${escId}/decide`, {
        decision:      { notes },
        action_chosen: action,
        decided_by:    decidedBy,
      })
      onDone()
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <Modal
      open
      onClose={onDismiss}
      title={
        <span className="flex items-center gap-2">
          <ShieldAlert className="w-4 h-4 text-warning" />
          Human Decision Required
        </span>
      }
    >
      <div className="space-y-4">
        {/* Context brief */}
        <div className="bg-warning/8 border border-warning/25 rounded-2xl p-4">
          <p className="text-xs font-bold text-warning mb-1 flex items-center gap-1.5">
            <AlertTriangle className="w-3.5 h-3.5" />
            Escalated at: {esc.node_id}
          </p>
          <p className="text-sm text-[rgb(var(--text-secondary))] leading-relaxed">{esc.reason}</p>
        </div>

        {esc.context_brief && (
          <pre className="text-xs text-[rgb(var(--text-secondary))] bg-[rgb(var(--bg-base))] rounded-xl p-3 overflow-auto max-h-28 whitespace-pre-wrap border border-[rgb(var(--border))] font-mono leading-relaxed">
            {esc.context_brief}
          </pre>
        )}

        {esc.recommended_action && (
          <div className="flex items-center gap-2 text-xs bg-success/8 border border-success/25 rounded-xl px-3 py-2">
            <Bot className="w-3.5 h-3.5 text-success flex-shrink-0" />
            <span className="text-[rgb(var(--text-muted))]">Agent recommends:</span>
            <strong className="text-success">{esc.recommended_action}</strong>
          </div>
        )}

        {/* Prosecutor findings — collapsible */}
        {faults.length > 0 && (
          <div>
            <button
              onClick={() => setShowFaults(p => !p)}
              className="flex items-center gap-2 text-xs text-warning hover:text-warning/80 transition-colors w-full"
            >
              <Scale className="w-3.5 h-3.5" />
              <span className="font-semibold">Prosecutor Findings</span>
              <span className="px-1.5 py-0.5 bg-warning/10 border border-warning/25 rounded text-[10px]">
                {faults.length}
              </span>
              {showFaults
                ? <ChevronUp className="w-3.5 h-3.5 ml-auto" />
                : <ChevronDown className="w-3.5 h-3.5 ml-auto" />
              }
            </button>
            <AnimatePresence>
              {showFaults && (
                <motion.div
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: 'auto', opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }}
                  className="overflow-hidden mt-2"
                >
                  <div className="bg-warning/6 border border-warning/20 rounded-xl p-3 space-y-1 max-h-28 overflow-y-auto">
                    {faults.map((f, i) => (
                      <p key={i} className="text-xs text-warning/80 leading-relaxed">{f}</p>
                    ))}
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        )}

        {/* Multi-sig progress */}
        {esc.required_signatures > 1 && (
          <div className="text-xs text-primary-400 bg-primary-500/8 border border-primary-500/20 rounded-xl px-3 py-2">
            Multi-step approval: {esc.signatures?.length ?? 0} / {esc.required_signatures} signatures
          </div>
        )}

        {/* Decision inputs */}
        <div>
          <label className="block text-xs font-medium text-[rgb(var(--text-secondary))] mb-1.5">
            Action to take <span className="text-danger">*</span>
          </label>
          <input
            value={action}
            onChange={e => setAction(e.target.value)}
            className={fieldCls}
            placeholder="e.g. send_csm_outreach_email"
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-[rgb(var(--text-secondary))] mb-1.5">
            Your name <span className="text-danger">*</span>
          </label>
          <input
            value={decidedBy}
            onChange={e => setDecidedBy(e.target.value)}
            className={fieldCls}
            placeholder="Jane Smith"
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-[rgb(var(--text-secondary))] mb-1.5">
            Notes <span className="text-[rgb(var(--text-muted))] font-normal">(optional)</span>
          </label>
          <textarea
            value={notes}
            onChange={e => setNotes(e.target.value)}
            rows={2}
            className={cn(fieldCls, 'resize-none')}
          />
        </div>

        {error && <Alert type="error">{error}</Alert>}

        <Button
          variant="success"
          loading={loading}
          onClick={submit}
          disabled={!action || !decidedBy}
          className="w-full"
          icon={<CheckCircle2 className="w-4 h-4" />}
        >
          Submit Decision
        </Button>

        <button
          onClick={() => navigate('/escalations')}
          className="w-full text-xs text-[rgb(var(--text-muted))] hover:text-[rgb(var(--text-primary))] py-1.5 text-center flex items-center justify-center gap-1.5 transition-colors"
        >
          Decide later from Escalations page
          <ExternalLink className="w-3 h-3" />
        </button>
      </div>
    </Modal>
  )
}

// ── Decision Portal ───────────────────────────────────────────────────────────
export default function DecisionPortal({
  pendingA2A, pendingEsc, api,
  onA2ADone, onEscDone, onEscDismiss,
}) {
  if (!pendingA2A && !pendingEsc) return null
  return (
    <>
      {pendingA2A && (
        <A2AModal req={pendingA2A} api={api} onDone={onA2ADone} />
      )}
      {pendingEsc && !pendingA2A && (
        <EscModal
          esc={pendingEsc}
          api={api}
          onDone={onEscDone}
          onDismiss={onEscDismiss}
        />
      )}
    </>
  )
}