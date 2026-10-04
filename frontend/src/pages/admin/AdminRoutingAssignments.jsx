// AdminRoutingAssignments — LLM Routing Configuration
import { useState, useEffect, useCallback } from 'react'
import { RefreshCw, XCircle, Save, AlertCircle, CheckCircle2, GitMerge, Cpu } from 'lucide-react'
import { useAuth } from '../../contexts/AuthContext'

const PROVIDER_OPTIONS = ['anthropic', 'openai', 'google_ai', 'groq', 'pollinations', '']

function ProviderSelect({ value, onChange, label }) {
  return (
    <div>
      {label && <p className="text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1.5">{label}</p>}
      <select
        value={value || ''}
        onChange={e => onChange(e.target.value)}
        className="w-full px-3 py-2 text-sm bg-white dark:bg-[#162030] border border-slate-200 dark:border-[#2a3850] text-slate-900 dark:text-white rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
      >
        <option value="">— Not set —</option>
        <option value="anthropic">Anthropic (Claude 3.5 Sonnet / Haiku)</option>
        <option value="openai">OpenAI (GPT-4o / GPT-4o-mini)</option>
        <option value="google_ai">Google AI (Gemini 1.5 Pro / Flash)</option>
        <option value="groq">Groq (Llama 3.3 70B Fast Inference)</option>
        <option value="pollinations">Pollinations AI (Flux / SDXL)</option>
      </select>
    </div>
  )
}

