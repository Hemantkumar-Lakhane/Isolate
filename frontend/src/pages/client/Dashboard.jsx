// frontend/src/pages/client/Dashboard.jsx
// ─────────────────────────────────────────────────────────────────────────────
// Clean, professional enterprise operations dashboard:
//   • Dual-theme design (light slate & dark enterprise obsidian #0b0f17 / #121826 / #233048)
//   • Shows only necessary operational metrics (Active Runs, Approvals, Completed, Workflows, Savings)
//   • Clean Recent Activity timeline & Workflow Health tracking
//   • Zero purple, zero saffron, zero gratuitous emojis, crisp typography
// ─────────────────────────────────────────────────────────────────────────────

import React, { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Activity, ArrowUpRight, CheckCircle2, AlertTriangle, Play,
  DollarSign, BookOpen, Clock, ShieldCheck, Layers, ArrowRight,
  Terminal, BarChart3, Check, X
} from 'lucide-react'
import { LineChart, Line, ResponsiveContainer, Tooltip } from 'recharts'
import { useAuth } from '../../contexts/AuthContext'
import { useWebSocket } from '../../contexts/WSContext'
import { fmtCost, timeAgo } from '../../utils/helpers'

const POLL_MS = 5000

// ── KPI Card Component ────────────────────────────────────────────────────────
function KpiCard({ title, icon, value, sub, chart, highlight }) {
  return (
    <div className={`p-4 rounded-xl border transition-all relative overflow-hidden flex flex-col justify-between ${
      highlight
        ? 'bg-blue-50/60 dark:bg-[#182234] border-blue-200 dark:border-[#233048]'
        : 'bg-white dark:bg-[#121826] border-slate-200 dark:border-[#233048] shadow-2xs'
    }`}>
      <div>
        <div className="flex items-center justify-between mb-2">
          <p className="text-[11px] font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider">{title}</p>
          <div className="w-7 h-7 rounded-lg bg-slate-100 dark:bg-[#182234] text-slate-600 dark:text-slate-300 flex items-center justify-center">
            {icon}
          </div>
        </div>
        <p className="text-2xl font-bold text-slate-900 dark:text-white tracking-tight">{value}</p>
      </div>

      <div className="mt-2 flex items-center justify-between">
        <p className="text-xs text-slate-500 dark:text-slate-400 truncate">{sub}</p>
        {chart && (
          <div className="w-16 h-6 opacity-75">
            {chart}
          </div>
        )}
      </div>
    </div>
  )
}

