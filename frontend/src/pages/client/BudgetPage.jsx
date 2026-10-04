// frontend/src/pages/client/BudgetPage.jsx
// Industry-aware Usage & Billing page.
//
// The page title is derived dynamically from the org's industry
// (e.g. "Healthcare Usage & Billing", "Finance Usage & Billing").
//
// Usage data is fetched from GET /api/v1/billing/summary which:
//   - Returns only workflows applicable to the org's industry
//   - Excludes cross-industry workflows from cost calculations
//   - Derives industry from the authenticated org (never trusted from frontend)
//
// Budget settings (optimization level, caching) are preserved from the
// previous implementation via GET/PUT /tenants/:id/budget.

import { useState, useEffect, useCallback } from 'react'
import { useAuth } from '../../contexts/AuthContext'
import {
  DollarSign, RefreshCw, TrendingUp, Zap,
  CheckCircle2, AlertTriangle, ChevronDown, ChevronUp,
} from 'lucide-react'
import { fmtCost } from '../../utils/helpers'

// ── helpers ───────────────────────────────────────────────────────────────────
const INDUSTRY_LABELS = {
  saas:        'SaaS / Growth',
  healthcare:  'Healthcare',
  finance:     'Finance',
  real_estate: 'Real Estate',
  retail:      'Retail',
  general:     'General',
}

function industryTitle(industry) {
  if (!industry) return 'Usage & Billing'
  const label = INDUSTRY_LABELS[industry] || (industry.charAt(0).toUpperCase() + industry.slice(1))
  return `${label} Usage & Billing`
}

function fmtRuns(n) {
  if (n == null) return '—'
  return n.toLocaleString()
}

function fmtTokens(n) {
  if (!n) return '0'
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000)     return `${(n / 1_000).toFixed(1)}K`
  return n.toString()
}

// ── Stat card ─────────────────────────────────────────────────────────────────
function StatCard({ label, value, icon: Icon, accent = 'blue', note }) {
  const accents = {
    blue:   'bg-blue-50 text-blue-600',
    green:  'bg-emerald-50 text-emerald-600',
    orange: 'bg-orange-50 text-orange-600',
    slate:  'bg-slate-100 text-slate-500',
  }
  return (
    <div className="bg-white border border-gray-200 rounded-xl p-4 shadow-sm flex flex-col gap-2">
      <div className="flex items-center justify-between">
        <p className="text-xs font-medium text-gray-500">{label}</p>
        <div className={`w-7 h-7 rounded-lg flex items-center justify-center ${accents[accent]}`}>
          <Icon size={14} />
        </div>
      </div>
      <p className="text-xl font-bold text-gray-900">{value ?? <span className="text-gray-300 text-base font-normal">No data</span>}</p>
      {note && <p className="text-[11px] text-gray-400">{note}</p>}
    </div>
  )
}

// ── Workflow usage row ────────────────────────────────────────────────────────
function WorkflowRow({ wf, rank }) {
  const [expanded, setExpanded] = useState(false)
  const hasDetails = wf.tokens_in > 0 || wf.tokens_out > 0

  return (
    <>
      <tr
        className={`border-b border-gray-100 hover:bg-gray-50 transition-colors ${hasDetails ? 'cursor-pointer' : ''}`}
        onClick={() => hasDetails && setExpanded(e => !e)}
      >
        <td className="px-4 py-3">
          <div className="flex items-center gap-2">
            <span className="w-5 h-5 rounded-full bg-blue-50 text-blue-600 text-[10px] font-bold flex items-center justify-center shrink-0">
              {rank}
            </span>
            <div>
              <p className="text-sm font-medium text-gray-900">
                {wf.workflow_key?.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase()) || '—'}
              </p>
              <p className="text-[11px] text-gray-400 font-mono">{wf.workflow_key}</p>
            </div>
          </div>
        </td>
        <td className="px-4 py-3 text-center">
          <span className="text-sm font-semibold text-gray-900">{fmtRuns(wf.run_count)}</span>
          <span className="text-xs text-gray-400 ml-1">run{wf.run_count !== 1 ? 's' : ''}</span>
        </td>
        <td className="px-4 py-3 text-right">
          {wf.cost_usd != null
            ? <span className="text-sm font-semibold text-gray-900">{fmtCost(wf.cost_usd)}</span>
            : <span className="text-xs text-gray-400 italic">Not reported</span>}
        </td>
        <td className="px-4 py-3 text-center w-8">
          {hasDetails
            ? (expanded ? <ChevronUp size={13} className="text-gray-400" /> : <ChevronDown size={13} className="text-gray-400" />)
            : null}
        </td>
      </tr>
      {expanded && hasDetails && (
        <tr className="bg-slate-50 border-b border-gray-100">
          <td colSpan={4} className="px-8 py-2">
            <div className="flex items-center gap-6 text-xs text-gray-500">
              <span>Tokens in: <strong className="text-gray-700">{fmtTokens(wf.tokens_in)}</strong></span>
              <span>Tokens out: <strong className="text-gray-700">{fmtTokens(wf.tokens_out)}</strong></span>
              <span>Total qty: <strong className="text-gray-700">{fmtRuns(wf.total_quantity)}</strong></span>
            </div>
          </td>
        </tr>
      )}
    </>
  )
}

