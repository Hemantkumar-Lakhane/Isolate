// AdminWorkflowAssignments — Cross-org workflow assignment manager
import { useState, useEffect, useCallback, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  RefreshCw, XCircle, Search, CheckCircle2, Globe,
  Plus, Minus, Building2, Layers, AlertCircle, ChevronRight,
  LayoutGrid, List,
} from 'lucide-react'
import { useAuth } from '../../contexts/AuthContext'
import { EmptyState } from '../../components/ui'

// ── helpers ───────────────────────────────────────────────────────────────────
const INDUSTRY_LABELS = {
  saas:        'SaaS / Growth',
  healthcare:  'Healthcare / Medical Tourism',
  finance:     'Finance',
  real_estate: 'Real Estate',
  retail:      'Retail',
  general:     'General',
}

function industryLabel(ind) {
  return INDUSTRY_LABELS[ind] || (ind ? ind.charAt(0).toUpperCase() + ind.slice(1) : 'Unknown')
}

// ── Assignment toggle cell ────────────────────────────────────────────────────
function AssignCell({ assigned, loading, onAssign, onRevoke }) {
  if (loading) {
    return (
      <div className="flex items-center justify-center">
        <div className="w-4 h-4 rounded-full border-2 border-slate-300 dark:border-slate-600 border-t-blue-500 animate-spin" />
      </div>
    )
  }
  if (assigned) {
    return (
      <button onClick={onRevoke} title="Revoke access"
        className="group flex items-center justify-center w-7 h-7 rounded-lg bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-900/50 hover:bg-rose-50 dark:hover:bg-rose-950/40 hover:border-rose-200 dark:hover:border-rose-900/50 transition-all">
        <CheckCircle2 size={14} className="text-emerald-500 group-hover:hidden" />
        <Minus size={13} className="text-rose-500 hidden group-hover:block" />
      </button>
    )
  }
  return (
    <button onClick={onAssign} title="Assign workflow"
      className="flex items-center justify-center w-7 h-7 rounded-lg bg-slate-50 dark:bg-[#162030] border border-slate-200 dark:border-[#2a3850] hover:bg-blue-50 dark:hover:bg-blue-950/40 hover:border-blue-200 dark:hover:border-blue-900/50 transition-all">
      <Plus size={13} className="text-slate-400 hover:text-blue-500" />
    </button>
  )
}