// ── Timeline Item Component (Clickable Direct Navigation) ────────────────────
function TimelineItem({ run, isLast, onNavigate }) {
  const isCompleted = run.status === 'completed' || run.status === 'WorkflowStatus.COMPLETED'
  const isRunning   = run.status === 'running'
  const isEscalated = run.status === 'escalated' || run.status === 'pending' || run.status === 'pending_a2a'
  const isFailed    = run.status === 'failed' || run.status === 'stopped'

  let icon, badge
  if (isCompleted) {
    icon  = <CheckCircle2 className="w-4 h-4 text-emerald-500" />
    badge = <span className="text-[10px] font-semibold text-emerald-600 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-950/60 border border-emerald-200 dark:border-emerald-800 px-2 py-0.5 rounded-full">Completed</span>
  } else if (isRunning) {
    icon  = <div className="w-4 h-4 rounded-full border-2 border-blue-500 border-t-transparent animate-spin" />
    badge = <span className="text-[10px] font-semibold text-blue-600 dark:text-blue-400 bg-blue-50 dark:bg-blue-950/60 border border-blue-200 dark:border-blue-800 px-2 py-0.5 rounded-full">Running</span>
  } else if (isEscalated) {
    icon  = <AlertTriangle className="w-4 h-4 text-amber-500" />
    badge = <span className="text-[10px] font-semibold text-amber-600 dark:text-amber-400 bg-amber-50 dark:bg-amber-950/60 border border-amber-200 dark:border-amber-800 px-2 py-0.5 rounded-full">Pending Approval</span>
  } else if (isFailed) {
    icon  = <AlertTriangle className="w-4 h-4 text-red-500" />
    badge = <span className="text-[10px] font-semibold text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-950/60 border border-red-200 dark:border-red-800 px-2 py-0.5 rounded-full">Failed</span>
  } else {
    icon  = <Play className="w-3.5 h-3.5 text-slate-400" />
    badge = <span className="text-[10px] font-semibold text-slate-500 dark:text-slate-400 bg-slate-100 dark:bg-[#182234] px-2 py-0.5 rounded-full">{run.status}</span>
  }

  function handleClick() {
    const rawKey = (run.workflow_name || run.name || '').toLowerCase()
    if (rawKey.includes('launch') || rawKey.includes('product')) {
      onNavigate('/workflows/product_launch')
    } else if (rawKey.includes('email') || rawKey.includes('gmail') || rawKey.includes('inbox') || rawKey.includes('summariz')) {
      onNavigate('/workflows/email_summarizer')
    } else if (rawKey.includes('invoice') || rawKey.includes('bill')) {
      onNavigate('/workflows/invoice_processing')
    } else if (rawKey.includes('churn') || rawKey.includes('finance')) {
      onNavigate('/workflows/finance_operations')
    } else if (rawKey.includes('meeting') || rawKey.includes('conversation')) {
      onNavigate('/workflows/meeting_intelligence_followup')
    } else {
      onNavigate('/workflows')
    }
  }

  return (
    <div
      onClick={handleClick}
      className="relative flex gap-3.5 group cursor-pointer -mx-2 px-2 py-2 rounded-xl hover:bg-slate-50 dark:hover:bg-[#182234] transition-all"
    >
      {!isLast && <div className="absolute left-[15px] top-7 bottom-0 w-px bg-slate-200 dark:bg-[#233048]" />}
      <div className="w-4 h-4 mt-0.5 shrink-0 bg-white dark:bg-[#121826] z-10">{icon}</div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center justify-between gap-3 mb-0.5">
          <p className="text-xs font-bold text-slate-900 dark:text-slate-100 group-hover:text-blue-600 dark:group-hover:text-blue-400 transition-colors truncate">
            {run.name || run.workflow_name}
          </p>
          {badge}
        </div>
        <p className="text-xs text-slate-500 dark:text-slate-400 truncate">{run.description || run.workflow_name}</p>
        <div className="flex items-center justify-between mt-1">
          <p className="text-[10px] text-slate-400 dark:text-slate-500 font-mono">{timeAgo(run.timestamp || run.started_at)}</p>
          <span className="text-[10px] text-blue-600 dark:text-blue-400 font-semibold opacity-0 group-hover:opacity-100 transition-opacity flex items-center gap-0.5">
            <span>Open Pipeline</span>
            <ArrowRight size={10} />
          </span>
        </div>
      </div>
    </div>
  )
}

// ── Progress Row Component ────────────────────────────────────────────────────
function ProgressRow({ name, pct, color, runs, onOpen }) {
  return (
    <div
      onClick={onOpen}
      className={onOpen ? 'cursor-pointer group -mx-2 px-2 py-1.5 rounded-lg hover:bg-slate-100 dark:hover:bg-[#182234] transition-colors' : undefined}
      title={onOpen ? `Open ${name}` : undefined}
    >
      <div className="flex items-center justify-between gap-2 mb-1.5">
        <p className={`text-xs font-semibold text-slate-900 dark:text-slate-200 truncate ${onOpen ? 'group-hover:text-blue-500 transition-colors' : ''}`}>
          {name}
        </p>
        {runs != null && (
          <span className="text-[10px] font-mono text-slate-400 whitespace-nowrap">
            {runs} {runs === 1 ? 'run' : 'runs'}
          </span>
        )}
      </div>
      <div className="flex items-center gap-3">
        <div className="flex-1 h-1.5 bg-slate-100 dark:bg-[#182234] rounded-full overflow-hidden">
          <div className={`h-full rounded-full transition-all duration-500 ${color}`} style={{ width: `${pct}%` }} />
        </div>
        <span className="text-xs font-mono font-bold text-slate-900 dark:text-slate-200 w-8 text-right">{pct}%</span>
      </div>
    </div>
  )
}

