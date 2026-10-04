// frontend/src/pages/client/ModelSettings.jsx
// Shows current model assignments per agent and lets client override per-agent models.

import { useState, useEffect, useCallback } from 'react'
import { useAuth } from '../../contexts/AuthContext'
import {
  Card, Button, Select, Alert, Spinner, Badge, Modal, StatCard
} from '../../components/ui'
import { fmtCost, AGENT_ICONS, AGENT_LABELS, AGENT_DESCRIPTIONS, TIER_COLORS, TIER_LABELS, TIER_DESCRIPTIONS, PROVIDER_COLORS, PROVIDER_LABELS } from '../../utils/helpers'

// ── Model card for an agent ────────────────────────────────────────────────────
function AgentModelCard({ agentKey, defaultTier, currentOverride, allModels, onSave }) {
  const [editing,  setEditing]  = useState(false)
  const [selected, setSelected] = useState(currentOverride || '')

  const Icon = AGENT_ICONS[agentKey]
  const label = AGENT_LABELS[agentKey] || agentKey
  const desc  = AGENT_DESCRIPTIONS[agentKey] || ''
  const tierCls = TIER_COLORS[defaultTier] || 'text-gray-400 bg-gray-800 border-gray-700'

const flatModels = Object.entries(allModels).flatMap(([provider, models]) => {
  // Add this guard clause:
  if (!Array.isArray(models)) return []; 
  
  return models.map(m => ({ value: m.id, label: `${m.label} [${provider}]`, provider }));
});

  const handleSave = async () => {
    await onSave(agentKey, selected || null)
    setEditing(false)
  }

  return (
    <div className="bg-gray-800/50 border border-gray-700/50 rounded-xl p-4">
      <div className="flex items-start gap-3 mb-3">
        <span className="text-2xl flex-shrink-0"><Icon className="w-6 h-6" /></span>
        <div className="flex-1 min-w-0">
          <div className="text-sm font-semibold text-white">{label}</div>
          <div className="text-xs text-gray-500 mt-0.5 leading-snug">{desc}</div>
        </div>
        <span className={`px-2 py-0.5 rounded text-xs border font-mono ${tierCls}`}>
          {TIER_LABELS[defaultTier] || defaultTier}
        </span>
      </div>

      {/* Current model */}
      <div className="text-xs text-gray-600 mb-1">Current model</div>
      {currentOverride ? (
        <div className="flex items-center gap-2 mb-3">
          <span className="text-xs text-blue-300 font-mono bg-blue-900/20 border border-blue-800/40 rounded px-2 py-1 flex-1 truncate">
            {currentOverride.split('/').pop()}
          </span>
          <span className="text-[10px] text-blue-400 flex-shrink-0">override</span>
        </div>
      ) : (
        <div className="text-xs text-gray-400 mb-3 font-mono">
          System default ({defaultTier} tier)
        </div>
      )}

      {editing ? (
        <div className="space-y-2">
          <select
            value={selected}
            onChange={e => setSelected(e.target.value)}
            className="w-full bg-gray-800 border border-gray-600 rounded px-2 py-1.5 text-white text-xs focus:outline-none focus:ring-1 focus:ring-blue-500"
          >
            <option value="">— use system default —</option>
            {flatModels.map(m => (
              <option key={`${m.provider}-${m.value}`} value={m.value}>{m.label}</option>
            ))}
          </select>
          <div className="flex gap-2">
            <Button size="xs" variant="success" onClick={handleSave}>Save</Button>
            <Button size="xs" variant="ghost"   onClick={() => { setEditing(false); setSelected(currentOverride || '') }}>Cancel</Button>
          </div>
        </div>
      ) : (
        <Button size="xs" variant="ghost" onClick={() => setEditing(true)} className="w-full">
          ✏️ {currentOverride ? 'Change' : 'Override'} Model
        </Button>
      )}
    </div>
  )
}