export default function AdminRoutingAssignments() {
  const { api } = useAuth()
  const [routing,  setRouting]  = useState(null)
  const [loading,  setLoading]  = useState(true)
  const [saving,   setSaving]   = useState(false)
  const [error,    setError]    = useState(null)
  const [success,  setSuccess]  = useState('')

  // Editable defaults
  const [defaults, setDefaults] = useState({
    primary_provider:  '',
    fallback_provider: '',
    image_provider:    '',
  })

  const load = useCallback(async () => {
    setLoading(true); setError(null)
    try {
      const d = await api.get('/admin/routing')
      setRouting(d)
      if (d?.current_defaults) {
        setDefaults({
          primary_provider:  d.current_defaults.primary_provider  || '',
          fallback_provider: d.current_defaults.fallback_provider || '',
          image_provider:    d.current_defaults.image_provider    || '',
        })
      }
    } catch (e) {
      setError(e?.response?.data?.detail || e.message || 'Failed to load routing config')
    } finally {
      setLoading(false)
    }
  }, [api])

  useEffect(() => { load() }, [load])

  async function save() {
    setSaving(true); setError(null); setSuccess('')
    try {
      const payload = {
        ...routing,
        current_defaults: defaults,
        note: null,
      }
      await api.patch('/admin/settings', { settings: { llm_routing: payload } })
      setSuccess('Routing configuration saved.')
      setTimeout(() => setSuccess(''), 3000)
      load()
    } catch (e) {
      setError(e?.response?.data?.detail || e.message || 'Save failed')
    } finally {
      setSaving(false)
    }
  }

  const hierarchy = routing?.hierarchy || []

  return (
    <div className="flex flex-col gap-6 p-6 min-h-full bg-slate-50 dark:bg-[#0b0f17] text-slate-900 dark:text-slate-100 transition-colors">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-xl font-bold text-slate-900 dark:text-white flex items-center gap-2">
            <Cpu className="text-blue-500" size={22} />
            Routing &amp; LLM Configuration
          </h1>
          <p className="text-sm text-slate-500 dark:text-slate-400 mt-0.5">
            Configure which AI providers handle platform-wide requests with failover routing.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={load} disabled={loading}
            className="p-2 rounded-xl text-slate-500 dark:text-slate-400 bg-white dark:bg-[#121826] border border-slate-200 dark:border-[#233048] hover:bg-slate-50 dark:hover:bg-[#162030] transition-colors disabled:opacity-50">
            <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
          </button>
          <button onClick={save} disabled={saving || loading}
            className="flex items-center gap-2 px-4 py-2 text-sm font-semibold text-white bg-blue-600 hover:bg-blue-700 rounded-xl transition-colors disabled:opacity-50 shadow-xs">
            <Save size={14} />
            {saving ? 'Saving…' : 'Save Routing'}
          </button>
        </div>
      </div>

      {error && (
        <div className="flex items-center gap-2 px-4 py-3 bg-red-500/10 border border-red-500/20 rounded-xl text-sm text-red-600 dark:text-red-400">
          <XCircle size={15} className="shrink-0" />{error}
        </div>
      )}
      {success && (
        <div className="flex items-center gap-2 px-4 py-3 bg-emerald-500/10 border border-emerald-500/20 rounded-xl text-sm text-emerald-600 dark:text-emerald-400">
          <CheckCircle2 size={15} className="shrink-0" />{success}
        </div>
      )}

      {loading ? (
        <div className="flex items-center justify-center h-48 text-slate-400 text-sm">Loading routing configuration…</div>
      ) : (
        <>
          {/* Assignment hierarchy */}
          {hierarchy.length > 0 && (
            <div className="bg-white dark:bg-[#121826] border border-slate-200 dark:border-[#233048] rounded-2xl p-5 shadow-2xs">
              <div className="flex items-center gap-2 mb-4">
                <GitMerge size={16} className="text-blue-500" />
                <h2 className="text-sm font-bold text-slate-900 dark:text-white">Assignment Hierarchy</h2>
              </div>
              <div className="flex items-center gap-2 flex-wrap text-xs text-slate-500 dark:text-slate-400 mb-4">
                {hierarchy.map((h, i) => (
                  <span key={h.level} className="flex items-center gap-2">
                    <span className="font-semibold text-slate-700 dark:text-slate-200 px-2 py-0.5 rounded-md bg-slate-100 dark:bg-[#162030]">{h.label}</span>
                    {i < hierarchy.length - 1 && <span className="text-slate-400">›</span>}
                  </span>
                ))}
              </div>
              <div className="space-y-2">
                {hierarchy.map(h => (
                  <div key={h.level} className="flex items-start gap-2 text-xs text-slate-500 dark:text-slate-400">
                    <span className="font-semibold text-slate-700 dark:text-slate-300 min-w-[160px]">{h.label}:</span>
                    <span>{h.description}</span>
                  </div>
                ))}
              </div>
              <div className="mt-4 flex items-start gap-2.5 px-3.5 py-3 bg-blue-500/10 border border-blue-500/20 rounded-xl">
                <AlertCircle size={14} className="text-blue-500 shrink-0 mt-0.5" />
                <p className="text-xs text-blue-700 dark:text-blue-300 leading-relaxed">
                  The most specific valid configuration applies. A workflow override takes precedence over an agent assignment, which takes precedence over the task default.
                </p>
              </div>
            </div>
          )}

          {/* Platform defaults editor */}
          <div className="bg-white dark:bg-[#121826] border border-slate-200 dark:border-[#233048] rounded-2xl p-5 shadow-2xs">
            <h2 className="text-sm font-bold text-slate-900 dark:text-white mb-4">Platform Default Providers</h2>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <ProviderSelect
                label="Primary LLM Provider"
                value={defaults.primary_provider}
                onChange={v => setDefaults(d => ({ ...d, primary_provider: v }))}
              />
              <ProviderSelect
                label="Fallback LLM Provider"
                value={defaults.fallback_provider}
                onChange={v => setDefaults(d => ({ ...d, fallback_provider: v }))}
              />
              <ProviderSelect
                label="Image Generation Provider"
                value={defaults.image_provider}
                onChange={v => setDefaults(d => ({ ...d, image_provider: v }))}
              />
            </div>
            {routing?.note && (
              <p className="text-xs text-slate-400 dark:text-slate-500 mt-4 italic">{routing.note}</p>
            )}
          </div>
        </>
      )}
    </div>
  )
}
