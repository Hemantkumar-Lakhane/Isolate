// AdminSubscriptions — Organization Subscriptions
import { useState, useEffect, useCallback, useMemo } from 'react'
import {
  ReceiptText, RefreshCw, Search, XCircle, ChevronRight,
  AlertCircle, CheckCircle2, Clock, PauseCircle, CalendarDays, AlertTriangle,
} from 'lucide-react'
import { useAuth } from '../../contexts/AuthContext'
import { useNavigate } from 'react-router-dom'
import { EmptyState, Modal, Button, Select } from '../../components/ui'

// ── Status metadata ───────────────────────────────────────────────────────────
const STATUS_META = {
  active:        { label: 'Active',         cls: 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20', icon: CheckCircle2 },
  trialing:      { label: 'Trial',          cls: 'bg-blue-500/10 text-blue-600 dark:text-blue-400 border border-blue-500/20',       icon: Clock },
  trial_expired: { label: 'Trial Expired',  cls: 'bg-rose-500/10 text-rose-600 dark:text-rose-400 border border-rose-500/20',         icon: AlertTriangle },
  past_due:      { label: 'Past Due',       cls: 'bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20',         icon: AlertCircle },
  cancelled:     { label: 'Cancelled',      cls: 'bg-slate-500/10 text-slate-500 dark:text-slate-400 border border-slate-500/20',     icon: XCircle },
  paused:        { label: 'Paused',         cls: 'bg-yellow-500/10 text-yellow-600 dark:text-yellow-400 border border-yellow-500/20',   icon: PauseCircle },
}

function StatusBadge({ status, effective_status }) {
  const display = effective_status || status
  const m = STATUS_META[display] || { label: display, cls: 'bg-slate-500/10 text-slate-500 dark:text-slate-400 border border-slate-500/20', icon: AlertCircle }
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

function trialDaysLeft(trial_ends_at) {
  if (!trial_ends_at) return null
  const diff = new Date(trial_ends_at).getTime() - Date.now()
  return Math.max(0, Math.ceil(diff / 86400000))
}

// ── Trial countdown pill ──────────────────────────────────────────────────────
function TrialCountdown({ sub }) {
  if (sub.effective_status === 'trial_expired') {
    return <span className="text-xs font-semibold text-rose-500">Expired {fmt(sub.trial_ends_at)}</span>
  }
  if (sub.status !== 'trialing' || !sub.trial_ends_at) return null
  const days = trialDaysLeft(sub.trial_ends_at)
  return (
    <span className={`text-xs font-medium ${days <= 3 ? 'text-amber-500' : 'text-blue-500'}`}>
      {days}d remaining · ends {fmt(sub.trial_ends_at)}
    </span>
  )
}

// ── Edit subscription modal ───────────────────────────────────────────────────
function EditSubModal({ open, onClose, api, sub, plans, onDone }) {
  const [form, setForm] = useState({
    status: '', billing_cycle: '', plan_id: '', notes: '',
    trial_ends_at: '',
  })
  const [loading, setLoading] = useState(false)
  const [error, setError]     = useState('')
  const [extendDays, setExtendDays] = useState(7)
  const [extending, setExtending] = useState(false)

  useEffect(() => {
    if (sub) {
      setForm({
        status:        sub.status        || 'active',
        billing_cycle: sub.billing_cycle || 'monthly',
        plan_id:       sub.plan_id       || '',
        notes:         sub.notes         || '',
        trial_ends_at: sub.trial_ends_at ? sub.trial_ends_at.split('T')[0] : '',
      })
      setExtendDays(7)
    }
    setError('')
  }, [sub, open])

  async function submit(e) {
    e.preventDefault()
    setLoading(true); setError('')
    try {
      const payload = {
        status:        form.status        || undefined,
        billing_cycle: form.billing_cycle || undefined,
        notes:         form.notes         || undefined,
      }
      if (form.plan_id) payload.plan_id = form.plan_id
      if (form.trial_ends_at) payload.trial_ends_at = new Date(form.trial_ends_at).toISOString()
      await api.patch(`/admin/subscriptions/${sub.organization_id}`, payload)
      onDone(); onClose()
    } catch (err) {
      setError(err?.response?.data?.detail || err.message || 'Update failed')
    } finally { setLoading(false) }
  }

  async function extendTrial() {
    if (!extendDays || extendDays < 1) return
    setExtending(true); setError('')
    try {
      const base = sub.trial_ends_at && new Date(sub.trial_ends_at) > new Date()
        ? new Date(sub.trial_ends_at)
        : new Date()
      base.setDate(base.getDate() + extendDays)
      await api.patch(`/admin/subscriptions/${sub.organization_id}`, {
        status: 'trialing',
        trial_ends_at: base.toISOString(),
      })
      onDone(); onClose()
    } catch (err) {
      setError(err?.response?.data?.detail || err.message || 'Extension failed')
    } finally { setExtending(false) }
  }

  const isTrialing = sub?.status === 'trialing' || sub?.effective_status === 'trial_expired'

  return (
    <Modal open={open} onClose={onClose}
      title={`Edit Subscription — ${sub?.organization_name || ''}`}
      subtitle="Update plan, status, or billing cycle"
      width="max-w-md"
    >
      <form onSubmit={submit} className="flex flex-col gap-4">
        {error && (
          <div className="flex items-center gap-2 px-3 py-2.5 bg-red-500/10 border border-red-500/20 rounded-lg text-sm text-red-600 dark:text-red-400">
            <XCircle size={14} />{error}
          </div>
        )}

        <Select label="Plan" value={form.plan_id}
          onChange={e => setForm(f => ({ ...f, plan_id: e.target.value }))}
          options={[{ value: '', label: 'Keep current plan' }, ...plans.map(p => ({ value: p.id, label: p.name }))]}
        />
        <Select label="Status" value={form.status}
          onChange={e => setForm(f => ({ ...f, status: e.target.value }))}
          options={[
            { value: 'active',    label: 'Active' },
            { value: 'trialing',  label: 'Trialing' },
            { value: 'past_due',  label: 'Past Due' },
            { value: 'paused',    label: 'Paused' },
            { value: 'cancelled', label: 'Cancelled' },
          ]}
        />
        <Select label="Billing Cycle" value={form.billing_cycle}
          onChange={e => setForm(f => ({ ...f, billing_cycle: e.target.value }))}
          options={[{ value: 'monthly', label: 'Monthly' }, { value: 'annual', label: 'Annual' }]}
        />

        {/* Trial end date */}
        {(form.status === 'trialing' || isTrialing) && (
          <div>
            <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">Trial End Date</label>
            <input
              type="date"
              value={form.trial_ends_at}
              onChange={e => setForm(f => ({ ...f, trial_ends_at: e.target.value }))}
              className="w-full bg-white dark:bg-[#162030] border border-slate-200 dark:border-[#2a3850] text-slate-900 dark:text-white rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
            />
          </div>
        )}

        <div>
          <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1">Internal Notes</label>
          <textarea
            value={form.notes}
            onChange={e => setForm(f => ({ ...f, notes: e.target.value }))}
            rows={2}
            placeholder="Optional admin notes…"
            className="w-full bg-white dark:bg-[#162030] border border-slate-200 dark:border-[#2a3850] text-slate-900 dark:text-white rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 resize-none"
          />
        </div>

        {/* Quick trial extension */}
        {isTrialing && (
          <div className="flex items-center gap-3 px-3 py-2.5 bg-blue-500/10 border border-blue-500/20 rounded-xl">
            <CalendarDays size={15} className="text-blue-500 shrink-0" />
            <p className="text-xs text-blue-700 dark:text-blue-300 flex-1">Quick extend trial by</p>
            <input
              type="number" min={1} max={90} value={extendDays}
              onChange={e => setExtendDays(parseInt(e.target.value) || 7)}
              className="w-16 border border-blue-200 dark:border-blue-800 rounded-lg px-2 py-1 text-sm text-blue-900 dark:text-blue-100 bg-white dark:bg-[#121826] focus:outline-none"
            />
            <span className="text-xs text-blue-700 dark:text-blue-300">days</span>
            <button
              type="button"
              onClick={extendTrial}
              disabled={extending}
              className="px-2.5 py-1 text-xs font-semibold text-white bg-blue-600 hover:bg-blue-700 rounded-lg transition-colors disabled:opacity-50"
            >
              {extending ? '…' : 'Extend'}
            </button>
          </div>
        )}

        <div className="flex justify-end gap-2 pt-1">
          <Button variant="secondary" size="sm" type="button" onClick={onClose}>Cancel</Button>
          <Button variant="primary" size="sm" loading={loading} type="submit">Save Changes</Button>
        </div>
      </form>
    </Modal>
  )
}

// ── Main ──────────────────────────────────────────────────────────────────────
export default function AdminSubscriptions() {
  const { api } = useAuth()
  const navigate = useNavigate()
  const [subs, setSubs]     = useState([])
  const [plans, setPlans]   = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError]   = useState(null)
  const [search, setSearch] = useState('')
  const [filterStatus, setFilterStatus] = useState('all')
  const [editSub, setEditSub] = useState(null)

  const load = useCallback(async () => {
    setLoading(true); setError(null)
    try {
      const [s, p] = await Promise.all([
        api.get('/admin/subscriptions'),
        api.get('/admin/plans').catch(() => []),
      ])
      setSubs(Array.isArray(s) ? s : [])
      setPlans(Array.isArray(p) ? p : [])
    } catch (e) {
      setError(e?.response?.data?.detail || e.message || 'Failed to load subscriptions')
    } finally { setLoading(false) }
  }, [api])

  useEffect(() => { load() }, [load])

  const filtered = useMemo(() => {
    let list = subs
    if (search) {
      const q = search.toLowerCase()
      list = list.filter(s =>
        s.organization_name?.toLowerCase().includes(q) ||
        s.plan_name?.toLowerCase().includes(q) ||
        s.plan_slug?.toLowerCase().includes(q)
      )
    }
    if (filterStatus !== 'all') {
      list = list.filter(s =>
        s.effective_status === filterStatus || s.status === filterStatus
      )
    }
    return list
  }, [subs, search, filterStatus])

  const counts = useMemo(() => ({
    active:        subs.filter(s => s.status === 'active').length,
    trialing:      subs.filter(s => s.status === 'trialing').length,
    trial_expired: subs.filter(s => s.effective_status === 'trial_expired').length,
    past_due:      subs.filter(s => s.status === 'past_due').length,
  }), [subs])

  return (
    <div className="flex flex-col gap-6 p-6 min-h-full bg-slate-50 dark:bg-[#0b0f17] text-slate-900 dark:text-slate-100 transition-colors">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-xl font-bold text-slate-900 dark:text-white flex items-center gap-2">
            <ReceiptText className="text-blue-500" size={22} />
            Subscriptions
          </h1>
          <p className="text-sm text-slate-500 dark:text-slate-400 mt-0.5">
            {loading ? '…' : `${subs.length} subscription${subs.length !== 1 ? 's' : ''}`}
          </p>
        </div>
        <button onClick={load} disabled={loading}
          className="p-2 rounded-xl text-slate-500 dark:text-slate-400 bg-white dark:bg-[#121826] border border-slate-200 dark:border-[#233048] hover:bg-slate-50 dark:hover:bg-[#162030] transition-colors disabled:opacity-50">
          <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
        </button>
      </div>

      {/* Summary cards */}
      {!loading && !error && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {[
            { label: 'Active',         value: counts.active,        cls: 'text-emerald-600 dark:text-emerald-400', status: 'active' },
            { label: 'Trialing',       value: counts.trialing,      cls: 'text-blue-600 dark:text-blue-400',       status: 'trialing' },
            { label: 'Trial Expired',  value: counts.trial_expired, cls: 'text-rose-600 dark:text-rose-400',       status: 'trial_expired' },
            { label: 'Past Due',       value: counts.past_due,      cls: 'text-amber-600 dark:text-amber-400',     status: 'past_due' },
          ].map(c => (
            <button
              key={c.label}
              onClick={() => setFilterStatus(filterStatus === c.status ? 'all' : c.status)}
              className={`bg-white dark:bg-[#121826] border rounded-2xl p-4 text-center transition-all shadow-2xs ${
                filterStatus === c.status
                  ? 'border-blue-500 ring-2 ring-blue-500/20'
                  : 'border-slate-200 dark:border-[#233048] hover:border-slate-300 dark:hover:border-[#2f4060]'
              }`}
            >
              <p className={`text-2xl font-bold ${c.cls}`}>{c.value}</p>
              <p className="text-xs text-slate-500 dark:text-slate-400 mt-1 font-medium">{c.label}</p>
            </button>
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
          <input type="text" placeholder="Search by organization or plan…" value={search}
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
        <div className="flex items-center justify-center h-48 text-slate-400 text-sm">Loading subscriptions…</div>
      ) : filtered.length === 0 ? (
        <EmptyState icon={ReceiptText} title="No subscriptions found"
          description={search || filterStatus !== 'all' ? 'Try a different filter.' : 'No subscriptions yet.'} />
      ) : (
        <div className="bg-white dark:bg-[#121826] border border-slate-200 dark:border-[#233048] rounded-2xl overflow-hidden shadow-2xs">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-100 dark:border-[#1e2a3f] bg-slate-50/70 dark:bg-[#162030]/60">
                  {['Organization', 'Plan', 'Status', 'Cycle', 'Trial / Period End', 'Actions'].map(h => (
                    <th key={h} className="px-5 py-3 text-left text-[11px] font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-[#1a2336]">
                {filtered.map(s => (
                  <tr key={s.id} className="hover:bg-slate-50/60 dark:hover:bg-[#162030]/50 transition-colors">
                    <td className="px-5 py-3.5">
                      <button
                        onClick={() => navigate(`/admin/organizations/${s.organization_id}`)}
                        className="text-sm font-semibold text-blue-600 dark:text-blue-400 hover:underline text-left"
                      >
                        {s.organization_name || 'Unknown'}
                      </button>
                    </td>
                    <td className="px-5 py-3.5">
                      <span className="text-sm font-medium text-slate-700 dark:text-slate-200">{s.plan_name || s.plan_slug || '—'}</span>
                    </td>
                    <td className="px-5 py-3.5">
                      <StatusBadge status={s.status} effective_status={s.effective_status} />
                    </td>
                    <td className="px-5 py-3.5 text-xs text-slate-500 dark:text-slate-400 capitalize">{s.billing_cycle}</td>
                    <td className="px-5 py-3.5">
                      <div className="flex flex-col gap-0.5">
                        {s.status === 'trialing' || s.effective_status === 'trial_expired'
                          ? <TrialCountdown sub={s} />
                          : <span className="text-xs text-slate-500 dark:text-slate-400">{fmt(s.current_period_end)}</span>
                        }
                      </div>
                    </td>
                    <td className="px-5 py-3.5">
                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => setEditSub(s)}
                          className="px-2.5 py-1 text-xs font-semibold text-slate-700 dark:text-slate-200 bg-slate-50 dark:bg-[#162030] border border-slate-200 dark:border-[#2a3850] rounded-lg hover:bg-slate-100 dark:hover:bg-[#1f2c42] transition-colors"
                        >
                          Edit
                        </button>
                        <button
                          onClick={() => navigate(`/admin/organizations/${s.organization_id}`)}
                          className="p-1 text-slate-400 hover:text-blue-500 transition-colors"
                          title="View org"
                        >
                          <ChevronRight size={15} />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <EditSubModal
        open={!!editSub}
        onClose={() => setEditSub(null)}
        api={api}
        sub={editSub}
        plans={plans}
        onDone={load}
      />
    </div>
  )
}
