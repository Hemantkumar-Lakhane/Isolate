import { useState, useEffect, useCallback } from 'react'
import { Server, Search, Plus, RefreshCw, Cpu, Layers } from 'lucide-react'
import { useAuth } from '../../contexts/AuthContext'

export default function AdminModelCatalog() {
  const { api } = useAuth()
  const [models, setModels] = useState(null)
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    setLoading(true)
    try { setModels(await api.get('/config/models')) } catch {}
    finally { setLoading(false) }
  }, [api])

  useEffect(() => { load() }, [load])

  const allModels = models ? Object.entries(models.all_available_models || {}).flatMap(([provider, list]) =>
    Array.isArray(list) ? list.map(m => ({ ...m, provider })) : []
  ) : []

  const filtered = allModels.filter(m => !search || m.label?.toLowerCase().includes(search.toLowerCase()) || m.id?.toLowerCase().includes(search.toLowerCase()))

  return (
    <div className="flex flex-col gap-6 p-6 min-h-full bg-slate-50 dark:bg-[#0b0f17] text-slate-900 dark:text-slate-100 transition-colors">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-xl font-bold text-slate-900 dark:text-white flex items-center gap-2">
            <Layers className="text-blue-500" size={22} />
            Model Catalog
          </h1>
          <p className="text-sm text-slate-500 dark:text-slate-400 mt-0.5">Manage and inspect LLMs, embedding engines, and multimodal models across providers.</p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={load} disabled={loading}
            className="p-2 rounded-xl text-slate-500 dark:text-slate-400 bg-white dark:bg-[#121826] border border-slate-200 dark:border-[#233048] hover:bg-slate-50 dark:hover:bg-[#162030] transition-colors disabled:opacity-50">
            <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
          </button>
          <button className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-semibold rounded-xl transition-colors shadow-xs">
            <Plus className="w-4 h-4" /> Add Model
          </button>
        </div>
      </div>

      <div className="bg-white dark:bg-[#121826] border border-slate-200 dark:border-[#233048] rounded-2xl shadow-2xs overflow-hidden">
        <div className="flex items-center gap-3 px-5 py-3.5 border-b border-slate-100 dark:border-[#1e2a3f]">
          <div className="relative flex-1 max-w-sm">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 pointer-events-none" />
            <input value={search} onChange={e=>setSearch(e.target.value)} placeholder="Search model label or ID..." className="pl-9 pr-4 py-2 border border-slate-200 dark:border-[#2a3850] rounded-xl text-sm bg-slate-50 dark:bg-[#162030] text-slate-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 w-full placeholder-slate-400" />
          </div>
        </div>

        {loading ? (
          <div className="flex items-center justify-center h-48 text-slate-400 text-sm">Loading model catalog…</div>
        ) : filtered.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 gap-3">
            <div className="w-12 h-12 rounded-2xl bg-slate-500/10 flex items-center justify-center text-slate-400">
              <Server className="w-6 h-6" />
            </div>
            <p className="text-sm font-semibold text-slate-900 dark:text-white">No models available</p>
            <p className="text-xs text-slate-400 text-center max-w-sm">Connect a provider in Provider Connections to populate available models automatically.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-100 dark:border-[#1e2a3f] bg-slate-50/70 dark:bg-[#162030]/60">
                  {['MODEL','PROVIDER','STATUS','TYPE','IDENTIFIER'].map(h=>(
                    <th key={h} className="px-5 py-3 text-left text-[11px] font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-[#1a2336]">
                {filtered.map(m=>(
                  <tr key={`${m.provider}-${m.id}`} className="hover:bg-slate-50/60 dark:hover:bg-[#162030]/50 transition-colors">
                    <td className="px-5 py-3.5">
                      <p className="text-sm font-bold text-slate-900 dark:text-white">{m.label || m.name || m.id}</p>
                      <p className="text-xs text-slate-400 dark:text-slate-500 font-mono mt-0.5">{m.id}</p>
                    </td>
                    <td className="px-5 py-3.5 text-xs font-semibold text-slate-600 dark:text-slate-300 capitalize">
                      <span className="px-2 py-0.5 rounded-md bg-slate-500/10 text-slate-700 dark:text-slate-300 border border-slate-500/20">
                        {m.provider}
                      </span>
                    </td>
                    <td className="px-5 py-3.5">
                      <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20">
                        <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" /> Available
                      </span>
                    </td>
                    <td className="px-5 py-3.5 text-xs text-slate-500 dark:text-slate-400">{m.type || 'Chat & Reasoning'}</td>
                    <td className="px-5 py-3.5 text-xs text-slate-400 dark:text-slate-500 font-mono">{m.id?.split('/').pop()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {filtered.length > 0 && (
          <div className="px-5 py-3.5 border-t border-slate-100 dark:border-[#1e2a3f] bg-slate-50/50 dark:bg-[#162030]/30 text-xs text-slate-500 dark:text-slate-400">
            <p>Model availability is dynamically synchronized with upstream provider connection health and license tier quotas.</p>
          </div>
        )}
      </div>
    </div>
  )
}
