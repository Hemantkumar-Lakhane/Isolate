// frontend/src/components/workflow/LogTerminal.jsx
// ─────────────────────────────────────────────────────────────────────────────
// KEY CHANGES vs original:
//  1. react-virtuoso — only visible rows rendered, 60 FPS at 500+ events
//  2. No framer-motion per LogLine — CSS transition only (massive perf win)
//  3. Terminal aesthetic: gradient header, bottom fade mask, macOS dots
//  4. Auto-scroll to bottom on new events
// ─────────────────────────────────────────────────────────────────────────────
import { useRef, useCallback } from 'react'
import { Virtuoso } from 'react-virtuoso'
import { Terminal } from 'lucide-react'
import { fmtCost, AGENT_LABELS } from '../../utils/helpers'
import { cn } from '../ui'

// ── Event type → color class ──────────────────────────────────────────────────
function eventColor(type = '') {
  if (type.includes('fail'))    return 'text-danger'
  if (type.includes('complet')) return 'text-success'
  if (type.includes('escalat')) return 'text-warning'
  if (type.includes('a2a'))     return 'text-primary-400'
  if (type.includes('start'))   return 'text-accent'
  if (type.includes('pause'))   return 'text-warning'
  if (type.includes('stop'))    return 'text-danger'
  if (type.includes('resume'))  return 'text-primary-400'
  return 'text-[rgb(var(--text-muted))]'
}

// ── Event type → symbol ───────────────────────────────────────────────────────
function eventSymbol(type = '') {
  if (type.includes('fail'))    return '✗'
  if (type.includes('complet')) return '✓'
  if (type.includes('escalat')) return '⚠'
  if (type.includes('a2a'))     return '↩'
  if (type.includes('start'))   return '▶'
  if (type.includes('pause'))   return '⏸'
  if (type.includes('resume'))  return '▶'
  if (type.includes('stop'))    return '⏹'
  return '·'
}

// ── Individual log row — pure CSS transitions, no framer-motion ───────────────
function LogLine({ ev }) {
  const parts = []
  if (ev.node_id)    parts.push(ev.node_id)
  if (ev.agent_type) parts.push(AGENT_LABELS[ev.agent_type] || ev.agent_type)
  if (ev.model_used) parts.push(ev.model_used.split('/').pop())
  if (ev.cost_usd > 0) parts.push(fmtCost(ev.cost_usd))
  if (ev.confidence != null) parts.push(`${(ev.confidence * 100).toFixed(0)}%`)
  if (ev.reason)     parts.push(ev.reason.slice(0, 48))
  if (ev.error && !ev.error_type) parts.push(ev.error.slice(0, 55))
  if (ev.error_type) parts.push(`[${ev.error_type}]`)
  if (ev.error_message) parts.push(ev.error_message.slice(0, 40))
  if (!ev.llm_attempted && ev.type === 'agent_failed') parts.push('LLM not attempted')
  if (ev.tools_used?.length) parts.push(`tools:${ev.tools_used.length}`)

  return (
    <div
      className={cn(
        'flex gap-2 py-[3px] border-b border-white/[0.04] font-mono text-[11px] items-center',
        'animate-fadeInUp', // CSS keyframe from tailwind.config
        eventColor(ev.type),
      )}
    >
      <span className="text-white/20 flex-shrink-0 tabular-nums w-16 text-[10px]">
        {(ev.ts || '').slice(11, 19)}
      </span>
      <span className="text-[10px] flex-shrink-0 w-4 text-center opacity-80">
        {eventSymbol(ev.type)}
      </span>
      <span className="text-white/30 flex-shrink-0 text-[10px] max-w-[110px] truncate">
        [{ev.type || 'event'}]
      </span>
      <span className="truncate flex-1 opacity-90">
        {parts.join(' · ')}
      </span>
    </div>
  )
}

// ── Main LogTerminal ──────────────────────────────────────────────────────────
export default function LogTerminal({ events = [] }) {
  const virtuosoRef = useRef(null)

  // Auto-scroll to bottom when events are added
  const followOutput = useCallback((atBottom) => atBottom, [])

  return (
    <div className="rounded-xl border border-[rgb(var(--border))] overflow-hidden">
      {/* Terminal header — gradient for premium look */}
      <div
        className="flex items-center gap-2 px-4 py-2.5 border-b border-[rgb(var(--border))]"
        style={{
          background: 'linear-gradient(90deg, rgb(var(--bg-elevated)), rgb(var(--bg-surface)))',
        }}
      >
        {/* macOS-style window buttons */}
        <div className="flex gap-1.5">
          <div className="w-3 h-3 rounded-full bg-danger/70 hover:bg-danger transition-colors" />
          <div className="w-3 h-3 rounded-full bg-warning/70 hover:bg-warning transition-colors" />
          <div className="w-3 h-3 rounded-full bg-success/70 hover:bg-success transition-colors" />
        </div>
        <div className="flex items-center gap-1.5 ml-2">
          <Terminal className="w-3.5 h-3.5 text-[rgb(var(--text-muted))]" />
          <span className="text-[11px] font-mono text-[rgb(var(--text-muted))]">execution.log</span>
        </div>
        <div className="ml-auto flex items-center gap-2">
          {events.length > 0 && (
            <span className="text-[10px] text-[rgb(var(--text-muted))] font-mono">
              {events.length} events
            </span>
          )}
          {/* Pulsing dot when last event was recent */}
          {events.length > 0 && (
            <span className="relative flex h-1.5 w-1.5">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-success opacity-60" />
              <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-success" />
            </span>
          )}
        </div>
      </div>

      {/* Log body — virtualized + fade mask */}
      <div
        className="relative h-52 bg-[rgb(var(--bg-base))]"
        style={{
          maskImage: 'linear-gradient(to bottom, transparent 0%, black 12%, black 100%)',
          WebkitMaskImage: 'linear-gradient(to bottom, transparent 0%, black 12%, black 100%)',
        }}
      >
        {events.length === 0 ? (
          <div className="h-full flex items-center justify-center">
            <div className="flex items-center gap-2 text-[rgb(var(--text-muted))] text-xs font-mono">
              <span className="animate-typingCursor text-success">█</span>
              <span>Waiting for events…</span>
            </div>
          </div>
        ) : (
          <Virtuoso
            ref={virtuosoRef}
            style={{ height: '100%' }}
            data={events}
            itemContent={(_, ev) => (
              <div className="px-4">
                <LogLine ev={ev} />
              </div>
            )}
            followOutput={followOutput}
            initialTopMostItemIndex={events.length - 1}
            className="scrollbar-thin"
          />
        )}
      </div>
    </div>
  )
}