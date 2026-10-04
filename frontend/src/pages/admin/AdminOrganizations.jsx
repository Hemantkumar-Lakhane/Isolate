// frontend/src/pages/admin/AdminOrganizations.jsx
// Platform customer workspace management with full dark theme support
import { useState, useEffect, useCallback, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Building2, Search, Plus, RefreshCw, Users, Workflow,
  CheckCircle2, XCircle, ChevronRight, Clock,
  Power, PowerOff, AlertTriangle, LayoutGrid, List, Zap,
  DollarSign, Activity, ArrowUpRight
} from 'lucide-react'
import { useAuth } from '../../contexts/AuthContext'
import { Modal, Button, Input, Select, EmptyState } from '../../components/ui'

// ── helpers ───────────────────────────────────────────────────────────────────
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

function trialDaysLeft(trial_ends_at) {
  if (!trial_ends_at) return null
  const diff = new Date(trial_ends_at).getTime() - Date.now()
  return Math.max(0, Math.ceil(diff / 86400000))
}

function planBadge(slug) {
  const map = {
    free:       'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 border border-slate-200 dark:border-slate-700',
    starter:    'bg-blue-50 dark:bg-blue-950/60 text-blue-700 dark:text-blue-400 border border-blue-200 dark:border-blue-800',
    growth:     'bg-purple-50 dark:bg-purple-950/60 text-purple-700 dark:text-purple-400 border border-purple-200 dark:border-purple-800',
    enterprise: 'bg-amber-50 dark:bg-amber-950/60 text-amber-700 dark:text-amber-400 border border-amber-200 dark:border-amber-800',
  }
  return map[slug] || 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400'
}

function statusBadge(active) {
  return active
    ? 'bg-emerald-50 dark:bg-emerald-950/60 text-emerald-600 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-800'
    : 'bg-red-50 dark:bg-red-950/60 text-red-600 dark:text-red-400 border border-red-200 dark:border-red-800'
}

const INDUSTRY_OPTIONS = [
  { value: 'saas',        label: 'SaaS' },
  { value: 'healthcare',  label: 'Healthcare' },
  { value: 'finance',     label: 'Finance' },
  { value: 'retail',      label: 'Retail' },
  { value: 'real_estate', label: 'Real Estate' },
  { value: 'marketing',   label: 'Marketing Agency' },
  { value: 'general',     label: 'General' },
]