// ── Budget settings section (preserved from original) ─────────────────────────
function BudgetSettings({ tenantId, api }) {
  const [settings, setSettings] = useState(null)
  const [loading,  setLoading]  = useState(true)
  const [saving,   setSaving]   = useState(false)
  const [success,  setSuccess]  = useState('')
  const [error,    setError]    = useState('')

  useEffect(() => {
    if (!tenantId) { setLoading(false); return }
    api.get(`/tenants/${tenantId}/budget`)
      .then(d => setSettings(d))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [tenantId, api])

  async function save() {
    if (!settings || !tenantId) return
    setSaving(true); setError(''); setSuccess('')
    try {
      await api.put(`/tenants/${tenantId}/budget`, {
        optimization_level:              settings.optimization_level              ?? 1,
        enable_caching:                  settings.enable_caching                  ?? true,
        cache_ttl_seconds:               settings.cache_ttl_seconds               ?? 3600,
        max_context_tokens:              settings.max_context_tokens              ?? 10000,
        a2a_enabled:                     settings.a2a_enabled                     ?? false,
        auto_retry_on_low_confidence:    settings.auto_retry_on_low_confidence    ?? true,
        confidence_retry_threshold:      settings.confidence_retry_threshold      ?? 0.6,
        enable_map_reduce_summarization: settings.enable_map_reduce_summarization ?? false,
      })
      setSuccess('Settings saved!')
      setTimeout(() => setSuccess(''), 3000)
    } catch (err) { setError(err.message) }
    finally { setSaving(false) }
  }

  if (loading) return null
  if (!settings) return (
    <div className="bg-white border border-gray-200 rounded-xl shadow-sm p-6">
      <h2 className="text-base font-bold text-gray-900 mb-2">AI Budget Settings</h2>
      <p className="text-sm text-gray-400">No budget settings found. Run a workflow to initialize.</p>
    </div>
  )

  return (
    <div className="bg-white border border-gray-200 rounded-xl shadow-sm p-6">
      <h2 className="text-base font-bold text-gray-900 mb-4">AI Budget Settings</h2>
      {success && <div className="mb-3 p-2.5 bg-green-50 border border-green-200 text-green-700 rounded-lg text-sm">{success}</div>}
      {error   && <div className="mb-3 p-2.5 bg-red-50 border border-red-200 text-red-700 rounded-lg text-sm">{error}</div>}

      <div className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">Optimization Level</label>
          <div className="grid grid-cols-4 gap-2">
            {[0,1,2,3].map(n => {
              const labels = ['Max Accuracy','Balanced','Aggressive','Budget First']
              const active = settings?.optimization_level === n
              return (
                <button key={n} onClick={() => setSettings(s => ({ ...s, optimization_level: n }))}
                  className={`py-2 px-3 rounded-lg text-xs font-semibold border transition-colors ${
                    active ? 'bg-blue-600 text-white border-blue-600' : 'bg-white text-gray-600 border-gray-200 hover:border-blue-300'
                  }`}>
                  {labels[n]}
                </button>
              )
            })}
          </div>
        </div>

        <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg border border-gray-100">
          <div>
            <p className="text-sm font-medium text-gray-700">Semantic Caching</p>
            <p className="text-xs text-gray-400 mt-0.5">Reduce costs by caching similar LLM responses</p>
          </div>
          <button
            onClick={() => setSettings(s => ({ ...s, enable_caching: !s.enable_caching }))}
            className={`relative w-10 h-5 rounded-full transition-colors ${settings?.enable_caching ? 'bg-blue-600' : 'bg-gray-300'}`}
          >
            <div className={`absolute top-0.5 w-4 h-4 bg-white rounded-full shadow transition-transform ${settings?.enable_caching ? 'translate-x-5' : 'translate-x-0.5'}`} />
          </button>
        </div>

        <button onClick={save} disabled={saving}
          className="px-5 py-2.5 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white text-sm font-semibold rounded-lg transition-colors">
          {saving ? 'Saving…' : 'Save Settings'}
        </button>
      </div>
    </div>
  )
}

// ── Main ──────────────────────────────────────────────────────────────────────
export default function BudgetPage() {
  const { user, api } = useAuth()
  const tenantId = user?.tenant_id

  const [summary,  setSummary]  = useState(null)
  const [loading,  setLoading]  = useState(true)
  const [error,    setError]    = useState('')
  const [days,     setDays]     = useState(30)

  const loadSummary = useCallback(async () => {
    if (!tenantId) { setLoading(false); return }
    setLoading(true); setError('')
    try {
      // GET /api/v1/billing/summary — org-scoped, industry-filtered
      const data = await api.get(`/billing/summary?days=${days}`)
      setSummary(data)
    } catch (err) {
      // Graceful fallback: if the endpoint doesn't exist yet (pre-migration),
      // show empty state rather than an error
      if (err?.status === 404 || err?.response?.status === 404) {
        setSummary(null)
      } else {
        setError(err?.response?.data?.detail || err.message || 'Failed to load billing data')
      }
    } finally {
      setLoading(false)
    }
  }, [api, tenantId, days])

  useEffect(() => { loadSummary() }, [loadSummary])

  const title    = industryTitle(summary?.industry)
  const runs     = summary?.total_run_count ?? null
  const cost     = summary?.total_cost_usd  ?? null
  const breakdown = summary?.workflow_breakdown || []

  return (
    <div className="p-6 bg-gray-50 min-h-full">

      {/* Header — title derived from org industry, not hardcoded */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">{title}</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            Workflow usage and cost for your organization
          </p>
        </div>
        <div className="flex items-center gap-2">
          {/* Period selector */}
          <select
            value={days}
            onChange={e => setDays(Number(e.target.value))}
            className="px-3 py-2 text-sm bg-white border border-gray-200 rounded-lg focus:outline-none"
          >
            <option value={7}>Last 7 days</option>
            <option value={30}>Last 30 days</option>
            <option value={90}>Last 90 days</option>
          </select>
          <button onClick={loadSummary} disabled={loading}
            className="p-2 rounded-lg text-slate-500 bg-white border border-gray-200 hover:bg-gray-50 transition-colors disabled:opacity-50">
            <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
          </button>
        </div>
      </div>

      {error && (
        <div className="mb-4 flex items-center gap-2 p-3 bg-red-50 border border-red-200 text-red-700 rounded-lg text-sm">
          <AlertTriangle size={14} />{error}
        </div>
      )}

      {/* Stat cards */}
      <div className="grid grid-cols-2 lg:grid-cols-3 gap-4 mb-6">
        <StatCard
          label="Total Workflow Runs"
          value={loading ? '…' : fmtRuns(runs)}
          icon={Zap}
          accent="blue"
          note={`Last ${days} days`}
        />
        <StatCard
          label="Total Cost"
          value={loading ? '…' : cost != null ? fmtCost(cost) : null}
          icon={DollarSign}
          accent={cost != null && cost > 0 ? 'orange' : 'slate'}
          note={cost == null ? 'Provider cost not reported' : `Last ${days} days`}
        />
        <StatCard
          label="Unique Workflows Used"
          value={loading ? '…' : breakdown.filter(w => w.run_count > 0).length || null}
          icon={TrendingUp}
          accent="green"
          note="Workflows with at least 1 run"
        />
      </div>

      {/* Usage table */}
      <div className="bg-white border border-gray-200 rounded-xl shadow-sm mb-6">
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
          <h2 className="text-base font-bold text-gray-900">Workflow Usage Breakdown</h2>
          <span className="text-xs text-gray-400">
            All workflows executed by your organization
          </span>
        </div>

        {loading ? (
          <div className="flex items-center justify-center h-40 text-gray-400 text-sm">
            <RefreshCw size={14} className="animate-spin mr-2" /> Loading usage data…
          </div>
        ) : breakdown.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-40 gap-3">
            <CheckCircle2 className="w-8 h-8 text-gray-300" />
            <div className="text-center">
              <p className="text-sm font-medium text-gray-500">No workflow runs yet</p>
              <p className="text-xs text-gray-400 mt-1">
                Usage data will appear here once your workflows start running.
              </p>
            </div>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-100 bg-gray-50">
                  <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">Workflow</th>
                  <th className="px-4 py-3 text-center text-xs font-semibold text-gray-500 uppercase tracking-wide">Runs</th>
                  <th className="px-4 py-3 text-right text-xs font-semibold text-gray-500 uppercase tracking-wide">Cost</th>
                  <th className="w-8" />
                </tr>
              </thead>
              <tbody>
                {breakdown.map((wf, i) => (
                  <WorkflowRow key={wf.workflow_key || i} wf={wf} rank={i + 1} />
                ))}
              </tbody>
              {/* Totals row */}
              <tfoot>
                <tr className="bg-gray-50 border-t border-gray-200">
                  <td className="px-4 py-3 text-sm font-bold text-gray-900">Total</td>
                  <td className="px-4 py-3 text-center text-sm font-bold text-gray-900">{fmtRuns(runs)}</td>
                  <td className="px-4 py-3 text-right text-sm font-bold text-gray-900">
                    {cost != null ? fmtCost(cost) : <span className="text-gray-400 font-normal text-xs">Not reported</span>}
                  </td>
                  <td />
                </tr>
              </tfoot>
            </table>
          </div>
        )}
      </div>

      {/* Budget / AI optimization settings — preserved from original */}
      <BudgetSettings tenantId={tenantId} api={api} />
    </div>
  )
}
