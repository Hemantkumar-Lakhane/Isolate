// AdminExceptions — Platform-level failures and policy escalations
import { useState, useEffect, useCallback, useMemo } from 'react'
import {
  AlertTriangle, RefreshCw, XCircle, Search,
  Zap, ShieldAlert, ChevronDown, ChevronUp,
} from 'lucide-react'
import { useAuth } from '../../contexts/AuthContext'
import { useNavigate } from 'react-router-dom'
import { EmptyState } from '../../components/ui'

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

const SEVERITY_META = {
  error:   { cls: 'bg-rose-500/10 text-rose-600 dark:text-rose-400 border border-rose-500/20',       dot: 'bg-rose-500'    },
  warning: { cls: 'bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20', dot: 'bg-amber-500' },
}

function SeverityBadge({ severity }) {
  const m = SEVERITY_META[severity] || SEVERITY_META.warning
  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-semibold ${m.cls}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${m.dot}`} />
      {severity}
    </span>
  )
}

function FailureRow({ item }) {
  const [expanded, setExpanded] = useState(false)
  const navigate = useNavigate()

  return (
    <div className="border border-slate-200 dark:border-[#233048] rounded-2xl bg-white dark:bg-[#121826] overflow-hidden shadow-2xs">
      <div className="flex items-start gap-3.5 p-4">
        <div className="w-9 h-9 rounded-xl bg-rose-500/10 border border-rose-500/20 flex items-center justify-center shrink-0 mt-0.5">
          <Zap size={16} className="text-rose-500" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-2 flex-wrap">
            <div className="min-w-0">
              <p className="text-sm font-bold text-slate-900 dark:text-white">{item.workflow}</p>
              <button
                onClick={() => navigate(`/admin/organizations/${item.organization_id}`)}
                className="text-xs text-blue-600 dark:text-blue-400 hover:underline font-medium"
              >
                {item.organization}
              </button>
            </div>
            <div className="flex items-center gap-2 shrink-0">
              <SeverityBadge severity={item.severity} />
              <span className="text-xs text-slate-400 dark:text-slate-500">{timeAgo(item.started_at)}</span>
            </div>
          </div>
          {item.error && (
            <p className="text-xs text-rose-600 dark:text-rose-400 mt-1.5 font-mono line-clamp-2">{item.error}</p>
          )}
        </div>
        <button
          onClick={() => setExpanded(v => !v)}
          className="p-1.5 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 transition-colors"
        >
          {expanded ? <ChevronUp size={15} /> : <ChevronDown size={15} />}
        </button>
      </div>
      {expanded && (
        <div className="border-t border-slate-100 dark:border-[#1e2a3f] px-5 py-4 bg-slate-50/70 dark:bg-[#162030]/40">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 text-xs text-slate-600 dark:text-slate-300">
            <div><span className="font-semibold text-slate-500 dark:text-slate-400">Run ID:</span> <span className="font-mono text-slate-700 dark:text-slate-300">{item.id}</span></div>
            <div><span className="font-semibold text-slate-500 dark:text-slate-400">Org ID:</span> <span className="font-mono text-slate-700 dark:text-slate-300">{item.organization_id}</span></div>
            <div><span className="font-semibold text-slate-500 dark:text-slate-400">Started:</span> {item.started_at ? new Date(item.started_at).toLocaleString() : '—'}</div>
          </div>
          {item.error && (
            <div className="mt-3">
              <p className="text-[10px] font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider mb-1">Stack Trace &amp; Diagnostic Log</p>
              <pre className="text-xs font-mono text-rose-700 dark:text-rose-300 bg-rose-500/10 border border-rose-500/20 rounded-xl p-3.5 overflow-x-auto whitespace-pre-wrap">{item.error}</pre>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function PolicyRow({ item }) {
  const [expanded, setExpanded] = useState(false)
  const navigate = useNavigate()

  return (
    <div className="border border-slate-200 dark:border-[#233048] rounded-2xl bg-white dark:bg-[#121826] overflow-hidden shadow-2xs">
      <div className="flex items-start gap-3.5 p-4">
        <div className="w-9 h-9 rounded-xl bg-amber-500/10 border border-amber-500/20 flex items-center justify-center shrink-0 mt-0.5">
          <ShieldAlert size={16} className="text-amber-500" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-2 flex-wrap">
            <div className="min-w-0">
              <p className="text-sm font-bold text-slate-900 dark:text-white capitalize">{item.review_type?.replace(/_/g, ' ')}</p>
              <button
                onClick={() => navigate(`/admin/organizations/${item.organization_id}`)}
                className="text-xs text-blue-600 dark:text-blue-400 hover:underline font-medium"
              >
                Org: {item.organization_id?.slice(0, 10)}…
              </button>
            </div>
            <div className="flex items-center gap-2 shrink-0">
              <SeverityBadge severity={item.severity} />
              <span className="text-xs text-slate-400 dark:text-slate-500">{timeAgo(item.created_at)}</span>
            </div>
          </div>
          <p className="text-xs text-slate-600 dark:text-slate-300 mt-1.5">{item.reason}</p>
        </div>
        <button
          onClick={() => setExpanded(v => !v)}
          className="p-1.5 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 transition-colors"
        >
          {expanded ? <ChevronUp size={15} /> : <ChevronDown size={15} />}
        </button>
      </div>
      {expanded && (
        <div className="border-t border-slate-100 dark:border-[#1e2a3f] px-5 py-4 bg-slate-50/70 dark:bg-[#162030]/40">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 text-xs text-slate-600 dark:text-slate-300">
            <div><span className="font-semibold text-slate-500 dark:text-slate-400">Item ID:</span> <span className="font-mono text-slate-700 dark:text-slate-300">{item.id}</span></div>
            <div><span className="font-semibold text-slate-500 dark:text-slate-400">Review type:</span> {item.review_type}</div>
            <div><span className="font-semibold text-slate-500 dark:text-slate-400">Created:</span> {item.created_at ? new Date(item.created_at).toLocaleString() : '—'}</div>
          </div>
        </div>
      )}
    </div>
  )
}

export default function AdminExceptions() {
  const { api } = useAuth()
  const [data, setData]         = useState(null)
  const [loading, setLoading]   = useState(true)
  const [error, setError]       = useState(null)
  const [search, setSearch]     = useState('')
  const [tab, setTab]           = useState('failures')

  const load = useCallback(async () => {
    setLoading(true); setError(null)
    try {
      const d = await api.get('/admin/exceptions')
      setData(d)
    } catch (e) {
      setError(e?.response?.data?.detail || e.message || 'Failed to load exceptions')
    } finally { setLoading(false) }
  }, [api])

  useEffect(() => { load() }, [load])

  const failures = useMemo(() => {
    const list = data?.workflow_failures || []
    if (!search) return list
    const q = search.toLowerCase()
    return list.filter(i =>
      i.workflow?.toLowerCase().includes(q) ||
      i.organization?.toLowerCase().includes(q) ||
      i.error?.toLowerCase().includes(q)
    )
  }, [data, search])

  const policy = useMemo(() => {
    const list = data?.policy_escalations || []
    if (!search) return list
    const q = search.toLowerCase()
    return list.filter(i =>
      i.review_type?.toLowerCase().includes(q) ||
      i.reason?.toLowerCase().includes(q)
    )
  }, [data, search])

  const activeList = tab === 'failures' ? failures : policy

  return (
    <div className="flex flex-col gap-6 p-6 min-h-full bg-slate-50 dark:bg-[#0b0f17] text-slate-900 dark:text-slate-100 transition-colors">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-xl font-bold text-slate-900 dark:text-white flex items-center gap-2">
            <AlertTriangle className="text-amber-500" size={22} />
            Exceptions &amp; Policy Escalations
          </h1>
          <p className="text-sm text-slate-500 dark:text-slate-400 mt-0.5">
            Platform-level runtime failures, policy violations, and unhandled system errors.
          </p>
        </div>
        <button onClick={load} disabled={loading}
          className="p-2 rounded-xl text-slate-500 dark:text-slate-400 bg-white dark:bg-[#121826] border border-slate-200 dark:border-[#233048] hover:bg-slate-50 dark:hover:bg-[#162030] transition-colors disabled:opacity-50">
          <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
        </button>
      </div>

      {error && (
        <div className="flex items-center gap-2 px-4 py-3 bg-red-500/10 border border-red-500/20 rounded-xl text-sm text-red-600 dark:text-red-400">
          <XCircle size={15} className="shrink-0" />{error}
        </div>
      )}

      {/* Summary tabs */}
      {!loading && data && (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div
            onClick={() => setTab('failures')}
            className={`bg-white dark:bg-[#121826] border rounded-2xl p-5 cursor-pointer transition-all shadow-2xs ${
              tab === 'failures'
                ? 'border-rose-500 ring-2 ring-rose-500/20'
                : 'border-slate-200 dark:border-[#233048] hover:border-slate-300 dark:hover:border-[#2f4060]'
            }`}
          >
            <p className="text-3xl font-bold text-rose-600 dark:text-rose-400 tracking-tight">{data.workflow_failures?.length ?? 0}</p>
            <p className="text-xs font-semibold text-slate-600 dark:text-slate-300 mt-1">Workflow Failures</p>
            <p className="text-[11px] text-slate-400 dark:text-slate-500">Unhandled execution &amp; timeout exceptions</p>
          </div>
          <div
            onClick={() => setTab('policy')}
            className={`bg-white dark:bg-[#121826] border rounded-2xl p-5 cursor-pointer transition-all shadow-2xs ${
              tab === 'policy'
                ? 'border-amber-500 ring-2 ring-amber-500/20'
                : 'border-slate-200 dark:border-[#233048] hover:border-slate-300 dark:hover:border-[#2f4060]'
            }`}
          >
            <p className="text-3xl font-bold text-amber-600 dark:text-amber-400 tracking-tight">{data.policy_escalations?.length ?? 0}</p>
            <p className="text-xs font-semibold text-slate-600 dark:text-slate-300 mt-1">Policy Escalations</p>
            <p className="text-[11px] text-slate-400 dark:text-slate-500">Safety thresholds &amp; security gate alerts</p>
          </div>
        </div>
      )}

      {/* Search */}
      <div className="relative">
        <Search size={14} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" />
        <input type="text" placeholder="Search exceptions by error, workflow, or organization…" value={search}
          onChange={e => setSearch(e.target.value)}
          className="w-full pl-10 pr-3 py-2 text-sm bg-white dark:bg-[#121826] border border-slate-200 dark:border-[#233048] text-slate-900 dark:text-white rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 placeholder-slate-400" />
      </div>

      {/* List */}
      {loading ? (
        <div className="flex items-center justify-center h-48 text-slate-400 text-sm">Loading exceptions…</div>
      ) : activeList.length === 0 ? (
        <EmptyState
          icon={AlertTriangle}
          title={tab === 'failures' ? 'No workflow failures' : 'No policy escalations'}
          description={search ? 'No matches for your search filter.' : 'All services operating without reported exceptions.'}
        />
      ) : (
        <div className="flex flex-col gap-3">
          {tab === 'failures'
            ? failures.map(item => <FailureRow key={item.id} item={item} />)
            : policy.map(item  => <PolicyRow  key={item.id} item={item} />)
          }
        </div>
      )}
    </div>
  )
}
