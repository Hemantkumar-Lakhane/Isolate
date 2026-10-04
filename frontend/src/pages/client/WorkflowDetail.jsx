// frontend/src/pages/client/WorkflowDetail.jsx
import { useState, useEffect, useCallback, useMemo, useRef } from 'react'
import { getDisplayName } from '../../utils/workflowDisplayNames'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { motion, AnimatePresence } from 'framer-motion'
import {
  ArrowLeft, Pause, Play, Square, DollarSign, Activity,
  Clock, Cpu, ChevronDown, ChevronUp, Terminal, BarChart3,
  Layers, History, Zap, Download, ExternalLink, RefreshCw,
} from 'lucide-react'
import { useAuth }      from '../../contexts/AuthContext'
import { useWebSocket } from '../../contexts/WSContext'
import { useStreamingStore } from "../../utils/appStore";
import {
  Card, Badge, Button, Spinner, Alert, Modal, TabGroup, ProgressBar, cn,
} from '../../components/ui'
import { timeAgo, fmtCost, fmtTokens } from '../../utils/helpers'

import NodePipeline    from '../../components/workflow/NodePipeline'
import LogTerminal     from '../../components/workflow/LogTerminal'
import CostRibbon      from '../../components/workflow/CostRibbon'
import DecisionPortal  from '../../components/workflow/DecisionPortal'
import TrendIndicator  from '../../components/workflow/TrendIndicator'
import WorkflowSummary from '../../components/workflow/WorkflowSummary'
import EmailSummarizerPage from './EmailSummarizerPage'

const DEFAULT_NODES = [
  { id: 'research',     agent: 'research_agent' },
  { id: 'reasoning',   agent: 'reasoning_agent' },
  { id: 'drafting',    agent: 'drafting_agent' },
  { id: 'verification',agent: 'verification_agent' },
  { id: 'execution',   agent: 'execution_agent' },
  { id: 'memory',      agent: 'memory_agent' },
]

const TERMINAL_STATUSES = new Set(['completed','failed','stopped','escalated','pending_a2a'])

function resolveAgentStatus(d) {
  if (d.success !== undefined) return d.success ? 'success' : 'failed'
  if (['success','failed','running','skipped'].includes(d.status)) return d.status
  return 'failed'
}

function buildAgentMapFromRuns(agentRuns) {
  const map = {}
  if (!Array.isArray(agentRuns)) return map
  agentRuns.forEach(r => {
    if (!r?.node_id) return
    map[r.node_id] = { ...r, status: r.status === 'success' ? 'success' : r.status === 'failed' ? 'failed' : r.status === 'running' ? 'running' : 'skipped' }
  })
  return map
}

function buildEventsFromRuns(agentRuns) {
  const seen = new Set()
  return (agentRuns || []).filter(r => {
    if (!r?.node_id || seen.has(r.node_id)) return false
    seen.add(r.node_id); return true
  }).map(r => ({
    type: r.status === 'success' ? 'agent_completed' : 'agent_failed',
    node_id: r.node_id, agent_type: r.agent_type,
    model_used: r.model_used || '', cost_usd: r.cost_usd || 0,
    tokens_in: r.tokens_in || 0, tokens_out: r.tokens_out || 0,
    confidence: r.confidence, ts: r.completed_at || new Date().toISOString(), _fromDB: true,
    error: r.error || null,
    error_type: r.error_type || null,
    error_message: r.error_message || null,
    error_provider: r.error_provider || null,
    error_safe_detail: r.error_safe_detail || null,
    llm_attempted: r.llm_attempted ?? true,
    tools_used: r.tools_used || [],
    duration_ms: r.duration_ms || 0,
    node_description: r.node_description || '',
  }))
}

