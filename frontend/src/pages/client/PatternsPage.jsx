// frontend/src/pages/client/PatternsPage.jsx
// ============================================
// Pattern Memory Browser — for business owners (tenant users).
// Shows what SMBFlow has learned from past workflow runs.
// Business owner can promote sandbox patterns to active (inject into future RAG)
// or demote active patterns back to review if they seem incorrect.

import { useState, useEffect, useCallback } from 'react'
import { useAuth } from '../../contexts/AuthContext'
import {
  Card, Button, Alert, Spinner, EmptyState, TabGroup, Modal
} from '../../components/ui'
import { timeAgo, truncate } from '../../utils/helpers'

const OUTCOME_CONFIG = {
  positive: { icon: '↑', color: 'text-green-400', bg: 'bg-green-900/20 border-green-700/30' },
  negative: { icon: '↓', color: 'text-red-400',   bg: 'bg-red-900/20   border-red-700/30'   },
  neutral:  { icon: '→', color: 'text-blue-400',  bg: 'bg-blue-900/20  border-blue-700/30'  },
}

// ── Pattern Detail Modal ──────────────────────────────────────────────────────
function PatternModal({ pattern, open, onClose }) {
  if (!open || !pattern) return null
  const pd = pattern.pattern_data || {}
  const oc = OUTCOME_CONFIG[pd.outcome_indicator] || OUTCOME_CONFIG.neutral

  return (
    <Modal open onClose={onClose} title={`🧠 Pattern: ${pattern.pattern_key}`} width="max-w-lg">
      <div className="space-y-4">
        <div className="flex items-center gap-2">
          <span className={`text-xs px-2 py-0.5 rounded border font-mono ${oc.bg} ${oc.color}`}>
            {oc.icon} {pd.outcome_indicator || 'neutral'}
          </span>
          <span className={`text-xs px-2 py-0.5 rounded font-mono ${
            pattern.pattern_status === 'active'
              ? 'bg-green-900/30 text-green-300 border border-green-700/40'
              : 'bg-yellow-900/30 text-yellow-300 border border-yellow-700/40'
          }`}>
            {pattern.pattern_status}
          </span>
          <span className="text-xs text-gray-500 ml-auto">
            {pattern.sample_size} run{pattern.sample_size !== 1 ? 's' : ''} observed
          </span>
        </div>

        {pd.description && (
          <div className="bg-gray-800/50 rounded-lg p-3">
            <div className="text-xs text-gray-500 mb-1 uppercase tracking-wide font-semibold">
              What was learned
            </div>
            <p className="text-sm text-gray-300 leading-relaxed">{pd.description}</p>
          </div>
        )}

        {pattern.success_rate != null && (
          <div className="flex items-center gap-4 text-xs">
            <span className="text-gray-500">Success rate</span>
            <div className="flex-1 h-2 bg-gray-800 rounded-full overflow-hidden">
              <div
                className="h-full bg-gradient-to-r from-green-600 to-green-400 rounded-full"
                style={{ width: `${Math.round((pattern.success_rate || 0) * 100)}%` }}
              />
            </div>
            <span className={`font-mono font-bold ${
              (pattern.success_rate || 0) >= 0.7 ? 'text-green-400'
              : (pattern.success_rate || 0) >= 0.4 ? 'text-yellow-400'
              : 'text-red-400'
            }`}>
              {Math.round((pattern.success_rate || 0) * 100)}%
            </span>
          </div>
        )}

        {pd.value && (
          <div>
            <div className="text-xs text-gray-500 mb-1 uppercase tracking-wide font-semibold">
              Raw pattern data
            </div>
            <pre className="bg-gray-950 border border-gray-800 rounded-lg p-3 text-xs text-green-400 font-mono overflow-auto max-h-36 whitespace-pre-wrap">
              {JSON.stringify(pd.value, null, 2)}
            </pre>
          </div>
        )}

        <div className="text-xs text-gray-600">
          Last updated: {timeAgo(pattern.last_updated)} · Key: <code className="text-gray-500">{pattern.pattern_key}</code>
        </div>
      </div>
    </Modal>
  )
}

