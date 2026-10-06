import React, { useState, useEffect, useCallback, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Layers, Plus, RefreshCw, Search, XCircle,
  Edit2, ToggleLeft, ToggleRight, Tag, Plug, Globe, Building2,
  Sparkles, ArrowRight, Play, CheckCircle2, ShieldCheck,
  Activity, ArrowUpRight, Filter
} from 'lucide-react'
import { useAuth } from '../../contexts/AuthContext'
import { Modal, Button, Input, Select, EmptyState } from '../../components/ui'

import ToolLogo from '../../components/common/ToolLogo'

// ── helpers ───────────────────────────────────────────────────────────────────
const CATEGORY_STYLES = {
  productivity: {
    badge: 'bg-blue-500/10 text-blue-600 dark:text-blue-400 border border-blue-500/20',
    iconBg: 'bg-blue-500/10 text-blue-500',
  },
  marketing: {
    badge: 'bg-purple-500/10 text-purple-600 dark:text-purple-400 border border-purple-500/20',
    iconBg: 'bg-purple-500/10 text-purple-500',
  },
  healthcare: {
    badge: 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20',
    iconBg: 'bg-emerald-500/10 text-emerald-500',
  },
  finance: {
    badge: 'bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20',
    iconBg: 'bg-amber-500/10 text-amber-500',
  },
  sales: {
    badge: 'bg-pink-500/10 text-pink-600 dark:text-pink-400 border border-pink-500/20',
    iconBg: 'bg-pink-500/10 text-pink-500',
  },
  operations: {
    badge: 'bg-cyan-500/10 text-cyan-600 dark:text-cyan-400 border border-cyan-500/20',
    iconBg: 'bg-cyan-500/10 text-cyan-500',
  },
  compliance: {
    badge: 'bg-rose-500/10 text-rose-600 dark:text-rose-400 border border-rose-500/20',
    iconBg: 'bg-rose-500/10 text-rose-500',
  },
  general: {
    badge: 'bg-slate-500/10 text-slate-600 dark:text-slate-400 border border-slate-500/20',
    iconBg: 'bg-slate-500/10 text-slate-500',
  },
}

const STATUS_COLORS = {
  active:     'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20',
  beta:       'bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20',
  deprecated: 'bg-rose-500/10 text-rose-600 dark:text-rose-400 border border-rose-500/20',
}

const SCOPE_COLORS = {
  GLOBAL:   'bg-indigo-500/10 text-indigo-600 dark:text-indigo-400 border border-indigo-500/20',
  INDUSTRY: 'bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20',
}

const CATEGORIES = ['general','productivity','marketing','healthcare','finance','sales','operations','compliance']
const STATUSES   = ['active','beta','deprecated']
const SCOPES     = ['GLOBAL','INDUSTRY']
const INDUSTRIES = ['saas','healthcare','finance','real_estate','retail','general']

const INDUSTRY_LABELS = {
  saas:        'SaaS / Growth',
  healthcare:  'Healthcare / Medical Tourism',
  finance:     'Finance',
  real_estate: 'Real Estate',
  retail:      'Retail',
  general:     'General',
}

// ── Scope badge ───────────────────────────────────────────────────────────────
function ScopeBadge({ scope, industry }) {
  if (scope === 'GLOBAL') {
    return (
      <span className={`inline-flex items-center gap-1 text-[10px] font-semibold px-2 py-0.5 rounded-full ${SCOPE_COLORS.GLOBAL}`}>
        <Globe size={10} /> Global
      </span>
    )
  }
  return (
    <span className={`inline-flex items-center gap-1 text-[10px] font-semibold px-2 py-0.5 rounded-full ${SCOPE_COLORS.INDUSTRY}`}>
      <Building2 size={10} /> {INDUSTRY_LABELS[industry] || industry || 'Industry'}
    </span>
  )
}