// ── Fork Modal ────────────────────────────────────────────────────────────────
function ForkModal({ nodeId, runId, api, onClose }) {
  const navigate = useNavigate()
  const [contextPatch, setContextPatch] = useState('{}')
  const [jsonErr, setJsonErr] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError]     = useState('')

  const submit = async () => {
    let patch = null
    const trimmed = contextPatch.trim()
    if (trimmed && trimmed !== '{}') {
      try { patch = JSON.parse(trimmed) } catch { setJsonErr('Fix JSON before forking'); return }
    }
    setLoading(true); setError('')
    try {
      const result = await api.post(`/workflows/${runId}/fork`, { from_node_id: nodeId, context_patch: patch })
      onClose(); navigate(`/workflows/${result.run_id}`)
    } catch (err) { setError(err.message) }
    finally { setLoading(false) }
  }

  return (
    <Modal open onClose={onClose} title="⏪ Time-Travel Fork" subtitle={`Resume from node: ${nodeId}`} width="max-w-lg">
      <div className="space-y-4">
        <Alert type="info">
          A new run will be created replaying from this node forward, reusing the accumulated context from the original run. Earlier agents are NOT re-run.
        </Alert>
        <div>
          <label className="block text-xs font-medium text-[rgb(var(--text-secondary))] mb-1.5">Context Patch (JSON — optional)</label>
          <textarea
            value={contextPatch}
            onChange={e => { setContextPatch(e.target.value); try { JSON.parse(e.target.value); setJsonErr('') } catch { setJsonErr('Invalid JSON') } }}
            rows={6}
            spellCheck={false}
            className={cn('input-base font-mono text-xs resize-none text-success', jsonErr && '!border-danger')}
            placeholder={'{\n  "reasoning": { "situation_summary": "override..." }\n}'}
          />
          {jsonErr && <p className="text-xs text-danger mt-1">{jsonErr}</p>}
        </div>
        {error && <Alert type="error" onClose={() => setError('')}>{error}</Alert>}
        <div className="flex gap-2">
          <Button variant="gradient" loading={loading} onClick={submit} disabled={!!jsonErr} className="flex-1" icon={<Zap className="w-4 h-4" />}>
            Create Fork Run
          </Button>
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
        </div>
      </div>
    </Modal>
  )
}

// ── Status Banner ─────────────────────────────────────────────────────────────
function StatusBanner({ status, workflow, liveStats, navigate }) {
  const cfg = {
    completed: { cls: 'border-success/25 bg-success/5', icon: '✅', title: 'Workflow Completed', color: 'text-success' },
    failed:    { cls: 'border-danger/25 bg-danger/5',   icon: '❌', title: 'Workflow Failed',    color: 'text-danger' },
    stopped:   { cls: 'border-danger/25 bg-danger/5',   icon: '⏹', title: 'Workflow Stopped',   color: 'text-danger' },
    escalated: { cls: 'border-warning/25 bg-warning/5', icon: '⚠️', title: 'Human Decision Required', color: 'text-warning' },
    pending_a2a:{ cls: 'border-primary-500/25 bg-primary-500/5', icon: '🤖', title: 'A2A Permission Pending', color: 'text-primary-400' },
  }[status]

  if (!cfg) return null

  // Extract error info from outcome or error_log
  const failedError = workflow?.outcome?.error || workflow?.error || null
  const failedNode = workflow?.outcome?.failed_node || null
  const engineError = workflow?.outcome?.status === 'engine_error'

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className={cn('border rounded-2xl p-4 flex items-start gap-4', cfg.cls)}
    >
      <span className="text-2xl">{cfg.icon}</span>
      <div className="flex-1">
        <p className={cn('font-semibold text-sm', cfg.color)}>{cfg.title}</p>
        <p className="text-xs text-[rgb(var(--text-muted))] mt-0.5">
          Final cost: {fmtCost(liveStats.cost_usd)} · Tokens in: {fmtTokens(liveStats.tokens_in)}
        </p>
        {status === 'escalated' && workflow?.outcome?.reason && (
          <p className="text-xs text-[rgb(var(--text-secondary))] mt-1">{workflow.outcome.reason}</p>
        )}
        {status === 'failed' && failedError && (
          <div className="mt-2 space-y-1">
            <p className="text-xs font-semibold text-danger">{failedNode ? `Failed at node: ${failedNode}` : 'Workflow error'}</p>
            <p className="text-xs text-[rgb(var(--text-secondary))] font-mono bg-danger/5 rounded-lg px-2 py-1.5 border border-danger/10 max-h-24 overflow-y-auto">
              {failedError}
            </p>
          </div>
        )}
        {status === 'failed' && engineError && (
          <p className="text-xs text-warning mt-1">
            LLM call was not attempted — workflow failed before agent execution.
          </p>
        )}
      </div>
      {status === 'escalated' && (
        <Button size="sm" variant="warning" onClick={() => navigate('/escalations')}>
          Decide <ExternalLink className="w-3.5 h-3.5" />
        </Button>
      )}
    </motion.div>
  )
}

