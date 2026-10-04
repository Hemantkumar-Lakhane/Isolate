// AdminInvoices — Platform Invoice Ledger
import { useState, useEffect, useCallback, useMemo } from 'react'
import {
  FileText, RefreshCw, Search, XCircle, ExternalLink,
  CheckCircle2, AlertCircle, Clock, Ban,
} from 'lucide-react'
import { useAuth } from '../../contexts/AuthContext'
import { useNavigate } from 'react-router-dom'
import { EmptyState } from '../../components/ui'

const STATUS_META = {
  draft:           { label: 'Draft',          cls: 'bg-slate-500/10 text-slate-500 dark:text-slate-400 border border-slate-500/20',    icon: Clock       },
  open:            { label: 'Open',           cls: 'bg-blue-500/10 text-blue-600 dark:text-blue-400 border border-blue-500/20',      icon: AlertCircle },
  paid:            { label: 'Paid',           cls: 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20',icon: CheckCircle2},
  void:            { label: 'Void',           cls: 'bg-slate-500/10 text-slate-400 border border-slate-500/20',    icon: Ban         },
  uncollectible:   { label: 'Uncollectible',  cls: 'bg-rose-500/10 text-rose-600 dark:text-rose-400 border border-rose-500/20',        icon: XCircle     },
}

function StatusBadge({ status }) {
  const m = STATUS_META[status] || { label: status, cls: 'bg-slate-500/10 text-slate-500 dark:text-slate-400 border border-slate-500/20', icon: AlertCircle }
  const Icon = m.icon
  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-semibold ${m.cls}`}>
      <Icon size={11} />{m.label}
    </span>
  )
}

function fmt(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' })
}

function fmtUSD(v) {
  if (v === null || v === undefined) return '—'
  return `$${Number(v).toFixed(2)}`
}

export default function AdminInvoices() {
  const { api }    = useAuth()
  const navigate   = useNavigate()
  const [invoices, setInvoices] = useState([])
  const [loading, setLoading]   = useState(true)
  const [error, setError]       = useState(null)
  const [search, setSearch]     = useState('')
  const [filterStatus, setFilterStatus] = useState('all')

  const load = useCallback(async () => {
    setLoading(true); setError(null)
    try {
      const data = await api.get('/admin/invoices?limit=500')
      setInvoices(Array.isArray(data) ? data : [])
    } catch (e) {
      setError(e?.response?.data?.detail || e.message || 'Failed to load invoices')
    } finally { setLoading(false) }
  }, [api])

  useEffect(() => { load() }, [load])

  const filtered = useMemo(() => {
    let list = invoices
    if (search) {
      const q = search.toLowerCase()
      list = list.filter(inv =>
        inv.organization_name?.toLowerCase().includes(q) ||
        inv.invoice_number?.toLowerCase().includes(q)
      )
    }
    if (filterStatus !== 'all') list = list.filter(inv => inv.status === filterStatus)
    return list
  }, [invoices, search, filterStatus])

  const totals = useMemo(() => ({
    open:       invoices.filter(i => i.status === 'open').reduce((s, i) => s + Number(i.total_usd || 0), 0),
    paid:       invoices.filter(i => i.status === 'paid').reduce((s, i) => s + Number(i.total_usd || 0), 0),
    openCount:  invoices.filter(i => i.status === 'open').length,
  }), [invoices])

  return (
    <div className="flex flex-col gap-6 p-6 min-h-full bg-slate-50 dark:bg-[#0b0f17] text-slate-900 dark:text-slate-100 transition-colors">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-xl font-bold text-slate-900 dark:text-white flex items-center gap-2">
            <FileText className="text-blue-500" size={22} />
            Invoices
          </h1>
          <p className="text-sm text-slate-500 dark:text-slate-400 mt-0.5">
            {loading ? '…' : `${invoices.length} invoice${invoices.length !== 1 ? 's' : ''}`}
          </p>
        </div>
        <button onClick={load} disabled={loading}
          className="p-2 rounded-xl text-slate-500 dark:text-slate-400 bg-white dark:bg-[#121826] border border-slate-200 dark:border-[#233048] hover:bg-slate-50 dark:hover:bg-[#162030] transition-colors disabled:opacity-50">
          <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
        </button>
      </div>

      {/* Summary cards */}
      {!loading && !error && (
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          {[
            { label: 'Open AR',     value: fmtUSD(totals.open),      sub: `${totals.openCount} invoice${totals.openCount !== 1 ? 's' : ''}`, cls: 'text-blue-600 dark:text-blue-400' },
            { label: 'Collected',   value: fmtUSD(totals.paid),       sub: `${invoices.filter(i => i.status === 'paid').length} paid`,       cls: 'text-emerald-600 dark:text-emerald-400' },
            { label: 'Total Invoiced', value: invoices.length.toString(), sub: 'All-time platform ledger',                                           cls: 'text-slate-800 dark:text-slate-200' },
          ].map(c => (
            <div key={c.label} className="bg-white dark:bg-[#121826] border border-slate-200 dark:border-[#233048] rounded-2xl p-5 shadow-2xs">
              <p className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider mb-1">{c.label}</p>
              <p className={`text-2xl font-bold ${c.cls}`}>{c.value}</p>
              <p className="text-xs text-slate-400 dark:text-slate-500 mt-1 font-medium">{c.sub}</p>
            </div>
          ))}
        </div>
      )}

      {error && (
        <div className="flex items-center gap-2 px-4 py-3 bg-red-500/10 border border-red-500/20 rounded-xl text-sm text-red-600 dark:text-red-400">
          <XCircle size={15} className="shrink-0" />{error}
        </div>
      )}

      {/* Filters */}
      <div className="flex items-center gap-3 flex-wrap">
        <div className="relative flex-1 min-w-[200px]">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" />
          <input type="text" placeholder="Search by organization or invoice #…" value={search}
            onChange={e => setSearch(e.target.value)}
            className="w-full pl-9 pr-3 py-2 text-sm bg-white dark:bg-[#121826] border border-slate-200 dark:border-[#233048] text-slate-900 dark:text-white rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 placeholder-slate-400" />
        </div>
        <select value={filterStatus} onChange={e => setFilterStatus(e.target.value)}
          className="px-3 py-2 text-sm bg-white dark:bg-[#121826] border border-slate-200 dark:border-[#233048] text-slate-900 dark:text-white rounded-xl focus:outline-none">
          <option value="all">All statuses</option>
          {Object.entries(STATUS_META).map(([v, m]) => (
            <option key={v} value={v}>{m.label}</option>
          ))}
        </select>
      </div>

      {/* Table */}
      {loading ? (
        <div className="flex items-center justify-center h-48 text-slate-400 text-sm">Loading invoices…</div>
      ) : filtered.length === 0 ? (
        <EmptyState icon={FileText} title="No invoices found"
          description={search || filterStatus !== 'all' ? 'Try a different filter.' : 'Invoices will appear here once billing periods close.'} />
      ) : (
        <div className="bg-white dark:bg-[#121826] border border-slate-200 dark:border-[#233048] rounded-2xl overflow-hidden shadow-2xs">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-100 dark:border-[#1e2a3f] bg-slate-50/70 dark:bg-[#162030]/60">
                  {['Invoice #', 'Organization', 'Status', 'Subtotal', 'Tax', 'Total', 'Due Date', 'Paid At'].map(h => (
                    <th key={h} className="px-5 py-3 text-left text-[11px] font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-[#1a2336]">
                {filtered.map(inv => (
                  <tr key={inv.id} className="hover:bg-slate-50/60 dark:hover:bg-[#162030]/50 transition-colors">
                    <td className="px-5 py-3.5">
                      <span className="font-mono text-xs font-semibold text-slate-700 dark:text-slate-300">{inv.invoice_number || inv.id?.slice(0, 8)}</span>
                    </td>
                    <td className="px-5 py-3.5">
                      <button
                        onClick={() => navigate(`/admin/organizations/${inv.organization_id}`)}
                        className="text-sm font-semibold text-blue-600 dark:text-blue-400 hover:underline text-left"
                      >
                        {inv.organization_name || 'Unknown'}
                      </button>
                    </td>
                    <td className="px-5 py-3.5"><StatusBadge status={inv.status} /></td>
                    <td className="px-5 py-3.5 text-xs text-slate-600 dark:text-slate-400 font-mono">{fmtUSD(inv.subtotal_usd)}</td>
                    <td className="px-5 py-3.5 text-xs text-slate-500 dark:text-slate-400 font-mono">{fmtUSD(inv.tax_usd)}</td>
                    <td className="px-5 py-3.5 text-sm font-bold text-slate-900 dark:text-white font-mono">{fmtUSD(inv.total_usd)}</td>
                    <td className="px-5 py-3.5 text-xs text-slate-500 dark:text-slate-400">{fmt(inv.due_date)}</td>
                    <td className="px-5 py-3.5 text-xs text-slate-500 dark:text-slate-400">{fmt(inv.paid_at)}</td>
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