// ── Trial badge ───────────────────────────────────────────────────────────────
function TrialBadge({ sub_status, trial_ends_at }) {
  const effective = sub_status
  if (effective === 'trial_expired') {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold bg-red-50 dark:bg-red-950/60 text-red-600 dark:text-red-400 border border-red-200 dark:border-red-800">
        <AlertTriangle size={9} /> Trial expired
      </span>
    )
  }
  if (effective === 'trialing' && trial_ends_at) {
    const days = trialDaysLeft(trial_ends_at)
    const urgent = days <= 3
    return (
      <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold ${
        urgent
          ? 'bg-amber-50 dark:bg-amber-950/60 text-amber-700 dark:text-amber-400 border border-amber-200 dark:border-amber-800'
          : 'bg-blue-50 dark:bg-blue-950/60 text-blue-700 dark:text-blue-400 border border-blue-200 dark:border-blue-800'
      }`}>
        <Clock size={9} /> {days}d trial
      </span>
    )
  }
  return null
}

// ── Create Org modal ──────────────────────────────────────────────────────────
function CreateOrgModal({ open, onClose, api, plans, catalog, onDone }) {
  const [form, setForm] = useState({
    name: '', industry: 'saas', plan_slug: 'free',
    billing_cycle: 'monthly', with_trial: false, trial_days: 14,
    owner_email: '', owner_name: '',
    workflow_keys: [],
  })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (open) {
      setForm({ name: '', industry: 'saas', plan_slug: 'free', billing_cycle: 'monthly', with_trial: false, trial_days: 14, owner_email: '', owner_name: '', workflow_keys: [] })
      setError('')
    }
  }, [open])

  function set(field, val) { setForm(f => ({ ...f, [field]: val })) }

  function toggleWorkflow(key) {
    setForm(f => ({
      ...f,
      workflow_keys: f.workflow_keys.includes(key)
        ? f.workflow_keys.filter(k => k !== key)
        : [...f.workflow_keys, key],
    }))
  }

  async function submit(e) {
    e.preventDefault()
    if (!form.name.trim()) { setError('Organization name is required.'); return }
    setLoading(true); setError('')
    try {
      await api.post('/admin/organizations', {
        name:          form.name.trim(),
        industry:      form.industry,
        plan_slug:     form.plan_slug,
        billing_cycle: form.billing_cycle,
        with_trial:    form.with_trial,
        trial_days:    form.with_trial ? (form.trial_days || 14) : undefined,
        owner_email:   form.owner_email || undefined,
        owner_name:    form.owner_name  || undefined,
        workflow_keys: form.workflow_keys,
      })
      onDone()
      onClose()
    } catch (e) {
      setError(e?.response?.data?.detail || e.message || 'Failed to create organization')
    } finally {
      setLoading(false)
    }
  }

  const entitledWorkflows = useMemo(() => {
    const plan = plans.find(p => p.slug === form.plan_slug)
    if (!plan || !plan.entitlements?.length) return catalog.slice(0, 20)
    return catalog.filter(w => plan.entitlements.includes(w.id))
  }, [plans, catalog, form.plan_slug])

  return (
    <Modal open={open} onClose={onClose} title="Create Organization" subtitle="Set up a new client workspace" width="max-w-xl">
      <form onSubmit={submit} className="flex flex-col gap-4">
        {error && (
          <div className="flex items-center gap-2 px-3 py-2.5 bg-red-50 dark:bg-red-950/60 border border-red-200 dark:border-red-800 rounded-lg text-xs text-red-700 dark:text-red-300">
            <XCircle size={14} className="shrink-0" /> {error}
          </div>
        )}

        <div className="grid grid-cols-2 gap-3">
          <Input
            label="Organization Name"
            value={form.name}
            onChange={e => set('name', e.target.value)}
            placeholder="e.g. Acme Health Corp"
            required
          />
          <Select
            label="Primary Industry"
            value={form.industry}
            onChange={e => set('industry', e.target.value)}
            options={INDUSTRY_OPTIONS}
          />
        </div>

        <div className="grid grid-cols-2 gap-3">
          <Select
            label="Subscription Plan"
            value={form.plan_slug}
            onChange={e => set('plan_slug', e.target.value)}
            options={plans.map(p => ({ value: p.slug, label: `${p.name} ($${p.price_monthly_usd}/mo)` }))}
          />
          <Select
            label="Billing Cycle"
            value={form.billing_cycle}
            onChange={e => set('billing_cycle', e.target.value)}
            options={[
              { value: 'monthly', label: 'Monthly' },
              { value: 'annual',  label: 'Annual (Discounted)' },
            ]}
          />
        </div>

        <div className="p-3 bg-slate-50 dark:bg-[#162030] border border-slate-200 dark:border-[#233048] rounded-xl flex items-center justify-between">
          <div>
            <p className="text-xs font-bold text-slate-900 dark:text-white">Enable Free Trial</p>
            <p className="text-[11px] text-slate-400">Give initial trial days without immediate charge</p>
          </div>
          <input
            type="checkbox"
            checked={form.with_trial}
            onChange={e => set('with_trial', e.target.checked)}
            className="w-4 h-4 rounded text-blue-600 focus:ring-0 cursor-pointer"
          />
        </div>

        <div className="grid grid-cols-2 gap-3">
          <Input
            label="Primary Admin Email"
            type="email"
            value={form.owner_email}
            onChange={e => set('owner_email', e.target.value)}
            placeholder="owner@acme.com"
          />
          <Input
            label="Admin Full Name"
            value={form.owner_name}
            onChange={e => set('owner_name', e.target.value)}
            placeholder="Jane Doe"
          />
        </div>

        <div>
          <p className="text-xs font-bold text-slate-700 dark:text-slate-300 mb-2">Entitled Workflows to Auto-Assign</p>
          <div className="flex flex-wrap gap-1.5 max-h-32 overflow-y-auto">
            {entitledWorkflows.map(w => {
              const on = form.workflow_keys.includes(w.key)
              return (
                <button
                  key={w.key}
                  type="button"
                  onClick={() => toggleWorkflow(w.key)}
                  className={`px-2.5 py-1 rounded-lg text-[11px] border transition-all cursor-pointer ${
                    on
                      ? 'bg-blue-50 dark:bg-blue-950/60 border-blue-300 dark:border-blue-700 text-blue-700 dark:text-blue-300 font-bold'
                      : 'bg-slate-50 dark:bg-[#162030] border-slate-200 dark:border-[#233048] text-slate-600 dark:text-slate-400'
                  }`}
                >
                  {w.display_name || w.name}
                </button>
              )
            })}
          </div>
        </div>

        <div className="flex justify-end gap-2 pt-2 border-t border-slate-100 dark:border-[#233048]">
          <Button variant="secondary" size="sm" type="button" onClick={onClose}>Cancel</Button>
          <Button variant="primary" size="sm" loading={loading} type="submit">Create Workspace</Button>
        </div>
      </form>
    </Modal>
  )
}

// ── Org Row Actions ───────────────────────────────────────────────────────────
function OrgActions({ org, api, onDone }) {
  const [loading, setLoading] = useState(false)

  async function toggleSuspend() {
    setLoading(true)
    try {
      const ep = org.active
        ? `/admin/organizations/${org.id}/suspend`
        : `/admin/organizations/${org.id}/reactivate`
      await api.patch(ep, {})
      onDone()
    } finally {
      setLoading(false)
    }
  }

  return (
    <button
      onClick={toggleSuspend}
      disabled={loading}
      className={`p-1.5 rounded-lg transition-colors cursor-pointer ${
        org.active
          ? 'text-slate-400 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-950/40'
          : 'text-emerald-600 hover:bg-emerald-50 dark:hover:bg-emerald-950/40'
      }`}
      title={org.active ? 'Suspend Organization' : 'Reactivate Organization'}
    >
      {org.active ? <PowerOff size={14} /> : <Power size={14} />}
    </button>
  )
}

// ── Main component ─────────────────────────────────────────────────────────────
export default function AdminOrganizations() {
  const { api } = useAuth()
  const navigate = useNavigate()

  const [orgs, setOrgs]         = useState([])
  const [plans, setPlans]       = useState([])
  const [catalog, setCatalog]   = useState([])
  const [loading, setLoading]   = useState(true)
  const [error, setError]       = useState(null)
  const [search, setSearch]     = useState('')
  const [filterStatus, setFilterStatus] = useState('all')
  const [filterPlan, setFilterPlan]     = useState('all')
  const [filterTrial, setFilterTrial]   = useState('all')
  const [viewMode, setViewMode]         = useState('cards')
  const [showCreate, setShowCreate]     = useState(false)

  const load = useCallback(async () => {
    setLoading(true); setError(null)
    try {
      const [o, p, c] = await Promise.all([
        api.get('/admin/organizations'),
        api.get('/admin/plans').catch(() => []),
        api.get('/admin/workflows/catalog').catch(() => []),
      ])
      setOrgs(Array.isArray(o) ? o : [])
      setPlans(Array.isArray(p) ? p : [])
      setCatalog(Array.isArray(c) ? c : [])
    } catch (e) {
      setError(e?.response?.data?.detail || e.message || 'Failed to load organizations')
    } finally {
      setLoading(false)
    }
  }, [api])

  useEffect(() => { load() }, [load])

  const filtered = useMemo(() => {
    let list = orgs
    if (search) {
      const q = search.toLowerCase()
      list = list.filter(o =>
        o.name?.toLowerCase().includes(q) ||
        o.industry?.toLowerCase().includes(q)
      )
    }
    if (filterStatus !== 'all') {
      list = list.filter(o => filterStatus === 'active' ? o.active : !o.active)
    }
    if (filterPlan !== 'all') {
      list = list.filter(o => o.plan_slug === filterPlan)
    }
    if (filterTrial !== 'all') {
      if (filterTrial === 'trialing') {
        list = list.filter(o => o.subscription_status === 'trialing')
      } else if (filterTrial === 'trial_expired') {
        list = list.filter(o => o.effective_subscription_status === 'trial_expired')
      }
    }
    return list
  }, [orgs, search, filterStatus, filterPlan, filterTrial])

  const trialingCount = orgs.filter(o => o.subscription_status === 'trialing').length
  const expiredCount  = orgs.filter(o => o.effective_subscription_status === 'trial_expired').length

  return (
    <div className="flex flex-col gap-6 p-6 min-h-full bg-slate-50 dark:bg-[#0b0f17] text-slate-900 dark:text-slate-100 font-sans transition-colors">
      
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-white tracking-tight">Organization Workspaces</h1>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
            {loading ? '…' : `${orgs.length} client organization${orgs.length !== 1 ? 's' : ''} on platform`}
            {trialingCount > 0 && (
              <span className="ml-2 text-blue-500 font-bold">· {trialingCount} trialing</span>
            )}
            {expiredCount > 0 && (
              <span className="ml-2 text-red-400 font-bold">· {expiredCount} trial expired</span>
            )}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {/* View Toggle */}
          <div className="flex items-center bg-white dark:bg-[#121826] border border-slate-200 dark:border-[#233048] rounded-xl p-0.5 shadow-2xs">
            <button
              onClick={() => setViewMode('cards')}
              className={`flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs font-semibold transition-all cursor-pointer ${
                viewMode === 'cards'
                  ? 'bg-blue-600 text-white shadow-xs'
                  : 'text-slate-500 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white'
              }`}
              title="Cards View"
            >
              <LayoutGrid size={13} />
              <span>Cards</span>
            </button>
            <button
              onClick={() => setViewMode('table')}
              className={`flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs font-semibold transition-all cursor-pointer ${
                viewMode === 'table'
                  ? 'bg-blue-600 text-white shadow-xs'
                  : 'text-slate-500 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white'
              }`}
              title="Table View"
            >
              <List size={13} />
              <span>Table</span>
            </button>
          </div>

          <button
            onClick={load}
            disabled={loading}
            className="p-2 rounded-xl text-slate-600 dark:text-slate-300 bg-white dark:bg-[#121826] border border-slate-200 dark:border-[#233048] hover:bg-slate-50 dark:hover:bg-[#182234] transition-colors shadow-2xs cursor-pointer disabled:opacity-50"
            title="Refresh"
          >
            <RefreshCw size={15} className={loading ? 'animate-spin text-blue-500' : ''} />
          </button>
          <Button variant="primary" size="sm" icon={<Plus size={14} />} onClick={() => setShowCreate(true)}>
            Create Organization
          </Button>
        </div>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-3 flex-wrap">
        <div className="relative flex-1 min-w-[220px]">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" />
          <input
            type="text"
            placeholder="Search organizations by name or industry…"
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="w-full pl-9 pr-3 py-2 text-xs bg-white dark:bg-[#162030] border border-slate-200 dark:border-[#2a3850] rounded-xl text-slate-900 dark:text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 transition-all"
          />
        </div>
        <select
          value={filterStatus}
          onChange={e => setFilterStatus(e.target.value)}
          className="px-3 py-2 text-xs bg-white dark:bg-[#162030] border border-slate-200 dark:border-[#2a3850] rounded-xl text-slate-900 dark:text-white focus:outline-none focus:border-blue-500 cursor-pointer"
        >
          <option value="all">All statuses</option>
          <option value="active">Active</option>
          <option value="suspended">Suspended</option>
        </select>
        <select
          value={filterPlan}
          onChange={e => setFilterPlan(e.target.value)}
          className="px-3 py-2 text-xs bg-white dark:bg-[#162030] border border-slate-200 dark:border-[#2a3850] rounded-xl text-slate-900 dark:text-white focus:outline-none focus:border-blue-500 cursor-pointer"
        >
          <option value="all">All plans</option>
          {plans.map(p => <option key={p.slug} value={p.slug}>{p.name}</option>)}
        </select>
        <select
          value={filterTrial}
          onChange={e => setFilterTrial(e.target.value)}
          className="px-3 py-2 text-xs bg-white dark:bg-[#162030] border border-slate-200 dark:border-[#2a3850] rounded-xl text-slate-900 dark:text-white focus:outline-none focus:border-blue-500 cursor-pointer"
        >
          <option value="all">All lifecycle</option>
          <option value="trialing">Trialing</option>
          <option value="trial_expired">Trial Expired</option>
        </select>
      </div>

      {error && (
        <div className="flex items-center gap-2 px-4 py-3 bg-red-50 dark:bg-red-950/60 border border-red-200 dark:border-red-800 rounded-xl text-xs text-red-700 dark:text-red-300">
          <XCircle size={15} className="shrink-0" /> {error}
        </div>
      )}

      {/* Main Content Area */}
      {loading ? (
        <div className="flex items-center justify-center h-48 text-slate-400 text-xs">Loading organizations…</div>
      ) : filtered.length === 0 ? (
        <EmptyState
          icon={Building2}
          title="No organizations found"
          description={search ? 'Try adjusting your search criteria.' : 'Create your first organization to get started.'}
          action={
            !search && (
              <Button size="sm" icon={<Plus size={13} />} onClick={() => setShowCreate(true)}>
                Create Organization
              </Button>
            )
          }
        />
      ) : viewMode === 'cards' ? (
        /* ── Card Grid View ──────────────────────────────────────────────── */
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-5">
          {filtered.map(org => (
            <div
              key={org.id}
              onClick={() => navigate(`/admin/organizations/${org.id}`)}
              className="bg-white dark:bg-[#121826] border border-slate-200 dark:border-[#233048] rounded-2xl p-5 flex flex-col justify-between gap-4 transition-all shadow-2xs hover:border-blue-500/60 hover:shadow-md cursor-pointer group"
            >
              <div className="space-y-3.5">
                {/* Top Avatar & Badges */}
                <div className="flex items-start justify-between gap-3">
                  <div className="flex items-center gap-3 min-w-0">
                    <div className="w-10 h-10 rounded-xl bg-blue-50 dark:bg-blue-950/80 border border-blue-200 dark:border-blue-800 flex items-center justify-center shrink-0 shadow-2xs">
                      <span className="text-blue-600 dark:text-blue-400 font-bold text-sm">
                        {(org.name || '?')[0].toUpperCase()}
                      </span>
                    </div>
                    <div className="min-w-0">
                      <h3 className="font-bold text-sm text-slate-900 dark:text-white truncate group-hover:text-blue-500 transition-colors">
                        {org.name}
                      </h3>
                      <p className="text-[11px] text-slate-400 capitalize">{org.industry || 'General'}</p>
                    </div>
                  </div>

                  <span className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-bold shrink-0 ${statusBadge(org.active)}`}>
                    {org.active ? <CheckCircle2 size={10} /> : <XCircle size={10} />}
                    <span>{org.active ? 'Active' : 'Suspended'}</span>
                  </span>
                </div>

                {/* Plan & Trial Pill */}
                <div className="flex items-center gap-2 flex-wrap pt-1">
                  <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold uppercase ${planBadge(org.plan_slug)}`}>
                    {org.plan_name || org.plan_slug || 'Free'}
                  </span>
                  <TrialBadge
                    sub_status={org.effective_subscription_status || org.subscription_status}
                    trial_ends_at={org.trial_ends_at}
                  />
                </div>

                {/* Metrics 4-grid */}
                <div className="grid grid-cols-2 gap-2.5 pt-1">
                  <div className="bg-slate-50 dark:bg-[#182234] border border-slate-100 dark:border-[#1e2a3f] rounded-xl p-2.5">
                    <span className="text-[10px] text-slate-400 uppercase font-semibold flex items-center gap-1">
                      <Users size={11} className="text-blue-500" /> Users
                    </span>
                    <span className="text-sm font-bold text-slate-900 dark:text-white block mt-0.5">
                      {org.user_count ?? 0}
                    </span>
                  </div>

                  <div className="bg-slate-50 dark:bg-[#182234] border border-slate-100 dark:border-[#1e2a3f] rounded-xl p-2.5">
                    <span className="text-[10px] text-slate-400 uppercase font-semibold flex items-center gap-1">
                      <Workflow size={11} className="text-indigo-500" /> Pipelines
                    </span>
                    <span className="text-sm font-bold text-slate-900 dark:text-white block mt-0.5">
                      {org.assigned_workflows ?? 0}
                    </span>
                  </div>

                  <div className="bg-slate-50 dark:bg-[#182234] border border-slate-100 dark:border-[#1e2a3f] rounded-xl p-2.5">
                    <span className="text-[10px] text-slate-400 uppercase font-semibold flex items-center gap-1">
                      <Zap size={11} className="text-amber-500" /> Total Runs
                    </span>
                    <span className="text-sm font-mono font-bold text-slate-900 dark:text-white block mt-0.5">
                      {org.run_count ?? 0}
                    </span>
                  </div>

                  <div className="bg-slate-50 dark:bg-[#182234] border border-slate-100 dark:border-[#1e2a3f] rounded-xl p-2.5">
                    <span className="text-[10px] text-slate-400 uppercase font-semibold flex items-center gap-1">
                      <DollarSign size={11} className="text-emerald-500" /> Spend
                    </span>
                    <span className="text-sm font-mono font-bold text-emerald-600 dark:text-emerald-400 block mt-0.5">
                      {org.total_spend_usd !== null && org.total_spend_usd !== undefined
                        ? `$${Number(org.total_spend_usd).toFixed(2)}`
                        : '$0.00'}
                    </span>
                  </div>
                </div>
              </div>

              {/* Bottom Card Footer */}
              <div className="flex items-center justify-between border-t border-slate-100 dark:border-[#1e2a3f] pt-3 text-xs text-slate-400">
                <span className="text-[11px]">
                  Active: {timeAgo(org.last_activity)}
                </span>
                <div className="flex items-center gap-1" onClick={e => e.stopPropagation()}>
                  <OrgActions org={org} api={api} onDone={load} />
                  <button
                    type="button"
                    onClick={() => navigate(`/admin/organizations/${org.id}`)}
                    className="flex items-center gap-1 px-2.5 py-1 text-xs font-semibold text-blue-600 dark:text-blue-400 hover:bg-blue-50 dark:hover:bg-blue-950/60 rounded-lg transition-colors cursor-pointer"
                  >
                    <span>View Detail</span>
                    <ArrowUpRight size={12} />
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      ) : (
        /* ── Table View ──────────────────────────────────────────────────── */
        <div className="bg-white dark:bg-[#121826] border border-slate-200 dark:border-[#233048] rounded-2xl overflow-hidden shadow-2xs">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-slate-100 dark:border-[#1e2a3f] bg-slate-50/70 dark:bg-[#162030]/60">
                  {['Organization', 'Status', 'Plan / Trial', 'Users', 'Workflows', 'Runs', 'Spend', 'Last Activity', 'Actions'].map(h => (
                    <th key={h} className="px-4 py-3 text-[11px] font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider whitespace-nowrap">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-[#1a2336]">
                {filtered.map(org => (
                  <tr
                    key={org.id}
                    className="hover:bg-slate-50 dark:hover:bg-[#162030]/50 cursor-pointer transition-colors"
                    onClick={() => navigate(`/admin/organizations/${org.id}`)}
                  >
                    <td className="px-4 py-3.5">
                      <div className="flex items-center gap-2.5">
                        <div className="w-8 h-8 rounded-xl bg-blue-50 dark:bg-blue-950/80 border border-blue-200 dark:border-blue-800 flex items-center justify-center shrink-0">
                          <span className="text-blue-700 dark:text-blue-400 text-xs font-bold">
                            {(org.name || '?')[0].toUpperCase()}
                          </span>
                        </div>
                        <div className="min-w-0">
                          <p className="font-bold text-slate-900 dark:text-white truncate">{org.name}</p>
                          <p className="text-[11px] text-slate-400 capitalize">{org.industry}</p>
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-3.5">
                      <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-bold ${statusBadge(org.active)}`}>
                        {org.active
                          ? <><CheckCircle2 size={10} />Active</>
                          : <><XCircle size={10} />Suspended</>}
                      </span>
                    </td>
                    <td className="px-4 py-3.5">
                      <div className="flex flex-col gap-1">
                        <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold uppercase w-fit ${planBadge(org.plan_slug)}`}>
                          {org.plan_name || org.plan_slug || '—'}
                        </span>
                        <TrialBadge
                          sub_status={org.effective_subscription_status || org.subscription_status}
                          trial_ends_at={org.trial_ends_at}
                        />
                      </div>
                    </td>
                    <td className="px-4 py-3.5">
                      <div className="flex items-center gap-1.5 text-slate-600 dark:text-slate-300 font-medium">
                        <Users size={12} className="text-slate-400" />
                        {org.user_count ?? 0}
                      </div>
                    </td>
                    <td className="px-4 py-3.5">
                      <div className="flex items-center gap-1.5 text-slate-600 dark:text-slate-300 font-medium">
                        <Workflow size={12} className="text-slate-400" />
                        {org.assigned_workflows ?? 0}
                      </div>
                    </td>
                    <td className="px-4 py-3.5 text-slate-700 dark:text-slate-300 font-mono font-medium">{org.run_count ?? 0}</td>
                    <td className="px-4 py-3.5 text-emerald-600 dark:text-emerald-400 font-bold font-mono">
                      {org.total_spend_usd !== null && org.total_spend_usd !== undefined
                        ? `$${Number(org.total_spend_usd).toFixed(2)}`
                        : <span className="text-slate-400 italic text-xs">—</span>}
                    </td>
                    <td className="px-4 py-3.5 text-slate-400 text-[11px] whitespace-nowrap">
                      {timeAgo(org.last_activity)}
                    </td>
                    <td className="px-4 py-3.5">
                      <div className="flex items-center gap-1" onClick={e => e.stopPropagation()}>
                        <OrgActions org={org} api={api} onDone={load} />
                        <button
                          type="button"
                          onClick={e => { e.stopPropagation(); navigate(`/admin/organizations/${org.id}`) }}
                          className="p-1.5 rounded-lg text-slate-400 hover:text-blue-600 dark:hover:text-blue-400 hover:bg-slate-100 dark:hover:bg-[#1f2c42] transition-colors cursor-pointer"
                        >
                          <ChevronRight size={14} />
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

      <CreateOrgModal
        open={showCreate}
        onClose={() => setShowCreate(false)}
        api={api}
        plans={plans}
        catalog={catalog}
        onDone={load}
      />
    </div>
  )
}
