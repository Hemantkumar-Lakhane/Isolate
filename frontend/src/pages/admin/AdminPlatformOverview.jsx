// frontend/src/pages/admin/AdminPlatformOverview.jsx
// Real SaaS control-plane dashboard with full dark-mode design system
import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Building2, Users, Zap, AlertTriangle, DollarSign, RefreshCw,
  TrendingUp, Activity, ArrowRight, CheckCircle2, XCircle,
  BarChart3, Cpu, Shield, Clock, ArrowUpRight
} from 'lucide-react'
import { useAuth } from '../../contexts/AuthContext'

// ── Helpers ───────────────────────────────────────────────────────────────────
function fmt(n, fallback = '—') {
  if (n === null || n === undefined) return fallback
  if (typeof n === 'number') return n.toLocaleString()
  return n
}
function fmtCost(v) {
  if (v === null || v === undefined) return 'No data'
  return `$${Number(v).toFixed(2)}`
}
function fmtTokens(n) {
  if (!n) return '0'
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000)     return `${(n / 1_000).toFixed(1)}K`
  return n.toLocaleString()
}
function timeAgo(iso) {
  if (!iso) return '—'
  const diff = Date.now() - new Date(iso).getTime()
  const m = Math.floor(diff / 60000)
  if (m < 1)  return 'just now'
  if (m < 60) return `${m}m ago`
  const h = Math.floor(m / 60)
  if (h < 24) return `${h}h ago`
  return `${Math.floor(h / 24)}d ago`
}

