// frontend/src/pages/client/PromptStudio.jsx
import { useState, useEffect, useCallback, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import Editor from '@monaco-editor/react'
import {
  FileText, Plus, Save, Eye, Code2, Tag,
  ChevronRight, Search, Folder, RefreshCw,
  Wand2, CheckCircle2, XCircle, AlertCircle,
  Copy, Trash2, X, Play,
} from 'lucide-react'
import { useAuth }  from '../../contexts/AuthContext'
import { useTheme } from '../../contexts/ThemeContext'
import {
  Card, Button, Alert, Spinner, EmptyState, Modal, Badge, cn,
} from '../../components/ui'
import { AGENT_ICONS, AGENT_LABELS } from '../../utils/helpers'
import DOMPurify from 'dompurify'

// Known placeholders reference
const KNOWN_PLACEHOLDERS = [
  { key: 'tenant_name',       desc: 'Company name from config' },
  { key: 'industry',          desc: 'Industry vertical' },
  { key: 'company_profile',   desc: 'Full company profile JSON' },
  { key: 'business_rules',    desc: 'Business rules JSON' },
  { key: 'tone_profile',      desc: 'Tone profile object' },
  { key: 'tone_profile_json', desc: 'Tone profile as JSON string' },
  { key: 'action_library',    desc: 'Available action IDs JSON' },
  { key: 'confidence_threshold', desc: 'Minimum confidence (0–1)' },
  { key: 'integration_config',   desc: 'Enabled integrations JSON' },
  { key: 'current_datetime',     desc: 'UTC timestamp of this run' },
  { key: 'reasoning_output',     desc: 'Previous reasoning agent output' },
  { key: 'relevant_patterns',    desc: 'Historical patterns from memory' },
  { key: 'rag_historical_context','desc': 'RAG semantic context' },
  { key: 'business_rules_json',  desc: 'Business rules as JSON string' },
  { key: 'churn_risk',           desc: 'Churn risk config' },
  { key: 'pipeline',             desc: 'Pipeline config' },
  { key: 'listing_data',         desc: 'MLS listing details and DOM data' },
  { key: 'tenant_ledger',        desc: 'Tenant payment history and ledger' },
  { key: 'showing_feedback',     desc: 'Buyer/showing agent feedback data' },
  { key: 'comparable_sales',     desc: 'Recent comp sales from MLS' },
  { key: 'operating_hours',      desc: 'Brokerage operating hours' },
  { key: 'business_rules_json',  desc: 'Business rules as JSON string' },
]

function guessAgent(filename = '') {
  const f = filename.toLowerCase()
  if (f.startsWith('research'))     return 'research_agent'
  if (f.startsWith('reasoning'))    return 'reasoning_agent'
  if (f.startsWith('drafting'))     return 'drafting_agent'
  if (f.startsWith('verification')) return 'verification_agent'
  if (f.startsWith('execution'))    return 'execution_agent'
  if (f.startsWith('memory'))       return 'memory_agent'
  return null
}

function extractPlaceholders(text = '') {
  const matches = text.match(/\{([^{}]+)\}/g) || []
  return [...new Set(matches.map(m => m.slice(1, -1).split('.')[0]))]
}

// ── File Tree Item ────────────────────────────────────────────────────────────
function FileItem({ name, path, isSelected, agentType, onSelect }) {
  const Icon = agentType ? AGENT_ICONS[agentType] : null
  return (
    <button
      onClick={() => onSelect(path)}
      className={cn(
        'w-full flex items-center gap-2.5 px-3 py-2 rounded-xl text-left text-xs transition-all',
        isSelected
          ? 'bg-primary-500/10 text-primary-400 border border-primary-500/20'
          : 'text-[rgb(var(--text-secondary))] hover:bg-[rgb(var(--bg-hover))] hover:text-[rgb(var(--text-primary))]',
      )}
    >
      <span className="flex-shrink-0 text-sm">{Icon ? <Icon className="w-4 h-4" /> : '📄'}</span>
      <span className="truncate font-medium">{name.replace('.txt', '')}</span>
    </button>
  )
}

// ── Placeholder Chip ──────────────────────────────────────────────────────────
function PlaceholderChip({ placeholder, onClick, isUsed }) {
  return (
    <button
      onClick={() => onClick(placeholder)}
      className={cn(
        'inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-[11px] font-mono border transition-all',
        isUsed
          ? 'bg-primary-500/10 text-primary-400 border-primary-500/25 hover:bg-primary-500/15'
          : 'bg-[rgb(var(--bg-hover))] text-[rgb(var(--text-muted))] border-[rgb(var(--border))] hover:border-primary-500/30 hover:text-primary-400',
      )}
      title={placeholder.desc}
    >
      <span className="text-warning">{`{`}</span>
      {placeholder.key}
      <span className="text-warning">{`}`}</span>
    </button>
  )
}

// ── New Prompt Modal ──────────────────────────────────────────────────────────
function NewPromptModal({ open, onClose, onSave, files }) {
  const [folder,  setFolder]  = useState('saas')
  const [agent,   setAgent]   = useState('research_agent')
  const [suffix,  setSuffix]  = useState('my_workflow')
  const [content, setContent] = useState('')

  const STARTERS = {
    research_agent: `You are a data gathering agent for {tenant_name}, a {industry} company.\nYour ONLY job: collect data using the available tools. DO NOT analyze.\n\nCurrent datetime: {current_datetime}\nTenant: {tenant_name}\nIntegration config: {integration_config}\n\nReturn ONLY valid JSON.`,
    reasoning_agent: `You are an autonomous reasoning agent for {tenant_name}, a {industry} company.\n\nCOMPANY CONTEXT:\n{company_profile}\n\nBUSINESS RULES:\n{business_rules}\n\nCONFIDENCE THRESHOLD: {confidence_threshold}\n\nReturn ONLY valid JSON with: situation_summary, urgency, reasoning_confidence, recommended_actions, escalate (bool).`,
    drafting_agent: `You are a professional writer for {tenant_name}, a {industry} company.\n\nTONE PROFILE:\n{tone_profile_json}\n\nReasoning output: {reasoning_output}\n\nReturn ONLY valid JSON.`,
    verification_agent: `You are a quality verification agent for {tenant_name}.\n\nRules:\n1. Real recipients — no placeholders\n2. Data accuracy\n3. Tone compliance\n4. No duplicate outreach\n\nReturn ONLY valid JSON: { "passed": bool, "approved_drafts": [...] }`,
    execution_agent: `You are an execution agent for {tenant_name}.\n\nExecute all approved actions using available tools.\nIntegrations: {integrations_json}\n\nReturn ONLY valid JSON.`,
    memory_agent: `You are a memory extraction agent for {tenant_name}, a {industry} company.\n\nExtract learnable patterns from this completed workflow run.\n\nReturn ONLY valid JSON: { "patterns_to_store": [...], "summary": "..." }`,
  }

  useEffect(() => { setContent(STARTERS[agent] || '') }, [agent])

  const path = `${folder}/${agent.replace('_agent', '')}_${suffix}.txt`
  const exists = files.some(f => f.path === path)

  return (
    <Modal open={open} onClose={onClose} title="Create New Prompt" width="max-w-2xl">
      <div className="space-y-4">
        <div className="grid grid-cols-3 gap-3">
          <div>
            <label className="block text-xs font-medium text-[rgb(var(--text-secondary))] mb-1.5">Folder</label>
            <input
              value={folder}
              onChange={e => setFolder(e.target.value.replace(/\s/g,'_').toLowerCase())}
              className="input-base"
              placeholder="saas"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-[rgb(var(--text-secondary))] mb-1.5">Agent</label>
            <select value={agent} onChange={e => setAgent(e.target.value)} className="input-base appearance-none">
              {['research_agent','reasoning_agent','drafting_agent','verification_agent','execution_agent','memory_agent'].map(a => (
                <option key={a} value={a}>{AGENT_LABELS[a]}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-[rgb(var(--text-secondary))] mb-1.5">Suffix</label>
            <input
              value={suffix}
              onChange={e => setSuffix(e.target.value.replace(/\s/g,'_').toLowerCase())}
              className="input-base"
              placeholder="my_workflow"
            />
          </div>
        </div>

        <div className="flex items-center gap-2 text-xs">
          <span className="text-[rgb(var(--text-muted))]">Path:</span>
          <code className={cn('font-mono', exists ? 'text-danger' : 'text-success')}>{path}</code>
          {exists && <span className="text-danger">(already exists)</span>}
        </div>

        <div className="h-64 border border-[rgb(var(--border))] rounded-xl overflow-hidden">
          <textarea
            value={content}
            onChange={e => setContent(e.target.value)}
            spellCheck={false}
            className="w-full h-full bg-[rgb(var(--bg-base))] text-success font-mono text-xs p-4 resize-none focus:outline-none"
          />
        </div>

        <div className="flex gap-2">
          <Button variant="gradient" disabled={exists || !content.trim()} className="flex-1"
            onClick={() => { onSave(path, content); onClose() }}>
            Create Prompt
          </Button>
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
        </div>
      </div>
    </Modal>
  )
}

// ── Auto-Eval Suggestions Modal ────────────────────────────────────────────────
function AutoEvalModal({ open, onClose, suggestions, onApply, onDismiss, loading, error }) {
  return (
    <Modal open={open} onClose={onClose} title="🔬 Prompt Improvement Suggestions" subtitle="AI-generated from human escalation corrections" width="max-w-2xl">
      <div className="space-y-4 max-h-[60vh] overflow-y-auto pr-1">
        <Alert type="warning">
          Admin review required. Suggestions are NEVER auto-applied. Review carefully before applying.
        </Alert>
        {error && <Alert type="error">{error}</Alert>}
        {loading && <div className="flex justify-center py-8"><Spinner /></div>}
        {!loading && suggestions.length === 0 && (
          <EmptyState icon={AlertCircle} title="No suggestions available" description="Run more workflows and resolve escalations to generate suggestions." />
        )}
        {suggestions.map(s => (
          <div key={s.id} className={cn('border rounded-xl p-4 space-y-3 transition-opacity',
            s.status === 'applied' && 'opacity-50',
            s.status === 'dismissed' && 'opacity-30',
            s.status === 'pending' && 'border-primary-500/20 bg-primary-500/4',
            s.status === 'applied' && 'border-success/20 bg-success/4',
            s.status === 'dismissed' && 'border-[rgb(var(--border))]',
          )}>
            <div className="flex items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <code className="text-[10px] text-primary-400 bg-primary-500/10 border border-primary-500/20 rounded-lg px-2 py-0.5">{s.prompt_file}</code>
                <span className={cn('text-[10px] px-2 py-0.5 rounded-full font-medium',
                  s.status === 'pending' ? 'bg-primary-500/10 text-primary-400' :
                  s.status === 'applied' ? 'bg-success/10 text-success' : 'bg-[rgb(var(--bg-hover))] text-[rgb(var(--text-muted))]'
                )}>{s.status}</span>
                <span className="text-[10px] text-[rgb(var(--text-muted))]">{Math.round((s.confidence||0)*100)}% confidence</span>
              </div>
              {s.status === 'pending' && (
                <div className="flex gap-1">
                  <Button size="xs" variant="success" icon={<CheckCircle2 className="w-3 h-3" />} onClick={() => onApply(s.id)}>Apply</Button>
                  <Button size="xs" variant="ghost" icon={<X className="w-3 h-3" />} onClick={() => onDismiss(s.id)}>Dismiss</Button>
                </div>
              )}
            </div>
            <div className="grid grid-cols-1 gap-2">
              {s.current_behavior_problem && (
                <div>
                  <p className="text-[10px] text-danger uppercase tracking-wider font-semibold mb-1">Problem</p>
                  <p className="text-xs text-[rgb(var(--text-secondary))] leading-relaxed">{s.current_behavior_problem}</p>
                </div>
              )}
              {s.suggested_addition && (
                <div>
                  <p className="text-[10px] text-success uppercase tracking-wider font-semibold mb-1">Suggested Addition</p>
                  <pre className="text-xs text-success bg-success/5 border border-success/15 rounded-lg p-2 whitespace-pre-wrap font-mono leading-relaxed">
                    {s.suggested_addition}
                  </pre>
                </div>
              )}
              {s.rationale && (
                <div>
                  <p className="text-[10px] text-[rgb(var(--text-muted))] uppercase tracking-wider font-semibold mb-1">Rationale</p>
                  <p className="text-xs text-[rgb(var(--text-muted))] leading-relaxed">{s.rationale}</p>
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
    </Modal>
  )
}

// ── Main PromptStudio ──────────────────────────────────────────────────────────
export default function PromptStudio() {
  const { api, user }    = useAuth()
  const { isDark }       = useTheme()
  const isAdmin          = user?.role === 'super_admin'
  const editorRef        = useRef(null)

  const [tree,     setTree]     = useState({})
  const [files,    setFiles]    = useState([])
  const [selected, setSelected] = useState(null)
  const [content,  setContent]  = useState('')
  const [dirty,    setDirty]    = useState(false)
  const [loading,  setLoading]  = useState(true)
  const [saving,   setSaving]   = useState(false)
  const [error,    setError]    = useState('')
  const [success,  setSuccess]  = useState('')
  const [view,     setView]     = useState('edit') // edit | preview | placeholders
  const [search,   setSearch]   = useState('')
  const [showNew,  setShowNew]  = useState(false)
  const [expandedFolders, setExpandedFolders] = useState({})

  // Auto-eval
  const [autoEvalOpen, setAutoEvalOpen]         = useState(false)
  const [autoEvalLoading, setAutoEvalLoading]   = useState(false)
  const [autoEvalSuggestions, setAutoEvalSuggestions] = useState([])
  const [autoEvalError, setAutoEvalError]       = useState('')

  const loadTree = useCallback(async () => {
    try {
      const data = await api.get('/config/prompt-tree')
      setTree(data.tree || {})
      setFiles(data.files || [])
    } catch (e) { setError(e.message) }
    finally { setLoading(false) }
  }, [api])

  useEffect(() => { loadTree() }, [loadTree])

  const selectFile = async (path) => {
    if (dirty && !window.confirm('Discard unsaved changes?')) return
    try {
      const data = await api.get(`/config/prompts/${path}`)
      setSelected(path)
      setContent(data.content)
      setDirty(false)
      setView('edit')
    } catch (e) { setError(e.message) }
  }

  const save = async () => {
    if (!selected) return
    setSaving(true); setError(''); setSuccess('')
    try {
      await api.put(`/config/prompts/${selected}`, { content })
      setDirty(false)
      setSuccess('Prompt saved successfully!')
      setTimeout(() => setSuccess(''), 3000)
    } catch (e) { setError(e.message) }
    finally { setSaving(false) }
  }

  const createPrompt = async (path, promptContent) => {
    try {
      await api.post(`/config/prompts/${path}`, { content: promptContent })
      await loadTree()
      await selectFile(path)
    } catch (e) { setError(e.message) }
  }

  const insertPlaceholder = (placeholder) => {
    if (!editorRef.current) return
    const editor = editorRef.current
    const selection = editor.getSelection()
    const id = { major: 1, minor: 1 }
    const op = { identifier: id, range: selection, text: `{${placeholder.key}}`, forceMoveMarkers: true }
    editor.executeEdits('insert-placeholder', [op])
    editor.focus()
    setDirty(true)
    setView('edit')
  }

  const runAutoEval = async () => {
    if (!selected) { setAutoEvalError('Select a prompt first'); return }
    const parts = selected.split('/')
    // Derive workflow name from the folder prefix (e.g. "real_estate/research_listing.txt" → "real_estate")
    // Then try to find a matching DAG by listing them, falling back to the prefix itself
    let workflowName = parts[0]
    try {
      const workflows = await api.get('/config/workflows')
      const match = workflows.find(w =>
        w.name.startsWith(parts[0]) || w.industry === parts[0]
      )
      if (match) workflowName = match.name
    } catch (_) {}

    setAutoEvalLoading(true); setAutoEvalError('')
    try {
      const result = await api.post('/admin/auto-eval/run', { tenant_id: user?.tenant_id || 'global', workflow_name: workflowName })
      setAutoEvalSuggestions(result.suggestions || [])
      setAutoEvalOpen(true)
      if (!(result.suggestions?.length)) setAutoEvalError('No suggestions — resolve more escalations first.')
    } catch (err) { setAutoEvalError(err.message) }
    finally { setAutoEvalLoading(false) }
  }

  const applyAutoEval = async (id) => {
    try {
      await api.post(`/admin/auto-eval/suggestions/${id}/apply`, { admin_email: user?.email || 'admin' })
      setAutoEvalSuggestions(s => s.map(x => x.id === id ? { ...x, status: 'applied' } : x))
      if (selected) await selectFile(selected)
    } catch (e) { setAutoEvalError(e.message) }
  }

  const dismissAutoEval = async (id) => {
    try {
      await api.post(`/admin/auto-eval/suggestions/${id}/dismiss`, {})
      setAutoEvalSuggestions(s => s.map(x => x.id === id ? { ...x, status: 'dismissed' } : x))
    } catch (e) { setAutoEvalError(e.message) }
  }

  const agentType = selected ? guessAgent(selected.split('/').pop()) : null
  const usedPlaceholders = extractPlaceholders(content)

  // Group files by folder
  const grouped = files.reduce((acc, f) => {
    const folder = f.path.split('/').slice(0, -1).join('/') || 'root'
    if (!acc[folder]) acc[folder] = []
    acc[folder].push(f)
    return acc
  }, {})

  const filteredGroups = Object.entries(grouped).reduce((acc, [folder, fls]) => {
    const filtered = fls.filter(f => !search || f.path.toLowerCase().includes(search.toLowerCase()))
    if (filtered.length) acc[folder] = filtered
    return acc
  }, {})

  if (loading) return <div className="flex items-center justify-center h-64"><Spinner size="lg" /></div>

  return (
    <div className="flex h-[calc(100vh-var(--nav-height)-80px)] gap-0 surface-card rounded-2xl overflow-hidden border border-[rgb(var(--border))]">
      {/* ── Sidebar ─────────────────────────────────────────────────────── */}
      <div className="w-60 flex-shrink-0 border-r border-[rgb(var(--border))] flex flex-col">
        <div className="px-3 py-3 border-b border-[rgb(var(--border))]">
          <div className="flex items-center justify-between mb-2">
            <p className="text-xs font-bold text-[rgb(var(--text-primary))]">Prompts</p>
            <Button size="xs" variant="primary" icon={<Plus className="w-3 h-3" />} onClick={() => setShowNew(true)} />
          </div>
          <div className="relative">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-[rgb(var(--text-muted))]" />
            <input
              value={search}
              onChange={e => setSearch(e.target.value)}
              placeholder="Search prompts…"
              className="input-base !pl-8 !py-1.5 text-xs"
            />
          </div>
        </div>

        <div className="flex-1 overflow-y-auto py-2 px-2 space-y-2">
          {Object.entries(filteredGroups).map(([folder, fls]) => (
            <div key={folder}>
              <button
                onClick={() => setExpandedFolders(p => ({ ...p, [folder]: !p[folder] }))}
                className="flex items-center gap-1.5 px-2 py-1 w-full text-[10px] font-bold text-[rgb(var(--text-muted))] uppercase tracking-wider hover:text-[rgb(var(--text-primary))] transition-colors"
              >
                <Folder className="w-3 h-3" />
                {folder}
                <ChevronRight className={cn('w-3 h-3 ml-auto transition-transform', !expandedFolders[folder] && 'rotate-90')} />
              </button>
              <AnimatePresence initial={false}>
                {!expandedFolders[folder] && (
                  <motion.div
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: 'auto', opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                    className="overflow-hidden space-y-0.5 pl-2"
                  >
                    {fls.map(f => (
                      <FileItem
                        key={f.path}
                        name={f.filename}
                        path={f.path}
                        isSelected={selected === f.path}
                        agentType={guessAgent(f.filename)}
                        onSelect={selectFile}
                      />
                    ))}
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          ))}

          {Object.keys(filteredGroups).length === 0 && (
            <EmptyState icon={FileText} title="No prompts found" description="Create your first prompt" />
          )}
        </div>

        <div className="px-3 py-2 border-t border-[rgb(var(--border))] text-[10px] text-[rgb(var(--text-muted))] text-center">
          {files.length} files
        </div>
      </div>

      {/* ── Editor area ─────────────────────────────────────────────────── */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Editor toolbar */}
        {selected ? (
          <>
            <div className="flex items-center justify-between px-4 py-2.5 border-b border-[rgb(var(--border))] bg-[rgb(var(--bg-surface))]/80 backdrop-blur-sm gap-3">
              <div className="flex items-center gap-2 min-w-0">
                {agentType && <span className="text-base">{(() => { const Icon = AGENT_ICONS[agentType]; return <Icon className="w-5 h-5" />; })()}</span>}
                <div className="min-w-0">
                  <p className="text-sm font-bold text-[rgb(var(--text-primary))] truncate">{selected.split('/').pop()}</p>
                  <p className="text-[10px] text-[rgb(var(--text-muted))] font-mono truncate">{selected}</p>
                </div>
                {dirty && <span className="px-2 py-0.5 bg-warning/10 text-warning border border-warning/20 rounded-full text-[10px] font-semibold flex-shrink-0">unsaved</span>}
              </div>

              <div className="flex items-center gap-2 flex-shrink-0">
                {/* View switcher */}
                <div className="flex bg-[rgb(var(--bg-base))] rounded-xl p-0.5 gap-0.5">
                  {[['edit', Code2, 'Edit'], ['preview', Eye, 'Preview'], ['placeholders', Tag, 'Vars']].map(([v, Icon, label]) => (
                    <button
                      key={v}
                      onClick={() => setView(v)}
                      className={cn('flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-semibold transition-all', view === v ? 'bg-[rgb(var(--bg-card))] text-[rgb(var(--text-primary))] shadow-sm' : 'text-[rgb(var(--text-muted))] hover:text-[rgb(var(--text-primary))]')}
                    >
                      <Icon className="w-3.5 h-3.5" />{label}
                    </button>
                  ))}
                </div>

                {isAdmin && (
                  <Button size="sm" variant="secondary" loading={autoEvalLoading} onClick={runAutoEval} icon={<Wand2 className="w-3.5 h-3.5" />}>
                    Auto-Eval
                  </Button>
                )}
                <Button size="sm" variant="gradient" loading={saving} onClick={save} disabled={!dirty} icon={<Save className="w-3.5 h-3.5" />}>
                  Save
                </Button>
              </div>
            </div>

            {/* Alerts */}
            <AnimatePresence>
              {(error || success) && (
                <div className="px-4 pt-3">
                  {error   && <Alert type="error"   onClose={() => setError('')}>{error}</Alert>}
                  {success && <Alert type="success" onClose={() => setSuccess('')}>{success}</Alert>}
                </div>
              )}
            </AnimatePresence>

            {/* Views */}
            <div className="flex-1 overflow-hidden">
              {/* Monaco Editor */}
              {view === 'edit' && (
                <Editor
                  height="100%"
                  language="plaintext"
                  value={content}
                  theme={isDark ? 'vs-dark' : 'light'}
                  onChange={(val) => { setContent(val || ''); setDirty(true) }}
                  onMount={(editor) => { editorRef.current = editor }}
                  options={{
                    fontSize: 13,
                    fontFamily: "'JetBrains Mono', 'Fira Code', monospace",
                    lineHeight: 1.7,
                    wordWrap: 'on',
                    minimap: { enabled: false },
                    scrollBeyondLastLine: false,
                    renderWhitespace: 'selection',
                    padding: { top: 16, bottom: 16 },
                    bracketPairColorization: { enabled: false },
                    fontLigatures: true,
                    smoothScrolling: true,
                    cursorSmoothCaretAnimation: 'on',
                  }}
                />
              )}

              {/* Preview */}
              {view === 'preview' && (
                <div className="h-full overflow-y-auto p-5">
                  <div className="max-w-3xl mx-auto">
                    <div
                      className="text-sm text-[rgb(var(--text-secondary))] font-mono whitespace-pre-wrap leading-relaxed bg-[rgb(var(--bg-base))] border border-[rgb(var(--border))] rounded-xl p-5"
                      dangerouslySetInnerHTML={{
                        __html: DOMPurify.sanitize(
                          content
                            .replace(/\{([^{}]+)\}/g, (m) =>
                              `<mark class="bg-primary-500/15 text-primary-400 rounded px-0.5 border border-primary-500/20 not-italic">${m}</mark>`
                            )
                            .replace(/\n/g, '<br>'),
                          { ALLOWED_TAGS: ['mark', 'br'], ALLOWED_ATTR: ['class'] }
                        )
                      }}
                    />
                  </div>
                </div>
              )}

              {/* Placeholders */}
              {view === 'placeholders' && (
                <div className="h-full overflow-y-auto p-5">
                  <div className="max-w-2xl mx-auto space-y-5">
                    {usedPlaceholders.length > 0 && (
                      <Card title="Used in this prompt">
                        <div className="flex flex-wrap gap-2">
                          {usedPlaceholders.map(key => {
                            const ph = KNOWN_PLACEHOLDERS.find(p => p.key === key) || { key, desc: 'Custom placeholder' }
                            return <PlaceholderChip key={key} placeholder={ph} onClick={insertPlaceholder} isUsed />
                          })}
                        </div>
                      </Card>
                    )}

                    <Card title="All Available Placeholders">
                      <p className="text-xs text-[rgb(var(--text-muted))] mb-3">Click any placeholder to insert it at cursor position</p>
                      <div className="flex flex-wrap gap-2">
                        {KNOWN_PLACEHOLDERS.map(ph => (
                          <PlaceholderChip
                            key={ph.key}
                            placeholder={ph}
                            onClick={insertPlaceholder}
                            isUsed={usedPlaceholders.includes(ph.key)}
                          />
                        ))}
                      </div>
                    </Card>

                    <Card>
                      <div className="text-xs text-[rgb(var(--text-muted))] space-y-1">
                        <p className="font-semibold text-[rgb(var(--text-secondary))]">Syntax</p>
                        <p><code className="text-primary-400 bg-primary-500/8 px-1.5 py-0.5 rounded">{'{'}placeholder_name{'}'}</code> — runtime values injected by agents</p>
                        <p><code className="text-warning bg-warning/8 px-1.5 py-0.5 rounded">{'{{'}literal_braces{'}}'}</code> — literal curly braces in JSON instructions</p>
                      </div>
                    </Card>
                  </div>
                </div>
              )}
            </div>
          </>
        ) : (
          <div className="flex-1 flex items-center justify-center">
            <div className="text-center">
              <div className="w-16 h-16 rounded-2xl bg-[rgb(var(--bg-hover))] flex items-center justify-center mx-auto mb-4 animate-float">
                <FileText className="w-8 h-8 text-[rgb(var(--text-muted))]" />
              </div>
              <p className="text-sm font-semibold text-[rgb(var(--text-primary))] mb-1">Select a prompt to edit</p>
              <p className="text-xs text-[rgb(var(--text-muted))] mb-4">Choose from the sidebar or create a new prompt</p>
              <Button variant="gradient" onClick={() => setShowNew(true)} icon={<Plus className="w-4 h-4" />}>
                Create New Prompt
              </Button>
            </div>
          </div>
        )}
      </div>

      {/* Modals */}
      <NewPromptModal open={showNew} onClose={() => setShowNew(false)} onSave={createPrompt} files={files} />
      <AutoEvalModal
        open={autoEvalOpen}
        onClose={() => setAutoEvalOpen(false)}
        suggestions={autoEvalSuggestions}
        onApply={applyAutoEval}
        onDismiss={dismissAutoEval}
        loading={autoEvalLoading}
        error={autoEvalError}
      />
    </div>
  )
}