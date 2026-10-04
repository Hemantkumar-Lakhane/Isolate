// frontend/src/pages/client/ToolsPage.jsx
// ==========================================
// Three tabs:
//   1. Credentials — encrypted API keys (unchanged)
//   2. Custom REST tools — user-defined HTTP tools (unchanged)
//   3. Built-in Tools — local dev tools + utility tools (NEW)

import { useState, useEffect, useCallback } from 'react'
import { useAuth }  from '../../contexts/AuthContext'
import {
  Card, Button, Input, Select, Modal, Alert, Spinner,
  EmptyState, TabGroup, Toggle
} from '../../components/ui'
import { timeAgo } from '../../utils/helpers'

const TOOL_TYPES = [
  'hubspot', 'gmail', 'slack', 'stripe', 'openai',
  'anthropic', 'google', 'groq', 'generic_rest', 'product_db',
  'reso_api', 'property_management', 'twilio',
]

const TOOL_ICONS = {
  hubspot: '🟠', gmail: '📧', slack: '💬', stripe: '💳',
  openai: '🟢', anthropic: '🔵', google: '🔍', groq: '⚡',
  generic_rest: '🔧', product_db: '🗄️',
  reso_api: '🏠', property_management: '🏢', twilio: '📱',
}

const INDUSTRY_COLORS = {
  saas:        'text-blue-300 bg-blue-900/20 border-blue-800/40',
  retail:      'text-orange-300 bg-orange-900/20 border-orange-800/40',
  healthcare:  'text-green-300 bg-green-900/20 border-green-800/40',
  finance:     'text-yellow-300 bg-yellow-900/20 border-yellow-800/40',
  real_estate: 'text-teal-300 bg-teal-900/20 border-teal-800/40',
  logistics:   'text-cyan-300 bg-cyan-900/20 border-cyan-800/40',
  universal:   'text-gray-300 bg-gray-800/40 border-gray-700/40',
  utility:     'text-purple-300 bg-purple-900/20 border-purple-800/40',
}

// ── Add Credential Modal ───────────────────────────────────────────────────────
function AddCredentialModal({ open, onClose, tenantId, api, onDone }) {
  const [toolName,   setToolName]   = useState('hubspot')
  const [display,    setDisplay]    = useState('')
  const [schema,     setSchema]     = useState([])
  const [values,     setValues]     = useState({})
  const [loading,    setLoading]    = useState(false)
  const [schLoading, setSchLoading] = useState(false)
  const [error,      setError]      = useState('')

  useEffect(() => { if (!open) return; setValues({}); setDisplay('') }, [open])

  const loadSchema = useCallback(async (name) => {
    setSchLoading(true)
    try {
      const s = await api.get(`/credentials/schema/${name}`)
      setSchema(s?.fields || [])
    } catch { setSchema([]) }
    finally { setSchLoading(false) }
  }, [api])

  useEffect(() => { if (toolName) loadSchema(toolName) }, [toolName, loadSchema])

  const submit = async () => {
    if (!tenantId) { setError('No tenant'); return }
    const missing = schema.filter(f => f.required && !values[f.key])
    if (missing.length > 0) { setError(`Required: ${missing.map(f => f.label).join(', ')}`); return }
    setLoading(true); setError('')
    try {
      await api.post('/credentials', {
        tenant_id: tenantId, tool_name: toolName,
        display_name: display || toolName, credentials: values,
      })
      onDone(); onClose()
    } catch (err) { setError(err.message) }
    finally { setLoading(false) }
  }

  return (
    <Modal open={open} onClose={onClose} title="🔑 Add Integration Credentials" width="max-w-lg">
      <div className="space-y-4">
        <Select
          label="Integration Type"
          value={toolName}
          onChange={e => setToolName(e.target.value)}
          options={TOOL_TYPES.map(t => ({ value: t, label: `${TOOL_ICONS[t] || '🔧'} ${t}` }))}
        />
        <Input label="Display Name (optional)" value={display} onChange={e => setDisplay(e.target.value)} placeholder={`e.g. Production ${toolName}`} />
        {schLoading ? (
          <div className="flex items-center gap-2 text-gray-500 text-sm py-4"><Spinner size="sm" /> Loading fields…</div>
        ) : (
          <div className="space-y-3">
            {schema.map(field => (
              <Input
                key={field.key}
                label={field.label}
                type={field.type === 'password' ? 'password' : 'text'}
                value={values[field.key] || ''}
                onChange={e => setValues(p => ({ ...p, [field.key]: e.target.value }))}
                hint={field.hint}
                required={field.required}
                placeholder={field.hint}
              />
            ))}
          </div>
        )}
        {error && <Alert type="error" onClose={() => setError('')}>{error}</Alert>}
        <div className="flex gap-2 pt-2">
          <Button variant="success" loading={loading} onClick={submit} className="flex-1">🔒 Store Securely</Button>
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
        </div>
      </div>
    </Modal>
  )
}