// ── KPI card ──────────────────────────────────────────────────────────────────
function KpiCard({ label, value, icon: Icon, sub, accent = 'blue', loading, onClick }) {
  const accents = {
    blue:   'bg-blue-50 dark:bg-blue-950/60 text-blue-600 dark:text-blue-400 border border-blue-200 dark:border-blue-800/80',
    green:  'bg-emerald-50 dark:bg-emerald-950/60 text-emerald-600 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-800/80',
    purple: 'bg-purple-50 dark:bg-purple-950/60 text-purple-600 dark:text-purple-400 border border-purple-200 dark:border-purple-800/80',
    orange: 'bg-amber-50 dark:bg-amber-950/60 text-amber-600 dark:text-amber-400 border border-amber-200 dark:border-amber-800/80',
    red:    'bg-red-50 dark:bg-red-950/60 text-red-600 dark:text-red-400 border border-red-200 dark:border-red-800/80',
    slate:  'bg-slate-100 dark:bg-slate-800 text-slate-500 dark:text-slate-400 border border-slate-200 dark:border-slate-700',
  }
  return (
    <div
      onClick={onClick}
      className={`bg-white dark:bg-[#121826] border border-slate-200 dark:border-[#233048] rounded-2xl p-5 flex items-start justify-between gap-4 shadow-2xs transition-all ${
        onClick ? 'cursor-pointer hover:border-blue-300 dark:hover:border-blue-500/50 hover:shadow-sm' : ''
      }`}
    >
      <div className="min-w-0">
        <p className="text-[11px] font-bold text-slate-400 dark:text-slate-400 uppercase tracking-wider mb-1">{label}</p>
        <p className={`text-2xl font-extrabold text-slate-900 dark:text-white ${loading ? 'opacity-30 animate-pulse' : ''}`}>
          {loading ? '…' : value}
        </p>
        {sub && <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">{sub}</p>}
      </div>
      {Icon && (
        <div className={`p-2.5 rounded-xl shrink-0 ${accents[accent]}`}>
          <Icon size={18} strokeWidth={2} />
        </div>
      )}
    </div>
  )
}

// ── Status badge ──────────────────────────────────────────────────────────────
function RunBadge({ status }) {
  const map = {
    completed: 'bg-emerald-50 dark:bg-emerald-950/60 text-emerald-700 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-800/80',
    running:   'bg-blue-50 dark:bg-blue-950/60 text-blue-700 dark:text-blue-400 border border-blue-200 dark:border-blue-800/80',
    failed:    'bg-red-50 dark:bg-red-950/60 text-red-700 dark:text-red-400 border border-red-200 dark:border-red-800/80',
    pending:   'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 border border-slate-200 dark:border-slate-700',
    paused:    'bg-amber-50 dark:bg-amber-950/60 text-amber-700 dark:text-amber-400 border border-amber-200 dark:border-amber-800/80',
  }
  return (
    <span className={`px-2.5 py-0.5 rounded-full text-[11px] font-mono font-semibold capitalize ${map[status?.toLowerCase()] || 'bg-slate-100 text-slate-500'}`}>
      {status || 'unknown'}
    </span>
  )
}

// ── Section header ────────────────────────────────────────────────────────────
function SectionHeader({ title, action, actionTo, navigate }) {
  return (
    <div className="flex items-center justify-between px-5 py-3.5 border-b border-slate-100 dark:border-[#1e2a3f] bg-slate-50/50 dark:bg-[#162030]/60">
      <h2 className="text-xs font-bold text-slate-900 dark:text-white uppercase tracking-wider">{title}</h2>
      {action && (
        <button
          onClick={() => navigate(actionTo)}
          className="flex items-center gap-1 text-xs text-blue-600 dark:text-blue-400 hover:text-blue-500 font-semibold cursor-pointer"
        >
          {action} <ArrowRight size={12} />
        </button>
      )}
    </div>
  )
}

// ── Main component ────────────────────────────────────────────────────────────
export default function AdminPlatformOverview() {
  const { api } = useAuth()
  const navigate = useNavigate()

  const [overview, setOverview]     = useState(null)
  const [usage, setUsage]           = useState(null)
  const [runs, setRuns]             = useState([])
  const [exceptions, setExceptions] = useState(null)
  const [orgs, setOrgs]             = useState([])
  const [loading, setLoading]       = useState(true)
  const [lastRefresh, setLastRefresh] = useState(null)
  const [error, setError]           = useState(null)

  const load = useCallback(async () => {
    setLoading(true); setError(null)
    try {
      const [ov, us, ru, ex, og] = await Promise.allSettled([
        api.get('/admin/overview'),
        api.get('/admin/usage?days=30'),
        api.get('/admin/runs?limit=10'),
        api.get('/admin/exceptions'),
        api.get('/admin/organizations'),
      ])
      if (ov.status === 'fulfilled') setOverview(ov.value)
      else setError('Failed to load platform metrics')
      if (us.status === 'fulfilled') setUsage(us.value)
      if (ru.status === 'fulfilled') setRuns(Array.isArray(ru.value) ? ru.value : [])
      if (ex.status === 'fulfilled') setExceptions(ex.value)
      if (og.status === 'fulfilled') setOrgs(Array.isArray(og.value) ? og.value : [])
      setLastRefresh(new Date())
    } finally {
      setLoading(false)
    }
  }, [api])

  useEffect(() => { load() }, [load])

  const m = overview?.metrics || {}

  // Derive workflow activity from runs
  const wfMap = {}
  runs.forEach(r => {
    if (!wfMap[r.workflow]) wfMap[r.workflow] = { workflow: r.workflow, runs: 0, failed: 0, last_run: null, orgs: new Set() }
    wfMap[r.workflow].runs++
    if (r.status === 'failed') wfMap[r.workflow].failed++
    if (!wfMap[r.workflow].last_run || r.started_at > wfMap[r.workflow].last_run)
      wfMap[r.workflow].last_run = r.started_at
    if (r.organization) wfMap[r.workflow].orgs.add(r.organization)
  })
  const wfActivity = Object.values(wfMap).slice(0, 6)

  // Org activity
  const orgActivity = orgs
    .filter(o => o.run_count > 0 || o.last_activity)
    .sort((a, b) => (b.last_activity || '') > (a.last_activity || '') ? 1 : -1)
    .slice(0, 6)

  return (
    <div className="flex flex-col gap-6 p-6 min-h-full bg-slate-50 dark:bg-[#0b0f17] text-slate-900 dark:text-slate-100 font-sans transition-colors">

      {/* ── Header ─────────────────────────────────────────────────────── */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-white tracking-tight">Platform Control Center</h1>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
            SMBFlow multi-tenant orchestrator telemetry
            {lastRefresh && <span className="ml-2 text-slate-400">· Refreshed {timeAgo(lastRefresh.toISOString())}</span>}
          </p>
        </div>
        <button
          onClick={load}
          disabled={loading}
          className="flex items-center gap-2 px-3 py-2 text-xs font-bold text-slate-700 dark:text-slate-200 bg-white dark:bg-[#162030] border border-slate-200 dark:border-[#233048] rounded-xl hover:bg-slate-50 dark:hover:bg-[#1c273c] transition-colors shadow-2xs cursor-pointer disabled:opacity-50"
        >
          <RefreshCw size={14} className={loading ? 'animate-spin text-blue-500' : ''} />
          <span>Refresh Metrics</span>
        </button>
      </div>

      {error && (
        <div className="flex items-center gap-3 px-4 py-3 bg-red-50 dark:bg-red-950/60 border border-red-200 dark:border-red-800 rounded-xl text-xs text-red-700 dark:text-red-300">
          <XCircle size={15} className="shrink-0" />{error}
        </div>
      )}

      {/* ── Trial Expiry Alerts ────────────────────────────────────────── */}
      {!loading && (() => {
        const expiring = orgs.filter(o => {
          if (!o.trial_ends_at) return false
          const days = Math.ceil((new Date(o.trial_ends_at) - Date.now()) / 86400000)
          return o.effective_subscription_status === 'trial_expired' || (o.subscription_status === 'trialing' && days <= 3)
        })
        if (expiring.length === 0) return null
        return (
          <div className="flex items-start gap-3 px-4 py-3.5 bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800 rounded-2xl text-amber-900 dark:text-amber-200 text-xs">
            <AlertTriangle size={16} className="text-amber-600 dark:text-amber-400 shrink-0 mt-0.5" />
            <div className="flex-1 min-w-0">
              <p className="font-bold">Subscription Action Required</p>
              <div className="flex flex-wrap gap-2 mt-1">
                {expiring.map(o => {
                  const expired = o.effective_subscription_status === 'trial_expired'
                  const days = Math.ceil((new Date(o.trial_ends_at) - Date.now()) / 86400000)
                  return (
                    <button
                      key={o.id}
                      onClick={() => navigate(`/admin/organizations/${o.id}`)}
                      className="font-medium text-amber-700 dark:text-amber-300 hover:underline cursor-pointer"
                    >
                      {o.name} ({expired ? 'expired' : `${days}d left`})
                    </button>
                  )
                })}
              </div>
            </div>
            <button
              onClick={() => navigate('/admin/subscriptions')}
              className="font-bold text-amber-700 dark:text-amber-300 hover:text-amber-900 cursor-pointer"
            >
              Manage →
            </button>
          </div>
        )
      })()}

      {/* ── KPI Grid ───────────────────────────────────────────────────── */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3.5">
        <KpiCard label="Active Organizations" value={fmt(m.active_organizations, '0')}
          icon={Building2} accent="blue" loading={loading}
          sub="registered client workspaces" onClick={() => navigate('/admin/organizations')} />
        <KpiCard label="Active Users" value={fmt(m.active_users, '0')}
          icon={Users} accent="purple" loading={loading}
          sub={`${fmt(m.total_users, '0')} total accounts`} onClick={() => navigate('/admin/users')} />
        <KpiCard label="Enabled Workflows" value={fmt(m.enabled_workflows, '0')}
          icon={TrendingUp} accent="green" loading={loading}
          sub="active DAG assignments" onClick={() => navigate('/admin/workflows/assignments')} />
        <KpiCard label="Runs Today" value={fmt(m.runs_today, '0')}
          icon={Zap} accent="slate" loading={loading}
          sub={`${fmt(m.total_runs, '0')} all-time executions`} onClick={() => navigate('/admin/runs')} />
        <KpiCard label="Pending Exceptions" value={fmt(m.pending_exceptions, '0')}
          icon={AlertTriangle} accent={m.pending_exceptions > 0 ? 'red' : 'slate'} loading={loading}
          sub="requiring SME review" onClick={() => navigate('/admin/exceptions')} />
        <KpiCard label="AI Spend (Month)" value={loading ? '…' : fmtCost(m.ai_spend_month_usd)}
          icon={DollarSign} accent="orange" loading={loading}
          sub="platform LLM usage" onClick={() => navigate('/admin/usage')} />
        <KpiCard label="Active Subscriptions" value={fmt(m.active_subscriptions, '0')}
          icon={BarChart3} accent="green" loading={loading}
          sub="paying & trialing orgs" onClick={() => navigate('/admin/subscriptions')} />
        <KpiCard label="Platform Engine"
          value={loading ? '…' : 'Operational'}
          icon={Activity} accent="green" loading={loading}
          sub="all connectors live →" onClick={() => navigate('/admin/health')} />
      </div>

      {/* ── Two-Column Operational Activity Tables ─────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        
        {/* Recent Workflow Executions */}
        <div className="bg-white dark:bg-[#121826] border border-slate-200 dark:border-[#233048] rounded-2xl overflow-hidden shadow-2xs flex flex-col">
          <SectionHeader title="Recent Workflow Runs" action="View All Runs" actionTo="/admin/runs" navigate={navigate} />
          <div className="p-0 overflow-x-auto flex-1">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-slate-100 dark:border-[#1e2a3f] text-slate-400 text-[10px] uppercase font-bold tracking-wider">
                  <th className="px-4 py-2.5">Workflow</th>
                  <th className="px-4 py-2.5">Organization</th>
                  <th className="px-4 py-2.5">Status</th>
                  <th className="px-4 py-2.5">Time</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-[#1a2336]">
                {runs.slice(0, 6).map(r => (
                  <tr key={r.run_id} onClick={() => navigate('/admin/runs')} className="hover:bg-slate-50 dark:hover:bg-[#162030]/50 transition-colors cursor-pointer">
                    <td className="px-4 py-3 font-bold text-slate-900 dark:text-white max-w-[140px] truncate">{r.workflow}</td>
                    <td className="px-4 py-3 text-slate-500 dark:text-slate-400 truncate max-w-[120px]">{r.organization || '—'}</td>
                    <td className="px-4 py-3"><RunBadge status={r.status} /></td>
                    <td className="px-4 py-3 text-slate-400 text-[11px] whitespace-nowrap">{timeAgo(r.started_at)}</td>
                  </tr>
                ))}
                {runs.length === 0 && !loading && (
                  <tr>
                    <td colSpan={4} className="px-4 py-8 text-center text-slate-400 text-xs">No recent workflow runs recorded.</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* Organization Workspaces */}
        <div className="bg-white dark:bg-[#121826] border border-slate-200 dark:border-[#233048] rounded-2xl overflow-hidden shadow-2xs flex flex-col">
          <SectionHeader title="Organization Workspaces" action="View All Orgs" actionTo="/admin/organizations" navigate={navigate} />
          <div className="p-0 overflow-x-auto flex-1">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-slate-100 dark:border-[#1e2a3f] text-slate-400 text-[10px] uppercase font-bold tracking-wider">
                  <th className="px-4 py-2.5">Organization</th>
                  <th className="px-4 py-2.5">Plan</th>
                  <th className="px-4 py-2.5">Runs</th>
                  <th className="px-4 py-2.5">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-[#1a2336]">
                {orgActivity.slice(0, 6).map(o => (
                  <tr key={o.id} onClick={() => navigate(`/admin/organizations/${o.id}`)} className="hover:bg-slate-50 dark:hover:bg-[#162030]/50 transition-colors cursor-pointer">
                    <td className="px-4 py-3 font-bold text-slate-900 dark:text-white max-w-[140px] truncate">{o.name}</td>
                    <td className="px-4 py-3 text-slate-500 dark:text-slate-400 font-mono text-[11px] uppercase">{o.plan || 'Starter'}</td>
                    <td className="px-4 py-3 font-bold text-slate-700 dark:text-slate-300 font-mono">{o.run_count || 0}</td>
                    <td className="px-4 py-3">
                      <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-50 dark:bg-emerald-950/60 text-emerald-600 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-800">
                        {o.subscription_status || 'Active'}
                      </span>
                    </td>
                  </tr>
                ))}
                {orgActivity.length === 0 && !loading && (
                  <tr>
                    <td colSpan={4} className="px-4 py-8 text-center text-slate-400 text-xs">No active organizations found.</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>

      </div>

    </div>
  )
}
