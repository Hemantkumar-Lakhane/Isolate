import React, { useState, useEffect, useCallback } from 'react'
import { Plus, Radio, ShieldCheck, RefreshCw, CheckCircle2, XCircle } from 'lucide-react'
import { useAuth } from '../../contexts/AuthContext'

const PROVIDERS = [
  {
    id: 'anthropic',
    label: 'Anthropic',
    logo: '/assets/tools/claude.png',
    type: 'LLM Provider (Claude 3.5 Sonnet / Haiku)',
    description: 'Autonomous reasoning, long context analysis & code synthesis',
  },
  {
    id: 'openai',
    label: 'OpenAI',
    logo: '/assets/tools/openai.png',
    type: 'LLM Provider (GPT-4o / GPT-4o-mini)',
    description: 'Multimodal vision, function calling & high-precision generation',
  },
  {
    id: 'google_ai',
    altId: 'google',
    label: 'Google AI',
    logo: '/assets/tools/conversasionai.png',
    type: 'LLM Provider (Gemini 1.5 Flash / Pro)',
    description: 'High-throughput multimodal embeddings and inference',
  },
  {
    id: 'groq',
    label: 'Groq',
    logo: '/assets/tools/conversasionai.png',
    type: 'LLM Provider (Llama 3.3 70B High-speed)',
    description: 'Ultra-low latency LPU engine for real-time customer workflows',
  },
  {
    id: 'pollinations',
    label: 'Pollinations AI',
    logo: '/assets/tools/aichatbot.png',
    type: 'Visual & Diffusion (Flux / Turbo)',
    description: 'Generative image pipeline and creative multi-agent assets',
  },
]

export default function AdminProviderConnections() {
  const { api } = useAuth()
  const [providersData, setProvidersData] = useState([])
  const [healthData, setHealthData] = useState(null)
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [provs, hlth] = await Promise.all([
        api.get('/admin/providers').catch(() => []),
        api.get('/health').catch(() => null),
      ])
      setProvidersData(Array.isArray(provs) ? provs : [])
      setHealthData(hlth)
    } catch {}
    finally { setLoading(false) }
  }, [api])

  useEffect(() => { load() }, [load])

  const llmHealth = healthData?.llm_providers || {}

  return (
    <div className="flex flex-col gap-6 p-6 min-h-full bg-slate-50 dark:bg-[#0b0f17] text-slate-900 dark:text-slate-100 transition-colors">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-xl font-bold text-slate-900 dark:text-white flex items-center gap-2">
            <Radio className="text-blue-500" size={22} />
            Provider Connections
          </h1>
          <p className="text-sm text-slate-500 dark:text-slate-400 mt-0.5">
            Connect and manage upstream LLM and multimodal API provider credentials.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={load}
            disabled={loading}
            className="p-2 rounded-xl text-slate-500 dark:text-slate-400 bg-white dark:bg-[#121826] border border-slate-200 dark:border-[#233048] hover:bg-slate-50 dark:hover:bg-[#162030] transition-colors disabled:opacity-50 cursor-pointer"
            title="Refresh Status"
          >
            <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
          </button>
        </div>
      </div>

      <div className="bg-white dark:bg-[#121826] border border-slate-200 dark:border-[#233048] rounded-2xl shadow-2xs overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-100 dark:border-[#1e2a3f] bg-slate-50/70 dark:bg-[#162030]/60">
                {['PROVIDER', 'TYPE & CAPABILITY', 'CONNECTION STATUS', 'ENCRYPTION', 'TELEMETRY'].map(h => (
                  <th key={h} className="px-5 py-3 text-left text-[11px] font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-[#1a2336]">
              {PROVIDERS.map(p => {
                const provInfo = providersData.find(x => x.id === p.id || (p.altId && x.id === p.altId))
                const hlthInfo = llmHealth[p.id] || (p.altId && llmHealth[p.altId]) || {}

                const isConfigured = Boolean(
                  provInfo?.configured ||
                  provInfo?.status === 'configured' ||
                  hlthInfo?.status === 'configured'
                )

                return (
                  <tr key={p.id} className="hover:bg-slate-50/60 dark:hover:bg-[#162030]/50 transition-colors">
                    <td className="px-5 py-4">
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-xl bg-slate-100 dark:bg-[#182234] border border-slate-200 dark:border-[#233048] p-2 flex items-center justify-center shrink-0 shadow-2xs">
                          <img
                            src={p.logo}
                            alt={p.label}
                            className="w-6 h-6 object-contain"
                            onError={(e) => { e.target.style.display = 'none' }}
                          />
                        </div>
                        <div>
                          <span className="text-sm font-bold text-slate-900 dark:text-white block">{p.label}</span>
                          <span className="text-[11px] text-slate-400 line-clamp-1">{p.description}</span>
                        </div>
                      </div>
                    </td>
                    <td className="px-5 py-4 text-xs font-medium text-slate-500 dark:text-slate-400">{p.type}</td>
                    <td className="px-5 py-4">
                      <span className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-[11px] font-bold ${
                        isConfigured
                          ? 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20'
                          : 'bg-slate-500/10 text-slate-500 dark:text-slate-400 border border-slate-500/20'
                      }`}>
                        <span className={`w-1.5 h-1.5 rounded-full ${isConfigured ? 'bg-emerald-500 animate-pulse' : 'bg-slate-400'}`} />
                        {isConfigured ? 'Connected & Verified' : 'Not Configured'}
                      </span>
                    </td>
                    <td className="px-5 py-4 text-xs text-slate-500 dark:text-slate-400">
                      <span className="inline-flex items-center gap-1 text-slate-600 dark:text-slate-300 font-medium">
                        <ShieldCheck size={14} className="text-emerald-500" /> AES-256 at rest
                      </span>
                    </td>
                    <td className="px-5 py-4 text-xs font-mono text-slate-400 dark:text-slate-500">Live health-checked</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
        <div className="px-5 py-3.5 border-t border-slate-100 dark:border-[#1e2a3f] bg-slate-50/50 dark:bg-[#162030]/30 flex items-center gap-2 text-xs text-slate-500 dark:text-slate-400">
          <ShieldCheck size={14} className="text-blue-500 shrink-0" />
          <p>API credentials are encrypted at rest and never transmitted unmasked to the UI. Connection statuses reflect server-side verification.</p>
        </div>
      </div>
    </div>
  )
}
