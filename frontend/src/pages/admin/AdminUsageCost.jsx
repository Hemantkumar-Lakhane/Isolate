// AdminUsageCost — Usage & Metering
import { useState, useEffect, useCallback, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  BarChart3, RefreshCw, XCircle, Search,
  DollarSign, Zap, Cpu, Image, ChevronRight, Activity,
} from 'lucide-react'
import { useAuth } from '../../contexts/AuthContext'
import { EmptyState } from '../../components/ui'

// ── helpers ───────────────────────────────────────────────────────────────────
function fmtCost(v) {
  if (v === null || v === undefined) return 'No data'
  return `$${Number(v).toFixed(4)}`
}
function fmtTokens(n) {
  if (!n) return '0'
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(2)}M`
  if (n >= 1_000)     return `${(n / 1_000).toFixed(1)}K`
  return n.toString()
}
function fmt(n) {
  if (n === null || n === undefined) return '—'
  return Number(n).toLocaleString()
}

const DAYS_OPTIONS = [7, 14, 30, 60, 90]

// ── Summary card ──────────────────────────────────────────────────────────────
function MetricCard({ label, value, icon: Icon, accent = 'slate', note }) {
  const accents = {
    blue:   'bg-blue-500/10 text-blue-600 dark:text-blue-400 border border-blue-500/20',
    purple: 'bg-purple-500/10 text-purple-600 dark:text-purple-400 border border-purple-500/20',
    orange: 'bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20',
    green:  'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20',
    slate:  'bg-slate-500/10 text-slate-600 dark:text-slate-400 border border-slate-500/20',
  }
  return (
    <div className="bg-white dark:bg-[#121826] border border-slate-200 dark:border-[#233048] rounded-2xl p-5 flex items-start gap-4 shadow-2xs">
      <div className={`p-3 rounded-xl shrink-0 ${accents[accent]}`}>
        <Icon size={18} strokeWidth={2} />
      </div>
      <div className="min-w-0">
        <p className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider mb-1">{label}</p>
        <p className="text-2xl font-bold text-slate-900 dark:text-white tracking-tight">{value}</p>
        {note && <p className="text-xs text-slate-400 dark:text-slate-500 mt-1 font-medium">{note}</p>}
      </div>
    </div>
  )
}

// ── Usage breakdown table ─────────────────────────────────────────────────────
function UsageTable({ rows, loading }) {
  const [search, setSearch] = useState('')

  const filtered = useMemo(() => {
    if (!search) return rows
    const q = search.toLowerCase()
    return rows.filter(r =>
      r.usage_type?.toLowerCase().includes(q) ||
      r.workflow_key?.toLowerCase().includes(q)
    )
  }, [rows, search])

  return (
    <div className="bg-white dark:bg-[#121826] border border-slate-200 dark:border-[#233048] rounded-2xl overflow-hidden shadow-2xs">
      <div className="flex items-center justify-between px-5 py-4 border-b border-slate-100 dark:border-[#1e2a3f] flex-wrap gap-3">
        <div>
          <h2 className="text-sm font-bold text-slate-900 dark:text-white">Usage Breakdown</h2>
          <p className="text-xs text-slate-500 dark:text-slate-400">Tokens, runs, and event metrics partitioned by type</p>
        </div>
        <div className="relative">
          <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" />
          <input
            type="text" placeholder="Filter usage type…" value={search}
            onChange={e => setSearch(e.target.value)}
            className="pl-8 pr-3 py-1.5 text-xs bg-slate-50 dark:bg-[#162030] border border-slate-200 dark:border-[#2a3850] text-slate-900 dark:text-white rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 w-48 placeholder-slate-400"
          />
        </div>
      </div>
      {loading ? (
        <div className="py-12 text-center text-slate-400 text-sm">Loading usage events…</div>
      ) : filtered.length === 0 ? (
        <div className="py-12 text-center text-slate-400 text-sm">
          {rows.length === 0 ? 'No usage events in this period' : 'No results for your filter'}
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-100 dark:border-[#1e2a3f] bg-slate-50/70 dark:bg-[#162030]/60">
                {['Usage Type', 'Workflow', 'Events', 'Tokens In', 'Tokens Out', 'Quantity'].map(h => (
                  <th key={h} className="px-5 py-3 text-left text-[11px] font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-[#1a2336]">
              {filtered.map((row, i) => (
                <tr key={i} className="hover:bg-slate-50/60 dark:hover:bg-[#162030]/50 transition-colors">
                  <td className="px-5 py-3.5 font-mono text-xs font-semibold text-slate-700 dark:text-slate-200">
                    <span className="px-2 py-0.5 rounded-md bg-blue-500/10 text-blue-600 dark:text-blue-400 border border-blue-500/20">
                      {row.usage_type}
                    </span>
                  </td>
                  <td className="px-5 py-3.5 text-xs text-slate-500 dark:text-slate-400 font-mono">{row.workflow_key || '—'}</td>
                  <td className="px-5 py-3.5 text-sm font-semibold text-slate-800 dark:text-slate-200">{fmt(row.event_count)}</td>
                  <td className="px-5 py-3.5 font-mono text-xs text-slate-500 dark:text-slate-400">{fmtTokens(row.tokens_in)}</td>
                  <td className="px-5 py-3.5 font-mono text-xs text-slate-500 dark:text-slate-400">{fmtTokens(row.tokens_out)}</td>
                  <td className="px-5 py-3.5 text-xs text-slate-500 dark:text-slate-400 font-mono">{fmt(row.total_quantity)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

// ── Per-org usage drill-down ──────────────────────────────────────────────────
function OrgUsageTable({ orgs, days, api, navigate }) {
  const [orgUsage, setOrgUsage] = useState({})
  const [loading, setLoading]   = useState({})

  async function loadOrg(orgId) {
    if (orgUsage[orgId] !== undefined) return
    setLoading(l => ({ ...l, [orgId]: true }))
    try {
      const d = await api.get(`/admin/usage/${orgId}?days=${days}`)
      setOrgUsage(u => ({ ...u, [orgId]: d }))
    } catch {
      setOrgUsage(u => ({ ...u, [orgId]: null }))
    } finally {
      setLoading(l => ({ ...l, [orgId]: false }))
    }
  }

  const [expanded, setExpanded] = useState(null)
  function toggle(orgId) {
    if (expanded === orgId) { setExpanded(null); return }
    setExpanded(orgId)
    loadOrg(orgId)
  }

  return (
    <div className="bg-white dark:bg-[#121826] border border-slate-200 dark:border-[#233048] rounded-2xl overflow-hidden shadow-2xs">
      <div className="px-5 py-4 border-b border-slate-100 dark:border-[#1e2a3f]">
        <h2 className="text-sm font-bold text-slate-900 dark:text-white">Usage by Organization</h2>
        <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">Click any workspace row to expand per-org telemetry &amp; billing</p>
      </div>
      {orgs.length === 0 ? (
        <div className="py-10 text-center text-slate-400 text-sm">No organizations registered</div>
      ) : (
        <div className="divide-y divide-slate-100 dark:divide-[#1a2336]">
          {orgs.map(org => (
            <div key={org.id}>
              <div
                className="flex items-center justify-between px-5 py-3.5 hover:bg-slate-50/60 dark:hover:bg-[#162030]/50 cursor-pointer transition-colors"
                onClick={() => toggle(org.id)}
              >
                <div className="flex items-center gap-3.5 min-w-0 flex-1">
                  <div className="w-8 h-8 rounded-lg bg-blue-500/10 border border-blue-500/20 flex items-center justify-center shrink-0">
                    <span className="text-blue-600 dark:text-blue-400 text-xs font-bold">{(org.name || '?')[0].toUpperCase()}</span>
                  </div>
                  <div className="min-w-0">
                    <p className="text-sm font-semibold text-slate-900 dark:text-white">{org.name}</p>
                    <p className="text-xs text-slate-500 dark:text-slate-400">{org.run_count ?? 0} runs · {org.plan_name || org.plan_slug || '—'}</p>
                  </div>
                </div>
                <div className="flex items-center gap-4 shrink-0">
                  <span className="text-xs font-mono font-medium text-slate-700 dark:text-slate-300">
                    {org.total_spend_usd !== null && org.total_spend_usd !== undefined
                      ? `$${Number(org.total_spend_usd).toFixed(4)}`
                      : 'No cost data'}
                  </span>
                  <button
                    onClick={e => { e.stopPropagation(); navigate(`/admin/organizations/${org.id}`) }}
                    className="p-1 text-slate-400 hover:text-blue-500 transition-colors"
                    title="View org"
                  >
                    <ChevronRight size={15} />
                  </button>
                  <span className={`text-slate-400 transition-transform ${expanded === org.id ? 'rotate-90' : ''}`}>
                    <ChevronRight size={15} />
                  </span>
                </div>
              </div>

              {expanded === org.id && (
                <div className="border-t border-slate-100 dark:border-[#1e2a3f] bg-slate-50/50 dark:bg-[#162030]/30 px-5 py-4">
                  {loading[org.id] ? (
                    <p className="text-xs text-slate-400 text-center py-4">Loading usage telemetry…</p>
                  ) : !orgUsage[org.id] ? (
                    <p className="text-xs text-slate-400 text-center py-4">No usage data for this organization</p>
                  ) : (
                    <div className="flex flex-col gap-3">
                      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                        {[
                          { label: 'Total Cost', value: fmtCost(orgUsage[org.id].total_cost_usd) },
                          { label: 'Reported Events', value: fmt(orgUsage[org.id].reported_events) },
                          { label: 'Unreported Events', value: fmt(orgUsage[org.id].unreported_events) },
                        ].map(item => (
                          <div key={item.label} className="bg-white dark:bg-[#121826] border border-slate-200 dark:border-[#233048] rounded-xl p-3.5 shadow-2xs">
                            <p className="text-[10px] font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide">{item.label}</p>
                            <p className="text-sm font-bold text-slate-900 dark:text-white mt-0.5">{item.value}</p>
                          </div>
                        ))}
                      </div>
                      {orgUsage[org.id].breakdown?.length > 0 && (
                        <div className="overflow-x-auto rounded-xl border border-slate-200 dark:border-[#233048]">
                          <table className="w-full text-xs bg-white dark:bg-[#121826]">
                            <thead>
                              <tr className="border-b border-slate-100 dark:border-[#1e2a3f] bg-slate-50/70 dark:bg-[#162030]/60">
                                {['Type', 'Workflow', 'Events', 'Tokens In', 'Tokens Out'].map(h => (
                                  <th key={h} className="px-3 py-2 text-left text-[10px] font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wide">{h}</th>
                                ))}
                              </tr>
                            </thead>
                            <tbody className="divide-y divide-slate-100 dark:divide-[#1a2336]">
                              {orgUsage[org.id].breakdown.map((row, i) => (
                                <tr key={i}>
                                  <td className="px-3 py-2 font-mono text-slate-700 dark:text-slate-300">{row.usage_type}</td>
                                  <td className="px-3 py-2 text-slate-500 dark:text-slate-400">{row.workflow_key || '—'}</td>
                                  <td className="px-3 py-2 font-medium text-slate-800 dark:text-slate-200">{fmt(row.event_count)}</td>
                                  <td className="px-3 py-2 font-mono text-slate-500 dark:text-slate-400">{fmtTokens(row.tokens_in)}</td>
                                  <td className="px-3 py-2 font-mono text-slate-500 dark:text-slate-400">{fmtTokens(row.tokens_out)}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ── Main component ─────────────────────────────────────────────────────────────
export default function AdminUsageCost() {
  const { api } = useAuth()
  const navigate = useNavigate()

  const [days, setDays]         = useState(30)
  const [usage, setUsage]       = useState(null)
  const [orgs, setOrgs]         = useState([])
  const [loading, setLoading]   = useState(true)
  const [error, setError]       = useState(null)

  const load = useCallback(async () => {
    setLoading(true); setError(null)
    try {
      const [u, o] = await Promise.all([
        api.get(`/admin/usage?days=${days}`),
        api.get('/admin/organizations').catch(() => []),
      ])
      setUsage(u)
      setOrgs(Array.isArray(o) ? o : [])
    } catch (e) {
      setError(e?.response?.data?.detail || e.message || 'Failed to load usage data')
    } finally {
      setLoading(false) }
  }, [api, days])

  useEffect(() => { load() }, [load])

  const summary = useMemo(() => {
    const b = usage?.breakdown || []
    return {
      wf_runs:    b.filter(r => r.usage_type === 'workflow_run').reduce((s, r) => s + (r.event_count || 0), 0),
      tokens_in:  b.reduce((s, r) => s + (r.tokens_in  || 0), 0),
      tokens_out: b.reduce((s, r) => s + (r.tokens_out || 0), 0),
      img_gens:   b.filter(r => r.usage_type === 'image_gen').reduce((s, r) => s + (r.event_count || 0), 0),
      cost:       usage?.total_cost_usd,
    }
  }, [usage])

  return (
    <div className="flex flex-col gap-6 p-6 min-h-full bg-slate-50 dark:bg-[#0b0f17] text-slate-900 dark:text-slate-100 transition-colors">

      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-xl font-bold text-slate-900 dark:text-white flex items-center gap-2">
            <Activity className="text-blue-500" size={22} />
            Usage &amp; Metering
          </h1>
          <p className="text-sm text-slate-500 dark:text-slate-400 mt-0.5">Platform-wide AI usage, token consumption, and cost</p>
        </div>
        <div className="flex items-center gap-2">
          <select
            value={days}
            onChange={e => setDays(Number(e.target.value))}
            className="px-3 py-2 text-sm bg-white dark:bg-[#121826] border border-slate-200 dark:border-[#233048] text-slate-900 dark:text-white rounded-xl focus:outline-none"
          >
            {DAYS_OPTIONS.map(d => <option key={d} value={d}>Last {d} days</option>)}
          </select>
          <button onClick={load} disabled={loading}
            className="p-2 rounded-xl text-slate-500 dark:text-slate-400 bg-white dark:bg-[#121826] border border-slate-200 dark:border-[#233048] hover:bg-slate-50 dark:hover:bg-[#162030] transition-colors disabled:opacity-50">
            <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
          </button>
        </div>
      </div>

      {error && (
        <div className="flex items-center gap-2 px-4 py-3 bg-red-500/10 border border-red-500/20 rounded-xl text-sm text-red-600 dark:text-red-400">
          <XCircle size={15} className="shrink-0" />{error}
        </div>
      )}

      {/* KPI cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <MetricCard label="Workflow Runs" value={loading ? '…' : fmt(summary.wf_runs)}
          icon={Zap} accent="blue" note={`Last ${days} days`} />
        <MetricCard label="AI Tokens In" value={loading ? '…' : fmtTokens(summary.tokens_in)}
          icon={Cpu} accent="purple" note="Prompt tokens" />
        <MetricCard label="AI Tokens Out" value={loading ? '…' : fmtTokens(summary.tokens_out)}
          icon={Cpu} accent="slate" note="Completion tokens" />
        <MetricCard label="Platform Cost" value={loading ? '…' : fmtCost(summary.cost)}
          icon={DollarSign} accent="green" note="Reported events" />
      </div>

      {/* Reported/unreported note */}
      {!loading && usage && (
        <div className="flex items-center gap-4 px-4 py-3 bg-slate-500/10 border border-slate-500/20 rounded-2xl text-xs text-slate-600 dark:text-slate-400 flex-wrap">
          <span><span className="font-semibold text-slate-900 dark:text-white">{fmt(usage.reported_events)}</span> events with cost telemetry</span>
          <span className="text-slate-400 dark:text-slate-600">·</span>
          <span><span className="font-semibold text-slate-900 dark:text-white">{fmt(usage.unreported_events)}</span> events without upstream provider cost</span>
        </div>
      )}

      {/* Platform breakdown table */}
      <UsageTable rows={usage?.breakdown || []} loading={loading} />

      {/* Per-org drill-down */}
      <OrgUsageTable orgs={orgs} days={days} api={api} navigate={navigate} />
    </div>
  )
}
