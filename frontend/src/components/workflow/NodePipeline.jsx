// frontend/src/components/workflow/NodePipeline.jsx
// ─────────────────────────────────────────────────────────────────────────────
// KEY CHANGES vs original:
//  1. dagre auto-layout — no more hardcoded grid math
//  2. LiveOutputMini reads from Zustand directly — eliminates prop-drilling
//     that caused the whole canvas to re-render on every LLM token
//  3. setRfNodes / setRfEdges only fire when DAG *structure* changes
//     (not on every streaming tick)
//  4. Agent icons use lucide-react from helpers, no emojis
//  5. Animated SVG "data flow" pulse on active edges
// ─────────────────────────────────────────────────────────────────────────────
import { useEffect, useState, useCallback, useRef, memo } from 'react'
import {
  ReactFlow, Background, Controls, useNodesState, useEdgesState,
  Handle, Position, MarkerType, BackgroundVariant,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import dagre from 'dagre'
import { motion } from 'framer-motion'
import { Spinner, Modal, Badge, cn } from '../ui'
import { fmtCost, fmtTokens, AGENT_ICON_MAP, AGENT_ICON_FALLBACK, AGENT_LABELS, AGENT_DESCRIPTIONS } from '../../utils/helpers'
import { useTheme } from '../../contexts/ThemeContext'
import { useStreamingStore } from '../../utils/appStore'

// ── Dagre layout helper ───────────────────────────────────────────────────────
const NODE_W = 200
const NODE_H = 110

function getLayoutedElements(nodes, edges) {
  const g = new dagre.graphlib.Graph()
  g.setDefaultEdgeLabel(() => ({}))
  g.setGraph({ rankdir: 'LR', nodesep: 70, ranksep: 110, marginx: 20, marginy: 20 })

  nodes.forEach(n => g.setNode(n.id, { width: NODE_W, height: NODE_H }))
  edges.forEach(e => g.setEdge(e.source, e.target))

  dagre.layout(g)

  return nodes.map(n => {
    const pos = g.node(n.id)
    return {
      ...n,
      position: { x: pos.x - NODE_W / 2, y: pos.y - NODE_H / 2 },
    }
  })
}

// ── Status config ──────────────────────────────────────────────────────────────
const STATUS_CFG = {
  pending: { border: '#1E2A3A', bg: 'rgba(30,42,58,0.4)',  text: '#64748B', dot: '○' },
  running: { border: '#10E580', bg: 'rgba(16,229,128,0.06)', text: '#10E580', dot: '●' },
  success: { border: '#10E580', bg: 'rgba(16,229,128,0.04)', text: '#10E580', dot: '✓' },
  failed:  { border: '#FF4757', bg: 'rgba(255,71,87,0.06)',  text: '#FF4757', dot: '✗' },
  skipped: { border: '#334155', bg: 'rgba(51,65,85,0.3)',    text: '#475569', dot: '⊘' },
}

// ── LiveOutputMini reads DIRECTLY from Zustand — no prop drilling ─────────────
// This means only this tiny component re-renders on each token, not the whole canvas.
const LiveOutputMini = memo(function LiveOutputMini({ nodeId }) {
  // Selector ensures only this component re-renders when its node's data changes
  const entries     = useStreamingStore(s => s.agentLiveOutputs[nodeId] || [])
  const streaming   = useStreamingStore(s => s.streamingTexts[nodeId]   || '')
  const ref = useRef(null)

  useEffect(() => {
    if (ref.current) ref.current.scrollTop = ref.current.scrollHeight
  }, [entries.length, streaming.length])

  if (!entries.length && !streaming) return null

  return (
    <div className="mt-2 pt-1.5 border-t border-white/5">
      <div className="flex items-center gap-1 mb-1">
        <span className="relative flex h-1.5 w-1.5 flex-shrink-0">
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-success opacity-75" />
          <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-success" />
        </span>
        <span className="text-[9px] text-success uppercase tracking-widest font-bold">Live</span>
      </div>
      <div ref={ref} className="max-h-[5.5rem] overflow-y-auto space-y-0.5 text-[9px] font-mono leading-relaxed scrollbar-none">
        {entries.slice(-5).map((entry, i) => {
          const text   = typeof entry === 'string' ? entry : (entry.preview || '')
          const isTool = typeof entry === 'object' && (entry.type === 'tool' || entry.type === 'tool_calling')
          return (
            <div key={i} className={cn('truncate', isTool ? 'text-accent' : 'text-[rgb(var(--text-muted))]')}>
              {isTool ? `⟳ ${entry.tool}` : text.slice(0, 55)}
            </div>
          )
        })}
        {streaming && (
          <div className="text-success/80 break-all">
            {streaming.slice(-70)}
            <span className="animate-typingCursor">█</span>
          </div>
        )}
      </div>
    </div>
  )
})

// ── Pipeline Agent Node ────────────────────────────────────────────────────────
// `data` contains: status, agentType, nodeId, agentData, isActive
// Live streaming is read from Zustand inside LiveOutputMini — NOT passed as props
function PipelineNode({ data }) {
  const { status, agentType, nodeId, agentData, isActive } = data
  const cfg = STATUS_CFG[status] || STATUS_CFG.pending
  const [showDetail, setShowDetail] = useState(false)

  // Get icon component
  const IconComponent = AGENT_ICON_MAP[agentType] || AGENT_ICON_FALLBACK
  const isClickable = status !== 'pending'

  const hasLiveData = isActive || status === 'running'

  return (
    <>
      <div
        className={cn(
          'relative rounded-2xl transition-all duration-300 select-none',
          isClickable && 'cursor-pointer hover:-translate-y-0.5',
        )}
        style={{
          width: NODE_W,
          border: `2px solid ${cfg.border}`,
          background: cfg.bg,
          boxShadow: isActive
            ? `0 0 18px ${cfg.border}45, 0 0 36px ${cfg.border}15`
            : undefined,
        }}
        onClick={isClickable ? () => setShowDetail(true) : undefined}
      >
        <Handle type="target" position={Position.Left}
          className="!w-2 !h-2 !-left-1 !border !border-[rgb(var(--bg-card))]"
          style={{ background: cfg.border }} />
        <Handle type="source" position={Position.Right}
          className="!w-2 !h-2 !-right-1 !border !border-[rgb(var(--bg-card))]"
          style={{ background: cfg.border }} />

        {/* Breathing pulse border when running */}
        {isActive && (
          <motion.div
            animate={{
              boxShadow: [
                `0 0 0px ${cfg.border}00`,
                `0 0 20px ${cfg.border}55`,
                `0 0 0px ${cfg.border}00`,
              ],
            }}
            transition={{ duration: 2.2, repeat: Infinity, ease: 'easeInOut' }}
            className="absolute -inset-[2px] rounded-[18px] pointer-events-none z-[-1]"
          />
        )}

        {/* Top accent bar */}
        <div
          className="h-1.5 rounded-t-2xl"
          style={{ background: `linear-gradient(90deg, ${cfg.border}, ${cfg.border}66)`, opacity: isActive ? 1 : 0.55 }}
        />

        <div className="p-3">
          <div className="flex items-start gap-2 mb-1.5">
            {/* Lucide icon — crisp vector, no emoji */}
            <div
              className="w-7 h-7 rounded-xl flex items-center justify-center flex-shrink-0"
              style={{ background: `${cfg.border}18` }}
            >
              <IconComponent className="w-4 h-4" style={{ color: cfg.text }} />
            </div>
            <div className="min-w-0 flex-1">
              <p className="text-[11px] font-bold text-[rgb(var(--text-primary))] leading-tight truncate">
                {AGENT_LABELS[agentType] || agentType}
              </p>
              <p className="text-[9px] text-[rgb(var(--text-muted))] font-mono">{nodeId}</p>
            </div>
            <div className="flex-shrink-0">
              {status === 'running'
                ? <Spinner size="sm" color="text-success" />
                : <span className="text-xs font-bold" style={{ color: cfg.text }}>{cfg.dot}</span>
              }
            </div>
          </div>

          {/* Agent metrics */}
          {agentData && status !== 'pending' && (
            <div className="space-y-0.5">
              {agentData.model_used && (
                <p className="text-[9px] text-[rgb(var(--text-muted))] font-mono truncate">
                  {agentData.model_used.split('/').pop()}
                </p>
              )}
              {agentData.cost_usd > 0 && (
                <p className="text-[9px] text-warning font-mono">{fmtCost(agentData.cost_usd)}</p>
              )}
              {agentData.confidence != null && (
                <p className={cn('text-[9px] font-bold',
                  agentData.confidence >= 0.75 ? 'text-success'
                  : agentData.confidence >= 0.5 ? 'text-warning'
                  : 'text-danger'
                )}>
                  {Math.round(agentData.confidence * 100)}% conf
                </p>
              )}
            </div>
          )}

          {/* Live streaming output — reads from Zustand, not props */}
          {hasLiveData && <LiveOutputMini nodeId={nodeId} />}
        </div>
      </div>

      {/* Detail modal */}
      <AgentDetailModal
        open={showDetail}
        onClose={() => setShowDetail(false)}
        nodeId={nodeId}
        agentType={agentType}
        data={agentData}
        status={status}
      />
    </>
  )
}

// ── Agent Detail Modal ────────────────────────────────────────────────────────
function AgentDetailModal({ open, onClose, nodeId, agentType, data, status }) {
  const IconComponent = AGENT_ICON_MAP[agentType] || AGENT_ICON_FALLBACK
  return (
    <Modal
      open={open}
      onClose={onClose}
      title={
        <span className="flex items-center gap-2">
          <IconComponent className="w-4 h-4 text-primary-400" />
          {AGENT_LABELS[agentType] || agentType}
        </span>
      }
      subtitle={nodeId}
      width="max-w-lg"
    >
      {data ? (
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-3 text-xs">
            {[
              ['Status', <Badge status={status} />],
              ['Model', data.model_used
                ? <span className="font-mono text-primary-400">{data.model_used.split('/').pop()}</span>
                : '—'],
              ['Cost', data.cost_usd > 0
                ? <span className="text-warning font-mono">{fmtCost(data.cost_usd)}</span>
                : '—'],
              ['Confidence', data.confidence != null
                ? <span className={data.confidence >= 0.75 ? 'text-success font-bold' : 'text-warning font-bold'}>
                    {Math.round(data.confidence * 100)}%
                  </span>
                : '—'],
              ['Tokens In',  data.tokens_in  > 0 ? <span className="text-accent font-mono">{fmtTokens(data.tokens_in)}</span>   : '—'],
              ['Tokens Out', data.tokens_out > 0 ? <span className="text-primary-400 font-mono">{fmtTokens(data.tokens_out)}</span> : '—'],
              ['Duration', data.duration_ms
                ? <span>{data.duration_ms < 1000 ? `${data.duration_ms}ms` : `${(data.duration_ms / 1000).toFixed(1)}s`}</span>
                : '—'],
              ['Judge', data._judge_verdict
                ? <span className={data._judge_verdict === 'PASS' ? 'text-success font-bold' : 'text-danger font-bold'}>
                    {data._judge_verdict}
                  </span>
                : '—'],
            ].map(([label, val]) => (
              <div key={label} className="surface-card rounded-xl p-3">
                <p className="text-[rgb(var(--text-muted))] mb-1">{label}</p>
                <div>{val}</div>
              </div>
            ))}
          </div>

          {data.tools_used?.length > 0 && (
            <div>
              <p className="text-xs font-semibold text-[rgb(var(--text-secondary))] mb-2">Tools Used</p>
              <div className="flex flex-wrap gap-1.5">
                {data.tools_used.map(t => (
                  <span key={t} className="px-2.5 py-1 bg-primary-500/10 text-primary-400 border border-primary-500/20 rounded-lg text-[11px] font-mono">
                    {t}
                  </span>
                ))}
              </div>
            </div>
          )}

          {data.error && (
            <div className="p-3 bg-danger/8 border border-danger/25 rounded-xl">
              <p className="text-xs font-semibold text-danger mb-1">Error</p>
              <p className="text-xs text-[rgb(var(--text-secondary))] font-mono leading-relaxed">
                {data.error.slice(0, 400)}
              </p>
            </div>
          )}

          {data._prosecutor_faults?.length > 0 && (
            <div className="p-3 bg-warning/8 border border-warning/25 rounded-xl">
              <p className="text-xs font-semibold text-warning mb-1.5">
                Prosecutor Findings ({data._prosecutor_faults.length})
              </p>
              <div className="space-y-1 max-h-32 overflow-y-auto">
                {data._prosecutor_faults.map((f, i) => (
                  <p key={i} className="text-[11px] text-[rgb(var(--text-secondary))] leading-relaxed">{f}</p>
                ))}
              </div>
            </div>
          )}
        </div>
      ) : (
        <div className="text-center py-8 text-sm text-[rgb(var(--text-muted))]">No data available</div>
      )}
    </Modal>
  )
}

const nodeTypes = { pipelineNode: PipelineNode }

// ── NodePipeline ──────────────────────────────────────────────────────────────
export default function NodePipeline({
  nodes: dagNodes,
  edges: dagEdges = [],
  agents,
  agentRuns = [],
  currentNode,
  isRunning,
  // NOTE: liveOutputs / streamingTexts are NOT accepted as props anymore.
  // Each PipelineNode reads directly from Zustand via LiveOutputMini.
}) {
  const { isDark } = useTheme()
  const [rfNodes, setRfNodes, onNodesChange] = useNodesState([])
  const [rfEdges, setRfEdges, onEdgesChange] = useEdgesState([])

  // Track previous dag structure to avoid re-layout on every render
  const prevDagHashRef = useRef('')
  const prevStatusHashRef = useRef('')

  const buildAgentMap = useCallback(() => {
    const map = {}
    ;(agentRuns || []).forEach(r => { if (r?.node_id) map[r.node_id] = r })
    return map
  }, [agentRuns])

  useEffect(() => {
    if (!dagNodes?.length) return
    const agentRunsMap = buildAgentMap()

    // Resolve the real DAG topology. Fall back to a linear chain only when no edges
    // were supplied (keeps the default 6-node pipeline / legacy callers working).
    const nodeIds = new Set(dagNodes.map(n => n.id))
    const edgeList = (dagEdges && dagEdges.length)
      ? dagEdges
          .map(e => ({ from: e.from ?? e.source, to: e.to ?? e.target }))
          .filter(e => e.from && e.to && nodeIds.has(e.from) && nodeIds.has(e.to))
      : dagNodes.slice(0, -1).map((n, i) => ({ from: n.id, to: dagNodes[i + 1].id }))

    // Hash the current statuses to check if only data changed (not structure)
    const statusHash = dagNodes
      .map(n => {
        const data = agents[n.id] || agentRunsMap[n.id]
        return `${n.id}:${data?.status || 'pending'}:${isRunning ? currentNode : ''}`
      })
      .join('|')

    // Hash the dag structure itself (nodes + edges)
    const dagHash =
      dagNodes.map(n => n.id + n.agent).join('|') +
      '::' + edgeList.map(e => `${e.from}>${e.to}`).join('|')

    const structureChanged = dagHash !== prevDagHashRef.current
    const statusChanged    = statusHash !== prevStatusHashRef.current

    if (!structureChanged && !statusChanged) return

    prevDagHashRef.current  = dagHash
    prevStatusHashRef.current = statusHash

    // Build raw nodes (positions assigned by dagre below)
    const rawNodes = dagNodes.map(n => {
      const data = agents[n.id] || agentRunsMap[n.id] || null
      const status = data?.status === 'success'  ? 'success'
        : data?.status === 'failed'  ? 'failed'
        : data?.status === 'running' ? 'running'
        : data?.status === 'skipped' ? 'skipped'
        : 'pending'

      const isActive = isRunning && (currentNode === n.id || status === 'running')

      return {
        id: n.id,
        type: 'pipelineNode',
        position: { x: 0, y: 0 }, // will be overwritten by dagre
        data: {
          status, agentType: n.agent, nodeId: n.id,
          agentData: data, isActive,
          // NO liveOutputs / streamingTexts in data — LiveOutputMini reads Zustand directly
        },
        draggable: false,
      }
    })

    // Build edges from the real DAG topology (branches, joins, conditional paths) —
    // not a hardcoded linear chain, which mis-rendered fan-out/fan-in workflows.
    const rawEdges = edgeList.map(({ from, to }) => {
      const fromStatus = (agents[from] || agentRunsMap[from])?.status || 'pending'
      const toStatus   = (agents[to]   || agentRunsMap[to])?.status   || 'pending'
      const isFlow = isRunning && (currentNode === to || toStatus === 'running')
      const color = fromStatus === 'success' ? '#10E580'
        : fromStatus === 'failed' ? '#FF4757'
        : isFlow ? '#6C63FF'
        : '#1E2A3A'

      return {
        id: `e-${from}-${to}`,
        source: from,
        target: to,
        animated: isFlow,
        markerEnd: { type: MarkerType.ArrowClosed, width: 12, height: 12, color },
        style: {
          stroke: color,
          strokeWidth: isFlow ? 2.5 : 1.5,
          opacity: fromStatus === 'pending' ? 0.3 : 1,
        },
      }
    })

    // Apply dagre layout only when structure changes
    const layoutedNodes = structureChanged
      ? getLayoutedElements(rawNodes, rawEdges)
      : rawNodes.map((n, i) => ({
          ...n,
          position: rfNodes[i]?.position || { x: 0, y: 0 },
        }))

    setRfNodes(layoutedNodes)
    setRfEdges(rawEdges)
  }, [dagNodes, dagEdges, agents, agentRuns, currentNode, isRunning, buildAgentMap])
  // NOTE: liveOutputs / streamingTexts intentionally excluded — they don't affect layout

  if (!dagNodes?.length) return null

  return (
    <div className="w-full rounded-2xl overflow-hidden border border-[rgb(var(--border))] bg-[rgb(var(--bg-surface))]"
      style={{ height: Math.max(220, Math.ceil(dagNodes.length / 4) * 180 + 80) }}>
      <ReactFlow
        nodes={rfNodes}
        edges={rfEdges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        nodeTypes={nodeTypes}
        fitView
        fitViewOptions={{ padding: 0.18 }}
        nodesDraggable={false}
        nodesConnectable={false}
        panOnDrag={false}
        zoomOnScroll={false}
        zoomOnDoubleClick={false}
        elementsSelectable={false}
        proOptions={{ hideAttribution: true }}
      >
        <Background
          variant={BackgroundVariant.Dots}
          gap={22}
          size={1}
          color={isDark ? 'rgba(108,99,255,0.09)' : 'rgba(108,99,255,0.14)'}
        />
        <Controls showInteractive={false} />
      </ReactFlow>

      {/* Running indicator pill */}
      {isRunning && currentNode && (
        <div className="absolute bottom-3 left-1/2 -translate-x-1/2 px-4 py-1.5 glass rounded-full text-xs font-medium text-[rgb(var(--text-secondary))] flex items-center gap-2 pointer-events-none">
          <span className="w-2 h-2 rounded-full bg-success animate-pulse" />
          {AGENT_LABELS[dagNodes.find(n => n.id === currentNode)?.agent] || currentNode}
        </div>
      )}
    </div>
  )
}