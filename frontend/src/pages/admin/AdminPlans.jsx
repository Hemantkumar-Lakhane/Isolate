// AdminPlans — Plans & Pricing
import { useState, useEffect, useCallback, useMemo } from 'react'
import {
  CreditCard, Plus, RefreshCw, Edit2, CheckCircle2, XCircle,
  ChevronDown, ChevronUp, Tag,
} from 'lucide-react'
import { useAuth } from '../../contexts/AuthContext'
import { Modal, Button, Input, Select, EmptyState } from '../../components/ui'

const STATUS_COLORS = {
  active:   'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20',
  archived: 'bg-slate-500/10 text-slate-500 dark:text-slate-400 border border-slate-500/20',
  hidden:   'bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20',
}

// ── Plan form modal ───────────────────────────────────────────────────────────
function PlanModal({ open, onClose, api, existing, catalog, onDone }) {
  const isEdit = !!existing
  const blank = {
    name: '', slug: '', description: '',
    monthly_price_usd: '0', annual_price_usd: '0',
    included_workflow_runs: '0', included_ai_tokens: '0',
    included_image_gens: '0', included_users: '1',
    max_workflow_runs: '0', max_users: '0',
    overage_run_price_usd: '0', overage_token_price_usd: '0',
    overage_image_price_usd: '0',
    status: 'active', is_public: true,
  }
  const [form, setForm]       = useState(blank)
  const [entitlements, setEnt] = useState([])   // workflow ids
  const [loading, setLoading]  = useState(false)
  const [error, setError]      = useState('')

  useEffect(() => {
    if (existing) {
      setForm({
        name:                    existing.name              || '',
        slug:                    existing.slug              || '',
        description:             existing.description       || '',
        monthly_price_usd:       String(existing.monthly_price_usd  ?? 0),
        annual_price_usd:        String(existing.annual_price_usd   ?? 0),
        included_workflow_runs:  String(existing.included_workflow_runs  ?? 0),
        included_ai_tokens:      String(existing.included_ai_tokens      ?? 0),
        included_image_gens:     String(existing.included_image_gens     ?? 0),
        included_users:          String(existing.included_users           ?? 1),
        max_workflow_runs:       String(existing.max_workflow_runs        ?? 0),
        max_users:               String(existing.max_users               ?? 0),
        overage_run_price_usd:   String(existing.overage_run_price_usd   ?? 0),
        overage_token_price_usd: String(existing.overage_token_price_usd ?? 0),
        overage_image_price_usd: String(existing.overage_image_price_usd ?? 0),
        status:                  existing.status    || 'active',
        is_public:               existing.is_public ?? true,
      })
      setEnt(existing.entitlements || [])
    } else {
      setForm(blank)
      setEnt([])
    }
    setError('')
  }, [existing, open])

  function set(f, v) { setForm(s => ({ ...s, [f]: v })) }

  function toggleEnt(id) {
    setEnt(prev => prev.includes(id) ? prev.filter(e => e !== id) : [...prev, id])
  }

  async function submit(e) {
    e.preventDefault()
    if (!form.name.trim() || !form.slug.trim()) { setError('Name and slug are required'); return }
    setLoading(true); setError('')
    try {
      const num = v => parseFloat(v) || 0
      const int = v => parseInt(v)  || 0
      const payload = {
        name:                    form.name.trim(),
        slug:                    form.slug.trim().toLowerCase().replace(/\s+/g, '-'),
        description:             form.description.trim() || undefined,
        monthly_price_usd:       num(form.monthly_price_usd),
        annual_price_usd:        num(form.annual_price_usd),
        included_workflow_runs:  int(form.included_workflow_runs),
        included_ai_tokens:      int(form.included_ai_tokens),
        included_image_gens:     int(form.included_image_gens),
        included_users:          int(form.included_users),
        max_workflow_runs:       int(form.max_workflow_runs),
        max_users:               int(form.max_users),
        overage_run_price_usd:   num(form.overage_run_price_usd),
        overage_token_price_usd: num(form.overage_token_price_usd),
        overage_image_price_usd: num(form.overage_image_price_usd),
        status:                  form.status,
        is_public:               form.is_public,
      }
      let planId
      if (isEdit) {
        await api.patch(`/admin/plans/${existing.id}`, payload)
        planId = existing.id
      } else {
        const created = await api.post('/admin/plans', payload)
        planId = created.id
      }
      // Update entitlements
      await api.put(`/admin/plans/${planId}/entitlements`, { workflow_ids: entitlements })
      onDone(); onClose()
    } catch (err) {
      setError(err?.response?.data?.detail || err.message || 'Save failed')
    } finally { setLoading(false) }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={isEdit ? `Edit Plan: ${existing?.name}` : 'New Billing Plan'}
      subtitle="Configure pricing, limits, and included workflows"
      width="max-w-2xl"
    >
      <form onSubmit={submit} className="flex flex-col gap-5">
        {error && (
          <div className="flex items-center gap-2 px-3 py-2.5 bg-red-500/10 border border-red-500/20 rounded-lg text-sm text-red-600 dark:text-red-400">
            <XCircle size={14} className="shrink-0" />{error}
          </div>
        )}

        {/* Identity */}
        <div>
          <p className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-widest mb-3">Plan Identity</p>
          <div className="grid grid-cols-2 gap-3">
            <Input label="Plan Name" required value={form.name}
              onChange={e => set('name', e.target.value)} placeholder="Starter" />
            <Input label="Slug" required value={form.slug}
              onChange={e => set('slug', e.target.value)} placeholder="starter"
              hint="Lowercase, hyphens. Used in API." />
            <Input label="Description" value={form.description}
              onChange={e => set('description', e.target.value)}
              placeholder="For small teams getting started"
              className="col-span-2" />
            <Select label="Status" value={form.status}
              onChange={e => set('status', e.target.value)}
              options={[
                { value: 'active',   label: 'Active'   },
                { value: 'hidden',   label: 'Hidden'   },
                { value: 'archived', label: 'Archived' },
              ]} />
            <div className="flex items-center gap-2 pt-5">
              <input type="checkbox" id="is_public" checked={form.is_public}
                onChange={e => set('is_public', e.target.checked)}
                className="w-4 h-4 text-blue-600 rounded bg-white dark:bg-[#162030] border-slate-300 dark:border-[#2a3850]" />
              <label htmlFor="is_public" className="text-sm text-slate-700 dark:text-slate-300">Public (visible on pricing page)</label>
            </div>
          </div>
        </div>

        {/* Pricing */}
        <div>
          <p className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-widest mb-3">Pricing (USD)</p>
          <div className="grid grid-cols-2 gap-3">
            <Input label="Monthly Price" type="number" step="0.01" min="0"
              value={form.monthly_price_usd} onChange={e => set('monthly_price_usd', e.target.value)} />
            <Input label="Annual Price" type="number" step="0.01" min="0"
              value={form.annual_price_usd} onChange={e => set('annual_price_usd', e.target.value)} />
          </div>
        </div>

        {/* Included */}
        <div>
          <p className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-widest mb-3">Included Quotas</p>
          <div className="grid grid-cols-2 gap-3">
            <Input label="Workflow Runs" type="number" min="0"
              value={form.included_workflow_runs} onChange={e => set('included_workflow_runs', e.target.value)} />
            <Input label="AI Tokens" type="number" min="0"
              value={form.included_ai_tokens} onChange={e => set('included_ai_tokens', e.target.value)} />
            <Input label="Image Generations" type="number" min="0"
              value={form.included_image_gens} onChange={e => set('included_image_gens', e.target.value)} />
            <Input label="Users" type="number" min="1"
              value={form.included_users} onChange={e => set('included_users', e.target.value)} />
          </div>
        </div>

        {/* Limits */}
        <div>
          <p className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-widest mb-3">Hard Limits <span className="font-normal normal-case">(0 = unlimited)</span></p>
          <div className="grid grid-cols-2 gap-3">
            <Input label="Max Workflow Runs" type="number" min="0"
              value={form.max_workflow_runs} onChange={e => set('max_workflow_runs', e.target.value)} />
            <Input label="Max Users" type="number" min="0"
              value={form.max_users} onChange={e => set('max_users', e.target.value)} />
          </div>
        </div>

        {/* Overages */}
        <div>
          <p className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-widest mb-3">Overage Pricing (USD)</p>
          <div className="grid grid-cols-3 gap-3">
            <Input label="Per Run" type="number" step="0.000001" min="0"
              value={form.overage_run_price_usd} onChange={e => set('overage_run_price_usd', e.target.value)} />
            <Input label="Per 1K Tokens" type="number" step="0.000000001" min="0"
              value={form.overage_token_price_usd} onChange={e => set('overage_token_price_usd', e.target.value)} />
            <Input label="Per Image" type="number" step="0.000001" min="0"
              value={form.overage_image_price_usd} onChange={e => set('overage_image_price_usd', e.target.value)} />
          </div>
        </div>

        {/* Workflow entitlements */}
        {catalog.length > 0 && (
          <div>
            <p className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-widest mb-3">
              Included Workflows <span className="font-normal normal-case text-slate-400 dark:text-slate-500">({entitlements.length} selected)</span>
            </p>
            <div className="grid grid-cols-2 gap-2 max-h-48 overflow-y-auto pr-1">
              {catalog.filter(w => w.active).map(w => (
                <label key={w.id}
                  className={`flex items-start gap-2.5 px-3 py-2.5 rounded-xl border cursor-pointer transition-colors ${
                    entitlements.includes(w.id)
                      ? 'border-blue-500/30 bg-blue-500/10 text-blue-900 dark:text-blue-200'
                      : 'border-slate-200 dark:border-[#233048] bg-white dark:bg-[#121826] hover:bg-slate-50 dark:hover:bg-[#162030]'
                  }`}
                >
                  <input type="checkbox" checked={entitlements.includes(w.id)}
                    onChange={() => toggleEnt(w.id)}
                    className="w-3.5 h-3.5 text-blue-600 rounded mt-0.5 shrink-0" />
                  <div className="min-w-0">
                    <p className="text-xs font-semibold text-slate-800 dark:text-slate-200 leading-tight">{w.name}</p>
                    <p className="text-[11px] text-slate-400 dark:text-slate-500 font-mono">{w.key}</p>
                  </div>
                </label>
              ))}
            </div>
          </div>
        )}

        <div className="flex justify-end gap-2 pt-1 border-t border-slate-100 dark:border-[#1e2a3f]">
          <Button variant="secondary" size="sm" type="button" onClick={onClose}>Cancel</Button>
          <Button variant="primary" size="sm" loading={loading} type="submit">
            {isEdit ? 'Save Changes' : 'Create Plan'}
          </Button>
        </div>
      </form>
    </Modal>
  )
}

