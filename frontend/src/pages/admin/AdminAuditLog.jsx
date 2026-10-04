// AdminAuditLog — Platform audit event log
import { useState, useEffect, useCallback, useMemo } from 'react'
import {
  ShieldAlert, Search, RefreshCw, XCircle, Download,
  ChevronDown, ChevronUp, Shield,
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

// Action category colour coding
function actionColor(action) {
  if (!action) return 'bg-slate-500/10 text-slate-500 dark:text-slate-400 border border-slate-500/20'
  if (action.includes('created') || action.includes('invited'))  return 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20'
  if (action.includes('updated') || action.includes('changed'))  return 'bg-blue-500/10 text-blue-600 dark:text-blue-400 border border-blue-500/20'
  if (action.includes('deleted') || action.includes('removed'))  return 'bg-rose-500/10 text-rose-600 dark:text-rose-400 border border-rose-500/20'
  if (action.includes('suspend') || action.includes('deactivate')) return 'bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20'
  if (action.includes('assigned') || action.includes('granted'))  return 'bg-purple-500/10 text-purple-600 dark:text-purple-400 border border-purple-500/20'
  return 'bg-slate-500/10 text-slate-600 dark:text-slate-300 border border-slate-500/20'
}

// ── Event row ─────────────────────────────────────────────────────────────────
function EventRow({ event }) {
  const [expanded, setExpanded] = useState(false)
  const hasMetadata = event.metadata_ && Object.keys(event.metadata_).length > 0

  return (
    <>
      <tr
        className={`border-b border-slate-100 dark:border-[#1a2336] hover:bg-slate-50/60 dark:hover:bg-[#162030]/50 transition-colors ${hasMetadata ? 'cursor-pointer' : ''}`}
        onClick={() => hasMetadata && setExpanded(v => !v)}
      >
        <td className="px-5 py-3.5 text-xs font-mono text-slate-400 dark:text-slate-500 whitespace-nowrap">
          {event.created_at
            ? new Date(event.created_at).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', second: '2-digit' })
            : '—'}
        </td>
        <td className="px-5 py-3.5 text-xs font-medium text-slate-800 dark:text-slate-200">
          {event.actor_id || <span className="text-slate-400 dark:text-slate-500 italic">system</span>}
        </td>
        <td className="px-5 py-3.5">
          <span className={`px-2.5 py-0.5 rounded-full text-[11px] font-semibold ${actionColor(event.action)}`}>
            {event.action}
          </span>
        </td>
        <td className="px-5 py-3.5 text-xs text-slate-500 dark:text-slate-400">{event.entity_type || '—'}</td>
        <td className="px-5 py-3.5 text-xs font-mono text-slate-400 dark:text-slate-500 max-w-[140px] truncate">
          {event.entity_id ? event.entity_id.slice(0, 12) + '…' : '—'}
        </td>
        <td className="px-5 py-3.5 text-xs text-slate-400 dark:text-slate-500">
          {timeAgo(event.created_at)}
        </td>
        <td className="px-5 py-3.5 text-right">
          {hasMetadata && (
            <button className="p-1 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 transition-colors">
              {expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
            </button>
          )}
        </td>
      </tr>
      {expanded && hasMetadata && (
        <tr className="border-b border-slate-100 dark:border-[#1a2336] bg-slate-50/70 dark:bg-[#162030]/40">
          <td colSpan={7} className="px-5 py-4">
            <pre className="text-[11px] font-mono text-slate-700 dark:text-slate-300 bg-white dark:bg-[#0f1523] border border-slate-200 dark:border-[#233048] rounded-xl p-4 overflow-x-auto shadow-2xs">
              {JSON.stringify(event.metadata_, null, 2)}
            </pre>
          </td>
        </tr>
      )}
    </>
  )
}

// ── Main component ─────────────────────────────────────────────────────────────
export default function AdminAuditLog() {
  const { api } = useAuth()
  const [events,  setEvents]  = useState([])
  const [orgs,    setOrgs]    = useState([])
  const [loading, setLoading] = useState(true)
  const [error,   setError]   = useState(null)
  const [search,  setSearch]  = useState('')
  const [filterAction,   setFilterAction]   = useState('')
  const [filterEntityType, setFilterEntityType] = useState('')
  const [filterOrg, setFilterOrg] = useState('')

  const load = useCallback(async () => {
    setLoading(true); setError(null)
    try {
      const params = new URLSearchParams({ limit: '500' })
      if (filterOrg)        params.set('organization_id', filterOrg)
      if (filterAction)     params.set('action', filterAction)
      if (filterEntityType) params.set('entity_type', filterEntityType)

      const [evData, orgsData] = await Promise.all([
        api.get(`/admin/audit?${params.toString()}`),
        api.get('/admin/organizations').catch(() => []),
      ])
      setEvents(Array.isArray(evData) ? evData : [])
      setOrgs(Array.isArray(orgsData) ? orgsData : [])
    } catch (e) {
      setError(e?.response?.data?.detail || e.message || 'Failed to load audit log')
    } finally {
      setLoading(false)
    }
  }, [api, filterOrg, filterAction, filterEntityType])

  useEffect(() => { load() }, [load])

  const filtered = useMemo(() => {
    if (!search) return events
    const q = search.toLowerCase()
    return events.filter(e =>
      e.action?.toLowerCase().includes(q) ||
      e.actor_id?.toLowerCase().includes(q) ||
      e.entity_type?.toLowerCase().includes(q) ||
      e.entity_id?.toLowerCase().includes(q)
    )
  }, [events, search])

  const actionOptions = useMemo(() => [...new Set(events.map(e => e.action).filter(Boolean))].sort(), [events])
  const entityOptions = useMemo(() => [...new Set(events.map(e => e.entity_type).filter(Boolean))].sort(), [events])

  function exportCSV() {
    const rows = [
      ['Timestamp', 'Actor', 'Action', 'Entity Type', 'Entity ID', 'Metadata'],
      ...filtered.map(e => [
        e.created_at || '',
        e.actor_id || '',
        e.action || '',
        e.entity_type || '',
        e.entity_id || '',
        JSON.stringify(e.metadata_ || {}),
      ])
    ]
    const csv = rows.map(r => r.map(v => `"${String(v).replace(/"/g, '""')}"`).join(',')).join('\n')
    const blob = new Blob([csv], { type: 'text/csv' })
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = `audit-log-${new Date().toISOString().slice(0, 10)}.csv`
    a.click()
    URL.revokeObjectURL(a.href)
  }

  return (
    <div className="flex flex-col gap-6 p-6 min-h-full bg-slate-50 dark:bg-[#0b0f17] text-slate-900 dark:text-slate-100 transition-colors">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-xl font-bold text-slate-900 dark:text-white flex items-center gap-2">
            <Shield className="text-blue-500" size={22} />
            Audit Log
          </h1>
          <p className="text-sm text-slate-500 dark:text-slate-400 mt-0.5">
            {loading ? '…' : `${filtered.length} audit record${filtered.length !== 1 ? 's' : ''} captured`}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={exportCSV} disabled={filtered.length === 0}
            className="flex items-center gap-1.5 px-3.5 py-2 text-sm font-medium text-slate-700 dark:text-slate-300 bg-white dark:bg-[#121826] border border-slate-200 dark:border-[#233048] rounded-xl hover:bg-slate-50 dark:hover:bg-[#162030] disabled:opacity-40 transition-colors">
            <Download size={14} /> Export CSV
          </button>
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

      {/* Filters */}
      <div className="flex items-center gap-3 flex-wrap">
        <div className="relative flex-1 min-w-[200px]">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" />
          <input type="text" placeholder="Search actor, action, entity…" value={search}
            onChange={e => setSearch(e.target.value)}
            className="w-full pl-9 pr-3 py-2 text-sm bg-white dark:bg-[#121826] border border-slate-200 dark:border-[#233048] text-slate-900 dark:text-white rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 placeholder-slate-400" />
        </div>
        <select value={filterOrg} onChange={e => setFilterOrg(e.target.value)}
          className="px-3 py-2 text-sm bg-white dark:bg-[#121826] border border-slate-200 dark:border-[#233048] text-slate-900 dark:text-white rounded-xl focus:outline-none">
          <option value="">All organizations</option>
          {orgs.map(o => <option key={o.id} value={o.id}>{o.name}</option>)}
        </select>
        <select value={filterAction} onChange={e => setFilterAction(e.target.value)}
          className="px-3 py-2 text-sm bg-white dark:bg-[#121826] border border-slate-200 dark:border-[#233048] text-slate-900 dark:text-white rounded-xl focus:outline-none">
          <option value="">All actions</option>
          {actionOptions.map(a => <option key={a} value={a}>{a}</option>)}
        </select>
        <select value={filterEntityType} onChange={e => setFilterEntityType(e.target.value)}
          className="px-3 py-2 text-sm bg-white dark:bg-[#121826] border border-slate-200 dark:border-[#233048] text-slate-900 dark:text-white rounded-xl focus:outline-none">
          <option value="">All entity types</option>
          {entityOptions.map(t => <option key={t} value={t}>{t}</option>)}
        </select>
      </div>

      {/* Table */}
      {loading ? (
        <div className="flex items-center justify-center h-48 text-slate-400 text-sm">Loading audit logs…</div>
      ) : filtered.length === 0 ? (
        <EmptyState icon={ShieldAlert} title="No audit events"
          description="Platform audit events appear here whenever an admin performs an action." />
      ) : (
        <div className="bg-white dark:bg-[#121826] border border-slate-200 dark:border-[#233048] rounded-2xl overflow-hidden shadow-2xs">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-100 dark:border-[#1e2a3f] bg-slate-50/70 dark:bg-[#162030]/60">
                  {['Timestamp', 'Actor', 'Action', 'Entity Type', 'Entity ID', 'Age', ''].map(h => (
                    <th key={h} className="px-5 py-3 text-left text-[11px] font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider whitespace-nowrap">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-[#1a2336]">
                {filtered.map(event => (
                  <EventRow key={event.id} event={event} />
                ))}
              </tbody>
            </table>
          </div>
          {events.length === 500 && (
            <div className="px-5 py-3 border-t border-slate-100 dark:border-[#1e2a3f] text-xs text-slate-400 dark:text-slate-500 text-center">
              Showing latest 500 events. Use filters to narrow results.
            </div>
          )}
        </div>
      )}
    </div>
  )
}
