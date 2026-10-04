// frontend/src/pages/setup/ConnectionsPage.jsx
// ─────────────────────────────────────────────────────────────────────────────
// SMBFlow — Minimal, Clean Tool Integrations & Authentication
// Features:
//   • Minimal uncluttered layout with short, crisp descriptions
//   • 1-Click Google Workspace OAuth (Gmail, Calendar, Drive)
//   • Category filters: All, Communication, Marketing, Databases, CRM
//   • Instant live connection testing & AES Vault security
// ─────────────────────────────────────────────────────────────────────────────

import React, { useState, useEffect, useMemo } from 'react'
import {
  Plug, CheckCircle2, XCircle, AlertTriangle, RefreshCw, Settings, ShieldCheck,
  ExternalLink, Mail, Calendar, HardDrive, Sliders, Lock, Check, Loader2, Plus,
  Trash2, ArrowRight
} from 'lucide-react'
import { useAuth } from '../../contexts/AuthContext'

function ToolLogo({ name, className = 'w-5 h-5' }) {
  const [useFallback, setUseFallback] = useState(false)
  const toolName = (name || '').toLowerCase()

  const imgSrc = useMemo(() => {
    if (!toolName) return null
    if (toolName === 'sheets' || toolName === 'sheet') return '/assets/tools/sheet.png'
    if (toolName === 'google_workspace' || toolName === 'google_calendar') return '/assets/tools/calendar.png'
    return `/assets/tools/${toolName}.png`
  }, [toolName])

  useEffect(() => {
    setUseFallback(false)
  }, [toolName])

  const svgFallbacks = {
    gmail: (
      <svg className={className} viewBox="0 0 24 24" fill="none">
        <path d="M22 6C22 4.9 21.1 4 20 4H4C2.9 4 2 4.9 2 6V18C2 19.1 2.9 20 4 20H20C21.1 20 22 19.1 22 18V6Z" fill="#EA4335" fillOpacity="0.15" />
        <path d="M20 4H4C2.9 4 2 4.9 2 6L12 13L22 6C22 4.9 21.1 4 20 4Z" fill="#EA4335" />
      </svg>
    ),
    calendar: (
      <svg className={className} viewBox="0 0 24 24" fill="none">
        <rect x="3" y="4" width="18" height="17" rx="3" fill="#4285F4" fillOpacity="0.2" stroke="#4285F4" strokeWidth="1.5" />
        <path d="M16 2V6M8 2V6M3 9H21" stroke="#4285F4" strokeWidth="1.5" strokeLinecap="round" />
        <circle cx="12" cy="14" r="1.5" fill="#4285F4" />
      </svg>
    ),
    slack: (
      <svg className={className} viewBox="0 0 24 24" fill="none">
        <rect x="3" y="3" width="18" height="18" rx="4" fill="#EC4899" fillOpacity="0.15" stroke="#EC4899" strokeWidth="1.5" />
        <path d="M8 12H16M12 8V16" stroke="#EC4899" strokeWidth="2" strokeLinecap="round" />
      </svg>
    ),
    telegram: (
      <svg className={className} viewBox="0 0 24 24" fill="#229ED9">
        <path d="M12 0C5.37 0 0 5.37 0 12s5.37 12 12 12 12-5.37 12-12S18.63 0 12 0zm5.56 8.16l-1.92 9.07c-.14.65-.53.81-1.07.51l-2.95-2.18-1.42 1.37c-.16.16-.29.29-.6.29l.21-3.01 5.48-4.95c.24-.21-.05-.33-.37-.12l-6.77 4.26-2.92-.91c-.63-.2-.64-.63.13-.93l11.4-4.4c.53-.19.99.13.83.9z" />
      </svg>
    ),
    hubspot: (
      <svg className={className} viewBox="0 0 24 24" fill="none">
        <circle cx="12" cy="12" r="5" fill="#FF7A59" fillOpacity="0.2" stroke="#FF7A59" strokeWidth="1.5" />
        <path d="M12 3V7M12 17V21M3 12H7M17 12H21" stroke="#FF7A59" strokeWidth="1.5" strokeLinecap="round" />
      </svg>
    ),
    postgres: (
      <svg className={className} viewBox="0 0 24 24" fill="none" stroke="#336791" strokeWidth="1.5">
        <ellipse cx="12" cy="5" rx="9" ry="3" fill="#336791" fillOpacity="0.2" />
        <path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3" />
        <path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5" />
      </svg>
    ),
  }

  if (!useFallback && imgSrc) {
    return (
      <img
        src={imgSrc}
        alt={name}
        className={`${className} object-contain`}
        onError={() => setUseFallback(true)}
      />
    )
  }

  return svgFallbacks[toolName] || <Plug className={className} />
}