// ── Add Custom Tool Modal ──────────────────────────────────────────────────────
function AddToolModal({ open, onClose, tenantId, credentials, api, onDone }) {
  const init = { tool_name: '', display_name: '', description: '', base_url: '', http_method: 'GET', auth_type: 'api_key', credential_id: '', response_path: '' }
  const [form, setForm]   = useState(init)
  const [loading, setLoading] = useState(false)
  const [error,   setError]   = useState('')

  const set = (k, v) => setForm(p => ({ ...p, [k]: v }))

  const submit = async () => {
    if (!form.tool_name || !form.base_url) { setError('Tool name and Base URL required'); return }
    setLoading(true); setError('')
    try {
      await api.post('/tools', { ...form, tenant_id: tenantId })
      onDone(); onClose(); setForm(init)
    } catch (err) { setError(err.message) }
    finally { setLoading(false) }
  }

  return (
    <Modal open={open} onClose={onClose} title="🔧 Add Custom Tool" width="max-w-lg">
      <div className="space-y-4">
        <div className="grid grid-cols-2 gap-3">
          <Input label="Tool Name *" value={form.tool_name} onChange={e => set('tool_name', e.target.value)} placeholder="my_crm_get_deals" hint="snake_case, no spaces" />
          <Input label="Display Name" value={form.display_name} onChange={e => set('display_name', e.target.value)} />
        </div>
        <Input label="Description" value={form.description} onChange={e => set('description', e.target.value)} placeholder="What this tool does — shown to agents" />
        <Input label="Base URL *" value={form.base_url} onChange={e => set('base_url', e.target.value)} placeholder="https://api.example.com/v1" />
        <div className="grid grid-cols-2 gap-3">
          <Select label="HTTP Method" value={form.http_method} onChange={e => set('http_method', e.target.value)}
            options={['GET', 'POST', 'PUT', 'PATCH', 'DELETE'].map(m => ({ value: m, label: m }))} />
          <Select label="Auth Type" value={form.auth_type} onChange={e => set('auth_type', e.target.value)}
            options={['api_key', 'bearer', 'basic', 'none'].map(a => ({ value: a, label: a }))} />
        </div>
        {form.auth_type !== 'none' && (
          <Select
            label="Use Saved Credentials"
            value={form.credential_id}
            onChange={e => set('credential_id', e.target.value)}
            options={[
              { value: '', label: '— none —' },
              ...credentials.map(c => ({ value: c.id, label: `${TOOL_ICONS[c.tool_name] || '🔧'} ${c.display_name}` })),
            ]}
          />
        )}
        <Input label="Response Path (JSONPath)" value={form.response_path} onChange={e => set('response_path', e.target.value)}
          placeholder="$.data.items" hint="Optional: path to extract from response" />
        {error && <Alert type="error" onClose={() => setError('')}>{error}</Alert>}
        <div className="flex gap-2 pt-2">
          <Button variant="success" loading={loading} onClick={submit} className="flex-1">Add Tool</Button>
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
        </div>
      </div>
    </Modal>
  )
}

// ── Seed Data Status Banner ───────────────────────────────────────────────────
function SeedDataBanner({ api }) {
  const [status, setStatus]   = useState(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    api.get('/seed-data/status').then(setStatus).catch(() => {})
  }, [api])

  const generate = async (industry) => {
    setLoading(true)
    try {
      await api.post(`/seed-data/generate${industry ? `?industry=${industry}` : ''}`)
      const s = await api.get('/seed-data/status')
      setStatus(s)
    } catch (e) { console.error(e) }
    finally { setLoading(false) }
  }

  if (!status) return null
  if (status.all_ready) return null

  return (
    <div className="bg-yellow-900/20 border border-yellow-700/40 rounded-xl p-4 mb-4">
      <div className="flex items-start gap-3">
        <span className="text-2xl flex-shrink-0">⚠️</span>
        <div className="flex-1">
          <div className="text-yellow-300 font-semibold text-sm mb-1">Seed Data Missing</div>
          <p className="text-xs text-gray-400 mb-3">
            Some local dev tool data files are missing. Agents will get empty data and escalate.
            Generate seed data to test workflows without real API credentials.
          </p>
          <div className="flex flex-wrap gap-2">
            {Object.entries(status.files || {}).map(([fname, info]) => (
              !info.exists && (
                <Button
                  key={info.industry}
                  size="xs"
                  variant="warning"
                  loading={loading}
                  onClick={() => generate(info.industry)}
                >
                  Generate {info.industry.toUpperCase()} data
                </Button>
              )
            ))}
            <Button size="xs" variant="success" loading={loading} onClick={() => generate(null)}>
              Generate ALL seed data
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
}