// ── Pattern Card ──────────────────────────────────────────────────────────────
function PatternCard({ pattern, onPromote, onDemote, onView, loading }) {
  const pd  = pattern.pattern_data || {}
  const oc  = OUTCOME_CONFIG[pd.outcome_indicator] || OUTCOME_CONFIG.neutral
  const isActive = pattern.pattern_status === 'active'
  const isPending = pattern.pattern_status === 'pending_review'

  return (
    <div className={`border rounded-xl p-4 transition-colors ${
      isPending ? 'border-yellow-700/30 bg-yellow-900/5' : 'border-gray-700/40 bg-gray-800/20'
    }`}>
      <div className="flex items-start gap-3">
        <span className={`text-xl flex-shrink-0 ${oc.color}`}>{oc.icon}</span>

        <div className="flex-1 min-w-0">
          {/* Badges */}
          <div className="flex items-center gap-2 flex-wrap mb-1">
            <span className={`text-[10px] px-1.5 py-0.5 rounded border font-mono ${
              isActive
                ? 'text-green-300 bg-green-900/20 border-green-700/40'
                : 'text-yellow-300 bg-yellow-900/20 border-yellow-700/40'
            }`}>
              {isActive ? '● active' : '○ sandbox'}
            </span>
            <span className={`text-[10px] px-1.5 py-0.5 rounded border font-mono ${oc.bg} ${oc.color}`}>
              {pd.outcome_indicator || 'neutral'}
            </span>
            {pattern.success_rate != null && (
              <span className={`text-[10px] font-mono ${
                pattern.success_rate >= 0.7 ? 'text-green-400'
                : pattern.success_rate >= 0.4 ? 'text-yellow-400'
                : 'text-red-400'
              }`}>
                {Math.round(pattern.success_rate * 100)}% success
              </span>
            )}
            <span className="text-[10px] text-gray-600 ml-auto">
              {pattern.sample_size} obs · {timeAgo(pattern.last_updated)}
            </span>
          </div>

          {/* Key */}
          <div className="text-[10px] text-gray-600 font-mono mb-1 truncate">{pattern.pattern_key}</div>

          {/* Description */}
          {pd.description && (
            <p className="text-xs text-gray-400 leading-relaxed">
              {truncate(pd.description, 140)}
            </p>
          )}
        </div>

        {/* Actions */}
        <div className="flex flex-col gap-1 flex-shrink-0">
          <Button size="xs" variant="ghost" onClick={() => onView(pattern)}>
            View
          </Button>
          {isPending && (
            <Button
              size="xs"
              variant="success"
              loading={loading === pattern.pattern_key}
              onClick={() => onPromote(pattern.pattern_key)}
              title="Activate — this pattern will be injected into future AI reasoning"
            >
              Activate
            </Button>
          )}
          {isActive && (
            <Button
              size="xs"
              variant="warning"
              loading={loading === pattern.pattern_key}
              onClick={() => onDemote(pattern.pattern_key)}
              title="Move back to sandbox — stops injection into future reasoning"
            >
              Sandbox
            </Button>
          )}
        </div>
      </div>
    </div>
  )
}

