// AdminOrgDetail — full organization detail with tabs
// /admin/organizations/:orgId
import { useState, useEffect, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  ArrowLeft, Building2, Users, Workflow, BarChart3, CreditCard,
  Activity, RefreshCw, CheckCircle2, XCircle, Power, PowerOff,
  Plus, Trash2, Plug, ReceiptText, AlertCircle,
} from 'lucide-react'
import { useAuth } from '../../contexts/AuthContext'
import { Modal, Button, Input, Select, EmptyState, TabGroup } from '../../components/ui'

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

function StatusBadge({ active }) {
  return active
    ? <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20 rounded-full text-[11px] font-semibold"><CheckCircle2 size={11} />Active</span>
    : <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 bg-rose-500/10 text-rose-600 dark:text-rose-400 border border-rose-500/20 rounded-full text-[11px] font-semibold"><XCircle size={11} />Suspended</span>
}

// ── Overview tab ──────────────────────────────────────────────────────────────
function OverviewTab({ detail }) {
  const m = detail?.run_stats || {}
  const sub = detail?.subscription
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
      {[
        { label: 'Total Runs',    value: m.total_runs ?? 0 },
        { label: 'Total Tokens',  value: m.total_tokens ? m.total_tokens.toLocaleString() : '0' },
        { label: 'Total Spend',   value: m.total_cost_usd !== null && m.total_cost_usd !== undefined ? `$${Number(m.total_cost_usd).toFixed(2)}` : 'Unavailable' },
        { label: 'Active Since',  value: detail?.created_at ? new Date(detail.created_at).toLocaleDateString() : '—' },
      ].map(item => (
        <div key={item.label} className="bg-slate-50 dark:bg-[#162030] rounded-2xl p-4 border border-slate-200 dark:border-[#2a3850]">
          <p className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide mb-1">{item.label}</p>
          <p className="text-2xl font-bold text-slate-900 dark:text-white tracking-tight">{item.value}</p>
        </div>
      ))}
      {sub && (
        <div className="col-span-2 md:col-span-4 bg-blue-500/10 border border-blue-500/20 rounded-2xl p-4">
          <p className="text-xs font-bold text-blue-600 dark:text-blue-400 uppercase tracking-wide mb-2">Active Subscription</p>
          <div className="flex items-center gap-4 flex-wrap text-sm">
            <span className="font-bold text-slate-900 dark:text-white">{sub.plan_name || sub.plan_slug || '—'}</span>
            <span className={`px-2 py-0.5 rounded-full text-[11px] font-semibold ${
              sub.status === 'active' ? 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20' : 'bg-slate-500/10 text-slate-500 dark:text-slate-400'
            }`}>{sub.status}</span>
            <span className="text-slate-500 dark:text-slate-400 capitalize">{sub.billing_cycle}</span>
            {sub.current_period_end && (
              <span className="text-slate-500 dark:text-slate-400 font-medium">Renews {new Date(sub.current_period_end).toLocaleDateString()}</span>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

// ── Users tab ─────────────────────────────────────────────────────────────────
function UsersTab({ users, orgId, api, onRefresh }) {
  const [showInvite, setShowInvite] = useState(false)
  const [inviteEmail, setInviteEmail] = useState('')
  const [inviteName, setInviteName]  = useState('')
  const [inviteLoading, setInviteLoading] = useState(false)
  const [inviteError, setInviteError] = useState('')

  async function handleInvite(e) {
    e.preventDefault()
    if (!inviteEmail.trim()) return
    setInviteLoading(true); setInviteError('')
    try {
      await api.post('/admin/users/invite', {
        email: inviteEmail.trim(),
        full_name: inviteName.trim() || undefined,
        role: 'org_user',
        organization_id: orgId,
      })
      setShowInvite(false); setInviteEmail(''); setInviteName('')
      onRefresh()
    } catch (e) {
      setInviteError(e?.response?.data?.detail || e.message || 'Invite failed')
    } finally {
      setInviteLoading(false)
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-slate-500 dark:text-slate-400 font-medium">{users.length} member{users.length !== 1 ? 's' : ''}</p>
        <Button size="sm" variant="secondary" icon={<Plus size={13} />} onClick={() => setShowInvite(true)}>
          Invite User
        </Button>
      </div>

      {showInvite && (
        <form onSubmit={handleInvite} className="flex items-end gap-3 p-4 bg-blue-500/10 border border-blue-500/20 rounded-2xl flex-wrap">
          <Input label="Email" type="email" required value={inviteEmail} onChange={e => setInviteEmail(e.target.value)} className="flex-1 min-w-[200px]" />
          <Input label="Name (optional)" value={inviteName} onChange={e => setInviteName(e.target.value)} className="flex-1 min-w-[200px]" />
          <div className="flex gap-2 pb-0.5">
            <Button size="sm" variant="primary" loading={inviteLoading} type="submit">Send Invite</Button>
            <Button size="sm" variant="secondary" type="button" onClick={() => setShowInvite(false)}>Cancel</Button>
          </div>
          {inviteError && <p className="text-xs text-rose-500 w-full mt-1">{inviteError}</p>}
        </form>
      )}

      {users.length === 0 ? (
        <EmptyState icon={Users} title="No users" description="Invite the first user to this organization." />
      ) : (
        <div className="border border-slate-200 dark:border-[#233048] rounded-2xl overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-slate-50/70 dark:bg-[#162030]/60 border-b border-slate-100 dark:border-[#1e2a3f]">
                {['User', 'Role', 'Joined'].map(h => (
                  <th key={h} className="px-5 py-3 text-left text-[11px] font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-[#1a2336]">
              {users.map(u => (
                <tr key={u.id} className="hover:bg-slate-50/60 dark:hover:bg-[#162030]/50 transition-colors">
                  <td className="px-5 py-3.5">
                    <p className="font-semibold text-slate-900 dark:text-white">{u.full_name || u.email}</p>
                    <p className="text-xs text-slate-400 dark:text-slate-500">{u.full_name ? u.email : ''}</p>
                  </td>
                  <td className="px-5 py-3.5">
                    <span className={`px-2.5 py-0.5 rounded-full text-[11px] font-semibold ${
                      u.role === 'platform_admin' ? 'bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20' : 'bg-slate-500/10 text-slate-600 dark:text-slate-300 border border-slate-500/20'
                    }`}>
                      {u.role}
                    </span>
                  </td>
                  <td className="px-5 py-3.5 text-xs text-slate-400 dark:text-slate-500">
                    {u.created_at ? new Date(u.created_at).toLocaleDateString() : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

// ── Workflows tab ─────────────────────────────────────────────────────────────
function WorkflowsTab({ assignments, catalog, orgId, api, onRefresh }) {
  const [showAssign, setShowAssign] = useState(false)
  const [selectedWf, setSelectedWf] = useState('')
  const [assigning, setAssigning]   = useState(false)
  const [removing, setRemoving]     = useState(null)

  const assignedIds = assignments.map(a => a.workflow_id)
  const unassigned  = catalog.filter(w => !assignedIds.includes(w.id) && w.active)

  async function assign() {
    if (!selectedWf) return
    setAssigning(true)
    try {
      await api.post(`/admin/organizations/${orgId}/workflows/${selectedWf}/assign`, {})
      setShowAssign(false); setSelectedWf('')
      onRefresh()
    } finally { setAssigning(false) }
  }

  async function remove(workflowId) {
    setRemoving(workflowId)
    try {
      await api.delete(`/admin/organizations/${orgId}/workflows/${workflowId}/assign`)
      onRefresh()
    } finally { setRemoving(null) }
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-slate-500 dark:text-slate-400 font-medium">{assignments.length} workflow{assignments.length !== 1 ? 's' : ''} assigned</p>
        {unassigned.length > 0 && (
          <Button size="sm" variant="secondary" icon={<Plus size={13} />} onClick={() => setShowAssign(true)}>
            Assign Workflow
          </Button>
        )}
      </div>

      {showAssign && (
        <div className="flex items-end gap-3 p-4 bg-blue-500/10 border border-blue-500/20 rounded-2xl">
          <Select
            label="Workflow"
            value={selectedWf}
            onChange={e => setSelectedWf(e.target.value)}
            options={[{ value: '', label: 'Select workflow…' }, ...unassigned.map(w => ({ value: w.id, label: w.name }))]}
            className="flex-1"
          />
          <div className="flex gap-2 pb-0.5">
            <Button size="sm" loading={assigning} onClick={assign}>Assign</Button>
            <Button size="sm" variant="secondary" onClick={() => { setShowAssign(false); setSelectedWf('') }}>Cancel</Button>
          </div>
        </div>
      )}

      {assignments.length === 0 ? (
        <EmptyState icon={Workflow} title="No workflows assigned" description="Assign workflows from the catalog to give this org access." />
      ) : (
        <div className="flex flex-col gap-2.5">
          {assignments.map(a => (
            <div key={a.id} className="flex items-center justify-between px-5 py-3.5 bg-white dark:bg-[#121826] border border-slate-200 dark:border-[#233048] rounded-2xl shadow-2xs">
              <div className="flex items-center gap-3">
                <div className={`w-2.5 h-2.5 rounded-full ${a.status === 'active' ? 'bg-emerald-500' : 'bg-slate-400'}`} />
                <div>
                  <p className="text-sm font-semibold text-slate-900 dark:text-white">{a.workflow_name || a.workflow_key}</p>
                  <p className="text-xs text-slate-400 dark:text-slate-500 font-mono mt-0.5">
                    {a.workflow_key} · Assigned {timeAgo(a.assigned_at)}
                    {a.assigned_by && ` by ${a.assigned_by}`}
                  </p>
                </div>
              </div>
              <button
                onClick={() => remove(a.workflow_id)}
                disabled={removing === a.workflow_id}
                className="p-1.5 rounded-xl text-slate-400 hover:text-rose-500 hover:bg-rose-500/10 transition-colors disabled:opacity-40"
              >
                <Trash2 size={15} />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ── Usage tab ─────────────────────────────────────────────────────────────────
function UsageTab({ orgId, api }) {
  const [usage, setUsage] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.get(`/admin/usage/${orgId}?days=30`)
      .then(d => setUsage(d))
      .catch(() => setUsage(null))
      .finally(() => setLoading(false))
  }, [orgId, api])

  if (loading) return <div className="py-12 text-center text-slate-400 text-sm">Loading usage…</div>
  if (!usage)  return <div className="py-12 text-center text-slate-400 text-sm">No usage data</div>

  return (
    <div className="flex flex-col gap-4">
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        {[
          { label: 'Total Cost (30d)',   value: usage.total_cost_usd !== null && usage.total_cost_usd !== undefined ? `$${Number(usage.total_cost_usd).toFixed(4)}` : 'Unavailable' },
          { label: 'Reported Events',    value: usage.reported_events ?? 0 },
          { label: 'Unreported Events',  value: usage.unreported_events ?? 0 },
        ].map(item => (
          <div key={item.label} className="bg-slate-50 dark:bg-[#162030] border border-slate-200 dark:border-[#2a3850] rounded-2xl p-4">
            <p className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide mb-1">{item.label}</p>
            <p className="text-2xl font-bold text-slate-900 dark:text-white tracking-tight">{item.value}</p>
          </div>
        ))}
      </div>
      {usage.breakdown?.length > 0 && (
        <div className="bg-white dark:bg-[#121826] border border-slate-200 dark:border-[#233048] rounded-2xl overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-100 dark:border-[#1e2a3f] bg-slate-50/70 dark:bg-[#162030]/60">
                {['Type', 'Workflow', 'Events', 'Tokens In', 'Tokens Out'].map(h => (
                  <th key={h} className="px-5 py-3 text-left text-[11px] font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-[#1a2336]">
              {usage.breakdown.map((row, i) => (
                <tr key={i} className="hover:bg-slate-50/60 dark:hover:bg-[#162030]/50 transition-colors">
                  <td className="px-5 py-3 font-mono text-xs text-slate-700 dark:text-slate-300">{row.usage_type}</td>
                  <td className="px-5 py-3 text-xs text-slate-500 dark:text-slate-400">{row.workflow_key || '—'}</td>
                  <td className="px-5 py-3 text-slate-800 dark:text-slate-200 font-semibold">{row.event_count}</td>
                  <td className="px-5 py-3 text-slate-500 dark:text-slate-400 font-mono text-xs">{row.tokens_in?.toLocaleString() || 0}</td>
                  <td className="px-5 py-3 text-slate-500 dark:text-slate-400 font-mono text-xs">{row.tokens_out?.toLocaleString() || 0}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

// ── Activity tab ──────────────────────────────────────────────────────────────
function ActivityTab({ orgId, api }) {
  const [events, setEvents] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.get(`/admin/audit?organization_id=${orgId}&limit=50`)
      .then(d => setEvents(Array.isArray(d) ? d : []))
      .catch(() => setEvents([]))
      .finally(() => setLoading(false))
  }, [orgId, api])

  if (loading) return <div className="py-12 text-center text-slate-400 text-sm">Loading audit events…</div>

  return (
    <div className="flex flex-col gap-1.5">
      {events.length === 0
        ? <EmptyState icon={Activity} title="No audit events" description="Activity for this organization will appear here." />
        : events.map(e => (
          <div key={e.id} className="flex items-start gap-3 px-4 py-3 hover:bg-slate-50 dark:hover:bg-[#162030]/50 rounded-xl transition-colors">
            <div className="w-2 h-2 rounded-full bg-blue-500 mt-2 shrink-0" />
            <div className="min-w-0 flex-1">
              <span className="text-sm text-slate-800 dark:text-slate-200 font-semibold">{e.action}</span>
              {e.actor_id && <span className="text-xs text-slate-400 dark:text-slate-500 ml-2">by {e.actor_id}</span>}
            </div>
            <span className="text-xs text-slate-400 dark:text-slate-500 shrink-0">{timeAgo(e.created_at)}</span>
          </div>
        ))}
    </div>
  )
}

// ── Billing tab ───────────────────────────────────────────────────────────────
function BillingTab({ orgId, api }) {
  const [sub, setSub]         = useState(null)
  const [invoices, setInvoices] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([
      api.get(`/admin/subscriptions/${orgId}`).catch(() => null),
      api.get(`/admin/invoices?organization_id=${orgId}&limit=20`).catch(() => []),
    ]).then(([s, inv]) => {
      setSub(s)
      setInvoices(Array.isArray(inv) ? inv : [])
    }).finally(() => setLoading(false))
  }, [orgId, api])

  if (loading) return <div className="py-12 text-center text-slate-400 text-sm">Loading billing…</div>

  const STATUS_CLS = {
    active:   'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20',
    trialing: 'bg-blue-500/10 text-blue-600 dark:text-blue-400 border border-blue-500/20',
    past_due: 'bg-rose-500/10 text-rose-600 dark:text-rose-400 border border-rose-500/20',
    cancelled:'bg-slate-500/10 text-slate-500 dark:text-slate-400 border border-slate-500/20',
    paused:   'bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20',
  }
  const INV_CLS = {
    paid:  'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20',
    open:  'bg-blue-500/10 text-blue-600 dark:text-blue-400 border border-blue-500/20',
    draft: 'bg-slate-500/10 text-slate-500 dark:text-slate-400 border border-slate-500/20',
    void:  'bg-slate-500/10 text-slate-400 border border-slate-500/20',
    uncollectible: 'bg-rose-500/10 text-rose-600 dark:text-rose-400 border border-rose-500/20',
  }

  return (
    <div className="flex flex-col gap-5">
      {/* Subscription */}
      {!sub ? (
        <div className="flex items-start gap-2.5 px-4 py-3 bg-amber-500/10 border border-amber-500/20 rounded-2xl text-sm text-amber-700 dark:text-amber-300">
          <AlertCircle size={16} className="shrink-0 mt-0.5" />
          No subscription record found for this organization.
        </div>
      ) : (
        <div className="bg-slate-50 dark:bg-[#162030] border border-slate-200 dark:border-[#2a3850] rounded-2xl p-5 shadow-2xs">
          <p className="text-xs font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider mb-3">Subscription Details</p>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {[
              { label: 'Plan',    value: sub.plan_name || sub.plan_slug || '—' },
              { label: 'Status',  value: <span className={`px-2.5 py-0.5 rounded-full text-[11px] font-semibold ${STATUS_CLS[sub.status] || 'bg-slate-500/10 text-slate-500'}`}>{sub.status}</span> },
              { label: 'Cycle',   value: sub.billing_cycle || '—' },
              { label: 'Period Ends', value: sub.current_period_end ? new Date(sub.current_period_end).toLocaleDateString() : '—' },
            ].map(item => (
              <div key={item.label}>
                <p className="text-[10px] font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide mb-1">{item.label}</p>
                <p className="text-sm font-bold text-slate-900 dark:text-white capitalize">{item.value}</p>
              </div>
            ))}
          </div>
          {sub.trial_ends_at && (
            <p className="text-xs text-blue-500 mt-3 font-medium">Trial ends {new Date(sub.trial_ends_at).toLocaleDateString()}</p>
          )}
          {sub.cancel_reason && (
            <p className="text-xs text-rose-500 mt-2">Cancel reason: {sub.cancel_reason}</p>
          )}
        </div>
      )}

      {/* Invoices */}
      <div>
        <p className="text-xs font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider mb-3">
          Invoices <span className="text-slate-400 dark:text-slate-500 font-normal normal-case">({invoices.length})</span>
        </p>
        {invoices.length === 0 ? (
          <EmptyState icon={ReceiptText} title="No invoices" description="Invoices appear when a billing period closes." />
        ) : (
          <div className="border border-slate-200 dark:border-[#233048] rounded-2xl overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-slate-50/70 dark:bg-[#162030]/60 border-b border-slate-100 dark:border-[#1e2a3f]">
                  {['Invoice #', 'Status', 'Subtotal', 'Total', 'Due', 'Paid'].map(h => (
                    <th key={h} className="px-5 py-3 text-left text-[11px] font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-[#1a2336]">
                {invoices.map(inv => (
                  <tr key={inv.id} className="hover:bg-slate-50/60 dark:hover:bg-[#162030]/50 transition-colors">
                    <td className="px-5 py-3 font-mono text-xs text-slate-700 dark:text-slate-300 font-semibold">{inv.invoice_number || inv.id?.slice(0,8)}</td>
                    <td className="px-5 py-3">
                      <span className={`px-2.5 py-0.5 rounded-full text-[11px] font-semibold ${INV_CLS[inv.status] || 'bg-slate-500/10 text-slate-500'}`}>
                        {inv.status}
                      </span>
                    </td>
                    <td className="px-5 py-3 text-xs font-mono text-slate-500 dark:text-slate-400">${Number(inv.subtotal_usd || 0).toFixed(2)}</td>
                    <td className="px-5 py-3 text-sm font-bold text-slate-900 dark:text-white font-mono">${Number(inv.total_usd || 0).toFixed(2)}</td>
                    <td className="px-5 py-3 text-xs text-slate-400 dark:text-slate-500">{inv.due_date ? new Date(inv.due_date).toLocaleDateString() : '—'}</td>
                    <td className="px-5 py-3 text-xs text-slate-400 dark:text-slate-500">{inv.paid_at ? new Date(inv.paid_at).toLocaleDateString() : '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}

// ── Connections tab ───────────────────────────────────────────────────────────
function ConnectionsTab({ orgId, api }) {
  const [connections, setConnections] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.get(`/connections?organization_id=${orgId}`)
      .then(d => setConnections(Array.isArray(d) ? d : []))
      .catch(() => setConnections([]))
      .finally(() => setLoading(false))
  }, [orgId, api])

  const STATUS_META = {
    connected:     { cls: 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20', dot: 'bg-emerald-500' },
    not_connected: { cls: 'bg-slate-500/10 text-slate-500 dark:text-slate-400 border border-slate-500/20',     dot: 'bg-slate-400'   },
    error:         { cls: 'bg-rose-500/10 text-rose-600 dark:text-rose-400 border border-rose-500/20',         dot: 'bg-rose-500'     },
  }

  if (loading) return <div className="py-12 text-center text-slate-400 text-sm">Loading connections…</div>

  return (
    <div className="flex flex-col gap-4">
      <p className="text-sm text-slate-500 dark:text-slate-400 font-medium">{connections.length} tool integration{connections.length !== 1 ? 's' : ''}</p>
      {connections.length === 0 ? (
        <EmptyState icon={Plug} title="No tool connections"
          description="This organization has not connected any external tools yet." />
      ) : (
        <div className="flex flex-col gap-2.5">
          {connections.map(conn => {
            const meta = STATUS_META[conn.status] || STATUS_META.not_connected
            return (
              <div key={conn.id} className="flex items-center justify-between px-5 py-3.5 bg-white dark:bg-[#121826] border border-slate-200 dark:border-[#233048] rounded-2xl shadow-2xs">
                <div className="flex items-center gap-3">
                  <div className={`w-2.5 h-2.5 rounded-full ${meta.dot}`} />
                  <div>
                    <p className="text-sm font-semibold text-slate-900 dark:text-white">{conn.display_name || conn.tool_name}</p>
                    <p className="text-xs text-slate-400 dark:text-slate-500 font-mono">{conn.tool_name}</p>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  {conn.last_tested_at && (
                    <span className="text-xs text-slate-400 dark:text-slate-500">
                      Last tested {timeAgo(conn.last_tested_at)}
                    </span>
                  )}
                  <span className={`px-2.5 py-0.5 rounded-full text-[11px] font-semibold ${meta.cls}`}>
                    {conn.status?.replace(/_/g, ' ')}
                  </span>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

// ── Main component ────────────────────────────────────────────────────────────
const TABS = [
  { value: 'overview',     label: 'Overview',     icon: Building2   },
  { value: 'users',        label: 'Users',        icon: Users       },
  { value: 'workflows',    label: 'Workflows',    icon: Workflow    },
  { value: 'usage',        label: 'Usage',        icon: BarChart3   },
  { value: 'billing',      label: 'Billing',      icon: CreditCard  },
  { value: 'connections',  label: 'Connections',  icon: Plug        },
  { value: 'activity',     label: 'Activity',     icon: Activity    },
]

export default function AdminOrgDetail() {
  const { orgId }  = useParams()
  const { api }    = useAuth()
  const navigate   = useNavigate()

  const [detail, setDetail]   = useState(null)
  const [catalog, setCatalog] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState(null)
  const [tab, setTab]         = useState('overview')
  const [toggling, setToggling] = useState(false)

  const load = useCallback(async () => {
    setLoading(true); setError(null)
    try {
      const [d, c] = await Promise.all([
        api.get(`/admin/organizations/${orgId}`),
        api.get('/admin/workflows/catalog').catch(() => []),
      ])
      setDetail(d)
      setCatalog(Array.isArray(c) ? c : [])
    } catch (e) {
      setError(e?.response?.data?.detail || e.message || 'Failed to load organization')
    } finally {
      setLoading(false)
    }
  }, [api, orgId])

  useEffect(() => { load() }, [load])

  async function toggleActive() {
    if (!detail) return
    setToggling(true)
    try {
      const ep = detail.active
        ? `/admin/organizations/${orgId}/suspend`
        : `/admin/organizations/${orgId}/activate`
      await api.post(ep, {})
      load()
    } finally { setToggling(false) }
  }

  if (loading && !detail) {
    return (
      <div className="flex items-center justify-center h-64 text-slate-400 text-sm">
        Loading organization details…
      </div>
    )
  }

  if (error) {
    return (
      <div className="p-6">
        <div className="flex items-center gap-2 px-4 py-3 bg-red-500/10 border border-red-500/20 rounded-2xl text-sm text-red-600 dark:text-red-400">
          <XCircle size={15} /> {error}
        </div>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-6 p-6 min-h-full bg-slate-50 dark:bg-[#0b0f17] text-slate-900 dark:text-slate-100 transition-colors">
      {/* Back + header */}
      <div className="flex items-start gap-4 flex-wrap">
        <button
          onClick={() => navigate('/admin/organizations')}
          className="p-2 rounded-xl text-slate-500 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white bg-white dark:bg-[#121826] border border-slate-200 dark:border-[#233048] hover:bg-slate-50 dark:hover:bg-[#162030] transition-colors mt-0.5"
        >
          <ArrowLeft size={16} />
        </button>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-3 flex-wrap">
            <h1 className="text-xl font-bold text-slate-900 dark:text-white">{detail?.name}</h1>
            <StatusBadge active={detail?.active} />
            {detail?.plan && (
              <span className="text-xs font-semibold text-blue-600 dark:text-blue-400 bg-blue-500/10 border border-blue-500/20 px-2.5 py-0.5 rounded-full">
                {detail.plan.name}
              </span>
            )}
          </div>
          <p className="text-sm text-slate-500 dark:text-slate-400 mt-0.5 capitalize">
            {detail?.industry} · {detail?.user_count ?? 0} users · Created {detail?.created_at ? new Date(detail.created_at).toLocaleDateString() : '—'}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={load} disabled={loading}
            className="p-2 rounded-xl text-slate-500 dark:text-slate-400 bg-white dark:bg-[#121826] border border-slate-200 dark:border-[#233048] hover:bg-slate-50 dark:hover:bg-[#162030] transition-colors disabled:opacity-50">
            <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
          </button>
          <Button
            variant={detail?.active ? 'danger' : 'success'}
            size="sm"
            loading={toggling}
            icon={detail?.active ? <PowerOff size={13} /> : <Power size={13} />}
            onClick={toggleActive}
          >
            {detail?.active ? 'Suspend Org' : 'Activate Org'}
          </Button>
        </div>
      </div>

      {/* Tabs */}
      <TabGroup tabs={TABS} value={tab} onChange={setTab} />

      {/* Tab content */}
      <div className="bg-white dark:bg-[#121826] border border-slate-200 dark:border-[#233048] rounded-2xl p-6 shadow-2xs">
        {tab === 'overview'     && <OverviewTab detail={detail} />}
        {tab === 'users'        && <UsersTab users={detail?.users || []} orgId={orgId} api={api} onRefresh={load} />}
        {tab === 'workflows'    && <WorkflowsTab assignments={detail?.workflow_assignments || []} catalog={catalog} orgId={orgId} api={api} onRefresh={load} />}
        {tab === 'usage'        && <UsageTab orgId={orgId} api={api} />}
        {tab === 'billing'      && <BillingTab orgId={orgId} api={api} />}
        {tab === 'connections'  && <ConnectionsTab orgId={orgId} api={api} />}
        {tab === 'activity'     && <ActivityTab orgId={orgId} api={api} />}
      </div>
    </div>
  )
}
