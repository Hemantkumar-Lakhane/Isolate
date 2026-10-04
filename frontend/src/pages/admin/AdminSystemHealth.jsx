// AdminSystemHealth — Platform service health
import { useState, useEffect, useCallback } from 'react'
import {
  RefreshCw, Database, Layers, Cpu, GitBranch,
  CheckCircle2, XCircle, AlertTriangle, HelpCircle, Minus, Activity,
} from 'lucide-react'
import { useAuth } from '../../contexts/AuthContext'

// ── Status helpers ─────────────────────────────────────────────────────────────
const STATUS_META = {
  operational:    { label: 'Operational',    cls: 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20', dot: 'bg-emerald-500', icon: CheckCircle2 },
  degraded:       { label: 'Degraded',       cls: 'bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/20',   dot: 'bg-amber-500', icon: AlertTriangle },
  unavailable:    { label: 'Unavailable',    cls: 'bg-rose-500/10 text-rose-600 dark:text-rose-400 border-rose-500/20',       dot: 'bg-rose-500',  icon: XCircle },
  not_configured: { label: 'Not Configured', cls: 'bg-slate-500/10 text-slate-500 dark:text-slate-400 border-slate-500/20', dot: 'bg-slate-400',  icon: Minus },
  configured:     { label: 'Configured',     cls: 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20', dot: 'bg-emerald-500', icon: CheckCircle2 },
  partial:        { label: 'Partial',        cls: 'bg-orange-500/10 text-orange-600 dark:text-orange-400 border-orange-500/20', dot: 'bg-orange-400', icon: AlertTriangle },
  unknown:        { label: 'Unknown',        cls: 'bg-slate-500/10 text-slate-500 dark:text-slate-400 border-slate-500/20', dot: 'bg-slate-400',  icon: HelpCircle },
}

function StatusBadge({ status }) {
  const m = STATUS_META[status] || STATUS_META.unknown
  const Icon = m.icon
  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold border ${m.cls}`}>
      <Icon size={12} strokeWidth={2} />
      {m.label}
    </span>
  )
}

function StatusDot({ status }) {
  const m = STATUS_META[status] || STATUS_META.unknown
  return <span className={`w-2.5 h-2.5 rounded-full shrink-0 ${m.dot}`} />
}

// ── Overall banner ─────────────────────────────────────────────────────────────
function OverallBanner({ overall, checkedAt }) {
  const m = STATUS_META[overall] || STATUS_META.unknown
  const Icon = m.icon
  const bannerCls = {
    operational:    'bg-emerald-500/10 border-emerald-500/20 text-emerald-800 dark:text-emerald-300',
    degraded:       'bg-amber-500/10 border-amber-500/20 text-amber-800 dark:text-amber-300',
    unavailable:    'bg-rose-500/10 border-rose-500/20 text-rose-800 dark:text-rose-300',
    partial:        'bg-orange-500/10 border-orange-500/20 text-orange-800 dark:text-orange-300',
  }[overall] || 'bg-slate-500/10 border-slate-500/20 text-slate-700 dark:text-slate-300'

  return (
    <div className={`flex items-center justify-between px-5 py-4 border rounded-2xl ${bannerCls} shadow-2xs`}>
      <div className="flex items-center gap-3.5">
        <Icon size={22} strokeWidth={2} />
        <div>
          <p className="text-sm font-bold">Platform Services: {m.label}</p>
          {checkedAt && (
            <p className="text-xs opacity-75 mt-0.5">
              Heartbeat verified at {new Date(checkedAt).toLocaleTimeString()}
            </p>
          )}
        </div>
      </div>
    </div>
  )
}

// ── Service card ──────────────────────────────────────────────────────────────
function ServiceCard({ title, subtitle, icon: Icon, status, extra }) {
  return (
    <div className="bg-white dark:bg-[#121826] border border-slate-200 dark:border-[#233048] rounded-2xl p-5 shadow-2xs">
      <div className="flex items-start justify-between mb-3">
        <div className="w-10 h-10 rounded-xl bg-blue-500/10 border border-blue-500/20 flex items-center justify-center shrink-0">
          <Icon size={18} className="text-blue-500" />
        </div>
        <StatusBadge status={status} />
      </div>
      <h3 className="text-sm font-bold text-slate-900 dark:text-white">{title}</h3>
      <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">{subtitle}</p>
      {extra && (
        <p className="text-xs text-slate-400 dark:text-slate-500 mt-2 font-mono truncate">{extra}</p>
      )}
    </div>
  )
}

// ── Main component ─────────────────────────────────────────────────────────────
export default function AdminSystemHealth() {
  const { api } = useAuth()
  const [health,  setHealth]  = useState(null)
  const [loading, setLoading] = useState(true)
  const [error,   setError]   = useState(null)

  const load = useCallback(async () => {
    setLoading(true); setError(null)
    try {
      const d = await api.get('/admin/health')
      setHealth(d)
    } catch (e) {
      setError(e?.response?.data?.detail || e.message || 'Failed to load health data')
    } finally {
      setLoading(false)
    }
  }, [api])

  useEffect(() => { load() }, [load])

  const services = health?.services || {}
  const aiProviders = services.ai_providers || {}

  return (
    <div className="flex flex-col gap-6 p-6 min-h-full bg-slate-50 dark:bg-[#0b0f17] text-slate-900 dark:text-slate-100 transition-colors">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-xl font-bold text-slate-900 dark:text-white flex items-center gap-2">
            <Activity className="text-blue-500" size={22} />
            Platform Health
          </h1>
          <p className="text-sm text-slate-500 dark:text-slate-400 mt-0.5">Live connectivity checks for all core background services and microservices</p>
        </div>
        <button onClick={load} disabled={loading}
          className="flex items-center gap-2 px-3.5 py-2 text-sm font-medium text-slate-700 dark:text-slate-300 bg-white dark:bg-[#121826] border border-slate-200 dark:border-[#233048] rounded-xl hover:bg-slate-50 dark:hover:bg-[#162030] transition-colors disabled:opacity-50">
          <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
          Refresh Status
        </button>
      </div>

      {error && (
        <div className="flex items-center gap-2 px-4 py-3 bg-red-500/10 border border-red-500/20 rounded-xl text-sm text-red-600 dark:text-red-400">
          <XCircle size={15} className="shrink-0" />{error}
        </div>
      )}

      {loading && !health ? (
        <div className="flex items-center justify-center h-48 text-slate-400 text-sm">Checking services…</div>
      ) : health ? (
        <>
          {/* Overall banner */}
          <OverallBanner overall={health.overall} checkedAt={health.checked_at} />

          {/* Core services */}
          <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
            <ServiceCard
              title="Database"
              subtitle="PostgreSQL — primary data store"
              icon={Database}
              status={services.database?.status}
              extra={services.database?.error}
            />
            <ServiceCard
              title="Redis / PubSub"
              subtitle="Cache & real-time WebSocket event bus"
              icon={Layers}
              status={services.redis?.status}
              extra={services.redis?.error}
            />
            <ServiceCard
              title="Workflow Engine"
              subtitle="Orchestration runtime & task workers"
              icon={GitBranch}
              status={services.workflow_engine?.status}
              extra={
                services.workflow_engine?.stuck_runs > 0
                  ? `${services.workflow_engine.stuck_runs} stuck run${services.workflow_engine.stuck_runs !== 1 ? 's' : ''} (>2h)`
                  : services.workflow_engine?.error
              }
            />
            <div className="bg-white dark:bg-[#121826] border border-slate-200 dark:border-[#233048] rounded-2xl p-5 shadow-2xs flex flex-col justify-between">
              <div>
                <div className="flex items-start justify-between mb-3">
                  <div className="w-10 h-10 rounded-xl bg-purple-500/10 border border-purple-500/20 flex items-center justify-center shrink-0">
                    <Cpu size={18} className="text-purple-500" />
                  </div>
                  <span className="text-xs text-slate-500 dark:text-slate-400 font-semibold px-2 py-0.5 rounded-full bg-slate-500/10 border border-slate-500/20">
                    {Object.values(aiProviders).filter(p => p?.configured).length}/{Object.keys(aiProviders).length} Configured
                  </span>
                </div>
                <h3 className="text-sm font-bold text-slate-900 dark:text-white">AI Providers</h3>
                <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">LLM &amp; visual diffusion engines</p>
              </div>
            </div>
          </div>

          {/* AI Providers detail */}
          {Object.keys(aiProviders).length > 0 && (
            <div className="bg-white dark:bg-[#121826] border border-slate-200 dark:border-[#233048] rounded-2xl overflow-hidden shadow-2xs">
              <div className="px-5 py-4 border-b border-slate-100 dark:border-[#1e2a3f]">
                <h2 className="text-sm font-bold text-slate-900 dark:text-white">AI Provider Details</h2>
              </div>
              <div className="divide-y divide-slate-100 dark:divide-[#1a2336]">
                {Object.entries(aiProviders).map(([id, info]) => (
                  <div key={id} className="flex items-center justify-between px-5 py-3.5 hover:bg-slate-50/60 dark:hover:bg-[#162030]/50 transition-colors">
                    <div className="flex items-center gap-3">
                      <StatusDot status={info?.status} />
                      <div>
                        <p className="text-sm font-semibold text-slate-900 dark:text-white">{info?.label || id}</p>
                        <p className="text-xs text-slate-400 dark:text-slate-500 font-mono">{id}</p>
                      </div>
                    </div>
                    <StatusBadge status={info?.status} />
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      ) : null}
    </div>
  )
}
