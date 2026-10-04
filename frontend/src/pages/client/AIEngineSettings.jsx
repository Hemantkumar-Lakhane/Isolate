// frontend/src/pages/client/AIEngine.jsx
// Matches screenshot: AI Engine Settings

import { useState, useEffect, useCallback } from 'react'
import { useAuth } from '../../contexts/AuthContext'
import { AlertCircle, Cpu, Bot, Zap, Wrench } from 'lucide-react'

const CAPABILITIES = [
  {
    id: 'ml',
    icon: <Cpu className="w-5 h-5 text-blue-500" />,
    bg: 'bg-blue-50',
    name: 'ML / Predictive Model',
    desc: 'Lead Assessment ML POC — configuration required before deployment.',
    defaultStatus: 'poc',
  },
  {
    id: 'llm',
    icon: <Bot className="w-5 h-5 text-purple-500" />,
    bg: 'bg-purple-50',
    name: 'LLM Agent',
    desc: 'Select an LLM provider and configure agent parameters once the backend is connected.',
    defaultStatus: 'not_configured',
  },
  {
    id: 'rule',
    icon: <Zap className="w-5 h-5 text-amber-500" />,
    bg: 'bg-amber-50',
    name: 'Rule Engine',
    desc: 'Define business rules and policies for deterministic routing.',
    defaultStatus: 'not_configured',
  },
  {
    id: 'api',
    icon: <Wrench className="w-5 h-5 text-green-500" />,
    bg: 'bg-green-50',
    name: 'API / Integration Tools',
    desc: 'Connect external tools once integrations are set up.',
    defaultStatus: 'not_configured',
  },
]

function StatusLabel({ type }) {
  if (type === 'poc')            return <span className="text-sm text-gray-400">POC in development</span>
  if (type === 'not_configured') return <span className="text-sm text-gray-400">Not configured</span>
  if (type === 'configured')     return <span className="text-sm font-semibold text-green-600">Configured</span>
  return null
}

export default function AIEngine() {
  const { api }           = useAuth()
  const [health,  setHealth]  = useState(null)
  const [connected, setConnected] = useState(false)

  const load = useCallback(async () => {
    try {
      const h = await api.get('/health')
      setHealth(h)
      const anyLLM = h?.llm_providers && Object.values(h.llm_providers).some(p => p.status === 'configured')
      setConnected(!!anyLLM)
    } catch { /* backend not reachable */ }
  }, [api])

  useEffect(() => { load() }, [load])

  // Enrich capability statuses from health data
  const capabilities = CAPABILITIES.map(cap => {
    if (cap.id === 'llm' && connected) return { ...cap, defaultStatus: 'configured' }
    return cap
  })

  return (
    <div className="p-6 bg-gray-50 min-h-full">
      {/* Header */}
      <div className="mb-5">
        <h1 className="text-2xl font-bold text-gray-900">AI Engine Settings</h1>
        <p className="text-sm text-gray-500 mt-0.5">Configure AI capabilities, models, and orchestration behaviour</p>
      </div>

      {/* Connection banner */}
      {!connected && (
        <div className="mb-5 flex items-start gap-3 p-4 bg-amber-50 border border-amber-200 rounded-xl">
          <AlertCircle className="w-5 h-5 text-amber-500 flex-shrink-0 mt-0.5" />
          <div>
            <p className="text-sm font-semibold text-amber-700">AI Engine not connected</p>
            <p className="text-sm text-amber-600 mt-0.5">
              AI Engine configuration will be available once the SMBFlow backend API is connected and the engine is provisioned.
            </p>
          </div>
        </div>
      )}

      <div className="space-y-4 max-w-2xl mx-auto">
        {/* Capability Status */}
        <div className="bg-white border border-gray-200 rounded-xl shadow-sm overflow-hidden">
          <div className="px-5 py-4 border-b border-gray-100">
            <h2 className="text-sm font-bold text-gray-900">Capability Status</h2>
          </div>
          <div className="divide-y divide-gray-50">
            {capabilities.map(cap => (
              <div key={cap.id} className="flex items-center gap-4 px-5 py-4">
                <div className={`w-9 h-9 rounded-lg ${cap.bg} flex items-center justify-center flex-shrink-0`}>
                  {cap.icon}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-semibold text-gray-900">{cap.name}</p>
                  <p className="text-xs text-gray-500 mt-0.5">{cap.desc}</p>
                </div>
                <div className="flex-shrink-0">
                  <StatusLabel type={cap.defaultStatus} />
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Orchestration Policy */}
        <div className="bg-white border border-gray-200 rounded-xl shadow-sm p-5">
          <h2 className="text-sm font-bold text-gray-900 mb-3">Orchestration Policy</h2>
          <p className="text-sm text-gray-500 leading-relaxed">
            Orchestration determines how SMBFlow routes tasks between capabilities. Policy configuration requires the AI Engine backend to be connected.
          </p>
          <p className="text-sm text-gray-400 italic mt-3">
            Orchestration settings will appear here once the AI Engine is connected.
          </p>
        </div>

        {/* Confidence Thresholds */}
        <div className="bg-white border border-gray-200 rounded-xl shadow-sm p-5">
          <h2 className="text-sm font-bold text-gray-900 mb-3">Confidence Thresholds</h2>
          <p className="text-sm text-gray-500 leading-relaxed">
            Set the minimum confidence score required before an action can proceed without human approval.
          </p>
          <p className="text-sm text-gray-400 italic mt-3">
            Threshold configuration requires the AI Engine to be connected.
          </p>
        </div>
      </div>
    </div>
  )
}
