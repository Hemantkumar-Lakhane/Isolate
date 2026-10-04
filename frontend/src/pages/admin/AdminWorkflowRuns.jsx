// frontend/src/pages/admin/AdminWorkflowRuns.jsx
// Data from: GET /api/v1/admin/runs  (platform admin endpoint, org-joined)
// GET /api/v1/admin/runs/:runId for detail + agent_runs
import { useState, useEffect, useCallback, useMemo } from 'react'
import {
  Zap, Search, RefreshCw, Building2, XCircle,
  CheckCircle2, AlertTriangle, Clock, ChevronDown, ChevronUp,
  ArrowLeft, Cpu, DollarSign, Eye, ShieldCheck, Activity, Terminal
} from 'lucide-react'
import { useAuth } from '../../contexts/AuthContext'
import { EmptyState } from '../../components/ui'

// ── helpers ───────────────────────────────────────────────────────────────────
function timeAgo(iso) {
  if (!iso) return '—'
  const diff = Date.now() - new Date(iso).getTime()
  const m = Math.floor(diff / 60000)
  if (m < 1) return 'just now'
  if (m < 60) return `${m}m ago`
  const h = Math.floor(m / 60)
  if (h < 24) return `${h}h ago`
  return `${Math.floor(h / 24)}d ago`
}