// ── Built-in Tool Detail Modal ────────────────────────────────────────────────
function BuiltinToolModal({ tool, open, onClose }) {
  if (!tool || !open) return null
  const params = tool.parameters || {}

  return (
    <Modal open onClose={onClose} title={`🔧 ${tool.display_name || tool.name}`} width="max-w-lg">
      <div className="space-y-4">
        <p className="text-sm text-gray-300">{tool.description}</p>
        <div className="flex items-center gap-2">
          <span className={`px-2 py-0.5 rounded text-xs border ${INDUSTRY_COLORS[tool.industry] || INDUSTRY_COLORS.universal}`}>
            {tool.industry}
          </span>
          <span className="text-xs text-gray-500 font-mono">{tool.type}</span>
          {tool.seed_file && (
            <span className="text-xs text-gray-600">📄 {tool.seed_file}</span>
          )}
        </div>

        {Object.keys(params).length > 0 && (
          <div>
            <div className="text-xs font-semibold text-gray-400 mb-2 uppercase tracking-wide">Parameters</div>
            <div className="space-y-2">
              {Object.entries(params).map(([pname, pdef]) => (
                <div key={pname} className="bg-gray-800/50 rounded-lg px-3 py-2">
                  <div className="flex items-center gap-2 mb-0.5">
                    <code className="text-xs text-green-300">{pname}</code>
                    <span className="text-[10px] text-gray-600">{pdef.type}</span>
                    {pdef.enum && (
                      <span className="text-[10px] text-gray-500">
                        [{pdef.enum.join(' | ')}]
                      </span>
                    )}
                    {pdef.default !== undefined && (
                      <span className="text-[10px] text-blue-400">default: {String(pdef.default)}</span>
                    )}
                  </div>
                  {pdef.description && (
                    <p className="text-xs text-gray-500">{pdef.description}</p>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        <div>
          <div className="text-xs font-semibold text-gray-400 mb-1 uppercase tracking-wide">Usage in DAG node</div>
          <code className="text-xs text-blue-300 bg-gray-950 border border-gray-800 rounded px-3 py-2 block">
            "tools": ["{tool.name}"]
          </code>
          <p className="text-xs text-gray-600 mt-1">Add this tool name to a node's tools array in the Workflow Builder.</p>
        </div>
      </div>
    </Modal>
  )
}

// ── Main ToolsPage ─────────────────────────────────────────────────────────────
export default function ToolsPage() {
  const { user, api } = useAuth()
  const tenantId      = user?.tenant_id

  const [tab,         setTab]        = useState('creds')
  const [creds,       setCreds]      = useState([])
  const [tools,       setTools]      = useState([])
  const [localTools,  setLocalTools] = useState([])
  const [loading,     setLoading]    = useState(true)
  const [error,       setError]      = useState('')
  const [showAddCred, setShowAddCred] = useState(false)
  const [showAddTool, setShowAddTool] = useState(false)
  const [deleting,    setDeleting]   = useState({})
  const [detailTool,  setDetailTool] = useState(null)
  const [industryFilter, setIndustryFilter] = useState('all')

  const load = useCallback(async () => {
    try {
      const [c, t, lt] = await Promise.all([
        api.get('/credentials'),
        api.get('/tools'),
        api.get('/tools/local').catch(() => ({ tools: [] })),
      ])
      setCreds(Array.isArray(c) ? c : [])
      setTools(Array.isArray(t) ? t : [])
      setLocalTools(lt.tools || [])
      setError('')
    } catch (err) { setError(err.message) }
    finally { setLoading(false) }
  }, [api])

  useEffect(() => { load() }, [load])

  const deleteCred = async (id) => {
    setDeleting(p => ({ ...p, [id]: true }))
    try { await api.delete(`/credentials/${id}`); load() }
    catch (err) { setError(err.message) }
    finally { setDeleting(p => { const n = { ...p }; delete n[id]; return n }) }
  }

  const deleteTool = async (id) => {
    setDeleting(p => ({ ...p, [id]: true }))
    try { await api.delete(`/tools/${id}`); load() }
    catch (err) { setError(err.message) }
    finally { setDeleting(p => { const n = { ...p }; delete n[id]; return n }) }
  }

 const industries = ['all', ...new Set(localTools.map(t => t.industry || 'universal'))]
  const filteredLocalTools = industryFilter === 'all'
    ? localTools
    : localTools.filter(t => t.industry === industryFilter)

  if (loading) return <div className="flex items-center justify-center h-64"><Spinner size="lg" /></div>

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-xl font-bold text-white">🔧 Tools & API Keys</h1>
          <p className="text-gray-400 text-xs mt-0.5">Manage integrations, credentials, and available tools for your workflows</p>
        </div>
        <div className="flex gap-2">
          <Button size="sm" variant="ghost"   onClick={() => setShowAddTool(true)}>+ Custom Tool</Button>
          <Button size="sm" variant="success" onClick={() => setShowAddCred(true)}>🔑 Add Credentials</Button>
        </div>
      </div>

      {error && <Alert type="error" onClose={() => setError('')}>{error}</Alert>}

      {/* Seed data banner */}
      <SeedDataBanner api={api} />

      <TabGroup
        tabs={[
          { value: 'builtin', label: '🔌 Built-in Tools',  badge: localTools.length },
          { value: 'creds',   label: '🔑 Credentials',     badge: creds.length },
          { value: 'tools',   label: '🔧 Custom Tools',    badge: tools.length },
        ]}
        value={tab}
        onChange={setTab}
      />

      {/* ── BUILT-IN TOOLS TAB ─────────────────────────────────────────────── */}
      {tab === 'builtin' && (
        <div className="space-y-4">
          <div className="bg-blue-900/10 border border-blue-800/30 rounded-xl p-4 text-xs text-blue-300">
            <div className="font-semibold mb-1">ℹ️ Local Dev Tools — No Credentials Needed</div>
            These tools read from seed data files in <code className="bg-blue-900/30 px-1 rounded">db/seed/data/</code>.
            They are automatically registered for every workflow run. Add their names to a DAG node's <code className="bg-blue-900/30 px-1 rounded">"tools": [...]</code> array in the Workflow Builder.
          </div>

          {/* Industry filter */}
          <div className="flex gap-2 flex-wrap">
            {industries.map(ind => (
              <button
                key={ind}
                onClick={() => setIndustryFilter(ind)}
                className={`px-3 py-1 rounded-full text-xs border transition-colors ${
                  industryFilter === ind
                    ? 'bg-blue-600 border-blue-500 text-white'
                    : 'bg-gray-800 border-gray-700 text-gray-400 hover:border-gray-600 hover:text-white'
                }`}
              >
                {/* Add the optional chaining or fallback here */}
                {(ind || 'universal').toUpperCase()} 
              </button>
            ))}
          </div>

          {filteredLocalTools.length === 0 ? (
            <EmptyState icon="🔌" title="No tools found" description="Filter may be too narrow" />
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
              {filteredLocalTools.map(tool => (
                <div
                  key={tool.name}
                  className="bg-gray-800/40 border border-gray-700/50 rounded-xl p-4 cursor-pointer hover:border-gray-600 transition-colors"
                  onClick={() => setDetailTool(tool)}
                >
                  <div className="flex items-start gap-2 mb-2">
                    <div className="flex-1 min-w-0">
                      <div className="text-sm text-white font-medium truncate">{tool.name}</div>
                      <div className="flex items-center gap-2 mt-0.5">
                        <span className={`text-[10px] px-1.5 py-0.5 rounded border ${INDUSTRY_COLORS[tool.industry] || INDUSTRY_COLORS.universal}`}>
                          {tool.industry}
                        </span>
                        <span className="text-[10px] text-gray-600">{Object.keys(tool.parameters || {}).length} params</span>
                      </div>
                    </div>
                    <span className="text-green-400 text-xs flex-shrink-0">✓ active</span>
                  </div>
                  <p className="text-xs text-gray-500 line-clamp-2 leading-relaxed">{tool.description}</p>
                  {Object.keys(tool.parameters || {}).length > 0 && (
                    <div className="mt-2 flex flex-wrap gap-1">
                      {Object.keys(tool.parameters).slice(0, 4).map(p => (
                        <code key={p} className="text-[10px] text-gray-500 bg-gray-900 rounded px-1">{p}</code>
                      ))}
                      {Object.keys(tool.parameters).length > 4 && (
                        <span className="text-[10px] text-gray-600">+{Object.keys(tool.parameters).length - 4} more</span>
                      )}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}

          {/* Utility tools */}
          <Card title="Utility Tools (always available)" className="mt-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {[
                { name: 'db_write_outcome',  desc: 'Log an action outcome to the database for future learning and RAG context.',       params: ['tenant_id', 'action_taken', 'metric_name', 'metric_value'] },
                { name: 'db_update_pattern', desc: 'Store a learned pattern in memory store so future runs can benefit from it.', params: ['tenant_id', 'pattern_key', 'pattern_data', 'success'] },
              ].map(t => (
                <div key={t.name} className="bg-gray-800/30 border border-gray-700/40 rounded-xl p-3">
                  <div className="text-sm text-white font-medium mb-1">{t.name}</div>
                  <p className="text-xs text-gray-500 mb-2">{t.desc}</p>
                  <div className="flex flex-wrap gap-1">
                    {t.params.map(p => (
                      <code key={p} className="text-[10px] text-purple-300 bg-purple-900/20 rounded px-1">{p}</code>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </Card>
        </div>
      )}

      {/* ── CREDENTIALS TAB ─────────────────────────────────────────────────── */}
      {tab === 'creds' && (
        <Card
          title="Stored Credentials"
          action={<span className="text-xs text-gray-500">{creds.length} stored · encrypted at rest</span>}
        >
          {creds.length === 0 ? (
            <EmptyState
              icon="🔑" title="No credentials stored"
              description="Add API keys for HubSpot, Gmail, Slack, Stripe, and more"
              action={<Button variant="success" size="sm" onClick={() => setShowAddCred(true)}>Add First Credential</Button>}
            />
          ) : (
            <div className="space-y-2">
              {creds.map(c => (
                <div key={c.id} className="flex items-center justify-between py-3 px-4 bg-gray-800/40 rounded-xl">
                  <div className="flex items-center gap-3">
                    <span className="text-2xl">{TOOL_ICONS[c.tool_name] || '🔧'}</span>
                    <div>
                      <div className="text-sm text-white font-medium">{c.display_name || c.tool_name}</div>
                      <div className="text-xs text-gray-500 font-mono">{c.tool_name} · Added {timeAgo(c.created_at)}</div>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-green-400 bg-green-900/20 border border-green-800/40 px-2 py-0.5 rounded">🔒 Encrypted</span>
                    <Button size="xs" variant="danger" loading={!!deleting[c.id]} onClick={() => deleteCred(c.id)}>Delete</Button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </Card>
      )}

      {/* ── CUSTOM TOOLS TAB ────────────────────────────────────────────────── */}
      {tab === 'tools' && (
        <Card title="Custom REST Tools" action={<span className="text-xs text-gray-500">{tools.length} registered</span>}>
          {tools.length === 0 ? (
            <EmptyState
              icon="🔧" title="No custom tools"
              description="Add REST API endpoints for agents to call during workflows"
              action={<Button variant="success" size="sm" onClick={() => setShowAddTool(true)}>Add First Tool</Button>}
            />
          ) : (
            <div className="space-y-2">
              {tools.map(t => (
                <div key={t.id} className="flex items-center justify-between py-3 px-4 bg-gray-800/40 rounded-xl">
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="text-white text-sm font-medium">{t.display_name || t.tool_name}</span>
                      <span className="text-xs font-mono text-gray-500 bg-gray-800 border border-gray-700 rounded px-1.5 py-0.5">{t.http_method}</span>
                    </div>
                    <div className="text-xs text-gray-500 truncate">{t.base_url}</div>
                    {t.description && <div className="text-xs text-gray-600 mt-0.5">{t.description}</div>}
                  </div>
                  <div className="flex items-center gap-2 flex-shrink-0 ml-3">
                    <span className={`text-xs px-2 py-0.5 rounded border ${t.is_active ? 'text-green-400 bg-green-900/20 border-green-800/40' : 'text-gray-500 bg-gray-800 border-gray-700'}`}>
                      {t.is_active ? 'active' : 'inactive'}
                    </span>
                    <Button size="xs" variant="danger" loading={!!deleting[t.id]} onClick={() => deleteTool(t.id)}>Delete</Button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </Card>
      )}

      {/* Modals */}
      <AddCredentialModal open={showAddCred} onClose={() => setShowAddCred(false)} tenantId={tenantId} api={api} onDone={load} />
      <AddToolModal open={showAddTool} onClose={() => setShowAddTool(false)} tenantId={tenantId} credentials={creds} api={api} onDone={load} />
      <BuiltinToolModal tool={detailTool} open={!!detailTool} onClose={() => setDetailTool(null)} />
    </div>
  )
}