// ── Main Dashboard Page ───────────────────────────────────────────────────────
export default function Dashboard() {
  const navigate = useNavigate()
  const { user, api } = useAuth()
  const { subscribe } = useWebSocket()

  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [workflowCount, setWorkflowCount] = useState(null)

  const load = useCallback(async () => {
    if (!user?.tenant_id) {
      setLoading(false)
      return
    }
    try {
      const res = await api.get(`/dashboard/${user.tenant_id}`)
      setData(res)
      setError('')
    } catch (err) {
      if (err?.status === 404 || err?.response?.status === 404) {
        setData(null)
        setError('')
      } else {
        setData(null)
        setError('')
      }
    } finally {
      setLoading(false)
    }
  }, [api, user?.tenant_id])

  useEffect(() => {
    load()
    const t = setInterval(load, POLL_MS)
    return () => clearInterval(t)
  }, [load])

  useEffect(() => {
    const unsubs = [
      subscribe('escalation_created', load),
      subscribe('workflow_completed', load),
      subscribe('workflow_failed', load),
    ]
    return () => unsubs.forEach(fn => fn())
  }, [subscribe, load])

  useEffect(() => {
    if (!user?.tenant_id) return
    api.get('/catalog/assigned')
      .then(data => {
        const assigned = Array.isArray(data) ? data.filter(w => w.is_assigned !== false) : []
        setWorkflowCount(assigned.length)
      })
      .catch(() => setWorkflowCount(null))
  }, [api, user?.tenant_id])

  const chartData = data?.cost_overview?.daily_trend?.map((item, idx) => ({ idx, cost: item.cost })) || []
  const sparkData = data?.tasks_completed?.trend?.map((v, idx) => ({ idx, v })) || []

  const activeRuns = data?.active_runs?.current ?? 0
  const activeRunning = data?.active_runs?.running ?? 0
  const activeAwait = data?.active_runs?.awaiting ?? 0
  const pendingAppr = data?.pending_approvals?.total ?? 0
  const tasksComp = data?.tasks_completed?.total ?? 0
  const netSavings = data?.net_savings?.value != null ? fmtCost(data.net_savings.value) : '—'
  const activity = data?.recent_activity || []
  const performance = data?.workflow_performance || []
  const mtdSpend = data?.cost_overview?.mtd_spend || 0
  const avgCost = data?.cost_overview?.avg_cost_per_run || 0

  return (
    <div className="p-6 bg-slate-50 dark:bg-[#0b0f17] min-h-full text-slate-900 dark:text-slate-100 transition-colors">
      {/* ── Header ─────────────────────────────────────────────────────────── */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-slate-900 dark:text-white">Dashboard</h1>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">Real-time operational summary, KPIs, and autonomous workflow performance</p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => navigate('/copilot')}
            className="flex items-center gap-1.5 px-3.5 py-1.5 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-xs font-semibold shadow-xs transition-all cursor-pointer"
          >
            <Terminal size={13} />
            <span>AI Assistant</span>
          </button>

          <button
            onClick={() => navigate('/workflows')}
            className="flex items-center gap-1.5 px-3.5 py-1.5 bg-white dark:bg-[#121826] border border-slate-200 dark:border-[#233048] text-slate-700 dark:text-slate-300 rounded-lg text-xs font-semibold shadow-2xs hover:bg-slate-100 dark:hover:bg-[#182234] transition-colors cursor-pointer"
          >
            <Play size={12} className="text-blue-500" />
            <span>Workflows</span>
          </button>
        </div>
      </div>

      {/* ── KPI Row ─────────────────────────────────────────────────────────── */}
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-3.5 mb-6">
        <KpiCard
          title="Active Runs"
          icon={<Activity size={15} />}
          value={loading ? '—' : activeRuns}
          sub={activeRuns > 0 ? `${activeRunning} running · ${activeAwait} awaiting` : '0 initiated today'}
        />
        <KpiCard
          title="Pending Approvals"
          icon={<AlertTriangle size={15} className="text-amber-500" />}
          value={loading ? '—' : pendingAppr}
          sub={pendingAppr ? 'Requires review' : 'No approvals pending'}
        />
        <KpiCard
          title="Tasks Completed"
          icon={<CheckCircle2 size={15} className="text-emerald-500" />}
          value={loading ? '—' : tasksComp}
          sub={tasksComp > 0 ? 'Actions executed' : 'No tasks completed'}
          chart={sparkData.length > 0 && (
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={sparkData}>
                <Line type="monotone" dataKey="v" stroke="#10b981" strokeWidth={1.5} dot={false} isAnimationActive={false} />
              </LineChart>
            </ResponsiveContainer>
          )}
        />
        <KpiCard
          title="Available Workflows"
          icon={<BookOpen size={15} className="text-blue-500" />}
          value={workflowCount != null ? workflowCount : '—'}
          sub="Assigned to your workspace"
        />
        <KpiCard
          title="Net Savings"
          icon={<DollarSign size={15} className="text-emerald-500" />}
          value={loading ? '—' : netSavings}
          sub="Governor cost optimization"
        />
      </div>

      {/* ── Content Grid ────────────────────────────────────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
        {/* Recent Activity */}
        <div className="lg:col-span-7">
          <div className="bg-white dark:bg-[#121826] border border-slate-200 dark:border-[#233048] rounded-xl shadow-2xs p-5 h-full transition-colors">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-sm font-bold text-slate-900 dark:text-white">Recent Activity</h2>
              <button
                onClick={() => navigate('/workflows')}
                className="text-xs font-semibold text-blue-600 dark:text-blue-400 hover:underline flex items-center gap-1 cursor-pointer"
              >
                <span>View all</span>
                <ArrowUpRight size={13} />
              </button>
            </div>

            {loading ? (
              <div className="flex items-center justify-center h-44 text-slate-400 text-xs">
                Loading activity…
              </div>
            ) : activity.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-44 text-center">
                <Activity className="w-8 h-8 text-slate-300 dark:text-slate-700 mb-2" />
                <p className="text-xs font-semibold text-slate-600 dark:text-slate-300">No activity yet</p>
                <p className="text-[11px] text-slate-400 mt-0.5">Activity will appear here once workflows start running.</p>
              </div>
            ) : (
              <div className="pt-2">
                {activity.map((run, i) => (
                  <TimelineItem key={run.id || i} run={run} isLast={i === activity.length - 1} onNavigate={navigate} />
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Right Column */}
        <div className="lg:col-span-5 flex flex-col gap-4">
          {/* Workflow Performance */}
          <div className="bg-white dark:bg-[#121826] border border-slate-200 dark:border-[#233048] rounded-xl shadow-2xs p-5 transition-colors">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-sm font-bold text-slate-900 dark:text-white">Workflow Performance</h2>
              <button
                onClick={() => navigate('/workflows')}
                className="text-xs font-semibold text-blue-600 dark:text-blue-400 hover:underline flex items-center gap-1 cursor-pointer"
              >
                <span>View all</span>
                <ArrowUpRight size={13} />
              </button>
            </div>

            {performance.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-28 text-center">
                <p className="text-xs text-slate-400">No workflows to report</p>
                <p className="text-[11px] text-slate-500 mt-0.5">Assigned workflows will show execution rates here.</p>
              </div>
            ) : (
              <div className="space-y-3">
                {performance.slice(0, 4).map((p, i) => {
                  const colors = ['bg-emerald-500', 'bg-blue-500', 'bg-amber-500', 'bg-sky-500']
                  return (
                    <ProgressRow
                      key={p.name}
                      name={p.name}
                      pct={p.success_rate || 0}
                      color={colors[i] || 'bg-blue-500'}
                      runs={p.runs}
                      onOpen={() => navigate('/workflows')}
                    />
                  )
                })}
              </div>
            )}
          </div>

          {/* Cost Overview */}
          <div className="bg-white dark:bg-[#121826] border border-slate-200 dark:border-[#233048] rounded-xl shadow-2xs p-5 transition-colors">
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-sm font-bold text-slate-900 dark:text-white">Cost Overview</h2>
              <button
                onClick={() => navigate('/budget')}
                className="text-xs font-semibold text-blue-600 dark:text-blue-400 hover:underline cursor-pointer"
              >
                Avg / run
              </button>
            </div>

            <div className="flex justify-between items-baseline mb-3">
              <div>
                <p className="text-[11px] text-slate-400">MTD Spend</p>
                <p className="text-lg font-bold text-slate-900 dark:text-white">{fmtCost(mtdSpend)}</p>
              </div>
              <div className="text-right">
                <p className="text-[11px] text-slate-400">Avg / run</p>
                <p className="text-sm font-semibold text-slate-700 dark:text-slate-300">{fmtCost(avgCost)}</p>
              </div>
            </div>

            {chartData.length > 0 && (
              <div className="h-16 border border-slate-100 dark:border-[#233048] rounded-lg overflow-hidden">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={chartData}>
                    <Tooltip
                      contentStyle={{ background: '#121826', border: '1px solid #233048', borderRadius: 6, fontSize: 11, color: '#fff' }}
                      formatter={v => [fmtCost(v), 'Cost']}
                      labelFormatter={() => ''}
                    />
                    <Line type="monotone" dataKey="cost" stroke="#3b82f6" strokeWidth={1.5} dot={false} isAnimationActive={false} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