function fmtDuration(ms) {
  if (!ms) return '—'
  if (ms < 1000) return `${ms}ms`
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`
  return `${(ms / 60000).toFixed(1)}m`
}

function fmtTokens(n) {
  if (!n) return '0'
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000)     return `${(n / 1_000).toFixed(1)}K`
  return String(n)
}

function fmtCost(v) {
  if (v === null || v === undefined) return '—'
  return `$${Number(v).toFixed(4)}`
}

// ── Status badge ──────────────────────────────────────────────────────────────
function StatusBadge({ status }) {
  const map = {
    completed:   'bg-emerald-50 dark:bg-emerald-950/60 text-emerald-700 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-800/80',
    running:     'bg-blue-50 dark:bg-blue-950/60 text-blue-700 dark:text-blue-400 border border-blue-200 dark:border-blue-800/80',
    failed:      'bg-red-50 dark:bg-red-950/60 text-red-700 dark:text-red-400 border border-red-200 dark:border-red-800/80',
    pending:     'bg-slate-100 dark:bg-slate-800/60 text-slate-600 dark:text-slate-400 border border-slate-200 dark:border-slate-700',
    escalated:   'bg-amber-50 dark:bg-amber-950/60 text-amber-700 dark:text-amber-400 border border-amber-200 dark:border-amber-800/80',
    pending_a2a: 'bg-yellow-50 dark:bg-yellow-950/60 text-yellow-700 dark:text-yellow-400 border border-yellow-200 dark:border-yellow-800/80',
    paused:      'bg-yellow-50 dark:bg-yellow-950/60 text-yellow-700 dark:text-yellow-400 border border-yellow-200 dark:border-yellow-800/80',
  }
  return (
    <span className={`px-2.5 py-0.5 rounded-full text-[11px] font-mono font-semibold capitalize ${map[status] || 'bg-slate-100 dark:bg-slate-800 text-slate-500'}`}>
      {status || 'unknown'}
    </span>
  )
}

// ── Run detail drawer ─────────────────────────────────────────────────────────
function RunDetail({ runId, api, onClose }) {
  const [detail, setDetail] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    if (!runId) return
    setLoading(true)
    api.get(`/admin/runs/${runId}`)
      .then(d => setDetail(d))
      .catch(e => setError(e?.response?.data?.detail || e.message || 'Failed to load run'))
      .finally(() => setLoading(false))
  }, [runId, api])

  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/60 backdrop-blur-xs" onClick={onClose} />
      <div className="relative bg-white dark:bg-[#121826] text-slate-900 dark:text-white rounded-2xl shadow-2xl w-full max-w-3xl border border-slate-200 dark:border-[#233048] flex flex-col max-h-[85vh] overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100 dark:border-[#1e2a3f] shrink-0 bg-slate-50/50 dark:bg-[#162030]/60">
          <div className="flex items-center gap-3">
            <button onClick={onClose} className="p-1.5 rounded-lg text-slate-400 hover:text-slate-700 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-[#1c273c] transition-colors">
              <ArrowLeft size={16} />
            </button>
            <div>
              <p className="text-sm font-bold text-slate-900 dark:text-white">
                {loading ? 'Loading…' : detail?.workflow || 'Run Detail'}
              </p>
              <p className="text-xs font-mono text-slate-400">{runId?.slice(0, 16)}…</p>
            </div>
          </div>
          {detail && <StatusBadge status={detail.status} />}
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {loading ? (
            <div className="flex items-center justify-center py-16 text-slate-400 text-sm">Loading telemetry trace…</div>
          ) : error ? (
            <div className="flex items-center gap-2 px-4 py-3 bg-red-50 dark:bg-red-950/60 border border-red-200 dark:border-red-800 rounded-xl text-sm text-red-700 dark:text-red-300">
              <XCircle size={14} />{error}
            </div>
          ) : detail ? (
            <div className="flex flex-col gap-5">
              {/* Meta grid */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                {[
                  { label: 'Organization', value: detail.organization },
                  { label: 'Duration',     value: fmtDuration(detail.duration_ms) },
                  { label: 'Tokens In',    value: fmtTokens(detail.tokens_in) },
                  { label: 'Tokens Out',   value: fmtTokens(detail.tokens_out) },
                  { label: 'Cost',         value: fmtCost(detail.cost_usd) },
                  { label: 'Started',      value: detail.started_at ? new Date(detail.started_at).toLocaleString() : '—' },
                  { label: 'Completed',    value: detail.completed_at ? new Date(detail.completed_at).toLocaleString() : '—' },
                  { label: 'Current Node', value: detail.current_node || '—' },
                ].map(item => (
                  <div key={item.label} className="bg-slate-50 dark:bg-[#162030] border border-slate-200 dark:border-[#233048] rounded-xl p-3">
                    <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wide">{item.label}</p>
                    <p className="text-sm font-semibold text-slate-900 dark:text-white mt-0.5 truncate">{item.value}</p>
                  </div>
                ))}
              </div>

              {/* Error log */}
              {detail.error_log && (
                <div>
                  <p className="text-xs font-bold text-slate-400 uppercase tracking-wide mb-2">Error Diagnostic</p>
                  <pre className="text-xs font-mono text-red-700 dark:text-red-400 bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-800 rounded-xl p-4 overflow-x-auto whitespace-pre-wrap">
                    {detail.error_log}
                  </pre>
                </div>
              )}

              {/* Agent runs */}
              {detail.agent_runs?.length > 0 && (
                <div>
                  <p className="text-xs font-bold text-slate-400 uppercase tracking-wide mb-2">
                    Multi-Agent Execution Steps ({detail.agent_runs.length})
                  </p>
                  <div className="flex flex-col gap-2">
                    {detail.agent_runs.map((ar, i) => (
                      <div key={ar.id || i} className="flex items-center justify-between px-4 py-3 bg-white dark:bg-[#162030] border border-slate-200 dark:border-[#233048] rounded-xl">
                        <div className="flex items-center gap-3 min-w-0">
                          <div className="w-7 h-7 rounded-lg bg-blue-50 dark:bg-blue-950/60 border border-blue-200 dark:border-blue-800 flex items-center justify-center shrink-0">
                            <Cpu size={13} className="text-blue-600 dark:text-blue-400" />
                          </div>
                          <div className="min-w-0">
                            <p className="text-xs font-bold text-slate-900 dark:text-white truncate">{ar.node_id || ar.agent_capability}</p>
                            <p className="text-[11px] text-slate-400 font-mono">{ar.model_used || 'Claude 3.5 / GPT-4o'}</p>
                          </div>
                        </div>
                        <div className="flex items-center gap-4 shrink-0 text-xs text-slate-500 dark:text-slate-400 font-mono">
                          <span>{fmtTokens((ar.tokens_in || 0) + (ar.tokens_out || 0))} tok</span>
                          <span className="font-semibold text-emerald-600 dark:text-emerald-400">{fmtCost(ar.cost_usd)}</span>
                          <StatusBadge status={ar.status} />
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ) : null}
        </div>
      </div>
    </div>
  )
}

// ── Main component ─────────────────────────────────────────────────────────────
export default function AdminWorkflowRuns() {
  const { api } = useAuth()
  const [runs, setRuns]         = useState([])
  const [orgs, setOrgs]         = useState([])
  const [loading, setLoading]   = useState(true)
  const [error, setError]       = useState(null)
  const [search, setSearch]     = useState('')
  const [statusFilter, setStatusFilter] = useState('all')
  const [orgFilter, setOrgFilter]       = useState('all')
  const [detailRunId, setDetailRunId]   = useState(null)

  const load = useCallback(async () => {
    setLoading(true); setError(null)
    try {
      const [runsData, orgsData] = await Promise.all([
        api.get('/admin/runs?limit=200'),
        api.get('/admin/organizations').catch(() => []),
      ])
      setRuns(Array.isArray(runsData) ? runsData : [])
      setOrgs(Array.isArray(orgsData) ? orgsData : [])
    } catch (e) {
      setError(e?.response?.data?.detail || e.message || 'Failed to load runs')
    } finally {
      setLoading(false)
    }
  }, [api])

  useEffect(() => { load() }, [load])

  const filtered = useMemo(() => {
    let list = runs
    if (search) {
      const q = search.toLowerCase()
      list = list.filter(r =>
        r.run_id?.toLowerCase().includes(q) ||
        r.workflow?.toLowerCase().includes(q) ||
        r.organization?.toLowerCase().includes(q)
      )
    }
    if (statusFilter !== 'all') list = list.filter(r => r.status === statusFilter)
    if (orgFilter    !== 'all') list = list.filter(r => r.organization_id === orgFilter)
    return list
  }, [runs, search, statusFilter, orgFilter])

  // Summary counts
  const counts = useMemo(() => ({
    total:     runs.length,
    completed: runs.filter(r => r.status === 'completed').length,
    running:   runs.filter(r => r.status === 'running').length,
    failed:    runs.filter(r => r.status === 'failed').length,
  }), [runs])

  return (
    <div className="flex flex-col gap-6 p-6 min-h-full bg-slate-50 dark:bg-[#0b0f17] text-slate-900 dark:text-slate-100 font-sans transition-colors">
      {detailRunId && (
        <RunDetail runId={detailRunId} api={api} onClose={() => setDetailRunId(null)} />
      )}

      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-white tracking-tight">Workflow Runs</h1>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
            {loading ? 'Fetching execution stream…' : `${runs.length} workflow run execution records across all organizations.`}
          </p>
        </div>
        <button
          onClick={load}
          disabled={loading}
          className="p-2.5 rounded-xl text-slate-600 dark:text-slate-300 bg-white dark:bg-[#162030] border border-slate-200 dark:border-[#233048] hover:bg-slate-50 dark:hover:bg-[#1c273c] transition-colors shadow-2xs cursor-pointer disabled:opacity-50"
          title="Refresh Run Stream"
        >
          <RefreshCw size={15} className={loading ? 'animate-spin text-blue-500' : ''} />
        </button>
      </div>

      {/* Summary KPI Cards */}
      {!loading && !error && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3.5">
          {[
            { label: 'Total Runs', value: counts.total, cls: 'text-slate-900 dark:text-white', icon: Activity, accent: 'bg-slate-100 dark:bg-slate-800 text-slate-500' },
            { label: 'Completed',  value: counts.completed, cls: 'text-emerald-600 dark:text-emerald-400', icon: CheckCircle2, accent: 'bg-emerald-50 dark:bg-emerald-950/60 text-emerald-600 dark:text-emerald-400' },
            { label: 'Running',    value: counts.running, cls: 'text-blue-600 dark:text-blue-400', icon: Zap, accent: 'bg-blue-50 dark:bg-blue-950/60 text-blue-600 dark:text-blue-400' },
            { label: 'Failed',     value: counts.failed, cls: 'text-red-600 dark:text-red-400', icon: AlertTriangle, accent: 'bg-red-50 dark:bg-red-950/60 text-red-600 dark:text-red-400' },
          ].map(c => {
            const IconComp = c.icon
            return (
              <div key={c.label} className="bg-white dark:bg-[#121826] border border-slate-200 dark:border-[#233048] rounded-2xl p-4.5 shadow-2xs flex items-center justify-between">
                <div>
                  <p className="text-[11px] font-bold text-slate-400 uppercase tracking-wider">{c.label}</p>
                  <p className={`text-2xl font-extrabold ${c.cls} mt-1`}>{c.value}</p>
                </div>
                <div className={`w-9 h-9 rounded-xl flex items-center justify-center ${c.accent}`}>
                  <IconComp size={18} />
                </div>
              </div>
            )
          })}
        </div>
      )}

      {error && (
        <div className="flex items-center gap-2 px-4 py-3 bg-red-50 dark:bg-red-950/60 border border-red-200 dark:border-red-800 rounded-xl text-sm text-red-700 dark:text-red-300">
          <XCircle size={16} className="shrink-0" />{error}
        </div>
      )}

      {/* Filters Bar */}
      <div className="flex items-center gap-3 flex-wrap">
        <div className="relative flex-1 min-w-[220px]">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" />
          <input
            type="text"
            placeholder="Search by run ID, workflow, or organization…"
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="w-full pl-9 pr-3 py-2 text-xs bg-white dark:bg-[#162030] border border-slate-200 dark:border-[#2a3850] rounded-xl text-slate-900 dark:text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 transition-all"
          />
        </div>
        <select
          value={statusFilter}
          onChange={e => setStatusFilter(e.target.value)}
          className="px-3 py-2 text-xs bg-white dark:bg-[#162030] border border-slate-200 dark:border-[#2a3850] rounded-xl text-slate-900 dark:text-white focus:outline-none focus:border-blue-500 cursor-pointer"
        >
          <option value="all">All statuses</option>
          {['completed','running','failed','pending','escalated','paused'].map(s => (
            <option key={s} value={s}>{s.charAt(0).toUpperCase() + s.slice(1)}</option>
          ))}
        </select>
        <select
          value={orgFilter}
          onChange={e => setOrgFilter(e.target.value)}
          className="px-3 py-2 text-xs bg-white dark:bg-[#162030] border border-slate-200 dark:border-[#2a3850] rounded-xl text-slate-900 dark:text-white focus:outline-none focus:border-blue-500 cursor-pointer"
        >
          <option value="all">All organizations</option>
          {orgs.map(o => <option key={o.id} value={o.id}>{o.name}</option>)}
        </select>
      </div>

      {/* Runs Table */}
      {loading ? (
        <div className="flex items-center justify-center h-48 text-slate-400 text-xs">Loading execution stream…</div>
      ) : filtered.length === 0 ? (
        <EmptyState icon={Zap} title="No runs found"
          description={search || statusFilter !== 'all' || orgFilter !== 'all' ? 'Try adjusting your search criteria.' : 'No workflow runs recorded yet.'} />
      ) : (
        <div className="bg-white dark:bg-[#121826] border border-slate-200 dark:border-[#233048] rounded-2xl overflow-hidden shadow-2xs">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-slate-100 dark:border-[#1e2a3f] bg-slate-50/70 dark:bg-[#162030]/60">
                  {['Run ID', 'Workflow', 'Organization', 'Status', 'Duration', 'Tokens', 'Cost', 'Started', 'Actions'].map(h => (
                    <th key={h} className="px-4 py-3 text-[11px] font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider whitespace-nowrap">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-[#1a2336]">
                {filtered.map(r => (
                  <tr
                    key={r.run_id}
                    className="hover:bg-slate-50 dark:hover:bg-[#162030]/50 transition-colors cursor-pointer"
                    onClick={() => setDetailRunId(r.run_id)}
                  >
                    <td className="px-4 py-3 font-mono font-bold text-blue-600 dark:text-blue-400">
                      {r.run_id?.slice(0, 8)}…
                    </td>
                    <td className="px-4 py-3">
                      <p className="font-bold text-slate-900 dark:text-white max-w-[150px] truncate">{r.workflow}</p>
                    </td>
                    <td className="px-4 py-3">
                      <span className="inline-flex items-center gap-1.5 text-slate-600 dark:text-slate-300">
                        <Building2 size={12} className="text-slate-400 shrink-0" />
                        <span className="truncate max-w-[120px] font-medium">{r.organization || 'Unknown'}</span>
                      </span>
                    </td>
                    <td className="px-4 py-3"><StatusBadge status={r.status} /></td>
                    <td className="px-4 py-3 text-slate-500 dark:text-slate-400 font-mono">{fmtDuration(r.duration_ms)}</td>
                    <td className="px-4 py-3 text-slate-500 dark:text-slate-400 font-mono">{fmtTokens(r.tokens)}</td>
                    <td className="px-4 py-3 font-bold text-emerald-600 dark:text-emerald-400 font-mono">{fmtCost(r.cost_usd)}</td>
                    <td className="px-4 py-3 text-slate-400 whitespace-nowrap">{timeAgo(r.started_at)}</td>
                    <td className="px-4 py-3">
                      <button
                        type="button"
                        onClick={e => { e.stopPropagation(); setDetailRunId(r.run_id) }}
                        className="px-2.5 py-1 text-xs font-semibold text-blue-600 dark:text-blue-400 bg-blue-50 dark:bg-blue-950/60 border border-blue-200 dark:border-blue-800/80 rounded-lg hover:bg-blue-100 dark:hover:bg-blue-900/60 transition-colors cursor-pointer"
                      >
                        Detail
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
