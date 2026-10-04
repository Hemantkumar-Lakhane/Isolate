// frontend/src/pages/client/EvidencePage.jsx
// Matches Figma: Evidence — audit trail of AI recommendations and actions

import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { FileSearch, Search } from 'lucide-react'
import { useAuth } from '../../contexts/AuthContext'
import { timeAgo, fmtCost } from '../../utils/helpers'

const POLL_MS = 15000

// ── Modal ─────────────────────────────────────────────────────────────────────
function Modal({ open, onClose, title, children }) {
  useEffect(() => {
    if (!open) return
    const h = e => { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', h)
    return () => document.removeEventListener('keydown', h)
  }, [open, onClose])
  if (!open) return null
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/40" onClick={onClose} />
      <div className="relative bg-white rounded-xl shadow-xl w-full max-w-2xl max-h-[90vh] flex flex-col border border-gray-200">
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
          <h2 className="text-base font-bold text-gray-900">{title}</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-xl leading-none">×</button>
        </div>
        <div className="p-5 overflow-y-auto flex-1">{children}</div>
      </div>
    </div>
  )
}

// ── Evidence Detail Modal ─────────────────────────────────────────────────────
function EvidenceModal({ artifact, open, onClose, api }) {
  const navigate = useNavigate()
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!open || !artifact) return
    setLoading(true)
    api.get(`/evidence/${encodeURIComponent(artifact.filename)}/content`)
      .then(setData).catch(() => {}).finally(() => setLoading(false))
  }, [open, artifact?.filename])

  const d = data?.data || {}
  const outcome = d.outcome || {}

  return (
    <Modal open={open} onClose={onClose} title={artifact?.filename || 'Evidence'}>
      {loading ? (
        <div className="flex items-center justify-center h-40 text-gray-400">Loading…</div>
      ) : (
        <div className="space-y-4">
          {/* Metrics */}
          <div className="grid grid-cols-4 gap-3">
            {[
              { label: 'Status', value: d.status || '—' },
              { label: 'Total Cost', value: d.total_cost_usd ? fmtCost(d.total_cost_usd) : '—' },
              { label: 'Tokens In', value: d.total_tokens_in?.toLocaleString() || '—' },
              { label: 'Workflow', value: d.workflow_name || artifact?.workflow_name || '—' },
            ].map(({ label, value }) => (
              <div key={label} className="bg-gray-50 border border-gray-100 rounded-lg p-3">
                <p className="text-[10px] text-gray-500 mb-1 uppercase tracking-wider">{label}</p>
                <p className="text-sm font-semibold text-gray-900 truncate">{value}</p>
              </div>
            ))}
          </div>

          {/* Situation summary */}
          {outcome.situation_summary && (
            <div className="p-3 bg-blue-50 border border-blue-100 rounded-lg">
              <p className="text-xs font-semibold text-blue-700 mb-1">Situation Analysis</p>
              <p className="text-sm text-gray-700">{outcome.situation_summary}</p>
            </div>
          )}

          {/* Agent runs */}
          {(d.agent_runs || []).length > 0 && (
            <div>
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">Agent Pipeline</p>
              <div className="space-y-2">
                {d.agent_runs.map((r, i) => (
                  <div key={i} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg border border-gray-100">
                    <div>
                      <p className="text-sm font-medium text-gray-900">{r.agent_type || r.node_id}</p>
                      <p className="text-xs text-gray-400 font-mono">{r.node_id}</p>
                    </div>
                    <div className="text-right text-xs text-gray-500">
                      <span className={r.status === 'success' ? 'text-green-600 font-semibold' : 'text-red-500 font-semibold'}>
                        {r.status}
                      </span>
                      {r.cost_usd > 0 && <p className="text-amber-600">{fmtCost(r.cost_usd)}</p>}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="flex gap-2 pt-2 border-t border-gray-100">
            {d.run_id && (
              <button onClick={() => { onClose(); navigate(`/workflows/${d.run_id}`) }}
                className="px-4 py-2 bg-blue-600 text-white text-sm font-semibold rounded-lg hover:bg-blue-700 transition-colors">
                View Full Run →
              </button>
            )}
            <button onClick={onClose} className="px-4 py-2 border border-gray-200 text-gray-600 text-sm font-semibold rounded-lg hover:bg-gray-50 transition-colors">Close</button>
          </div>
        </div>
      )}
    </Modal>
  )
}

// ── Main ──────────────────────────────────────────────────────────────────────
export default function EvidencePage() {
  const { api }                   = useAuth()
  const [artifacts, setArtifacts] = useState([])
  const [loading,   setLoading]   = useState(true)
  const [search,    setSearch]    = useState('')
  const [selected,  setSelected]  = useState(null)

  const load = useCallback(async () => {
    try {
      const data = await api.get('/evidence')
      setArtifacts(Array.isArray(data) ? data : [])
    } finally { setLoading(false) }
  }, [api])

  useEffect(() => {
    load()
    const t = setInterval(load, POLL_MS)
    return () => clearInterval(t)
  }, [load])

  const filtered = artifacts.filter(a =>
    !search ||
    a.filename.toLowerCase().includes(search.toLowerCase()) ||
    (a.workflow_name || '').toLowerCase().includes(search.toLowerCase())
  )

  const COLS = ['TIMESTAMP','WORKFLOW','STEP','AGENT / MODEL','ACTION TAKEN','SOURCE']

  return (
    <div className="p-6 bg-gray-50 min-h-full">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Evidence</h1>
        <p className="text-sm text-gray-500 mt-0.5">Audit trail of AI recommendations and actions taken</p>
      </div>

      {/* Search + count */}
      <div className="flex items-center justify-between mb-4 gap-3">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="Search evidence records..."
            className="pl-9 pr-4 py-2 border border-gray-200 rounded-lg text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-500 w-64"
          />
        </div>
        <span className="text-sm text-gray-400">{filtered.length} records</span>
      </div>

      {/* Table */}
      <div className="bg-white border border-gray-200 rounded-xl shadow-sm overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="border-b border-gray-100">
              {COLS.map(c => (
                <th key={c} className="px-5 py-3.5 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">{c}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={6} className="px-5 py-8 text-center text-sm text-gray-400">Loading…</td></tr>
            ) : filtered.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-5 py-16 text-center">
                  <div className="flex flex-col items-center gap-3">
                    <FileSearch className="w-10 h-10 text-gray-300" />
                    <div>
                      <p className="text-sm font-medium text-gray-500">No evidence records</p>
                      <p className="text-xs text-gray-400 mt-1">
                        Evidence will appear here when workflows run<br />and produce AI-driven recommendations and actions.
                      </p>
                    </div>
                  </div>
                </td>
              </tr>
            ) : (
              filtered.map((a, i) => (
                <tr key={a.filename} onClick={() => setSelected(a)}
                  className="border-b border-gray-50 hover:bg-gray-50 cursor-pointer transition-colors last:border-0">
                  <td className="px-5 py-3.5 text-sm text-gray-500 font-mono">{timeAgo(a.created)}</td>
                  <td className="px-5 py-3.5 text-sm text-gray-900">{a.workflow_name || '—'}</td>
                  <td className="px-5 py-3.5 text-sm text-gray-500 font-mono text-xs">{a.filename.slice(0,20)}</td>
                  <td className="px-5 py-3.5 text-sm text-gray-500">—</td>
                  <td className="px-5 py-3.5 text-sm text-gray-500">
                    {a.status ? <span className={`font-semibold ${a.status === 'completed' ? 'text-green-600' : a.status === 'failed' ? 'text-red-500' : 'text-gray-600'}`}>{a.status}</span> : '—'}
                  </td>
                  <td className="px-5 py-3.5 text-xs">
                    <span className={`px-2 py-0.5 rounded-full font-medium ${a.type === 'epi' ? 'bg-green-50 text-green-700 border border-green-200' : 'bg-blue-50 text-blue-700 border border-blue-200'}`}>
                      {a.type === 'epi' ? 'EPI Signed' : 'Summary'}
                    </span>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      <EvidenceModal artifact={selected} open={!!selected} onClose={() => setSelected(null)} api={api} />
    </div>
  )
}