// ── Edit / Create modal ───────────────────────────────────────────────────────
function WorkflowModal({ open, onClose, api, existing, onDone }) {
  const isEdit = !!existing
  const [form, setForm] = useState({
    name: '', key: '', description: '', category: 'general',
    status: 'active', version: '1.0.0', pricing_model: 'included',
    required_integrations: '', supported_modules: '',
    scope: 'GLOBAL', industry: '',
  })
  const [loading, setLoading] = useState(false)
  const [error, setError]     = useState('')

  useEffect(() => {
    if (existing) {
      setForm({
        name:                   existing.name || '',
        key:                    existing.key  || '',
        description:            existing.description || '',
        category:               existing.category || 'general',
        status:                 existing.status  || 'active',
        version:                existing.version || '1.0.0',
        pricing_model:          existing.pricing_model || 'included',
        required_integrations:  (existing.required_integrations || []).join(', '),
        supported_modules:      (existing.supported_modules || []).join(', '),
        scope:                  existing.scope    || 'GLOBAL',
        industry:               existing.industry || '',
      })
    } else {
      setForm({
        name:'', key:'', description:'', category:'general', status:'active',
        version:'1.0.0', pricing_model:'included', required_integrations:'',
        supported_modules:'', scope:'GLOBAL', industry:'',
      })
    }
    setError('')
  }, [existing, open])

  function set(f, v) { setForm(s => ({ ...s, [f]: v })) }

  async function submit(e) {
    e.preventDefault()
    if (!form.name.trim() || !form.key.trim()) { setError('Name and key are required'); return }
    if (form.scope === 'INDUSTRY' && !form.industry.trim()) {
      setError('Industry is required when scope is INDUSTRY'); return
    }
    setLoading(true); setError('')
    try {
      const payload = {
        name:                  form.name.trim(),
        key:                   form.key.trim().toLowerCase().replace(/\s+/g,'_'),
        description:           form.description.trim() || undefined,
        category:              form.category,
        status:                form.status,
        version:               form.version.trim() || '1.0.0',
        pricing_model:         form.pricing_model,
        required_integrations: form.required_integrations ? form.required_integrations.split(',').map(s=>s.trim()).filter(Boolean) : [],
        supported_modules:     form.supported_modules     ? form.supported_modules.split(',').map(s=>s.trim()).filter(Boolean)     : [],
        scope:                 form.scope,
        industry:              form.scope === 'INDUSTRY' ? form.industry : undefined,
      }
      if (isEdit) {
        await api.patch(`/admin/workflows/catalog/${existing.id}`, payload)
      } else {
        await api.post('/admin/workflows/catalog', payload)
      }
      onDone()
      onClose()
    } catch(err) {
      setError(err?.response?.data?.detail || err.message || 'Operation failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Modal open={open} onClose={onClose} title={isEdit ? 'Edit Workflow Definition' : 'Add Workflow to Catalog'}>
      <form onSubmit={submit} className="space-y-4">
        {error && (
          <div className="flex items-center gap-2 p-3 bg-red-500/10 border border-red-500/20 rounded-xl text-xs text-red-600 dark:text-red-400">
            <XCircle size={14} className="shrink-0" />{error}
          </div>
        )}
        <div className="grid grid-cols-2 gap-3">
          <Input label="Name" value={form.name} onChange={e => set('name', e.target.value)} required placeholder="e.g. Lead Enrichment" />
          <Input label="Key (slug)" value={form.key} onChange={e => set('key', e.target.value)} required placeholder="e.g. lead_enrichment" disabled={isEdit} />
        </div>
        <div className="grid grid-cols-3 gap-3">
          <Select label="Category" value={form.category} onChange={e => set('category', e.target.value)}
            options={CATEGORIES.map(c => ({ value: c, label: c.charAt(0).toUpperCase()+c.slice(1) }))} />
          <Select label="Status" value={form.status} onChange={e => set('status', e.target.value)}
            options={STATUSES.map(s => ({ value: s, label: s.charAt(0).toUpperCase()+s.slice(1) }))} />
          <Input label="Version" value={form.version} onChange={e => set('version', e.target.value)} placeholder="1.0.0" />
        </div>

        <div className="p-3.5 bg-slate-50 dark:bg-[#162030] rounded-xl border border-slate-200 dark:border-[#233048] space-y-3">
          <p className="text-xs font-semibold text-slate-700 dark:text-slate-200">Catalog Scope &amp; Target Industry</p>
          <div className="grid grid-cols-2 gap-3">
            <Select
              label="Scope"
              value={form.scope}
              onChange={e => {
                set('scope', e.target.value)
                if (e.target.value === 'GLOBAL') set('industry', '')
              }}
              options={SCOPES.map(s => ({ value: s, label: s === 'GLOBAL' ? 'Global (All Orgs)' : 'Industry-Specific' }))}
            />
            <Select
              label="Industry"
              value={form.industry}
              onChange={e => set('industry', e.target.value)}
              disabled={form.scope !== 'INDUSTRY'}
              options={[
                { value: '',           label: '— select industry —' },
                ...INDUSTRIES.map(i => ({ value: i, label: INDUSTRY_LABELS[i] || i })),
              ]}
            />
          </div>
        </div>

        <Select label="Pricing Model" value={form.pricing_model}
          onChange={e => set('pricing_model', e.target.value)}
          options={[
            { value:'included', label:'Included in plan' },
            { value:'per_run',  label:'Per run' },
            { value:'metered',  label:'Metered' },
          ]} />
        <Input label="Description" value={form.description}
          onChange={e => set('description', e.target.value)}
          placeholder="Brief description of what this workflow does" />
        <Input label="Required Integrations (comma-separated)" value={form.required_integrations}
          onChange={e => set('required_integrations', e.target.value)}
          placeholder="gmail, hubspot, stripe, postgres" />
        <Input label="Supported Modules (comma-separated)" value={form.supported_modules}
          onChange={e => set('supported_modules', e.target.value)}
          placeholder="email, medical_tourism" />
        <div className="flex justify-end gap-2 pt-1">
          <Button variant="secondary" size="sm" type="button" onClick={onClose}>Cancel</Button>
          <Button variant="primary" size="sm" loading={loading} type="submit">
            {isEdit ? 'Save Changes' : 'Add to Catalog'}
          </Button>
        </div>
      </form>
    </Modal>
  )
}

// ── Main component ────────────────────────────────────────────────────────────
export default function AdminWorkflowCatalog() {
  const { api } = useAuth()
  const navigate = useNavigate()
  const [catalog, setCatalog] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [search, setSearch] = useState('')
  const [filterStatus, setFilterStatus] = useState('all')
  const [filterCategory, setFilterCategory] = useState('all')
  const [filterScope, setFilterScope] = useState('all')
  const [editItem, setEditItem] = useState(null)
  const [showCreate, setShowCreate] = useState(false)
  const [toggling, setToggling] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await api.get('/admin/workflows/catalog')
      setCatalog(Array.isArray(data) ? data : [])
    } catch(e) {
      setError(e?.response?.data?.detail || e.message || 'Failed to load catalog')
    } finally {
      setLoading(false)
    }
  }, [api])

  useEffect(() => { load() }, [load])

  async function toggleActive(wf) {
    setToggling(wf.id)
    try {
      await api.patch(`/admin/workflows/catalog/${wf.id}`, { active: !wf.active })
      load()
    } finally {
      setToggling(null)
    }
  }

  const filtered = useMemo(() => {
    let list = catalog
    if (search) {
      const q = search.toLowerCase()
      list = list.filter(w =>
        w.name?.toLowerCase().includes(q) ||
        w.key?.toLowerCase().includes(q) ||
        w.description?.toLowerCase().includes(q) ||
        (w.industry || '').toLowerCase().includes(q)
      )
    }
    if (filterStatus   !== 'all') list = list.filter(w => w.status   === filterStatus)
    if (filterCategory !== 'all') list = list.filter(w => w.category === filterCategory)
    if (filterScope    !== 'all') list = list.filter(w => (w.scope || 'GLOBAL') === filterScope)
    return list
  }, [catalog, search, filterStatus, filterCategory, filterScope])

  const categories = useMemo(() => [...new Set(catalog.map(w => w.category).filter(Boolean))], [catalog])
  const globalCount = useMemo(() => catalog.filter(w => (w.scope || 'GLOBAL') === 'GLOBAL').length, [catalog])
  const industryCount = useMemo(() => catalog.filter(w => w.scope === 'INDUSTRY').length, [catalog])

  return (
    <div className="flex flex-col gap-6 p-6 min-h-full bg-slate-50 dark:bg-[#0b0f17] bg-dot-pattern text-slate-900 dark:text-slate-100 transition-colors">
      
      {/* ── Top Header ────────────────────────────────────────────────────── */}
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-xl font-bold text-slate-900 dark:text-white flex items-center gap-2">
            <div className="w-8 h-8 rounded-xl bg-blue-600 text-white flex items-center justify-center shadow-xs">
              <Layers size={18} />
            </div>
            <span>Platform Workflow Catalog</span>
          </h1>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
            {loading ? 'Synchronizing catalog…' : `${catalog.length} blueprints registered · ${globalCount} global · ${industryCount} industry-tailored`}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={load}
            disabled={loading}
            className="p-2 rounded-xl text-slate-500 dark:text-slate-400 bg-white dark:bg-[#121826] border border-slate-200 dark:border-[#233048] hover:bg-slate-50 dark:hover:bg-[#162030] transition-colors disabled:opacity-50"
            title="Refresh Catalog"
          >
            <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
          </button>
          <button
            onClick={() => navigate('/workflows/builder')}
            className="flex items-center gap-1.5 px-3 py-2 bg-white dark:bg-[#121826] hover:bg-slate-100 dark:hover:bg-[#182234] border border-slate-200 dark:border-[#233048] text-slate-900 dark:text-slate-100 text-xs font-semibold rounded-xl transition-all shadow-2xs cursor-pointer"
          >
            <Sparkles size={13} className="text-blue-500" />
            <span>DAG Visual Builder</span>
          </button>
          <button
            onClick={() => setShowCreate(true)}
            className="flex items-center gap-1.5 px-3.5 py-2 bg-blue-600 hover:bg-blue-500 text-white text-xs font-bold rounded-xl transition-all shadow-xs cursor-pointer"
          >
            <Plus size={14} />
            <span>Create Workflow</span>
          </button>
        </div>
      </div>

      {/* ── Filters & Search Bar ─────────────────────────────────────────── */}
      <div className="flex items-center gap-3 flex-wrap bg-white dark:bg-[#121826] border border-slate-200 dark:border-[#233048] p-3 rounded-2xl shadow-2xs">
        <div className="relative flex-1 min-w-[240px]">
          <Search size={14} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" />
          <input
            type="text"
            placeholder="Search workflows by title, slug, or target industry..."
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="w-full pl-9 pr-3 py-2 text-xs bg-slate-50 dark:bg-[#0b0f17] border border-slate-200 dark:border-[#233048] text-slate-900 dark:text-white rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 placeholder-slate-400"
          />
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <select
            value={filterScope}
            onChange={e => setFilterScope(e.target.value)}
            className="px-3 py-2 text-xs bg-slate-50 dark:bg-[#0b0f17] border border-slate-200 dark:border-[#233048] text-slate-900 dark:text-white rounded-xl focus:outline-none"
          >
            <option value="all">All Scopes</option>
            <option value="GLOBAL">Global Only</option>
            <option value="INDUSTRY">Industry Specific</option>
          </select>
          <select
            value={filterCategory}
            onChange={e => setFilterCategory(e.target.value)}
            className="px-3 py-2 text-xs bg-slate-50 dark:bg-[#0b0f17] border border-slate-200 dark:border-[#233048] text-slate-900 dark:text-white rounded-xl focus:outline-none"
          >
            <option value="all">All Categories</option>
            {categories.map(c => <option key={c} value={c}>{c.charAt(0).toUpperCase()+c.slice(1)}</option>)}
          </select>
          <select
            value={filterStatus}
            onChange={e => setFilterStatus(e.target.value)}
            className="px-3 py-2 text-xs bg-slate-50 dark:bg-[#0b0f17] border border-slate-200 dark:border-[#233048] text-slate-900 dark:text-white rounded-xl focus:outline-none"
          >
            <option value="all">All Statuses</option>
            {STATUSES.map(s => <option key={s} value={s}>{s.charAt(0).toUpperCase()+s.slice(1)}</option>)}
          </select>
        </div>
      </div>

      {error && (
        <div className="flex items-center gap-2 px-4 py-3 bg-red-500/10 border border-red-500/20 rounded-xl text-xs text-red-600 dark:text-red-400">
          <XCircle size={15} className="shrink-0" />{error}
        </div>
      )}

      {/* ── Workflow Cards Grid ──────────────────────────────────────────── */}
      {loading ? (
        <div className="flex flex-col items-center justify-center h-64 text-slate-400 gap-2">
          <RefreshCw size={20} className="animate-spin text-blue-500" />
          <span className="text-xs">Loading workflow registry...</span>
        </div>
      ) : filtered.length === 0 ? (
        <EmptyState
          icon={Layers}
          title="No workflows found"
          description={search ? 'No workflow matching your search query.' : 'Add the first workflow to the platform catalog.'}
          action={!search && <Button size="sm" icon={<Plus size={13} />} onClick={() => setShowCreate(true)}>Create Workflow</Button>}
        />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-5">
          {filtered.map(wf => {
            const catStyle = CATEGORY_STYLES[wf.category] || CATEGORY_STYLES.general
            const integrations = Array.isArray(wf.required_integrations) ? wf.required_integrations : []
            
            return (
              <div
                key={wf.id}
                className={`bg-white dark:bg-[#121826] border rounded-2xl p-5 flex flex-col justify-between gap-4 transition-all shadow-2xs hover:border-blue-500/50 hover:shadow-md group ${
                  wf.active ? 'border-slate-200 dark:border-[#233048]' : 'border-slate-200 dark:border-[#233048] opacity-60'
                }`}
              >
                <div className="space-y-3">
                  {/* Top Badges & Controls */}
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex items-center gap-1.5 flex-wrap">
                      <ScopeBadge scope={wf.scope || 'GLOBAL'} industry={wf.industry} />
                      <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full capitalize ${catStyle.badge}`}>
                        {wf.category}
                      </span>
                      <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full capitalize ${STATUS_COLORS[wf.status] || 'bg-slate-500/10 text-slate-400'}`}>
                        {wf.status}
                      </span>
                    </div>
                    <div className="flex items-center gap-1 shrink-0">
                      <button
                        onClick={() => setEditItem(wf)}
                        title="Edit Definition"
                        className="p-1.5 rounded-lg text-slate-400 hover:text-blue-500 hover:bg-slate-100 dark:hover:bg-[#162030] transition-colors cursor-pointer"
                      >
                        <Edit2 size={13} />
                      </button>
                      <button
                        onClick={() => toggleActive(wf)}
                        disabled={toggling === wf.id}
                        title={wf.active ? 'Disable workflow' : 'Enable workflow'}
                        className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 transition-colors disabled:opacity-40 cursor-pointer"
                      >
                        {wf.active
                          ? <ToggleRight size={20} className="text-emerald-500" />
                          : <ToggleLeft size={20} />}
                      </button>
                    </div>
                  </div>

                  {/* Header Title & Slug */}
                  <div>
                    <h3 className="text-sm font-bold text-slate-900 dark:text-white leading-snug group-hover:text-blue-500 transition-colors">
                      {wf.name}
                    </h3>
                    <p className="text-[11px] text-slate-400 font-mono mt-0.5 truncate">{wf.key}</p>
                  </div>

                  {/* Description */}
                  <p className="text-xs text-slate-500 dark:text-slate-400 leading-relaxed line-clamp-2 min-h-[32px]">
                    {wf.description || 'Production autonomous multi-agent pipeline.'}
                  </p>

                  {/* Tool Badges with Real PNG Logos */}
                  {integrations.length > 0 && (
                    <div className="pt-1">
                      <div className="flex items-center gap-1.5 flex-wrap">
                        {integrations.map((tool, tIdx) => (
                          <div
                            key={tIdx}
                            className="inline-flex items-center gap-1.5 px-2 py-1 rounded-lg bg-slate-100 dark:bg-[#162030] border border-slate-200 dark:border-[#233048] text-[10px] font-medium text-slate-700 dark:text-slate-300"
                          >
                            <ToolLogo name={tool} className="w-3.5 h-3.5" />
                            <span className="capitalize">{tool.replace('_', ' ')}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>

                {/* Footer Action Bar */}
                <div className="flex items-center justify-between border-t border-slate-100 dark:border-[#1e2a3f] pt-3 text-xs text-slate-400">
                  <div className="flex items-center gap-2 text-[11px]">
                    <span className="font-mono text-slate-500">v{wf.version}</span>
                    <span>·</span>
                    <span className="capitalize">{wf.pricing_model?.replace('_', ' ')}</span>
                  </div>

                  <button
                    onClick={() => navigate(`/workflows/builder?wf=${encodeURIComponent(wf.name || wf.key)}`)}
                    className="inline-flex items-center gap-1 px-3 py-1.5 rounded-xl bg-blue-600/10 hover:bg-blue-600 text-blue-600 hover:text-white dark:text-blue-400 dark:hover:text-white border border-blue-500/20 font-semibold text-xs transition-all cursor-pointer shadow-2xs"
                  >
                    <span>Open in DAG Builder</span>
                    <ArrowRight size={12} />
                  </button>
                </div>
              </div>
            )
          })}
        </div>
      )}

      <WorkflowModal open={showCreate} onClose={() => setShowCreate(false)} api={api} existing={null} onDone={load} />
      <WorkflowModal open={!!editItem}  onClose={() => setEditItem(null)}   api={api} existing={editItem} onDone={load} />
    </div>
  )
}