// ── Org-focused view ──────────────────────────────────────────────────────────
function OrgFocusView({ org, api, assignments, onAssign, onRevoke, pendingCells, onClose }) {
  const [applicable, setApplicable] = useState(null)
  const [loadingApplicable, setLoadingApplicable] = useState(true)
  const [applicableError, setApplicableError] = useState(null)

  useEffect(() => {
    if (!org) return
    setLoadingApplicable(true)
    setApplicableError(null)
    api.get(`/admin/organizations/${org.id}/workflows/applicable`)
      .then(d => setApplicable(d?.workflows || []))
      .catch(e => setApplicableError(e?.response?.data?.detail || e.message || 'Failed to load applicable workflows'))
      .finally(() => setLoadingApplicable(false))
  }, [org, api])

  const assignmentSet = useMemo(() => {
    const s = new Set()
    assignments.forEach(a => {
      if (a.organization_id === org?.id && a.status === 'active') s.add(a.workflow_id)
    })
    return s
  }, [assignments, org])

  const global_wfs   = useMemo(() => (applicable || []).filter(w => (w.scope || 'GLOBAL') === 'GLOBAL'), [applicable])
  const industry_wfs = useMemo(() => (applicable || []).filter(w => w.scope === 'INDUSTRY'), [applicable])

  if (!org) return null

  function WorkflowRow({ wf }) {
    const key = `${org.id}:${wf.id}`
    const assigned = assignmentSet.has(wf.id)
    const isLoading = pendingCells.has(key)
    return (
      <div className="flex items-center justify-between py-3 px-4 border-b border-slate-100 dark:border-[#1e2a3f] last:border-0 hover:bg-slate-50/50 dark:hover:bg-[#162030]/50 transition-colors">
        <div className="min-w-0 flex-1">
          <p className="text-sm font-medium text-slate-900 dark:text-white">{wf.name}</p>
          <p className="text-xs text-slate-400 dark:text-slate-500 font-mono mt-0.5">{wf.key}</p>
        </div>
        <div className="flex items-center gap-2 ml-3">
          {assigned && (
            <span className="text-[10px] font-semibold text-emerald-600 dark:text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 px-2 py-0.5 rounded-full">
              Assigned
            </span>
          )}
          <AssignCell
            assigned={assigned}
            loading={isLoading}
            onAssign={() => onAssign(org.id, wf.id, key)}
            onRevoke={() => onRevoke(org.id, wf.id, key)}
          />
        </div>
      </div>
    )
  }

  function Section({ title, icon: Icon, workflows, accentClass }) {
    if (workflows.length === 0) return null
    return (
      <div className="bg-white dark:bg-[#121826] border border-slate-200 dark:border-[#233048] rounded-2xl overflow-hidden shadow-2xs">
        <div className={`flex items-center gap-2 px-4 py-3 border-b border-slate-100 dark:border-[#1e2a3f] ${accentClass}`}>
          <Icon size={14} />
          <h3 className="text-xs font-semibold uppercase tracking-wide">{title}</h3>
          <span className="ml-auto text-xs font-medium opacity-70">{workflows.length} workflow{workflows.length !== 1 ? 's' : ''}</span>
        </div>
        <div>
          {workflows.map(wf => <WorkflowRow key={wf.id} wf={wf} />)}
        </div>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-4">
      {/* Org header */}
      <div className="flex items-center justify-between bg-white dark:bg-[#121826] border border-slate-200 dark:border-[#233048] rounded-2xl px-5 py-4 shadow-2xs">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-blue-500/10 border border-blue-500/20 flex items-center justify-center shrink-0">
            <span className="text-blue-600 dark:text-blue-400 text-sm font-bold">{(org.name || '?')[0].toUpperCase()}</span>
          </div>
          <div>
            <p className="text-sm font-bold text-slate-900 dark:text-white">{org.name}</p>
            <p className="text-xs text-slate-500 dark:text-slate-400">
              Industry: <span className="font-medium text-slate-700 dark:text-slate-300">{industryLabel(org.industry)}</span>
              {org.plan_name && <> · Plan: <span className="font-medium text-slate-700 dark:text-slate-300">{org.plan_name}</span></>}
            </p>
          </div>
        </div>
        <button onClick={onClose}
          className="text-xs text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-white bg-slate-50 dark:bg-[#162030] border border-slate-200 dark:border-[#2a3850] rounded-xl px-3 py-1.5 transition-colors">
          ← Back to All Orgs
        </button>
      </div>

      {/* Info note */}
      <div className="flex items-start gap-2.5 px-4 py-3 bg-amber-500/10 border border-amber-500/20 rounded-2xl text-xs text-amber-700 dark:text-amber-300">
        <AlertCircle size={14} className="shrink-0 mt-0.5 text-amber-500" />
        <p className="leading-relaxed">
          Showing workflows applicable to <strong>{industryLabel(org.industry)}</strong> organizations.
          Finance, Retail, and other industry workflows are hidden because they don't apply to this vertical.
          Plan entitlement is still required for a workflow to be executable.
        </p>
      </div>

      {loadingApplicable ? (
        <div className="flex items-center justify-center h-32 text-slate-400 text-sm">Loading applicable workflows…</div>
      ) : applicableError ? (
        <div className="flex items-center gap-2 px-4 py-3 bg-red-500/10 border border-red-500/20 rounded-xl text-sm text-red-600 dark:text-red-400">
          <XCircle size={14} />{applicableError}
        </div>
      ) : applicable?.length === 0 ? (
        <div className="text-center py-10 text-slate-400 text-sm">No applicable workflows found for this organization's industry.</div>
      ) : (
        <>
          <Section
            title={`${industryLabel(org.industry)} Workflows`}
            icon={Building2}
            workflows={industry_wfs}
            accentClass="bg-amber-500/10 text-amber-600 dark:text-amber-400"
          />
          <Section
            title="Global Workflows"
            icon={Globe}
            workflows={global_wfs}
            accentClass="bg-indigo-500/10 text-indigo-600 dark:text-indigo-400"
          />
        </>
      )}
    </div>
  )
}

// ── Matrix view ───────────────────────────────────────────────────────────────
function MatrixView({ catalog, orgs, assignmentMap, catalogStats, filteredOrgs, pendingCells, onAssign, onRevoke, navigate }) {
  return (
    <div className="bg-white dark:bg-[#121826] border border-slate-200 dark:border-[#233048] rounded-2xl overflow-hidden shadow-2xs">
      <div className="overflow-x-auto">
        <table className="text-sm w-full">
          <thead>
            <tr className="border-b border-slate-100 dark:border-[#1e2a3f] bg-slate-50/70 dark:bg-[#162030]/60">
              <th className="px-4 py-3 text-left text-[11px] font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider sticky left-0 bg-slate-50 dark:bg-[#162030] border-r border-slate-100 dark:border-[#1e2a3f] min-w-[220px]">
                Organization
              </th>
              {catalog.map((wf, i) => (
                <th key={wf.id} className="px-2 py-3 text-center min-w-[95px] max-w-[95px]">
                  <div className="flex flex-col items-center gap-1">
                    <span className="text-[11px] font-semibold text-slate-700 dark:text-slate-200 leading-tight break-words max-w-[85px] text-center" title={wf.name}>
                      {wf.name.length > 14 ? wf.name.slice(0, 12) + '…' : wf.name}
                    </span>
                    <span className={`text-[9px] px-1.5 py-0.5 rounded-full font-semibold ${(wf.scope || 'GLOBAL') === 'GLOBAL' ? 'bg-indigo-500/10 text-indigo-600 dark:text-indigo-400 border border-indigo-500/20' : 'bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20'}`}>
                      {(wf.scope || 'GLOBAL') === 'GLOBAL' ? 'Global' : wf.industry}
                    </span>
                    <span className="text-[10px] text-slate-400 dark:text-slate-500">{catalogStats[i]?.assignedCount}/{orgs.length}</span>
                  </div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 dark:divide-[#1a2336]">
            {filteredOrgs.length === 0 ? (
              <tr>
                <td colSpan={catalog.length + 1} className="px-5 py-12 text-center text-slate-400 text-sm">
                  No organizations match your search
                </td>
              </tr>
            ) : filteredOrgs.map(org => {
              const assignedCount = catalog.filter(wf => assignmentMap[`${org.id}:${wf.id}`]).length
              return (
                <tr key={org.id} className="hover:bg-slate-50/60 dark:hover:bg-[#162030]/50 transition-colors">
                  <td className="px-4 py-3 sticky left-0 bg-white dark:bg-[#121826] border-r border-slate-100 dark:border-[#1e2a3f] z-10 min-w-[220px]">
                    <div className="flex items-center gap-2.5">
                      <div className="w-7 h-7 rounded-lg bg-blue-500/10 border border-blue-500/20 flex items-center justify-center shrink-0">
                        <span className="text-blue-600 dark:text-blue-400 text-xs font-bold">{(org.name || '?')[0].toUpperCase()}</span>
                      </div>
                      <div className="min-w-0">
                        <p className="text-xs font-semibold text-slate-900 dark:text-white truncate">{org.name}</p>
                        <p className="text-[10px] text-slate-400 dark:text-slate-500">
                          {industryLabel(org.industry)} · {assignedCount}/{catalog.length}
                        </p>
                      </div>
                      <button onClick={() => navigate(`/admin/organizations/${org.id}`)}
                        className="ml-auto p-1 text-slate-400 hover:text-blue-500 transition-colors shrink-0">
                        <ChevronRight size={13} />
                      </button>
                    </div>
                  </td>
                  {catalog.map(wf => {
                    const key = `${org.id}:${wf.id}`
                    return (
                      <td key={wf.id} className="px-2 py-3 text-center">
                        <AssignCell
                          assigned={!!assignmentMap[key]}
                          loading={pendingCells.has(key)}
                          onAssign={() => onAssign(org.id, wf.id, key)}
                          onRevoke={() => onRevoke(org.id, wf.id, key)}
                        />
                      </td>
                    )
                  })}
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      <div className="border-t border-slate-100 dark:border-[#1e2a3f] px-5 py-3 flex items-center gap-6 text-xs text-slate-500 dark:text-slate-400 bg-slate-50/50 dark:bg-[#162030]/40 flex-wrap">
        <span className="flex items-center gap-1.5">
          <span className="w-5 h-5 rounded-md bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center">
            <CheckCircle2 size={11} className="text-emerald-500" />
          </span>
          Assigned (click to revoke)
        </span>
        <span className="flex items-center gap-1.5">
          <span className="w-5 h-5 rounded-md bg-slate-500/10 border border-slate-500/20 flex items-center justify-center">
            <Plus size={11} className="text-slate-400" />
          </span>
          Not assigned
        </span>
        <span className="flex items-center gap-1.5">
          <span className="inline-block w-2.5 h-2.5 rounded-full bg-indigo-500/40" /> Global
        </span>
        <span className="flex items-center gap-1.5">
          <span className="inline-block w-2.5 h-2.5 rounded-full bg-amber-500/40" /> Industry-specific
        </span>
      </div>
    </div>
  )
}

// ── Main component ─────────────────────────────────────────────────────────────
export default function AdminWorkflowAssignments() {
  const { api } = useAuth()
  const navigate = useNavigate()

  const [catalog,     setCatalog]     = useState([])
  const [orgs,        setOrgs]        = useState([])
  const [assignments, setAssignments] = useState([])
  const [loading,     setLoading]     = useState(true)
  const [error,       setError]       = useState(null)
  const [search,      setSearch]      = useState('')
  const [pendingCells,setPending]     = useState(new Set())
  const [viewMode,    setViewMode]    = useState('org')    // 'org' | 'matrix'
  const [selectedOrg, setSelectedOrg] = useState(null)

  const load = useCallback(async () => {
    setLoading(true); setError(null)
    try {
      const [cat, org, ass] = await Promise.all([
        api.get('/admin/workflows/catalog'),
        api.get('/admin/organizations'),
        api.get('/admin/workflows/assignments'),
      ])
      setCatalog(Array.isArray(cat) ? cat.filter(w => w.active) : [])
      setOrgs(Array.isArray(org) ? org : [])
      setAssignments(Array.isArray(ass) ? ass : [])
    } catch (e) {
      setError(e?.response?.data?.detail || e.message || 'Failed to load assignments')
    } finally {
      setLoading(false)
    }
  }, [api])

  useEffect(() => { load() }, [load])

  const assignmentMap = useMemo(() => {
    const m = {}
    assignments.forEach(a => {
      if (a.status === 'active') m[`${a.organization_id}:${a.workflow_id}`] = a
    })
    return m
  }, [assignments])

  const filteredOrgs = useMemo(() => {
    if (!search) return orgs
    const q = search.toLowerCase()
    return orgs.filter(o =>
      o.name?.toLowerCase().includes(q) ||
      o.industry?.toLowerCase().includes(q) ||
      o.plan_name?.toLowerCase().includes(q)
    )
  }, [orgs, search])

  const catalogStats = useMemo(() =>
    catalog.map(wf => ({
      id: wf.id,
      assignedCount: orgs.filter(o => assignmentMap[`${o.id}:${wf.id}`]).length,
    })),
  [catalog, orgs, assignmentMap])

  async function handleAssign(orgId, workflowId, key) {
    setPending(p => new Set(p).add(key))
    try {
      await api.post(`/admin/organizations/${orgId}/workflows/${workflowId}/assign`, {})
      setAssignments(prev => [
        ...prev.filter(a => !(a.organization_id === orgId && a.workflow_id === workflowId)),
        { organization_id: orgId, workflow_id: workflowId, status: 'active', assigned_at: new Date().toISOString() },
      ])
    } catch (e) {
      setError(`Failed to assign: ${e?.response?.data?.detail || e.message}`)
    } finally {
      setPending(p => { const s = new Set(p); s.delete(key); return s })
    }
  }

  async function handleRevoke(orgId, workflowId, key) {
    setPending(p => new Set(p).add(key))
    try {
      await api.delete(`/admin/organizations/${orgId}/workflows/${workflowId}/assign`)
      setAssignments(prev => prev.filter(a => !(a.organization_id === orgId && a.workflow_id === workflowId)))
    } catch (e) {
      setError(`Failed to revoke: ${e?.response?.data?.detail || e.message}`)
    } finally {
      setPending(p => { const s = new Set(p); s.delete(key); return s })
    }
  }

  const totalAssignments = assignments.filter(a => a.status === 'active').length

  return (
    <div className="flex flex-col gap-6 p-6 min-h-full bg-slate-50 dark:bg-[#0b0f17] text-slate-900 dark:text-slate-100 transition-colors">

      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-xl font-bold text-slate-900 dark:text-white flex items-center gap-2">
            <Layers className="text-blue-500" size={22} />
            Workflow Assignments
          </h1>
          <p className="text-sm text-slate-500 dark:text-slate-400 mt-0.5">
            {loading ? '…' : `${totalAssignments} active assignment${totalAssignments !== 1 ? 's' : ''} · ${orgs.length} organization${orgs.length !== 1 ? 's' : ''}`}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {/* View toggle */}
          <div className="flex items-center bg-white dark:bg-[#121826] border border-slate-200 dark:border-[#233048] rounded-xl overflow-hidden p-0.5">
            <button
              onClick={() => { setViewMode('org'); setSelectedOrg(null) }}
              className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg transition-colors ${viewMode === 'org' ? 'bg-blue-600 text-white' : 'text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-[#162030]'}`}
            >
              <List size={13} /> Org View
            </button>
            <button
              onClick={() => setViewMode('matrix')}
              className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg transition-colors ${viewMode === 'matrix' ? 'bg-blue-600 text-white' : 'text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-[#162030]'}`}
            >
              <LayoutGrid size={13} /> Matrix
            </button>
          </div>
          <button onClick={load} disabled={loading}
            className="p-2 rounded-xl text-slate-500 dark:text-slate-400 bg-white dark:bg-[#121826] border border-slate-200 dark:border-[#233048] hover:bg-slate-50 dark:hover:bg-[#162030] transition-colors disabled:opacity-50">
            <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
          </button>
        </div>
      </div>

      {/* Info banner */}
      <div className="flex items-start gap-3 px-4 py-3 bg-blue-500/10 border border-blue-500/20 rounded-2xl text-xs text-blue-700 dark:text-blue-300">
        <AlertCircle size={15} className="shrink-0 mt-0.5 text-blue-500" />
        <p className="leading-relaxed">
          <span className="font-semibold text-blue-900 dark:text-blue-200">Industry-aware & backend enforced.</span>{' '}
          Org View shows only workflows applicable to each organization's industry.
          Plan entitlement and explicit assignment are both required for active execution.
        </p>
      </div>

      {error && (
        <div className="flex items-center gap-2 px-4 py-3 bg-red-500/10 border border-red-500/20 rounded-xl text-sm text-red-600 dark:text-red-400">
          <XCircle size={15} className="shrink-0" />{error}
          <button onClick={() => setError(null)} className="ml-auto text-red-400 hover:text-red-600">×</button>
        </div>
      )}

      {loading ? (
        <div className="flex items-center justify-center h-48 text-slate-400 text-sm">Loading assignments…</div>
      ) : catalog.length === 0 ? (
        <EmptyState icon={Layers} title="No workflows in catalog"
          description="Add workflows to the catalog before assigning them."
          action={<button onClick={() => navigate('/admin/workflows/catalog')} className="text-sm text-blue-600 hover:underline font-medium">Go to Workflow Catalog →</button>}
        />
      ) : orgs.length === 0 ? (
        <EmptyState icon={Building2} title="No organizations"
          description="Create organizations to start assigning workflows."
          action={<button onClick={() => navigate('/admin/organizations')} className="text-sm text-blue-600 hover:underline font-medium">Go to Organizations →</button>}
        />
      ) : viewMode === 'matrix' ? (
        <>
          {/* Search bar for matrix */}
          <div className="relative max-w-xs">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" />
            <input type="text" placeholder="Filter organizations…" value={search}
              onChange={e => setSearch(e.target.value)}
              className="w-full pl-9 pr-3 py-2 text-sm bg-white dark:bg-[#121826] border border-slate-200 dark:border-[#233048] text-slate-900 dark:text-white rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 placeholder-slate-400" />
          </div>
          <MatrixView
            catalog={catalog}
            orgs={orgs}
            assignmentMap={assignmentMap}
            catalogStats={catalogStats}
            filteredOrgs={filteredOrgs}
            pendingCells={pendingCells}
            onAssign={handleAssign}
            onRevoke={handleRevoke}
            navigate={navigate}
          />
        </>
      ) : selectedOrg ? (
        // Org-focused assignment view
        <OrgFocusView
          org={selectedOrg}
          api={api}
          assignments={assignments}
          onAssign={handleAssign}
          onRevoke={handleRevoke}
          pendingCells={pendingCells}
          onClose={() => setSelectedOrg(null)}
        />
      ) : (
        // Org list — pick an org to manage
        <>
          <div className="relative max-w-xs">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" />
            <input type="text" placeholder="Filter organizations…" value={search}
              onChange={e => setSearch(e.target.value)}
              className="w-full pl-9 pr-3 py-2 text-sm bg-white dark:bg-[#121826] border border-slate-200 dark:border-[#233048] text-slate-900 dark:text-white rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 placeholder-slate-400" />
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            {filteredOrgs.map(org => {
              const orgAssigned = assignments.filter(a => a.organization_id === org.id && a.status === 'active').length
              return (
                <button key={org.id} onClick={() => setSelectedOrg(org)}
                  className="bg-white dark:bg-[#121826] border border-slate-200 dark:border-[#233048] hover:border-blue-500/50 hover:shadow-sm rounded-2xl p-4 text-left flex items-center gap-3.5 transition-all group">
                  <div className="w-11 h-11 rounded-xl bg-blue-500/10 border border-blue-500/20 flex items-center justify-center shrink-0">
                    <span className="text-blue-600 dark:text-blue-400 text-sm font-bold">{(org.name || '?')[0].toUpperCase()}</span>
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-semibold text-slate-900 dark:text-white truncate">{org.name}</p>
                    <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                      {industryLabel(org.industry)}
                    </p>
                    <p className="text-xs text-slate-400 dark:text-slate-500 mt-0.5 font-medium">
                      {orgAssigned} workflow{orgAssigned !== 1 ? 's' : ''} assigned
                    </p>
                  </div>
                  <ChevronRight size={16} className="text-slate-300 dark:text-slate-600 group-hover:text-blue-500 transition-colors shrink-0" />
                </button>
              )
            })}
          </div>
        </>
      )}
    </div>
  )
}