// ── Main WorkflowDetail ────────────────────────────────────────────────────────
export default function WorkflowDetail() {
  const { runId }     = useParams()
  const navigate      = useNavigate()
  const { api, user } = useAuth()
  const { subscribe } = useWebSocket()
  const queryClient   = useQueryClient()
  const isAdmin       = user?.role === 'super_admin'

  const { streamingTexts, agentLiveOutputs, setStreamingText, appendStreamingText, clearStreamingText, addLiveOutput, clearLiveOutput, resetAll } = useStreamingStore()

  const [agents,      setAgents]      = useState({})
  const [liveStats,   setLiveStats]   = useState({ cost_usd: 0, tokens_in: 0, tokens_out: 0 })
  const [events,      setEvents]      = useState([])
  const [pendingA2A,  setPendingA2A]  = useState(null)
  const [pendingEsc,  setPendingEsc]  = useState(null)
  const [seededFromDB, setSeededFromDB] = useState(false)
  const [activeEstimate, setActiveEstimate] = useState({ input_cost: 0, tokens_out: 0, output_cost_per_token: 0 })
  const [forkNode,    setForkNode]    = useState(null)
  const [activeTab,   setActiveTab]   = useState('pipeline')

  const streamingFlushTimer = useRef(null)
  const streamingRefs       = useRef({})

  // Query
  const { data: workflow, isLoading, error: wfError } = useQuery({
    queryKey: ['workflow', runId],
    queryFn: () => api.get(`/workflows/${runId}/status`),
    enabled: !!runId,
    refetchInterval: (q) => {
      const s = q.state.data?.status
      return s && TERMINAL_STATUSES.has(s) ? false : 2000
    },
    staleTime: 0,
  })

  const { data: dag } = useQuery({
    queryKey: ['dag', workflow?.workflow_name],
    queryFn: () => api.get(`/config/dag/${workflow?.workflow_name}`),
    enabled: !!workflow?.workflow_name,
    staleTime: Infinity,
  })

  const { data: escsData } = useQuery({
    queryKey: ['escalations-for-run', runId],
    queryFn: async () => {
      const all = await api.get('/escalations?status=pending')
      return (all || []).find(e => e.instance_id === runId) || null
    },
    enabled: !!runId && workflow?.status === 'escalated',
    refetchInterval: 5000,
  })

  const { data: a2aData } = useQuery({
    queryKey: ['a2a-for-run', runId],
    queryFn: async () => {
      const all = await api.get('/a2a/requests')
      return (all || []).find(a => a.run_id === runId) || null
    },
    enabled: !!runId && workflow?.status === 'pending_a2a',
    refetchInterval: 5000,
  })

  const invalidate = useCallback(() => queryClient.invalidateQueries({ queryKey: ['workflow', runId] }), [queryClient, runId])

  // Mutations
  const { mutate: pauseWf,  isPending: isPausing  } = useMutation({ mutationFn: () => api.post(`/workflows/${runId}/pause`,  {}), onSuccess: invalidate })
  const { mutate: stopWf,   isPending: isStopping  } = useMutation({ mutationFn: () => api.post(`/workflows/${runId}/stop`,   {}), onSuccess: invalidate })
  const { mutate: resumeWf, isPending: isResuming  } = useMutation({ mutationFn: () => api.post(`/workflows/${runId}/resume`, {}), onSuccess: invalidate })

  // Reset on run change
  useEffect(() => {
    setSeededFromDB(false); setEvents([]); setAgents({}); setLiveStats({ cost_usd: 0, tokens_in: 0, tokens_out: 0 })
    setPendingA2A(null); setPendingEsc(null); resetAll()
    setActiveEstimate({ input_cost: 0, tokens_out: 0, output_cost_per_token: 0 })
    if (streamingFlushTimer.current) clearTimeout(streamingFlushTimer.current)
  }, [runId, resetAll])

  // Seed from DB
  useEffect(() => {
    if (!workflow) return
    const isTerminal = TERMINAL_STATUSES.has(workflow.status)
    const hasRuns = Array.isArray(workflow.agent_runs) && workflow.agent_runs.length > 0

    if (hasRuns || (!isTerminal && workflow?.current_node)) {
      const map = hasRuns ? buildAgentMapFromRuns(workflow.agent_runs) : {}
      if (!isTerminal && workflow?.current_node) {
        const cur = workflow.current_node
        if (!map[cur] || map[cur].status !== 'success') map[cur] = { ...(map[cur] || {}), status: 'running' }
      }
      setAgents(isTerminal ? map : prev => {
        const merged = { ...map }
        Object.entries(prev).forEach(([k, v]) => { if (v?.status === 'running') merged[k] = { ...(map[k] || {}), ...v } })
        return merged
      })
    }

    const dbCost = workflow.total_cost_usd || 0, dbIn = workflow.total_tokens_in || 0, dbOut = workflow.total_tokens_out || 0
    if (isTerminal) setLiveStats({ cost_usd: dbCost, tokens_in: dbIn, tokens_out: dbOut })
    else if (dbCost > 0) setLiveStats(p => ({ cost_usd: Math.max(p.cost_usd, dbCost), tokens_in: Math.max(p.tokens_in, dbIn), tokens_out: Math.max(p.tokens_out, dbOut) }))

    if (!seededFromDB && hasRuns) {
      const dbEvents = buildEventsFromRuns(workflow.agent_runs)
      if (dbEvents.length > 0) { setEvents(prev => prev.filter(e => !e._fromDB).length > 0 ? prev : dbEvents); setSeededFromDB(true) }
    } else if (!seededFromDB && isTerminal) { setSeededFromDB(true) }
  }, [workflow?.run_id, workflow?.status, workflow?.current_node, workflow?.agent_runs?.length, seededFromDB])

  useEffect(() => { if (escsData) setPendingEsc(escsData) }, [escsData])
  useEffect(() => { if (a2aData)  setPendingA2A(a2aData)  }, [a2aData])

  // WebSocket
  useEffect(() => {
    if (!runId) return
    const match = ev => ev.data?.run_id === runId

    const addEvent = (type, data) => {
      setEvents(prev => {
        const filtered = data.node_id ? prev.filter(e => !(e._fromDB && e.node_id === data.node_id)) : prev
        return [...filtered, { type, ...data, ts: new Date().toISOString() }].slice(-500)
      })
    }

    const unsubs = [
      subscribe('agent_started', ev => {
        if (!match(ev)) return
        const d = ev.data
        setActiveEstimate({ input_cost: d.input_cost_estimate || 0, tokens_out: 0, output_cost_per_token: d.output_cost_per_token || 0 })
        streamingRefs.current[d.node_id] = ''
        clearLiveOutput(d.node_id)
        setAgents(p => ({ ...p, [d.node_id]: { ...(p[d.node_id]||{}), status: 'running', agent_type: d.agent_type, tokens_in_estimate: d.tokens_in_estimate, input_cost_estimate: d.input_cost_estimate, model_estimate: d.model_estimate } }))
        queryClient.setQueryData(['workflow', runId], old => old ? { ...old, status: 'running', current_node: d.node_id } : old)
        addEvent('agent_started', d)
      }),

      subscribe('agent_completed', ev => {
        if (!match(ev)) return
        setActiveEstimate({ input_cost: 0, tokens_out: 0, output_cost_per_token: 0 })
        const d = ev.data

        if (streamingRefs.current[d.node_id]) {
          const completedText = streamingRefs.current[d.node_id]
          streamingRefs.current[d.node_id] = ''
          setStreamingText(d.node_id, '')
          addLiveOutput(d.node_id, { type: 'llm', tool: '', preview: completedText.slice(0, 320), ts: Date.now() })
        }

        const wf = queryClient.getQueryData(['workflow', runId])
        const isTerminalNow = wf && TERMINAL_STATUSES.has(wf.status)
        if (!isTerminalNow) setLiveStats(p => ({ cost_usd: p.cost_usd + (d.cost_usd||0), tokens_in: p.tokens_in + (d.tokens_in||0), tokens_out: p.tokens_out + (d.tokens_out||0) }))

        setAgents(p => ({
          ...p,
          [d.node_id]: { ...(p[d.node_id]||{}), status: resolveAgentStatus(d), tokens_in: d.tokens_in||0, tokens_out: d.tokens_out||0, cost_usd: d.cost_usd||0, model_used: d.model_used||'', confidence: d.confidence, agent_type: d.agent_type||(p[d.node_id]?.agent_type), tools_used: d.tools_used||[], _prosecutor_issues: d._prosecutor_issues, _judge_verdict: d._judge_verdict, delta_analysis: d.delta_analysis, delta_vs_history: d.delta_vs_history, delta_trend: d.delta_trend, error: d.error||null, error_type: d.error_type||null, error_message: d.error_message||null, error_provider: d.error_provider||null, error_safe_detail: d.error_safe_detail||null, llm_attempted: d.llm_attempted ?? true, },
        }))
        addEvent('agent_completed', d)
        setSeededFromDB(true)
      }),

      subscribe('agent_live_output', ev => {
        if (!match(ev)) return
        const { node_id, type, preview, tool, token } = ev.data

        if (type === 'llm_token') {
          streamingRefs.current[node_id] = (streamingRefs.current[node_id] || '') + (token || '')
          const len = streamingRefs.current[node_id].length
          if (len % 20 === 0) setActiveEstimate(p => ({ ...p, tokens_out: Math.floor(len / 4) }))

          if (streamingFlushTimer.current) clearTimeout(streamingFlushTimer.current)
          streamingFlushTimer.current = setTimeout(() => {
            const snap = {}
            Object.entries(streamingRefs.current).forEach(([nid, txt]) => { if (txt) snap[nid] = txt })
            Object.entries(snap).forEach(([nid, txt]) => setStreamingText(nid, txt))
          }, 50)
          return
        }

        if (streamingRefs.current[node_id]) {
          const completedText = streamingRefs.current[node_id]
          streamingRefs.current[node_id] = ''
          setStreamingText(node_id, '')
          addLiveOutput(node_id, { type: 'llm', tool: '', preview: completedText.slice(0, 320), ts: Date.now() })
        }

        addLiveOutput(node_id, { type: type || 'llm', tool: tool || '', preview: preview || '', ts: Date.now() })
      }),

      subscribe('a2a_permission_requested', ev => {
        if (!match(ev)) return
        setPendingA2A(ev.data); addEvent('a2a_permission_requested', ev.data)
        queryClient.invalidateQueries({ queryKey: ['a2a-for-run', runId] })
      }),

      subscribe('escalation_created', ev => {
        if (!match(ev)) return
        setPendingEsc({ ...ev.data, id: ev.data.id || ev.data.escalation_id })
        queryClient.setQueryData(['workflow', runId], old => old ? { ...old, status: 'escalated' } : old)
        addEvent('escalation_created', ev.data)
        queryClient.invalidateQueries({ queryKey: ['escalations-for-run', runId] })
      }),

      subscribe('workflow_completed', ev => { if (match(ev)) { queryClient.invalidateQueries({ queryKey: ['workflow', runId] }); addEvent('workflow_completed', ev.data) } }),
      subscribe('workflow_failed',    ev => { if (match(ev)) { queryClient.invalidateQueries({ queryKey: ['workflow', runId] }); addEvent('workflow_failed', ev.data) } }),
      subscribe('workflow_paused',    ev => { if (match(ev)) { addEvent('workflow_paused', ev.data);  queryClient.invalidateQueries({ queryKey: ['workflow', runId] }) } }),
      subscribe('workflow_stopped',   ev => { if (match(ev)) { addEvent('workflow_stopped', ev.data); queryClient.invalidateQueries({ queryKey: ['workflow', runId] }) } }),
      subscribe('workflow_resumed',   ev => { if (match(ev)) { addEvent('workflow_resumed', ev.data); queryClient.invalidateQueries({ queryKey: ['workflow', runId] }) } }),
    ]

    return () => {
      unsubs.forEach(fn => fn())
      if (streamingFlushTimer.current) clearTimeout(streamingFlushTimer.current)
    }
  }, [runId, subscribe, queryClient, addLiveOutput, clearLiveOutput, setStreamingText])

  const deltaAnalysis = useMemo(() => {
    for (const [nodeId, data] of Object.entries(agents)) {
      if ((nodeId.includes('memory') || data.agent_type === 'memory_agent') && data.delta_analysis) return data.delta_analysis
    }
    if (Array.isArray(workflow?.agent_runs)) {
      const memRun = workflow.agent_runs.find(r => r.agent_type === 'memory_agent' || (r.node_id||'').includes('memory'))
      if (memRun?.delta_analysis) return memRun.delta_analysis
    }
    return workflow?.outcome?.delta_analysis || null
  }, [agents, workflow?.agent_runs, workflow?.outcome])

  const handleFork = useCallback((nodeId) => setForkNode(nodeId), [])

  const dagNodes  = (dag?.nodes || []).map(n => ({ id: n.id, agent: n.agent }))
  const nodes     = dagNodes.length > 0 ? dagNodes : DEFAULT_NODES
  const dagEdges  = (dag?.edges || []).map(e => ({ from: e.from, to: e.to }))
  const isRunning = workflow?.status === 'running'
  const isTerminal = TERMINAL_STATUSES.has(workflow?.status || '')
  const activeTotalCost = activeEstimate.input_cost + activeEstimate.tokens_out * activeEstimate.output_cost_per_token
  const activeNode = Object.keys(agents).find(k => agents[k]?.status === 'running') || workflow?.current_node
  const showSummary = isTerminal && ((workflow?.agent_runs?.length > 0) || workflow?.outcome?.situation_summary)

  const TABS = [
    { value: 'pipeline', label: 'Pipeline',    icon: Layers },
    { value: 'logs',     label: 'Logs',        icon: Terminal, badge: events.length },
    { value: 'summary',  label: 'Analysis',    icon: BarChart3 },
  ]

  if (isLoading) return (
    <div className="flex items-center justify-center h-64">
      <div className="text-center">
        <Spinner size="xl" className="mx-auto mb-3" />
        <p className="text-sm text-[rgb(var(--text-muted))]">Loading workflow…</p>
      </div>
    </div>
  )

  if (wfError) return <Alert type="error">{wfError.message}</Alert>

  if (workflow?.workflow_name === 'email_summarizer' || workflow?.workflow_name?.includes('email')) {
    return <EmailSummarizerPage runIdOverride={runId} />
  }

  return (
    <div className="space-y-5">
      {/* Action banner */}
      {(pendingA2A || pendingEsc) && (
        <motion.div
          initial={{ opacity: 0, y: -8 }}
          animate={{ opacity: 1, y: 0 }}
          className={cn('rounded-2xl border p-4 flex items-center gap-3', pendingA2A ? 'bg-primary-500/8 border-primary-500/25' : 'bg-warning/8 border-warning/25')}
        >
          <span className="text-2xl">{pendingA2A ? '🤖' : '⚠️'}</span>
          <div className="flex-1">
            <p className={cn('text-sm font-bold', pendingA2A ? 'text-primary-400' : 'text-warning')}>
              {pendingA2A ? 'Agent-to-Agent request waiting for approval' : 'Escalation requires your decision'}
            </p>
            <p className="text-xs text-[rgb(var(--text-muted))] mt-0.5">{pendingA2A ? pendingA2A.reason : pendingEsc?.reason}</p>
          </div>
          <span className="px-2.5 py-1 text-xs bg-danger text-white rounded-full font-bold animate-pulse">Action Needed</span>
        </motion.div>
      )}

      {/* Header */}
      <div className="flex items-start gap-4 flex-wrap">
        <button onClick={() => navigate(-1)} className="p-2 rounded-xl border border-[rgb(var(--border))] bg-[rgb(var(--bg-hover))] hover:border-primary-500/40 text-[rgb(var(--text-secondary))] hover:text-primary-400 transition-all flex-shrink-0">
          <ArrowLeft className="w-4 h-4" />
        </button>
        <div className="flex-1 min-w-0">
          <h1 className="text-xl font-bold text-[rgb(var(--text-primary))] truncate">{getDisplayName(workflow?.workflow_name, workflow?.display_name)}</h1>
          <div className="flex items-center gap-2.5 mt-1 flex-wrap text-xs text-[rgb(var(--text-muted))]">
            <span className="font-mono bg-[rgb(var(--bg-card))] px-2 py-0.5 rounded border border-[rgb(var(--border))]">{runId?.slice(0, 8)}</span>
            <span className="flex items-center gap-1"><Clock className="w-3 h-3" />{timeAgo(workflow?.started_at)}</span>
            <span className="px-2 py-0.5 rounded-full text-[11px] font-semibold border bg-purple-50 text-purple-700 border-purple-200">
              Trigger: {workflow?.trigger_type || (workflow?.trigger_source === 'manual_ui' ? 'Manual' : 'New Email')}
            </span>
            {workflow?.message_count != null && (
              <span className="px-2 py-0.5 rounded-full text-[11px] font-semibold border bg-blue-50 text-blue-700 border-blue-200">
                Messages: {workflow.message_count}
              </span>
            )}
          </div>
        </div>

        <div className="flex items-center gap-2 flex-wrap">
          {deltaAnalysis && <TrendIndicator deltaAnalysis={deltaAnalysis} compact />}
          <Badge status={workflow?.status || 'pending'} />
          {isRunning && (
            <>
              <Button size="sm" variant="warning" loading={isPausing} onClick={() => pauseWf()} icon={<Pause className="w-3.5 h-3.5" />}>Pause</Button>
              <Button size="sm" variant="danger"  loading={isStopping} onClick={() => stopWf()}  icon={<Square className="w-3.5 h-3.5" />}>Stop</Button>
            </>
          )}
          {workflow?.status === 'paused' && (
            <Button size="sm" variant="success" loading={isResuming} onClick={() => resumeWf()} icon={<Play className="w-3.5 h-3.5" />}>Resume</Button>
          )}
          <Button size="sm" variant="secondary" onClick={invalidate} icon={<RefreshCw className="w-3.5 h-3.5" />} />
        </div>
      </div>

      {/* Cost Ribbon */}
      <CostRibbon
        liveStats={liveStats}
        isRunning={isRunning}
        activeCost={isRunning ? activeTotalCost : 0}
        activeTokensOut={isRunning ? activeEstimate.tokens_out : 0}
      />

      {/* Status banner */}
      {isTerminal && <StatusBanner status={workflow.status} workflow={workflow} liveStats={liveStats} navigate={navigate} />}

      {/* Developer Debug Panel — failed runs only */}
      {workflow?.status === 'failed' && (workflow?.error || workflow?.outcome?.error) && (() => {
        const errorMsg = workflow?.error || workflow?.outcome?.error || ''
        const isConfigFailure = errorMsg.includes('blocking error') || errorMsg.includes('Configuration required') || errorMsg.includes('Tenant config')
        const configMissingFields = isConfigFailure ? errorMsg.split(': ').slice(1).join('; ').split('; ').map(s => s.trim()).filter(Boolean) : []
        const llmAttempted = workflow?.outcome?.llm_attempted ?? !isConfigFailure

        return (
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            className="border border-orange-200 bg-orange-50/50 rounded-2xl p-4"
          >
            <details open>
              <summary className="text-xs font-bold text-orange-700 cursor-pointer select-none flex items-center gap-1.5">
                <span>🔧</span> Developer Debug — Failure Details
              </summary>
              <div className="mt-3 space-y-2 text-xs font-mono">
                <div className="grid grid-cols-2 gap-2">
                  <div><span className="text-orange-600 font-semibold">Workflow:</span> <span className="text-gray-800">{workflow?.workflow_name}</span></div>
                  <div><span className="text-orange-600 font-semibold">Run ID:</span> <span className="text-gray-800">{runId?.slice(0, 8)}...</span></div>
                  <div><span className="text-orange-600 font-semibold">Failure Type:</span> <span className="text-gray-800">{isConfigFailure ? 'Configuration Validation' : (workflow?.outcome?.error_type || workflow?.outcome?.status || 'Runtime Error')}</span></div>
                  <div><span className="text-orange-600 font-semibold">Failed Before Node Execution:</span> <span className="text-gray-800">{isConfigFailure ? 'Yes' : 'No'}</span></div>
                  <div><span className="text-orange-600 font-semibold">Failed Node:</span> <span className="text-gray-800">{workflow?.outcome?.failed_node || (isConfigFailure ? '— (pre-execution)' : '—')}</span></div>
                  <div><span className="text-orange-600 font-semibold">Agent Type:</span> <span className="text-gray-800">{agents[workflow?.outcome?.failed_node]?.agent_type || '—'}</span></div>
                  <div><span className="text-orange-600 font-semibold">Status:</span> <span className="text-gray-800">{workflow?.status}</span></div>
                  <div><span className="text-orange-600 font-semibold">LLM Call Attempted:</span> <span className="text-gray-800">{llmAttempted ? 'Yes' : 'No — workflow failed before agent execution'}</span></div>
                  <div><span className="text-orange-600 font-semibold">Provider:</span> <span className="text-gray-800">{workflow?.outcome?.error_provider || '—'}</span></div>
                  <div><span className="text-orange-600 font-semibold">Timestamp:</span> <span className="text-gray-800">{workflow?.completed_at || '—'}</span></div>
                </div>
                {isConfigFailure && configMissingFields.length > 0 && (
                  <div>
                    <span className="text-orange-600 font-semibold">Missing Fields:</span>
                    <ul className="mt-1 space-y-0.5 text-gray-800">
                      {configMissingFields.map((f, i) => (
                        <li key={i} className="flex items-start gap-1.5">
                          <span className="text-orange-500">•</span>
                          <span>{f}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
                {(workflow?.error || workflow?.outcome?.error) && (
                  <div>
                    <span className="text-orange-600 font-semibold">Error:</span>
                    <pre className="mt-1 p-2 bg-white border border-orange-200 rounded-lg text-[11px] text-gray-800 whitespace-pre-wrap max-h-40 overflow-y-auto">
                      {workflow?.error || workflow?.outcome?.error}
                    </pre>
                  </div>
                )}
                {workflow?.outcome?.error_safe_detail && (
                  <div>
                    <span className="text-orange-600 font-semibold">Safe Detail:</span>
                    <pre className="mt-1 p-2 bg-white border border-orange-200 rounded-lg text-[11px] text-gray-800 whitespace-pre-wrap max-h-32 overflow-y-auto">
                      {workflow.outcome.error_safe_detail}
                    </pre>
                  </div>
                )}
              </div>
            </details>
          </motion.div>
        )
      })()}

      {/* Running indicator */}
      {isRunning && workflow?.current_node && (
        <div className="flex items-center gap-2 text-sm text-success">
          <span className="relative flex h-2.5 w-2.5">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-success opacity-75" />
            <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-success" />
          </span>
          <span>Currently executing: <strong>{workflow.current_node}</strong></span>
        </div>
      )}

      {/* Tab content */}
      <TabGroup
        tabs={TABS}
        value={activeTab}
        onChange={setActiveTab}
        className="w-full max-w-md"
      />

      <AnimatePresence mode="wait">
        <motion.div
          key={activeTab}
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.18 }}
        >
          {activeTab === 'pipeline' && (
            <Card title="Agent Pipeline" subtitle="Live execution flow">
              <NodePipeline
                nodes={nodes}
                edges={dagEdges}
                agents={agents}
                agentRuns={workflow?.agent_runs || []}
                currentNode={activeNode}
                isRunning={isRunning}
              />
            </Card>
          )}

          {activeTab === 'logs' && (
            <Card
              title="Execution Log"
              action={<span className="text-xs text-[rgb(var(--text-muted))]">{events.length} events</span>}
            >
              <LogTerminal events={events} />
            </Card>
          )}

          {activeTab === 'summary' && (
            showSummary
              ? <WorkflowSummary workflow={workflow} dag={dag} agents={agents} isAdmin={isAdmin} onFork={handleFork} />
              : <Card>
                  <div className="text-center py-12 text-sm text-[rgb(var(--text-muted))]">
                    {isRunning ? 'Analysis will appear after the workflow completes' : 'No analysis data available'}
                  </div>
                </Card>
          )}
        </motion.div>
      </AnimatePresence>

      {/* Decision Portal */}
      <DecisionPortal
        pendingA2A={pendingA2A}
        pendingEsc={pendingEsc}
        api={api}
        onA2ADone={() => { setPendingA2A(null); queryClient.invalidateQueries({ queryKey: ['a2a-for-run', runId] }); invalidate() }}
        onEscDone={() => { setPendingEsc(null); queryClient.invalidateQueries({ queryKey: ['escalations-for-run', runId] }); invalidate() }}
        onEscDismiss={() => setPendingEsc(null)}
      />

      {forkNode && (
        <ForkModal nodeId={forkNode} runId={runId} api={api} onClose={() => setForkNode(null)} />
      )}
    </div>
  )
}