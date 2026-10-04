// frontend/src/pages/client/AIEngine.jsx
// Configuration → AI Engine: card-based view matching Figma

import { useState, useEffect, useCallback } from 'react'
import { Bot, Cpu, Wrench, Zap } from 'lucide-react'
import { useAuth } from '../../contexts/AuthContext'

const ENGINE_CARDS = [
  {
    id: 'llm',
    icon: <Bot className="w-6 h-6 text-purple-600" />,
    bg: 'bg-purple-50',
    title: 'LLM Agent',
    desc: 'Language model agents for reasoning, summarization, recommendation, and conversation.',
  },
  {
    id: 'ml',
    icon: <Cpu className="w-6 h-6 text-blue-600" />,
    bg: 'bg-blue-50',
    title: 'ML / Predictive Model',
    desc: 'Trained models for scoring, classification, and prediction tasks.',
    badge: 'Under development',
    warning: 'Lead Assessment ML POC — configuration required before deployment.',
  },
  {
    id: 'rule',
    icon: <Zap className="w-6 h-6 text-amber-600" />,
    bg: 'bg-amber-50',
    title: 'Rule Engine',
    desc: 'Deterministic business logic and policy enforcement.',
  },
  {
    id: 'api',
    icon: <Wrench className="w-6 h-6 text-green-600" />,
    bg: 'bg-green-50',
    title: 'API / Integration Tool',
    desc: 'Connectors to external systems, APIs, and services.',
  },
]

const INNER_TABS = ['Agents', 'Models', 'Tools', 'Routing']

function StatusBadge({ type }) {
  if (type === 'configured')        return <span className="text-[11px] font-semibold text-green-700 bg-green-50 border border-green-200 px-2 py-0.5 rounded-full">Configured</span>
  if (type === 'not_configured')    return <span className="text-[11px] font-semibold text-gray-500 bg-gray-100 border border-gray-200 px-2 py-0.5 rounded-full">Not configured</span>
  if (type === 'under_development') return <span className="text-[11px] font-semibold text-blue-700 bg-blue-50 border border-blue-200 px-2 py-0.5 rounded-full">Under development</span>
  return null
}

export default function AIEngine() {
  const { api }        = useAuth()
  const [health,       setHealth]       = useState(null)
  const [models,       setModels]       = useState(null)
  const [innerTab,     setInnerTab]     = useState('Agents')
  const [loading,      setLoading]      = useState(true)
  const [engineStatus, setEngineStatus] = useState('not_connected')

  const load = useCallback(async () => {
    try {
      const [h, m] = await Promise.all([
        api.get('/health').catch(() => null),
        api.get('/config/models').catch(() => null),
      ])
      setHealth(h)
      setModels(m)
      if (h?.llm_providers) {
        const any = Object.values(h.llm_providers).some(p => p.status === 'configured')
        setEngineStatus(any ? 'connected' : 'not_connected')
      }
    } finally { setLoading(false) }
  }, [api])

  useEffect(() => { load() }, [load])

  const enrichedCards = ENGINE_CARDS.map(card => {
    if (card.id === 'llm') return { ...card, status: engineStatus === 'connected' ? 'configured' : 'not_configured' }
    if (card.id === 'ml')  return { ...card, status: 'under_development' }
    return { ...card, status: 'not_configured' }
  })

  const agentDefaults = models?.agent_defaults || {}
  const hasAgents = Object.keys(agentDefaults).filter(k => k !== '_comment').length > 0

  return (
    <div className="p-6 bg-gray-50 min-h-full">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">AI Engine</h1>
          <p className="text-sm text-gray-500 mt-0.5">Manage reusable agents, models, tools and orchestration routing</p>
        </div>
        <div className="flex items-center gap-2">
          <span className={`w-2 h-2 rounded-full ${engineStatus === 'connected' ? 'bg-green-500' : 'bg-gray-400'}`} />
          <span className={`text-sm font-medium ${engineStatus === 'connected' ? 'text-green-600' : 'text-red-500'}`}>
            Engine status: {engineStatus === 'connected' ? 'Connected' : 'Not connected'}
          </span>
        </div>
      </div>

      {/* Engine type cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        {enrichedCards.map(card => (
          <div key={card.id} className="bg-white border border-gray-200 rounded-xl p-5 shadow-sm">
            <div className={`w-10 h-10 rounded-xl ${card.bg} flex items-center justify-center mb-3`}>
              {card.icon}
            </div>
            <h3 className="text-sm font-bold text-gray-900 mb-1.5">{card.title}</h3>
            <p className="text-xs text-gray-500 leading-relaxed mb-3">{card.desc}</p>
            <StatusBadge type={card.status} />
            {card.warning && (
              <div className="mt-2 p-2 bg-amber-50 border border-amber-200 rounded-lg">
                <p className="text-[11px] text-amber-700 leading-relaxed">{card.warning}</p>
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Inner tabs panel */}
      <div className="bg-white border border-gray-200 rounded-xl shadow-sm overflow-hidden">
        <div className="flex border-b border-gray-100 px-1 pt-1">
          {INNER_TABS.map(tab => (
            <button key={tab} onClick={() => setInnerTab(tab)}
              className={`px-5 py-3 text-sm font-medium transition-colors border-b-2 -mb-px ${
                innerTab === tab ? 'border-blue-600 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-900'
              }`}>
              {tab}
            </button>
          ))}
        </div>

        <div className="p-6">
          {loading ? (
            <div className="flex items-center justify-center h-32 text-gray-400 text-sm">Loading…</div>
          ) : innerTab === 'Agents' && hasAgents ? (
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
              {Object.entries(agentDefaults).filter(([k]) => k !== '_comment').map(([key, conf]) => (
                <div key={key} className="p-4 border border-gray-100 rounded-xl bg-gray-50">
                  <p className="text-sm font-semibold text-gray-900 mb-1">{key.replace(/_/g,' ').replace(/\b\w/g,c=>c.toUpperCase())}</p>
                  <p className="text-xs text-gray-500">Tier: <span className="font-medium text-gray-700">{conf.tier || '—'}</span></p>
                </div>
              ))}
            </div>
          ) : innerTab === 'Models' && models?.task_models ? (
            <div className="space-y-3">
              {Object.entries(models.task_models).map(([tier, info]) => (
                <div key={tier} className="flex items-center justify-between p-3 border border-gray-100 rounded-xl bg-gray-50">
                  <div>
                    <p className="text-sm font-semibold text-gray-900 capitalize">{tier}</p>
                    <p className="text-xs text-gray-500 font-mono">{info.model?.split('/').pop()}</p>
                  </div>
                  <span className="text-xs font-medium text-green-600 bg-green-50 border border-green-200 px-2 py-0.5 rounded-full">Active</span>
                </div>
              ))}
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center h-32 gap-2">
              <Bot className="w-8 h-8 text-gray-300" />
              <p className="text-sm text-gray-400">No components configured</p>
              <p className="text-xs text-gray-400">Connect the AI Engine backend to discover and configure reusable agents, models, and tools.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
