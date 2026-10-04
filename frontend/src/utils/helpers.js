// frontend/src/utils/helpers.js
import { clsx } from 'clsx'
import {
  Search, BrainCircuit, PenTool, ShieldCheck,
  Zap, Database, Telescope, UsersRound, Bot,
  CheckCircle2, XCircle, AlertTriangle, ClipboardList,
} from 'lucide-react'

export function cn(...inputs) { return clsx(inputs) }

export const fmtCost   = (n) => `$${(n || 0).toFixed(5)}`
export const fmtTokens = (n) => (n || 0).toLocaleString()
export const fmtPct    = (n) => `${((n || 0) * 100).toFixed(1)}%`
export const truncate  = (str, max = 80) => (!str ? '' : str.length > max ? str.slice(0, max) + '…' : str)

export function timeAgo(iso) {
  if (!iso) return '—'
  const d = (Date.now() - new Date(iso)) / 1000
  if (d < 5)     return 'just now'
  if (d < 60)    return `${Math.floor(d)}s ago`
  if (d < 3600)  return `${Math.floor(d / 60)}m ago`
  if (d < 86400) return `${Math.floor(d / 3600)}h ago`
  return `${Math.floor(d / 86400)}d ago`
}

export function fmtDuration(ms) {
  if (!ms) return '—'
  if (ms < 1000)  return `${ms}ms`
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`
  return `${Math.floor(ms / 60000)}m ${Math.floor((ms % 60000) / 1000)}s`
}

export function safeJson(str, fallback = null) {
  try { return JSON.parse(str) } catch { return fallback }
}

// ── Status colors ─────────────────────────────────────────────────────────────
export const STATUS_COLORS = {
  running:   'bg-success/15 text-success border-success/30',
  completed: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30',
  escalated: 'bg-warning/15 text-warning border-warning/30',
  paused:    'bg-warning/15 text-warning border-warning/30',
  failed:    'bg-danger/15 text-danger border-danger/30',
  stopped:   'bg-danger/15 text-danger border-danger/30',
  pending:   'bg-[rgba(var(--text-muted)/0.1)] text-[rgb(var(--text-muted))] border-[rgb(var(--border))]',
  success:   'bg-emerald-500/15 text-emerald-400 border-emerald-500/30',
  skipped:   'bg-[rgba(var(--text-muted)/0.1)] text-[rgb(var(--text-muted))] border-[rgb(var(--border))]',
}

// ── Agent icons — lucide-react components (no emojis) ────────────────────────
// Usage: const Icon = AGENT_ICONS['research_agent']; <Icon className="w-4 h-4" />
// Fallback: if unknown key, use AGENT_ICON_FALLBACK
export const AGENT_ICON_FALLBACK = Bot

export const AGENT_ICON_MAP = {
  research_agent:     Search,
  reasoning_agent:    BrainCircuit,
  drafting_agent:     PenTool,
  verification_agent: ShieldCheck,
  execution_agent:    Zap,
  memory_agent:       Database,
  discovery_agent:    Telescope,
  consensus_agent:    UsersRound,
}

/**
 * Returns a lucide-react component for a given agent type.
 * Always safe — falls back to Bot icon for unknown types.
 * @param {string} agentType
 * @returns {React.ComponentType}
 */
export function getAgentIcon(agentType) {
  return AGENT_ICON_MAP[agentType] || AGENT_ICON_FALLBACK
}

/**
 * Legacy compatibility: AGENT_ICONS used in many places.
 * Returns the same lucide components via Proxy.
 * Old code: AGENT_ICONS['research_agent'] → Search component
 */
export const AGENT_ICONS = new Proxy(AGENT_ICON_MAP, {
  get(target, key) {
    return target[key] || AGENT_ICON_FALLBACK
  },
})

// ── Status icons ──────────────────────────────────────────────────────────────
export const STATUS_ICONS = {
  completed: CheckCircle2,
  success:   CheckCircle2,
  failed:    XCircle,
  stopped:   XCircle,
  escalated: AlertTriangle,
  pending:   ClipboardList,
}

export const AGENT_LABELS = {
  research_agent:     'Research',
  reasoning_agent:    'Reasoning',
  drafting_agent:     'Drafting',
  verification_agent: 'Verification',
  execution_agent:    'Execution',
  memory_agent:       'Memory',
  discovery_agent:    'Discovery',
  consensus_agent:    'Consensus',
}

export const AGENT_DESCRIPTIONS = {
  research_agent:     'Gathers data from all connected tools',
  reasoning_agent:    'Analyzes data and recommends actions',
  drafting_agent:     'Writes personalized communications',
  verification_agent: 'Checks drafts against business rules',
  execution_agent:    'Executes approved actions',
  memory_agent:       'Updates pattern store for future runs',
  discovery_agent:    'Automatically selects relevant tools',
  consensus_agent:    'Two sub-agents debate from opposing perspectives',
}

// ── Model tier display ────────────────────────────────────────────────────────
export const TIER_COLORS = {
  heavy:    'text-primary-300 bg-primary-900/30 border-primary-700/40',
  fast:     'text-success bg-success/10 border-success/30',
  mini:     'text-accent bg-accent/10 border-accent/30',
  balanced: 'text-warning bg-warning/10 border-warning/30',
}

export const TIER_LABELS = {
  heavy:    'Heavy',
  fast:     'Fast',
  mini:     'Mini',
  balanced: 'Balanced',
}

export const TIER_DESCRIPTIONS = {
  heavy:    'High-quality reasoning. Best for complex analysis and writing.',
  fast:     'Fast inference. Best for data gathering and tool-heavy tasks.',
  mini:     'Lightweight & cheap. Best for verification and execution.',
  balanced: 'Good quality at moderate cost. Good general purpose.',
}

// ── Budget levels ─────────────────────────────────────────────────────────────
export const BUDGET_LEVELS = [
  { n: 0, name: 'Max Accuracy',  color: 'text-success',  savings: '0%',   accuracy: 'None',         desc: 'Default models. No optimization. Full reasoning chains.' },
  { n: 1, name: 'Balanced',      color: 'text-accent',   savings: '~25%', accuracy: 'Negligible',   desc: 'Research & Verification on mini. Redis caching enabled.' },
  { n: 2, name: 'Aggressive',    color: 'text-warning',  savings: '~55%', accuracy: 'Low/Moderate', desc: 'Reasoning & Drafting downgraded. Context summarized at 500 chars.' },
  { n: 3, name: 'Budget First',  color: 'text-danger',   savings: '~80%', accuracy: 'Moderate',     desc: 'All agents on mini. Context summarized before passing.' },
]

// ── Provider display ──────────────────────────────────────────────────────────
export const PROVIDER_COLORS = {
  anthropic: 'text-orange-400',
  openai:    'text-success',
  google:    'text-accent',
  groq:      'text-primary-400',
}

export const PROVIDER_LABELS = {
  anthropic: 'Anthropic',
  openai:    'OpenAI',
  google:    'Google',
  groq:      'Groq',
}

// ── Industry display ──────────────────────────────────────────────────────────
export const INDUSTRY_COLORS = {
  saas:        'text-blue-300 bg-blue-900/20 border-blue-800/40',
  retail:      'text-orange-300 bg-orange-900/20 border-orange-800/40',
  healthcare:  'text-green-300 bg-green-900/20 border-green-800/40',
  finance:     'text-yellow-300 bg-yellow-900/20 border-yellow-800/40',
  real_estate: 'text-teal-300 bg-teal-900/20 border-teal-800/40',
  logistics:   'text-cyan-300 bg-cyan-900/20 border-cyan-800/40',
  cpg:         'text-pink-300 bg-pink-900/20 border-pink-800/40',
  universal:   'text-gray-300 bg-gray-800/40 border-gray-700/40',
  utility:     'text-purple-300 bg-purple-900/20 border-purple-800/40',
}