// ── Main PatternsPage ─────────────────────────────────────────────────────────
export default function PatternsPage() {
  const { user, api } = useAuth()
  const tenantId      = user?.tenant_id

  const [tab,         setTab]         = useState('pending_review')
  const [patterns,    setPatterns]    = useState([])
  const [loading,     setLoading]     = useState(true)
  const [actionLoading, setActionLoading] = useState(null)
  const [error,       setError]       = useState('')
  const [success,     setSuccess]     = useState('')
  const [viewing,     setViewing]     = useState(null)

  const load = useCallback(async () => {
    if (!tenantId) { setLoading(false); return }
    try {
      const data = await api.get(
        `/tenants/${tenantId}/patterns?status=${tab === 'all' ? 'all' : tab}`
      )
      setPatterns(Array.isArray(data) ? data : [])
      setError('')
    } catch (err) { setError(err.message) }
    finally { setLoading(false) }
  }, [api, tenantId, tab])

  useEffect(() => { load() }, [load])

  const promote = async (key) => {
    setActionLoading(key); setError(''); setSuccess('')
    try {
      await api.post(`/tenants/${tenantId}/patterns/${encodeURIComponent(key)}/promote`)
      setSuccess(`Pattern activated — it will now influence future AI reasoning.`)
      setTimeout(() => setSuccess(''), 4000)
      load()
    } catch (err) { setError(err.message) }
    finally { setActionLoading(null) }
  }

  const demote = async (key) => {
    setActionLoading(key); setError(''); setSuccess('')
    try {
      await api.post(`/tenants/${tenantId}/patterns/${encodeURIComponent(key)}/demote`)
      setSuccess(`Pattern moved to sandbox — it will no longer influence reasoning.`)
      setTimeout(() => setSuccess(''), 4000)
      load()
    } catch (err) { setError(err.message) }
    finally { setActionLoading(null) }
  }

  const pendingCount = patterns.filter(p => p.pattern_status === 'pending_review').length
  const activeCount  = patterns.filter(p => p.pattern_status === 'active').length

  if (!tenantId) return (
    <div className="flex items-center justify-center h-64 text-gray-500">No tenant assigned.</div>
  )

  if (loading) return <div className="flex items-center justify-center h-64"><Spinner size="lg" /></div>

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-xl font-bold text-white">🧠 Pattern Memory</h1>
          <p className="text-gray-400 text-xs mt-0.5">
            What SMBFlow has learned from your workflow runs — activate patterns you trust
          </p>
        </div>
        <Button size="sm" variant="ghost" onClick={load}>↻ Refresh</Button>
      </div>

      {/* Explainer */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="bg-yellow-900/10 border border-yellow-700/30 rounded-xl p-4">
          <div className="text-yellow-300 font-semibold text-sm mb-1">🟡 Sandbox Patterns</div>
          <p className="text-xs text-gray-400 leading-relaxed">
            New patterns start in the sandbox. They are NOT injected into the AI's reasoning yet.
            Review them and activate the ones that look correct.
          </p>
          <div className="text-yellow-400 font-bold text-lg mt-2">{pendingCount}</div>
        </div>
        <div className="bg-green-900/10 border border-green-700/30 rounded-xl p-4">
          <div className="text-green-300 font-semibold text-sm mb-1">🟢 Active Patterns</div>
          <p className="text-xs text-gray-400 leading-relaxed">
            Active patterns are injected into the Reasoning Agent's context on every run.
            They help the AI make better decisions based on past experience.
          </p>
          <div className="text-green-400 font-bold text-lg mt-2">{activeCount}</div>
        </div>
      </div>

      {error   && <Alert type="error"   onClose={() => setError('')}>{error}</Alert>}
      {success && <Alert type="success" onClose={() => setSuccess('')}>{success}</Alert>}

      {/* Tabs */}
      <TabGroup
        tabs={[
          { value: 'pending_review', label: '○ Sandbox',  badge: pendingCount },
          { value: 'active',         label: '● Active',   badge: activeCount  },
          { value: 'all',            label: '📋 All',      badge: 0            },
        ]}
        value={tab}
        onChange={setTab}
      />

      {/* Pattern list */}
      <Card
        title={tab === 'pending_review' ? 'Sandbox Patterns (awaiting your review)' : tab === 'active' ? 'Active Patterns' : 'All Patterns'}
        action={<span className="text-xs text-gray-500">{patterns.length} patterns</span>}
      >
        {patterns.length === 0 ? (
          <EmptyState
            icon="🧠"
            title={tab === 'pending_review' ? 'No sandbox patterns' : 'No patterns yet'}
            description={
              tab === 'pending_review'
                ? 'New patterns appear here after workflow runs complete. Run a workflow to start learning.'
                : 'Activate sandbox patterns to see them here.'
            }
          />
        ) : (
          <div className="space-y-3">
            {patterns.map(p => (
              <PatternCard
                key={p.id}
                pattern={p}
                loading={actionLoading}
                onPromote={promote}
                onDemote={demote}
                onView={setViewing}
              />
            ))}
          </div>
        )}
      </Card>

      <PatternModal pattern={viewing} open={!!viewing} onClose={() => setViewing(null)} />
    </div>
  )
}