// ── Plan card ─────────────────────────────────────────────────────────────────
function PlanCard({ plan, catalog = [], onEdit }) {
  const [expanded, setExpanded] = useState(false)
  const price = plan.monthly_price_usd

  // Map entitlement IDs/slugs to clean display names
  const entitledNames = useMemo(() => {
    if (!plan.entitlements || plan.entitlements.length === 0) return []
    return plan.entitlements.map(id => {
      const match = catalog.find(c => c.id === id || c.key === id || c.name?.toLowerCase() === id?.toLowerCase())
      return {
        id,
        name: match ? match.name : id.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase()),
      }
    })
  }, [plan.entitlements, catalog])

  return (
    <div 
      onClick={() => onEdit(plan)}
      className="bg-white dark:bg-[#121826] border border-slate-200 dark:border-[#233048] hover:border-blue-500/50 hover:shadow-md transition-all duration-200 rounded-2xl overflow-hidden cursor-pointer flex flex-col justify-between group shadow-2xs"
    >
      <div className="p-5 flex-1 flex flex-col justify-between gap-4">
        <div>
          {/* Header */}
          <div className="flex items-start justify-between gap-3 mb-2">
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2 mb-1 flex-wrap">
                <h3 className="text-base font-bold text-slate-900 dark:text-white group-hover:text-blue-500 transition-colors">
                  {plan.name}
                </h3>
                <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full capitalize ${STATUS_COLORS[plan.status] || 'bg-slate-500/10 text-slate-500'}`}>
                  {plan.status}
                </span>
                {!plan.is_public && (
                  <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-slate-500/10 text-slate-400 border border-slate-500/20">
                    Private
                  </span>
                )}
              </div>
              <p className="text-[11px] text-slate-400 dark:text-slate-500 font-mono">{plan.slug}</p>
            </div>
            <div className="text-right shrink-0">
              <p className="text-2xl font-bold text-slate-900 dark:text-white tracking-tight">
                {Number(price) === 0 ? 'Free' : `$${Number(price).toFixed(2)}`}
              </p>
              {Number(price) > 0 && <p className="text-[10px] text-slate-400 dark:text-slate-500 font-medium">/month</p>}
            </div>
          </div>

          {plan.description && (
            <p className="text-xs text-slate-500 dark:text-slate-400 mb-3 leading-relaxed line-clamp-2">
              {plan.description}
            </p>
          )}

          {/* Quotas grid */}
          <div className="grid grid-cols-2 gap-2 my-2.5 p-3 bg-slate-50 dark:bg-[#182234] rounded-xl border border-slate-100 dark:border-[#1e2a3f] text-xs">
            <div>
              <span className="text-[10px] uppercase tracking-wider text-slate-400 dark:text-slate-500 block font-bold">Included Runs</span>
              <span className="font-bold text-slate-900 dark:text-white text-xs mt-0.5 block">
                {plan.included_workflow_runs === 0 ? 'Unlimited' : `${plan.included_workflow_runs.toLocaleString()} runs/mo`}
              </span>
            </div>
            <div>
              <span className="text-[10px] uppercase tracking-wider text-slate-400 dark:text-slate-500 block font-bold">AI Token Budget</span>
              <span className="font-bold text-slate-900 dark:text-white text-xs mt-0.5 block">
                {plan.included_ai_tokens === 0 ? 'Unlimited' : `${(plan.included_ai_tokens / 1_000_000).toFixed(1)}M tokens`}
              </span>
            </div>
            <div>
              <span className="text-[10px] uppercase tracking-wider text-slate-400 dark:text-slate-500 block font-bold">Team Seats</span>
              <span className="font-bold text-slate-900 dark:text-white text-xs mt-0.5 block">
                {plan.included_users === 0 ? 'Unlimited' : `${plan.included_users} member${plan.included_users !== 1 ? 's' : ''}`}
              </span>
            </div>
            <div>
              <span className="text-[10px] uppercase tracking-wider text-slate-400 dark:text-slate-500 block font-bold">Image Gens</span>
              <span className="font-bold text-slate-900 dark:text-white text-xs mt-0.5 block">
                {plan.included_image_gens === 0 ? 'Pay as you go' : `${plan.included_image_gens.toLocaleString()} images`}
              </span>
            </div>
          </div>
        </div>

        {/* Feature Checkmarks */}
        <div className="space-y-1.5 pt-1">
          <div className="flex items-center gap-2 text-xs text-slate-600 dark:text-slate-300">
            <CheckCircle2 size={13} className="text-emerald-500 shrink-0" />
            <span>Autonomous multi-agent orchestration</span>
          </div>
          <div className="flex items-center gap-2 text-xs text-slate-600 dark:text-slate-300">
            <CheckCircle2 size={13} className="text-emerald-500 shrink-0" />
            <span>Real-time execution telemetry & evidence vault</span>
          </div>
          <div className="flex items-center gap-2 text-xs text-slate-600 dark:text-slate-300">
            <CheckCircle2 size={13} className="text-emerald-500 shrink-0" />
            <span>Encrypted connector tool dispatch</span>
          </div>
        </div>
      </div>

      <div className="border-t border-slate-100 dark:border-[#1e2a3f] px-5 py-3 flex items-center justify-between bg-slate-50/50 dark:bg-[#162030]/40" onClick={e => e.stopPropagation()}>
        <button
          onClick={() => setExpanded(v => !v)}
          className="flex items-center gap-1 text-xs text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-white transition-colors font-medium cursor-pointer"
        >
          {expanded ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
          {expanded ? 'Hide limits' : 'View overage rates'}
        </button>
        <Button variant="secondary" size="xs" icon={<Edit2 size={11} />} onClick={() => onEdit(plan)}>
          Edit Plan
        </Button>
      </div>

      {expanded && (
        <div className="border-t border-slate-100 dark:border-[#1e2a3f] px-5 py-3 bg-slate-50/80 dark:bg-[#162030]/70 grid grid-cols-2 gap-2 text-xs text-slate-600 dark:text-slate-300" onClick={e => e.stopPropagation()}>
          <div><span className="font-semibold text-slate-500 dark:text-slate-400">Annual billing:</span> {Number(plan.annual_price_usd) === 0 ? 'Free' : `$${Number(plan.annual_price_usd).toFixed(2)}/yr`}</div>
          <div><span className="font-semibold text-slate-500 dark:text-slate-400">Max runs cap:</span> {plan.max_workflow_runs === 0 ? 'Unlimited' : plan.max_workflow_runs.toLocaleString()}</div>
          <div><span className="font-semibold text-slate-500 dark:text-slate-400">Max users cap:</span> {plan.max_users === 0 ? 'Unlimited' : plan.max_users}</div>
          <div><span className="font-semibold text-slate-500 dark:text-slate-400">Included images:</span> {plan.included_image_gens === 0 ? '0' : plan.included_image_gens.toLocaleString()}</div>
          <div className="col-span-2 text-slate-500 dark:text-slate-400 pt-1 border-t border-slate-200/50 dark:border-slate-800/50 mt-1">
            <span className="font-semibold text-slate-600 dark:text-slate-300">Overage unit pricing:</span>
            {' '}${Number(plan.overage_run_price_usd).toFixed(4)}/run
            {' '} · ${Number(plan.overage_token_price_usd).toFixed(6)}/1k tokens
            {' '} · ${Number(plan.overage_image_price_usd).toFixed(4)}/gen
          </div>
        </div>
      )}
    </div>
  )
}

// ── Main component ─────────────────────────────────────────────────────────────
export default function AdminPlans() {
  const { api }      = useAuth()
  const [plans, setPlans]       = useState([])
  const [catalog, setCatalog]   = useState([])
  const [loading, setLoading]   = useState(true)
  const [error, setError]       = useState(null)
  const [editPlan, setEditPlan] = useState(null)
  const [showCreate, setShowCreate] = useState(false)
  const [showArchived, setShowArchived] = useState(false)

  const load = useCallback(async () => {
    setLoading(true); setError(null)
    try {
      const [p, c] = await Promise.all([
        api.get(`/admin/plans?include_archived=true`),
        api.get('/admin/workflows/catalog').catch(() => []),
      ])
      setPlans(Array.isArray(p) ? p : [])
      setCatalog(Array.isArray(c) ? c : [])
    } catch (e) {
      setError(e?.response?.data?.detail || e.message || 'Failed to load plans')
    } finally { setLoading(false) }
  }, [api])

  useEffect(() => { load() }, [load])

  const visible = useMemo(
    () => showArchived ? plans : plans.filter(p => p.status !== 'archived'),
    [plans, showArchived]
  )

  return (
    <div className="flex flex-col gap-6 p-6 min-h-full bg-slate-50 dark:bg-[#0b0f17] text-slate-900 dark:text-slate-100 transition-colors">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-xl font-bold text-slate-900 dark:text-white flex items-center gap-2">
            <CreditCard className="text-blue-500" size={22} />
            Plans &amp; Pricing
          </h1>
          <p className="text-sm text-slate-500 dark:text-slate-400 mt-0.5">
            {loading ? '…' : `${plans.filter(p => p.status === 'active').length} active tier${plans.filter(p => p.status === 'active').length !== 1 ? 's' : ''}`}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={load} disabled={loading}
            className="p-2 rounded-xl text-slate-500 dark:text-slate-400 bg-white dark:bg-[#121826] border border-slate-200 dark:border-[#233048] hover:bg-slate-50 dark:hover:bg-[#162030] transition-colors disabled:opacity-50">
            <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
          </button>
          <Button variant="primary" size="sm" icon={<Plus size={14} />} onClick={() => setShowCreate(true)}>
            New Plan
          </Button>
        </div>
      </div>

      {error && (
        <div className="flex items-center gap-2 px-4 py-3 bg-red-500/10 border border-red-500/20 rounded-xl text-sm text-red-600 dark:text-red-400">
          <XCircle size={15} className="shrink-0" />{error}
        </div>
      )}

      {/* Toggle archived */}
      {plans.some(p => p.status === 'archived') && (
        <label className="flex items-center gap-2 text-sm text-slate-500 dark:text-slate-400 self-start cursor-pointer">
          <input type="checkbox" checked={showArchived} onChange={e => setShowArchived(e.target.checked)}
            className="w-3.5 h-3.5 text-blue-600 rounded bg-white dark:bg-[#162030] border-slate-300 dark:border-[#2a3850]" />
          Show archived plans
        </label>
      )}

      {loading ? (
        <div className="flex items-center justify-center h-48 text-slate-400 text-sm">Loading plans…</div>
      ) : visible.length === 0 ? (
        <EmptyState icon={CreditCard} title="No plans yet"
          description="Create your first billing plan to start onboarding organizations."
          action={<Button size="sm" icon={<Plus size={13} />} onClick={() => setShowCreate(true)}>Create Plan</Button>}
        />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {visible.map(p => (
            <PlanCard key={p.id} plan={p} catalog={catalog} onEdit={setEditPlan} />
          ))}
        </div>
      )}

      <PlanModal open={showCreate} onClose={() => setShowCreate(false)} api={api} existing={null} catalog={catalog} onDone={load} />
      <PlanModal open={!!editPlan}  onClose={() => setEditPlan(null)}   api={api} existing={editPlan} catalog={catalog} onDone={load} />
    </div>
  )
}