// ── Main ModelSettings ─────────────────────────────────────────────────────────
export default function ModelSettings() {
  const { user, api }  = useAuth()
  const [modelsConfig, setModelsConfig] = useState(null)
  const [tenant,       setTenant]       = useState(null)
  const [healthData,   setHealthData]   = useState(null)
  const [loading,  setLoading]  = useState(true)
  const [saving,   setSaving]   = useState(false)
  const [error,    setError]    = useState('')
  const [success,  setSuccess]  = useState('')

  const tenantId = user?.tenant_id

    const load = useCallback(async () => {
    try {
      const [mc, t, health] = await Promise.all([
        api.get('/config/models'),
        tenantId ? api.get(`/tenants/${tenantId}`) : Promise.resolve(null),
        api.get('/health').catch(() => null),
      ])
      setModelsConfig(mc)
      setTenant(t)
      setHealthData(health)
      setError('')
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [api, tenantId])

  useEffect(() => { load() }, [load])

  const llmOverrides = tenant?.config?.llm_overrides || {}
  const agentDefaults = modelsConfig?.agent_defaults || {}
  const taskModels    = modelsConfig?.task_models    || {}
  const allModels     = modelsConfig?.all_available_models || {}
  const costRates     = modelsConfig?.cost_rates || {}

  const handleSaveOverride = async (agentKey, modelId) => {
    setSaving(true); setError(''); setSuccess('')
    try {
      const newOverrides = { ...llmOverrides, [agentKey]: modelId || null }
      await api.put(`/tenants/${tenantId}/config`, {
        config: { ...tenant.config, llm_overrides: newOverrides }
      })
      // Optimistic update
      setTenant(prev => ({
        ...prev,
        config: { ...prev.config, llm_overrides: newOverrides }
      }))
      setSuccess(`Updated model for ${AGENT_LABELS[agentKey] || agentKey}`)
      setTimeout(() => setSuccess(''), 3000)
    } catch (err) {
      setError(err.message)
    } finally {
      setSaving(false)
    }
  }

  if (loading) return <div className="flex items-center justify-center h-64"><Spinner size="lg" /></div>

  const agents = Object.entries(agentDefaults).filter(([k]) => k !== '_comment')

  // Cost summary for the tier defaults
  const getCostForTier = (tier) => {
    const model = taskModels[tier]?.model
    const rates = costRates[model]
    if (!rates) return null
    return { input: rates.input, output: rates.output, model }
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-xl font-bold text-white">🤖 Model Settings</h1>
          <p className="text-gray-400 text-xs mt-0.5">
            Configure which LLM each agent uses · overrides apply to your tenant only
          </p>
        </div>
        <Button size="sm" variant="ghost" onClick={load}>↻ Refresh</Button>
      </div>

      {error   && <Alert type="error"   onClose={() => setError('')}>{error}</Alert>}
      {success && <Alert type="success" onClose={() => setSuccess('')}>{success}</Alert>}
      {/* API Key Status */}
      {healthData?.llm_providers && (
        <Card title="API Key Status">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {Object.entries(healthData.llm_providers).map(([provider, info]) => (
              <div key={provider} className={`rounded-xl border p-3 ${
                info.status === 'configured'
                  ? 'bg-green-900/10 border-green-700/30'
                  : 'bg-red-900/10 border-red-700/30'
              }`}>
                <div className={`text-xs font-bold mb-1 ${PROVIDER_COLORS[provider] || 'text-gray-400'}`}>
                  {PROVIDER_LABELS[provider] || provider}
                </div>
                <div className={`text-xs font-mono mb-1 ${
                  info.status === 'configured' ? 'text-green-400' : 'text-red-400'
                }`}>
                  {info.status === 'configured' ? `✓ ${info.key_preview}` : '✗ Not configured'}
                </div>
                {info.recommended_for && (
                  <div className="text-[10px] text-gray-600 leading-tight">{info.recommended_for}</div>
                )}
                {info.tool_calling !== undefined && (
                  <div className={`text-[10px] mt-1 ${info.tool_calling ? 'text-blue-400' : 'text-gray-600'}`}>
                    {info.tool_calling ? '🔧 Tool calling' : '⚠ No tools'}
                  </div>
                )}
              </div>
            ))}
          </div>
          {Object.values(healthData.llm_providers).every(p => p.status !== 'configured') && (
            <div className="mt-3 p-3 bg-red-900/20 border border-red-700/30 rounded-lg text-xs text-red-300">
              ⚠ No API keys configured. Add keys to your .env file and restart the server.
            </div>
          )}
        </Card>
      )}
      {/* Tier overview */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {['heavy', 'fast', 'mini', 'balanced'].map(tier => {
          const info  = taskModels[tier] || {}
          const costs = getCostForTier(tier)
          return (
            <Card key={tier} className="py-3">
              <div className={`text-xs font-bold mb-1 ${TIER_COLORS[tier]?.split(' ')[0] || 'text-gray-400'}`}>
                {TIER_LABELS[tier]}
              </div>
              <div className="text-xs text-gray-400 font-mono truncate">{info.model?.split('/').pop()}</div>
              {costs && (
                <div className="text-[10px] text-gray-600 mt-1">
                  ${costs.input}/M in · ${costs.output}/M out
                </div>
              )}
              <div className="text-[10px] text-gray-600 mt-0.5 leading-snug">{TIER_DESCRIPTIONS[tier]}</div>
            </Card>
          )
        })}
      </div>

      {/* Per-agent model cards */}
      <Card title="Agent Model Assignments">
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {agents.map(([agentKey, agentConf]) => {
            if (agentKey === '_comment') return null
            return (
              <AgentModelCard
                key={agentKey}
                agentKey={agentKey}
                defaultTier={agentConf.tier}
                currentOverride={llmOverrides[agentKey] || null}
                allModels={allModels}
                onSave={handleSaveOverride}
              />
            )
          })}
        </div>
      </Card>

      {/* All available models reference */}
      <Card title="All Available Models" action={
        <span className="text-xs text-gray-500">{Object.values(allModels).flat().length} models</span>
      }>
        <div className="space-y-4">
          {Object.entries(allModels)
            .filter(([, models]) => Array.isArray(models))
            .map(([provider, models]) => {
  const colCls = PROVIDER_COLORS[provider] || 'text-gray-400';
            return (
              <div key={provider}>
                <div className={`text-xs font-bold mb-2 uppercase tracking-wider ${colCls}`}>{provider}</div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                  {models.map(m => {
                    const rates = costRates[m.id]
                    return (
                      <div key={`${provider}-${m.id}`} className="flex items-center justify-between bg-gray-800/40 rounded-lg px-3 py-2">
                        <div className="min-w-0">
                          <div className="text-sm text-white font-medium truncate">{m.label}</div>
                          <div className="text-xs text-gray-600 font-mono truncate">{m.id.split('/').pop()}</div>
                        </div>
                        <div className="text-right flex-shrink-0 ml-3">
                          {rates ? (
                            <div className="text-[10px] text-gray-500">
                              <div className="text-green-400">${rates.input}/M</div>
                              <div className="text-blue-400">${rates.output}/M</div>
                            </div>
                          ) : (
                            <span className="text-[10px] text-gray-600">—</span>
                          )}
                        </div>
                      </div>
                    )
                  })}
                </div>
              </div>
            )
          })}
        </div>
      </Card>
    </div>
  )
}