export default function ConnectionsPage() {
  const { user, api } = useAuth()
  const [available, setAvailable] = useState([])
  const [connections, setConnections] = useState([])
  const [loading, setLoading] = useState(true)
  const [testingId, setTestingId] = useState(null)
  const [categoryFilter, setCategoryFilter] = useState('all')

  // Modals & Form
  const [connectModalTool, setConnectModalTool] = useState(null)
  const [fieldValues, setFieldValues] = useState({})
  const [errorMsg, setErrorMsg] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [successToast, setSuccessToast] = useState(null)

  // OAuth processing state
  const [oauthProcessing, setOauthProcessing] = useState(false)

  useEffect(() => {
    loadData()
    handleOAuthCallback()
  }, [])

  const loadData = async () => {
    setLoading(true)
    try {
      const [availRes, connRes] = await Promise.all([
        api.get('/connections/available').catch(() => []),
        api.get('/connections').catch(() => []),
      ])
      setAvailable(availRes || [])
      setConnections(connRes || [])
    } finally {
      setLoading(false)
    }
  }

  // Handle Google OAuth callback from URL params
  const handleOAuthCallback = async () => {
    const urlParams = new URLSearchParams(window.location.search)
    const code = urlParams.get('code')
    const error = urlParams.get('error')

    if (error) {
      setErrorMsg(`Google authorization was cancelled: ${error}`)
      window.history.replaceState({}, document.title, window.location.pathname)
      return
    }

    if (code) {
      setOauthProcessing(true)
      try {
        const redirectUri = window.location.origin + window.location.pathname
        const res = await api.post('/connections/oauth/google/exchange', {
          code,
          redirect_uri: redirectUri,
        })
        setSuccessToast(`Connected Google Account (${res.connected_email || 'Verified'})!`)
        setTimeout(() => setSuccessToast(null), 5000)
        await loadData()
      } catch (err) {
        setErrorMsg(err.message || 'Failed to complete Google OAuth exchange.')
      } finally {
        setOauthProcessing(false)
        window.history.replaceState({}, document.title, window.location.pathname)
      }
    }
  }

  // 1-Click Connect Initiation
  const handleConnectClick = async (tool) => {
    setErrorMsg('')
    const tName = tool.tool_name?.toLowerCase()

    if (tName === 'google_workspace' || tName === 'gmail' || tName === 'google_calendar') {
      setSubmitting(true)
      try {
        const redirectUri = window.location.origin + window.location.pathname
        const queryParams = new URLSearchParams({
          redirect_uri: redirectUri,
          scopes: 'email,calendar,drive',
        }).toString()
        const res = await api.get(`/connections/oauth/google/authorize?${queryParams}`)

        if (res && res.url) {
          window.location.href = res.url
        } else {
          throw new Error('Google authorization URL was not returned.')
        }
      } catch (err) {
        setErrorMsg(err.message || 'Failed to initialize Google OAuth.')
      } finally {
        setSubmitting(false)
      }
      return
    }

    setConnectModalTool(tool)
    const initial = {}
    ;(tool.required_fields || []).forEach(f => { initial[f] = '' })
    setFieldValues(initial)
  }

  const handleTestConnection = async (connId) => {
    setTestingId(connId)
    try {
      const res = await api.post(`/connections/${connId}/test`)
      if (res && res.success) {
        setSuccessToast(`Connection verified successfully!`)
      } else {
        setErrorMsg(`Health check returned warning: ${res?.message || 'Check credentials'}`)
      }
      setTimeout(() => setSuccessToast(null), 4000)
    } catch (err) {
      setErrorMsg(err.message || 'Health check failed')
    } finally {
      setTestingId(null)
    }
  }

  const handleDisconnect = async (connId) => {
    if (!window.confirm('Disconnect this tool? Credentials will be removed from your secure vault.')) return
    try {
      await api.delete(`/connections/${connId}`)
      setSuccessToast('Integration disconnected.')
      setTimeout(() => setSuccessToast(null), 3000)
      await loadData()
    } catch (err) {
      alert(`Disconnect failed: ${err.message}`)
    }
  }

  const handleFormSubmit = async (e) => {
    e.preventDefault()
    if (!connectModalTool) return

    setSubmitting(true)
    setErrorMsg('')
    try {
      await api.post('/connections', {
        tool_name: connectModalTool.tool_name,
        display_name: connectModalTool.display_name,
        credentials: fieldValues,
        config: {},
      })
      setConnectModalTool(null)
      setFieldValues({})
      setSuccessToast(`Connected ${connectModalTool.display_name}!`)
      setTimeout(() => setSuccessToast(null), 4000)
      await loadData()
    } catch (err) {
      setErrorMsg(err.message || 'Connection failed.')
    } finally {
      setSubmitting(false)
    }
  }

  const getConnForTool = (toolName) => connections.find(c => c.tool_name === toolName)

  const toolDescriptions = {
    google_workspace: 'Sync launch posts with Google Calendar events, read inbound Gmail, and stage assets in Drive.',
    gmail: 'Parse inbound support inquiries and draft AI responses for human review.',
    calendar: 'Schedule launch deliverables and meeting reminders across integrated workspaces.',
    slack: 'Real-time team notifications, escalation alerts, and direct HITL decisions.',
    telegram: 'Autonomous customer chat support bot connected to pgvector embeddings.',
    hubspot: 'Ingest new CRM leads and route deals to sales reps automatically.',
    postgres: 'Query production database tables, verify ARR risk, and store vector context.',
    claude: 'Anthropic Claude 3.5 Sonnet reasoning agent for deep analysis and copy synthesis.',
    openai: 'GPT-4o multimodal parsing, entity extraction, and customer responses.',
  }

  const filteredTools = useMemo(() => {
    if (categoryFilter === 'all') return available
    return available.filter(t => (t.category || '').toLowerCase().includes(categoryFilter.toLowerCase()))
  }, [available, categoryFilter])

  return (
    <div className="p-6 bg-slate-50 dark:bg-[#0b0f17] text-slate-900 dark:text-slate-100 min-h-full font-sans transition-colors">
      <div className="max-w-6xl mx-auto space-y-6">

        {/* ── Toast Message ──────────────────────────────────────────────── */}
        {successToast && (
          <div className="p-3 bg-emerald-50 dark:bg-emerald-950/60 border border-emerald-200 dark:border-emerald-800 text-emerald-800 dark:text-emerald-200 text-xs rounded-xl flex items-center gap-2 animate-in fade-in duration-150">
            <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
            <span>{successToast}</span>
          </div>
        )}

        {/* ── Header ─────────────────────────────────────────────────────── */}
        <div className="flex items-center justify-between flex-wrap gap-4 pb-2 border-b border-slate-200 dark:border-[#233048]">
          <div>
            <div className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-xl bg-blue-600 flex items-center justify-center text-white shadow-xs">
                <Plug className="w-4 h-4" />
              </div>
              <h1 className="text-xl font-bold text-slate-900 dark:text-white tracking-tight">
                Integrations & Tools
              </h1>
            </div>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
              Connect external services to enable autonomous execution across your pipelines.
            </p>
          </div>

          <button
            onClick={loadData}
            className="px-3 py-1.5 bg-white dark:bg-[#182234] hover:bg-slate-100 dark:hover:bg-[#233048] border border-slate-200 dark:border-[#233048] text-slate-700 dark:text-slate-300 rounded-lg text-xs font-semibold flex items-center gap-1.5 cursor-pointer shadow-2xs transition-colors"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin text-blue-500' : ''}`} />
            <span>Refresh</span>
          </button>
        </div>

        {/* ── Categories Filter ───────────────────────────────────────────── */}
        <div className="flex items-center gap-1.5 flex-wrap">
          {[
            { id: 'all', label: 'All Tools' },
            { id: 'google', label: 'Google Workspace' },
            { id: 'communication', label: 'Communication' },
            { id: 'database', label: 'Databases' },
            { id: 'crm', label: 'CRM & Sales' },
          ].map((cat) => (
            <button
              key={cat.id}
              type="button"
              onClick={() => setCategoryFilter(cat.id)}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all cursor-pointer ${
                categoryFilter === cat.id
                  ? 'bg-blue-600 text-white shadow-2xs'
                  : 'bg-white dark:bg-[#182234] border border-slate-200 dark:border-[#233048] text-slate-700 dark:text-slate-300 hover:bg-slate-100'
              }`}
            >
              {cat.label}
            </button>
          ))}
        </div>

        {/* ── Tools Grid ─────────────────────────────────────────────────── */}
        {loading ? (
          <div className="p-12 text-center text-slate-400 text-xs flex flex-col items-center justify-center space-y-2">
            <Loader2 className="w-6 h-6 text-blue-500 animate-spin" />
            <span>Loading integrations...</span>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {filteredTools.map((tool) => {
              const conn = getConnForTool(tool.tool_name)
              const isConnected = conn?.status === 'connected' || conn?.status === 'CONNECTED'
              const isTesting = testingId === conn?.id
              const desc = toolDescriptions[tool.tool_name] || 'Autonomous integration connector for SMBFlow pipelines.'

              return (
                <div
                  key={tool.tool_name}
                  className="p-4 rounded-xl bg-white dark:bg-[#121826] border border-slate-200 dark:border-[#233048] shadow-2xs flex flex-col justify-between space-y-3 transition-all hover:border-slate-300 dark:hover:border-slate-700"
                >
                  <div>
                    <div className="flex items-start justify-between gap-2 mb-2">
                      <div className="flex items-center gap-2.5">
                        <div className="w-8 h-8 rounded-lg bg-slate-50 dark:bg-[#182234] border border-slate-200 dark:border-[#233048] flex items-center justify-center shrink-0">
                          <ToolLogo name={tool.tool_name} className="w-4 h-4" />
                        </div>
                        <div>
                          <h3 className="text-xs font-bold text-slate-900 dark:text-white">
                            {tool.display_name}
                          </h3>
                          <span className="text-[10px] font-mono text-slate-400 uppercase">
                            {tool.category || 'Workspace'}
                          </span>
                        </div>
                      </div>

                      {isConnected ? (
                        <span className="inline-flex items-center gap-1 text-[10px] font-mono font-bold text-emerald-600 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-950/60 px-2 py-0.5 rounded border border-emerald-200 dark:border-emerald-800">
                          Connected
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 text-[10px] font-mono text-slate-500 dark:text-slate-400 bg-slate-100 dark:bg-[#182234] px-2 py-0.5 rounded border border-slate-200 dark:border-[#233048]">
                          Ready
                        </span>
                      )}
                    </div>

                    <p className="text-xs text-slate-500 dark:text-slate-400 leading-relaxed line-clamp-2">
                      {desc}
                    </p>
                  </div>

                  <div className="pt-2 border-t border-slate-100 dark:border-[#1a2336] flex items-center justify-between gap-2">
                    {isConnected ? (
                      <>
                        <button
                          type="button"
                          disabled={isTesting}
                          onClick={() => handleTestConnection(conn.id)}
                          className="px-2.5 py-1 bg-slate-100 hover:bg-slate-200 dark:bg-[#182234] dark:hover:bg-[#233048] text-slate-700 dark:text-slate-300 rounded-lg text-xs font-semibold transition-colors flex items-center gap-1 cursor-pointer"
                        >
                          {isTesting ? <Loader2 className="w-3 h-3 animate-spin text-blue-500" /> : <ShieldCheck className="w-3 h-3 text-emerald-500" />}
                          <span>Test</span>
                        </button>

                        <button
                          type="button"
                          onClick={() => handleDisconnect(conn.id)}
                          className="p-1 text-slate-400 hover:text-red-500 transition-colors cursor-pointer"
                          title="Disconnect"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </>
                    ) : (
                      <button
                        type="button"
                        disabled={submitting}
                        onClick={() => handleConnectClick(tool)}
                        className="w-full py-1.5 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-xs font-bold transition-all shadow-xs flex items-center justify-center gap-1.5 cursor-pointer"
                      >
                        <Plus className="w-3.5 h-3.5" />
                        <span>Connect {tool.tool_name.includes('google') ? 'with Google' : ''}</span>
                      </button>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        )}

        {/* ── Connect API Key Modal ───────────────────────────────────────── */}
        {connectModalTool && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-xs">
            <div className="bg-white dark:bg-[#121826] border border-slate-200 dark:border-[#233048] rounded-2xl p-5 shadow-xl max-w-md w-full space-y-4 animate-in fade-in zoom-in duration-150">
              <div className="flex items-center justify-between border-b border-slate-100 dark:border-[#1a2336] pb-3">
                <div className="flex items-center gap-2">
                  <ToolLogo name={connectModalTool.tool_name} className="w-5 h-5" />
                  <h3 className="text-sm font-bold text-slate-900 dark:text-white">
                    Connect {connectModalTool.display_name}
                  </h3>
                </div>
                <button
                  type="button"
                  onClick={() => setConnectModalTool(null)}
                  className="text-slate-400 hover:text-slate-600 text-xs font-bold"
                >
                  ✕
                </button>
              </div>

              {errorMsg && (
                <div className="p-2.5 bg-red-50 dark:bg-red-950/60 border border-red-200 dark:border-red-800 text-red-700 dark:text-red-300 text-xs rounded-lg">
                  {errorMsg}
                </div>
              )}

              <form onSubmit={handleFormSubmit} className="space-y-3">
                {(connectModalTool.required_fields || ['api_key']).map((f) => (
                  <div key={f} className="space-y-1">
                    <label className="text-[11px] font-semibold text-slate-700 dark:text-slate-300 uppercase">
                      {f.replace(/_/g, ' ')}
                    </label>
                    <input
                      type={f.includes('key') || f.includes('secret') || f.includes('token') ? 'password' : 'text'}
                      value={fieldValues[f] || ''}
                      onChange={(e) => setFieldValues(prev => ({ ...prev, [f]: e.target.value }))}
                      required
                      placeholder={`Enter ${f}...`}
                      className="w-full bg-slate-50 dark:bg-[#0b0f17] border border-slate-200 dark:border-[#233048] rounded-lg px-2.5 py-1.5 text-xs text-slate-900 dark:text-slate-100 focus:outline-hidden focus:border-blue-500"
                    />
                  </div>
                ))}

                <div className="flex items-center justify-end gap-2 pt-2 border-t border-slate-100 dark:border-[#1a2336]">
                  <button
                    type="button"
                    onClick={() => setConnectModalTool(null)}
                    className="px-3 py-1.5 text-xs text-slate-500 hover:text-slate-700"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={submitting}
                    className="px-4 py-1.5 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-xs font-bold shadow-xs cursor-pointer"
                  >
                    {submitting ? 'Connecting...' : 'Save Connection'}
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}

      </div>
    </div>
  )
}
