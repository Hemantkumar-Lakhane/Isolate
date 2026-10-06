// frontend/src/pages/client/WorkflowBuilder.jsx
import { useState, useEffect, useCallback, useRef, useMemo } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import {
  ReactFlow, Controls, Background, MiniMap, addEdge, MarkerType,
  useNodesState, useEdgesState, Handle, Position,
  Panel, ReactFlowProvider, BackgroundVariant,
  getBezierPath, useReactFlow,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Save, Trash2, Plus, GitBranch, Zap, Settings2, X,
  ChevronRight, Play, AlignLeft, LayoutGrid, Code2,
  Map, Eye, RotateCcw, Download, Upload, Layers,
  Search, FlipHorizontal, GripVertical, CheckCircle2,
  AlertTriangle, ShieldCheck, Database, Mail, Globe,
  Terminal, Sparkles, Building2, CreditCard, ArrowRight,
  HelpCircle, Sliders, Send, Clock, Check, ChevronDown,
  Maximize2, Minimize2, Activity, PlayCircle, Loader2, Copy,
  Sun, Moon, BrainCircuit, PenTool, UserCheck, Calendar,
} from 'lucide-react'
import { useAuth }        from '../../contexts/AuthContext'
import { useTheme }       from '../../contexts/ThemeContext'
import { useBuilderStore } from '../../utils/appStore'
import {
  Card, Button, Input, Textarea, Select, Alert, Spinner,
  EmptyState, Modal, Badge, cn,
} from '../../components/ui'
import { AGENT_ICONS, AGENT_LABELS, AGENT_DESCRIPTIONS } from '../../utils/helpers'

// ── PALETTE DEFINITIONS ────────────────────────────────────────────────────────
const PALETTE_CATEGORIES = [
  { id: 'all',      label: 'All Items' },
  { id: 'triggers', label: '⚡ Triggers' },
  { id: 'agents',   label: '🤖 AI Agents' },
  { id: 'logic',    label: '🔀 Logic & Code' },
  { id: 'tools',    label: '🛠️ Actions & Tools' },
]

const PALETTE_ITEMS = [
  // Triggers
  {
    type: 'trigger_schedule',
    category: 'triggers',
    name: 'Every Morning',
    subtitle: 'Cron Schedule (8:00 AM)',
    description: 'Triggered periodically on automated cron schedule',
    color: '#10B981',
    light: '#064e3b',
    icon: Clock,
  },
  {
    type: 'trigger_email',
    category: 'triggers',
    name: 'Inbound Email Ingest',
    subtitle: 'Gmail / Outlook Webhook',
    description: 'Triggers automatically on incoming customer email',
    color: '#06B6D4',
    light: '#164e63',
    icon: Mail,
  },
  {
    type: 'trigger_manual',
    category: 'triggers',
    name: 'Manual Run',
    subtitle: 'On-Demand Execution',
    description: 'Triggered manually by user from Workflow Library',
    color: '#3B82F6',
    light: '#1e3a8a',
    icon: Play,
  },
  {
    type: 'trigger_webhook',
    category: 'triggers',
    name: 'REST Webhook Ingest',
    subtitle: 'HTTP POST Event',
    description: 'HTTP POST webhook payload ingestion',
    color: '#8B5CF6',
    light: '#4c1d95',
    icon: Globe,
  },

  // Multi-Agent Nodes
  {
    type: 'drafting_agent',
    category: 'agents',
    name: 'Summarize Emails',
    subtitle: 'Response Text',
    description: 'Combines and drafts synthesized response content with LLM',
    color: '#10B981',
    light: '#064e3b',
    icon: PenTool,
  },
  {
    type: 'research_agent',
    category: 'agents',
    name: 'Research & Intel',
    subtitle: 'Vector Context',
    description: 'Context gathering, database query & document fetch',
    color: '#6366F1',
    light: '#312e81',
    icon: Search,
  },
  {
    type: 'reasoning_agent',
    category: 'agents',
    name: 'Reasoning Agent',
    subtitle: 'Decision Synthesis',
    description: 'Multi-step logic, analysis, and classification',
    color: '#00D4FF',
    light: '#164e63',
    icon: BrainCircuit,
  },
  {
    type: 'verification_agent',
    category: 'agents',
    name: 'Verification Guardrail',
    subtitle: 'Quality & Policy',
    description: 'Deterministic safety, policy & quality verification',
    color: '#F59E0B',
    light: '#78350f',
    icon: ShieldCheck,
  },
  {
    type: 'execution_agent',
    category: 'agents',
    name: 'Execution Agent',
    subtitle: 'API Dispatcher',
    description: 'Dispatches tool actions and external integrations',
    color: '#EF4444',
    light: '#7f1d1d',
    icon: Zap,
  },

  // Logic & Code
  {
    type: 'code_transform',
    category: 'logic',
    name: 'Combine Emails',
    subtitle: 'Code JavaScript',
    description: 'Combines multiple email bodies into a single batch text',
    color: '#F59E0B',
    light: '#78350f',
    icon: Code2,
  },
  {
    type: 'logic_condition',
    category: 'logic',
    name: 'Condition / Filter',
    subtitle: 'Boolean Branch',
    description: 'Evaluates boolean logic and branches path',
    color: '#F59E0B',
    light: '#78350f',
    icon: GitBranch,
  },
  {
    type: 'logic_approval_gate',
    category: 'logic',
    name: 'HITL Approval Gate',
    subtitle: 'Action Center Review',
    description: 'Pauses execution for human SME review & approval',
    color: '#6366F1',
    light: '#312e81',
    icon: UserCheck,
  },
  {
    type: 'group_section',
    category: 'logic',
    name: 'Section Group Box',
    subtitle: 'Organize Nodes',
    description: 'Enclosing container box to organize workflow stages',
    color: '#64748B',
    light: '#1e293b',
    icon: Layers,
  },

  // Tools & Connectors (n8n-style real integrations)
  {
    type: 'tool_gmail',
    category: 'tools',
    name: 'Gmail API',
    subtitle: 'Email Ingest & Send',
    description: 'Sends and receives customer emails via OAuth',
    color: '#EA4335',
    light: '#7f1d1d',
    icon: Mail,
  },
  {
    type: 'tool_sheet',
    category: 'tools',
    name: 'Google Sheets',
    subtitle: 'Spreadsheet Logger',
    description: 'Appends rows, logs audit data, and synchronizes sheets',
    color: '#10B981',
    light: '#064e3b',
    icon: Database,
  },
  {
    type: 'tool_slack',
    category: 'tools',
    name: 'Slack Bot',
    subtitle: 'Channel Alerts',
    description: 'Dispatches real-time team alerts and escalations to Slack',
    color: '#EC4899',
    light: '#831843',
    icon: Terminal,
  },
  {
    type: 'tool_stripe',
    category: 'tools',
    name: 'Stripe Billing',
    subtitle: 'Payment & Invoices',
    description: 'Validates invoices, customer cards, and subscription tiers',
    color: '#6366F1',
    light: '#312e81',
    icon: CreditCard,
  },
  {
    type: 'tool_hubspot',
    category: 'tools',
    name: 'HubSpot CRM',
    subtitle: 'Contact & Deal Sync',
    description: 'Enriches contacts, updates deals, and creates tasks',
    color: '#FF7A59',
    light: '#7c2d12',
    icon: Globe,
  },
  {
    type: 'tool_telegram',
    category: 'tools',
    name: 'Telegram Bot',
    subtitle: 'Customer Chat Agent',
    description: 'Sends automated Telegram replies and customer notifications',
    color: '#229ED9',
    light: '#0c4a6e',
    icon: Send,
  },
  {
    type: 'tool_postgres',
    category: 'tools',
    name: 'PostgreSQL DB',
    subtitle: 'SQL Query & Mutation',
    description: 'Direct SQL execution and relational store sync',
    color: '#336791',
    light: '#1e3a8a',
    icon: Database,
  },
  {
    type: 'tool_calendar',
    category: 'tools',
    name: 'Google Calendar',
    subtitle: 'Slot Booking & Invites',
    description: 'Schedules calendar invites and sets reminders',
    color: '#4285F4',
    light: '#1e3a8a',
    icon: Calendar,
  },
  {
    type: 'tool_webhook',
    category: 'tools',
    name: 'Outbound Webhook',
    subtitle: 'REST Endpoint',
    description: 'Sends JSON payload to external REST API',
    color: '#14B8A6',
    light: '#134e4a',
    icon: Globe,
  },
]

// ── NODE REQUIRED FIELDS CATALOGUE ─────────────────────────────────────────────
// Maps agentType → array of required configuration descriptors.
// Each entry: { key, label, placeholder, type: 'text'|'textarea' }
// These fields live in node.data.config (separate namespace from existing node data).
// Empty array means the node type needs no extra configuration to be considered ready.
const NODE_REQUIRED_FIELDS = {
  // Triggers
  trigger_schedule:   [{ key: 'cronExpression',     label: 'Cron Expression',      placeholder: '0 8 * * 1-5 (weekdays at 8 AM)', type: 'text' }],
  trigger_email:      [{ key: 'emailFilter',         label: 'Email Filter / Label', placeholder: 'e.g. inbox OR label:support',      type: 'text' }],
  trigger_manual:     [], // on-demand — always ready
  trigger_webhook:    [{ key: 'webhookPath',          label: 'Webhook Path',         placeholder: '/hooks/my-event',                  type: 'text' }],
  // AI Agents — name is the minimum; all other fields are optional
  research_agent:     [],
  reasoning_agent:    [],
  drafting_agent:     [],
  verification_agent: [],
  execution_agent:    [],
  // Logic / Flow
  logic_condition:    [{ key: 'conditionExpression', label: 'Condition Expression', placeholder: 'e.g. output.confidence >= 0.8',    type: 'text'     }],
  logic_approval_gate:[{ key: 'reviewerRole',        label: 'Reviewer Role',        placeholder: 'e.g. manager, compliance_officer', type: 'text'     }],
  code_transform:     [{ key: 'codeSnippet',         label: 'Transform Code',       placeholder: '// JavaScript\nreturn items;',     type: 'textarea' }],
  group_section:      [], // visual only, never executes
  // Tools / Connectors
  tool_gmail:    [{ key: 'recipient',      label: 'Recipient(s)',        placeholder: 'email@example.com',                 type: 'text' }],
  tool_slack:    [{ key: 'slackChannel',   label: 'Slack Channel',       placeholder: '#notifications',                    type: 'text' }],
  tool_sheet:    [{ key: 'spreadsheetId',  label: 'Spreadsheet ID',      placeholder: 'Google Sheets ID or URL',           type: 'text' }],
  tool_stripe:   [], // connection-only — no inline config required
  tool_hubspot:  [], // connection-only
  tool_telegram: [{ key: 'telegramChatId', label: 'Chat ID / Channel',   placeholder: '-100123456 or @channel',            type: 'text' }],
  tool_postgres: [{ key: 'sqlQuery',       label: 'SQL Query',           placeholder: 'SELECT * FROM table WHERE id = ?',  type: 'textarea' }],
  tool_calendar: [], // connection-only
  tool_webhook:  [{ key: 'webhookUrl',     label: 'Webhook URL',         placeholder: 'https://api.example.com/endpoint',  type: 'text' }],
}

/**
 * Derive whether a node has all required configuration filled in.
 * Returns { ready: boolean, missing: string[] } where missing is a list of
 * human-readable field labels that are empty.
 * This is ALWAYS derived from node data — never stored in the DAG.
 */
function getNodeReadiness(data) {
  const agentType = data?.agentType || ''
  const requiredFields = NODE_REQUIRED_FIELDS[agentType]

  // Unknown type or no requirements → always ready
  if (!requiredFields || requiredFields.length === 0) {
    return { ready: true, missing: [] }
  }

  const config = data?.config || {}
  const missing = []

  for (const field of requiredFields) {
    const value = config[field.key]
    if (!value || String(value).trim() === '') {
      missing.push(field.label)
    }
  }

  return { ready: missing.length === 0, missing }
}

const EDGE_CONDITIONS = [
  { value: 'null',                label: 'Always run (Default)' },
  { value: '1 item',              label: '1 item' },
  { value: 'not output.escalate', label: 'If not escalated' },
  { value: 'output.escalate',     label: 'If escalated / HITL' },
  { value: 'output.passed',       label: 'If verification passed' },
  { value: 'not output.passed',   label: 'If verification failed' },
]

const INDUSTRIES = ['saas', 'retail', 'healthcare', 'finance', 'logistics', 'cpg', 'real_estate', 'general']
const CATEGORIES = ['operations', 'marketing', 'sales', 'support', 'finance', 'compliance', 'productivity']

// ── Brand Vector Logos for Stripe and HubSpot ─────────────────────────────────
function StripeIcon({ className = "w-4 h-4" }) {
  return (
    <svg viewBox="0 0 32 32" className={className} fill="none" aria-label="Stripe">
      <rect width="32" height="32" rx="8" fill="#635BFF"/>
      <path d="M14.5 13.2c0-1.1.9-1.5 2.3-1.5 2.1 0 4.7.7 6.4 1.7V8.5c-1.9-.8-4.2-1.2-6.4-1.2-5.4 0-9 2.8-9 7.7 0 7.5 10.3 6.3 10.3 9.5 0 1.2-1.1 1.7-2.6 1.7-2.4 0-5.5-1-7.5-2.2v5c2.3 1 4.9 1.5 7.4 1.5 5.6 0 9.4-2.8 9.4-7.8 0-8.1-10.3-6.7-10.3-9.5z" fill="#FFFFFF"/>
    </svg>
  )
}

function HubSpotIcon({ className = "w-4 h-4" }) {
  return (
    <svg viewBox="0 0 32 32" className={className} fill="none" aria-label="HubSpot">
      <rect width="32" height="32" rx="8" fill="#FF7A59"/>
      <path d="M22.5 14.2v-2.8a2.1 2.1 0 0 0 1.2-1.9 2.2 2.2 0 1 0-4.4 0c0 .8.5 1.5 1.2 1.9v2.8a6.3 6.3 0 0 0-3.3 1.8l-5.6-4.3a2.3 2.3 0 1 0-1.3 1.4l5.4 4.2a6.3 6.3 0 0 0-.2 1.7c0 .7.1 1.3.3 1.9l-2.4 1.8a2.1 2.1 0 1 0 1.1 1.5l2.6-2a6.3 6.3 0 1 0 6.5-8.1zm-3.5 6.3a3.5 3.5 0 1 1-7 0 3.5 3.5 0 0 1 7 0z" fill="#FFFFFF"/>
    </svg>
  )
}

// ── Comprehensive n8n-Style Node Visual & Icon Resolver ───────────────────────
// Maps any node data (type, name, tools, trigger) to its authentic visual representation.
// Eliminates the generic ChatGPT default icon across all workflow builder nodes.
function resolveNodeVisual(data = {}) {
  const t = (data.agentType || data.type || data.agent || '').toLowerCase()
  const n = (data.name || data.label || '').toLowerCase()
  const s = (data.subtitle || '').toLowerCase()
  const tools = (data.tools || []).map(x => (typeof x === 'string' ? x : x.name || '').toLowerCase())
  const p = (data.provider || '').toLowerCase()

  // 1. Gmail / Inbound Email (Triggers, Tools, & Dedicated Email Steps like n8n)
  const isEmail =
    t === 'trigger_email' || t === 'tool_gmail' || t.includes('gmail') ||
    n.includes('inbound email') || n.includes('fetch email') || n.includes('gmail') ||
    s.includes('gmail') || s.includes('inbound email') ||
    tools.some(x => x.includes('gmail') || x.includes('email_get_synthetic') || x === 'tool_email_dispatch' && n.includes('email'))

  if (isEmail) {
    return {
      kind: 'image',
      src: '/assets/tools/gmail.png',
      alt: 'Gmail',
      iconBg: 'bg-red-50 dark:bg-red-950/60 border-red-300 dark:border-red-500/40 text-red-500',
      accentColor: '#EA4335',
      defaultSubtitle: 'Gmail / Email Event',
    }
  }

  // 2. Google Sheets
  const isSheet = t.includes('sheet') || tools.some(x => x.includes('sheet')) || n.includes('sheet') || n.includes('spreadsheet')
  if (isSheet) {
    return {
      kind: 'image',
      src: '/assets/tools/sheet.png',
      alt: 'Google Sheets',
      iconBg: 'bg-emerald-50 dark:bg-emerald-950/60 border-emerald-300 dark:border-emerald-500/40 text-emerald-600',
      accentColor: '#10B981',
      defaultSubtitle: 'Google Sheets',
    }
  }

  // 3. Google Calendar
  const isCalendar = t.includes('calendar') || tools.some(x => x.includes('calendar')) || n.includes('calendar') || n.includes('booking') || n.includes('appointment')
  if (isCalendar) {
    return {
      kind: 'image',
      src: '/assets/tools/calendar.png',
      alt: 'Google Calendar',
      iconBg: 'bg-blue-50 dark:bg-blue-950/60 border-blue-300 dark:border-blue-500/40 text-blue-600',
      accentColor: '#4285F4',
      defaultSubtitle: 'Google Calendar',
    }
  }

  // 4. Slack
  const isSlack = t.includes('slack') || tools.some(x => x.includes('slack')) || n.includes('slack')
  if (isSlack) {
    return {
      kind: 'image',
      src: '/assets/tools/slack.png',
      alt: 'Slack',
      iconBg: 'bg-pink-50 dark:bg-pink-950/60 border-pink-300 dark:border-pink-500/40 text-pink-500',
      accentColor: '#EC4899',
      defaultSubtitle: 'Slack Bot & Alerts',
    }
  }

  // 5. Telegram
  const isTelegram = t.includes('telegram') || tools.some(x => x.includes('telegram')) || n.includes('telegram')
  if (isTelegram) {
    return {
      kind: 'image',
      src: '/assets/tools/telegram.png',
      alt: 'Telegram',
      iconBg: 'bg-sky-50 dark:bg-sky-950/60 border-sky-300 dark:border-sky-500/40 text-sky-500',
      accentColor: '#229ED9',
      defaultSubtitle: 'Telegram Bot',
    }
  }

  // 6. PostgreSQL / Relational Database
  const isDb = t.includes('postgres') || t.includes('database') || tools.some(x => x.includes('postgres') || x.includes('db_mutation')) || n.includes('postgres') || n.includes('database') || n.includes('sql')
  if (isDb) {
    return {
      kind: 'image',
      src: '/assets/tools/postgres.png',
      alt: 'PostgreSQL',
      iconBg: 'bg-blue-50 dark:bg-blue-950/60 border-blue-300 dark:border-blue-500/40 text-blue-600',
      accentColor: '#336791',
      defaultSubtitle: 'PostgreSQL DB',
    }
  }

  // 7. Webhook / REST Endpoint
  const isWebhook = t.includes('webhook') || tools.some(x => x.includes('webhook')) || n.includes('webhook') || n.includes('rest endpoint') || n.includes('http post')
  if (isWebhook) {
    return {
      kind: 'image',
      src: '/assets/tools/webhook.png',
      alt: 'Webhook',
      iconBg: 'bg-teal-50 dark:bg-teal-950/60 border-teal-300 dark:border-teal-500/40 text-teal-600',
      accentColor: '#14B8A6',
      defaultSubtitle: 'REST Webhook',
    }
  }

  // 8. Stripe Billing
  const isStripe = t.includes('stripe') || tools.some(x => x.includes('stripe')) || n.includes('stripe') || n.includes('billing') || n.includes('invoice')
  if (isStripe) {
    return {
      kind: 'stripe',
      iconBg: 'bg-indigo-50 dark:bg-indigo-950/60 border-indigo-300 dark:border-indigo-500/40 text-indigo-600',
      accentColor: '#635BFF',
      defaultSubtitle: 'Stripe Billing',
    }
  }

  // 9. HubSpot CRM
  const isHubSpot = t.includes('hubspot') || tools.some(x => x.includes('hubspot')) || n.includes('hubspot') || n.includes('crm') || n.includes('deal sync')
  if (isHubSpot) {
    return {
      kind: 'hubspot',
      iconBg: 'bg-orange-50 dark:bg-orange-950/60 border-orange-300 dark:border-orange-500/40 text-orange-600',
      accentColor: '#FF7A59',
      defaultSubtitle: 'HubSpot CRM',
    }
  }

  // 10. Social Media (Instagram / YouTube)
  if (t.includes('instagram') || n.includes('instagram')) {
    return {
      kind: 'image',
      src: '/assets/tools/instagram.png',
      alt: 'Instagram',
      iconBg: 'bg-pink-50 dark:bg-pink-950/60 border-pink-300 dark:border-pink-500/40',
      accentColor: '#E1306C',
      defaultSubtitle: 'Instagram',
    }
  }
  if (t.includes('youtube') || n.includes('youtube')) {
    return {
      kind: 'image',
      src: '/assets/tools/youtube.png',
      alt: 'YouTube',
      iconBg: 'bg-red-50 dark:bg-red-950/60 border-red-300 dark:border-red-500/40',
      accentColor: '#FF0000',
      defaultSubtitle: 'YouTube',
    }
  }

  // 11. Schedule / Cron Trigger
  if (t === 'trigger_schedule' || t.includes('schedule') || t.includes('cron') || n.includes('morning') || n.includes('schedule') || n.includes('cron')) {
    return {
      kind: 'lucide',
      Icon: Clock,
      iconBg: 'bg-emerald-50 dark:bg-emerald-950/60 border-emerald-300 dark:border-emerald-500/40 text-emerald-600 dark:text-emerald-400',
      accentColor: '#10B981',
      defaultSubtitle: 'Cron Schedule',
    }
  }

  // 12. Manual Trigger
  if (t === 'trigger_manual' || t.includes('manual') || n.includes('manual run') || n.includes('manual trigger')) {
    return {
      kind: 'lucide',
      Icon: Play,
      iconBg: 'bg-blue-50 dark:bg-blue-950/60 border-blue-300 dark:border-blue-500/40 text-blue-600 dark:text-blue-400',
      accentColor: '#3B82F6',
      defaultSubtitle: 'Manual Run',
    }
  }

  // 13. Code / Transform Node
  if (t === 'code_transform' || t.includes('code') || n.includes('code') || n.includes('transform') || n.includes('combine')) {
    return {
      kind: 'code',
      iconBg: 'bg-amber-50 dark:bg-amber-950/40 border-amber-300 dark:border-amber-500/40 text-amber-500',
      accentColor: '#F59E0B',
      defaultSubtitle: 'Code Transform',
    }
  }

  // 14. Condition / Logic Filter Node
  if (t.includes('condition') || t.includes('filter') || t.includes('branch') || n.includes('condition') || n.includes('filter') || n.includes('branch')) {
    return {
      kind: 'lucide',
      Icon: GitBranch,
      iconBg: 'bg-amber-50 dark:bg-amber-950/60 border-amber-300 dark:border-amber-500/40 text-amber-500',
      accentColor: '#F59E0B',
      defaultSubtitle: 'Boolean Condition',
    }
  }

  // 15. HITL Approval Gate Node
  if (t.includes('approval') || t.includes('gate') || n.includes('approval') || n.includes('gate') || n.includes('review') || n.includes('sme')) {
    return {
      kind: 'lucide',
      Icon: UserCheck,
      iconBg: 'bg-indigo-50 dark:bg-indigo-950/60 border-indigo-300 dark:border-indigo-500/40 text-indigo-600 dark:text-indigo-400',
      accentColor: '#6366F1',
      defaultSubtitle: 'HITL Review Gate',
    }
  }

  // 16. Multi-Agent Pipeline Nodes (Cognitive Roles)
  // RESEARCH AGENT / DATA GATHERER / INTEL
  if (t.includes('research') || t.includes('discovery') || n.includes('gather') || n.includes('research') || n.includes('intel')) {
    return {
      kind: 'lucide',
      Icon: Search,
      iconBg: 'bg-indigo-50 dark:bg-indigo-950/60 border-indigo-300 dark:border-indigo-500/40 text-indigo-600 dark:text-indigo-400',
      accentColor: '#6366F1',
      defaultSubtitle: 'Research & Intel',
    }
  }

  // REASONING AGENT / DECISION SYNTHESIS / LOGIC & RISK
  if (t.includes('reason') || n.includes('reason') || n.includes('logic') || n.includes('assessor') || n.includes('classify')) {
    return {
      kind: 'lucide',
      Icon: BrainCircuit,
      iconBg: 'bg-cyan-50 dark:bg-cyan-950/60 border-cyan-300 dark:border-cyan-500/40 text-cyan-600 dark:text-cyan-400',
      accentColor: '#00D4FF',
      defaultSubtitle: 'Decision Synthesis',
    }
  }

  // DRAFTING AGENT / CONTENT GENERATION / SUMMARIZER
  if (t.includes('draft') || t.includes('summar') || t.includes('humaniz') || n.includes('draft') || n.includes('compose') || n.includes('summar') || n.includes('report') || n.includes('response')) {
    return {
      kind: 'lucide',
      Icon: PenTool,
      iconBg: 'bg-emerald-50 dark:bg-emerald-950/60 border-emerald-300 dark:border-emerald-500/40 text-emerald-600 dark:text-emerald-400',
      accentColor: '#10B981',
      defaultSubtitle: 'Response Drafter',
    }
  }

  // VERIFICATION AGENT / SAFETY GUARDRAIL / POLICY
  if (t.includes('verif') || n.includes('verif') || n.includes('guard') || n.includes('safety') || n.includes('policy') || n.includes('compliance')) {
    return {
      kind: 'lucide',
      Icon: ShieldCheck,
      iconBg: 'bg-amber-50 dark:bg-amber-950/60 border-amber-300 dark:border-amber-500/40 text-amber-600 dark:text-amber-400',
      accentColor: '#F59E0B',
      defaultSubtitle: 'Quality & Guardrail',
    }
  }

  // EXECUTION AGENT / DISPATCH EXECUTOR / API CALLS
  if (t.includes('exec') || n.includes('exec') || n.includes('dispatch') || n.includes('action')) {
    return {
      kind: 'lucide',
      Icon: Zap,
      iconBg: 'bg-rose-50 dark:bg-rose-950/60 border-rose-300 dark:border-rose-500/40 text-rose-600 dark:text-rose-400',
      accentColor: '#EF4444',
      defaultSubtitle: 'Action Dispatcher',
    }
  }

  // MEMORY AGENT / CONTEXT STORE
  if (t.includes('memory') || n.includes('memory') || n.includes('persist')) {
    return {
      kind: 'lucide',
      Icon: Database,
      iconBg: 'bg-purple-50 dark:bg-purple-950/60 border-purple-300 dark:border-purple-500/40 text-purple-600 dark:text-purple-400',
      accentColor: '#8B5CF6',
      defaultSubtitle: 'Memory Store',
    }
  }

  // Explicit model override ONLY if requested and matches known provider
  if (p === 'claude' || p === 'anthropic') {
    return {
      kind: 'image',
      src: '/assets/tools/claude.png',
      alt: 'Claude',
      iconBg: 'bg-amber-50 dark:bg-amber-950/60 border-amber-300 dark:border-amber-500/40 text-amber-600',
      accentColor: '#D97706',
      defaultSubtitle: 'Anthropic Claude',
    }
  }

  if (p === 'openai' && (t.includes('openai') || t.includes('gpt'))) {
    return {
      kind: 'image',
      src: '/assets/tools/openai.png',
      alt: 'OpenAI',
      iconBg: 'bg-slate-100 dark:bg-slate-800 border-slate-200 dark:border-slate-700 text-slate-700',
      accentColor: '#10A37F',
      defaultSubtitle: 'OpenAI GPT',
    }
  }

  // Default clean agent fallback (Sparkles) — NEVER default to OpenAI / ChatGPT icon
  return {
    kind: 'lucide',
    Icon: Sparkles,
    iconBg: 'bg-indigo-50 dark:bg-indigo-950/60 border-indigo-300 dark:border-indigo-500/40 text-indigo-600 dark:text-indigo-400',
    accentColor: '#6366F1',
    defaultSubtitle: 'AI Agent',
  }
}

// ── NodeDisplayIcon Component ──────────────────────────────────────────────────
// Renders the resolved icon (image, vector SVG, code block, or Lucide icon)
function NodeDisplayIcon({ data, type, provider, className = "w-4 h-4", fallback = null }) {
  const nodeData = data || { agentType: type, provider }
  const visual = resolveNodeVisual(nodeData)

  if (visual.kind === 'image') {
    return (
      <img
        src={visual.src}
        alt={visual.alt}
        className={`${className} object-contain`}
        onError={(e) => { e.target.style.display = 'none' }}
      />
    )
  }
  if (visual.kind === 'stripe') {
    return <StripeIcon className={className} />
  }
  if (visual.kind === 'hubspot') {
    return <HubSpotIcon className={className} />
  }
  if (visual.kind === 'code') {
    return <span className="font-mono font-bold text-amber-500 text-xs leading-none">{`{ }`}</span>
  }
  if (fallback && visual.kind === 'lucide' && visual.Icon === Sparkles) {
    return fallback
  }
  const IconComp = visual.Icon || Sparkles
  return <IconComp className={className} />
}

// Backward-compatible alias
function ProviderOrToolLogo(props) {
  return <NodeDisplayIcon {...props} />
}

// ── N8N TRIGGER NODE ──────────────────────────────────────────────────────────
function N8nTriggerNode({ data, selected }) {
  const isCompleted = data.status === 'completed' || data.executionStatus === 'completed'
  const isRunning   = data.status === 'running'   || data.executionStatus === 'running'
  const isError     = data.status === 'error'     || data.executionStatus === 'error'
  const isDisabled  = data.status === 'disabled'  || data.executionStatus === 'disabled'

  const visual = resolveNodeVisual(data)

  return (
    <div
      className={cn(
        'group relative rounded-2xl transition-all duration-200 min-w-[175px] border shadow-lg overflow-visible select-none',
        'bg-white dark:bg-[#131b2a] text-slate-800 dark:text-white',
        isDisabled  ? 'border-slate-300 dark:border-slate-700/50 opacity-45 grayscale' :
        isError     ? 'border-red-500 ring-2 ring-red-500/40' :
        isRunning   ? 'border-amber-400 ring-2 ring-amber-400/50 shadow-[0_0_15px_rgba(245,158,11,0.4)]' :
        isCompleted ? 'border-emerald-500/80 shadow-[0_0_15px_rgba(16,185,129,0.3)]' :
        selected    ? 'border-emerald-500 ring-2 ring-emerald-400/40' :
                      'border-slate-200 dark:border-[#26354d] hover:border-emerald-500/60 shadow-sm'
      )}
    >
      {/* Left Lightning Trigger Badge */}
      <div className="absolute -left-3 top-1/2 -translate-y-1/2 w-6 h-6 rounded-full bg-white dark:bg-[#0d1422] border border-amber-400 flex items-center justify-center text-amber-500 shadow-sm z-10">
        <Zap className="w-3.5 h-3.5 fill-amber-400" />
      </div>

      <div className="p-3 pl-4 pr-3.5 flex items-center gap-3">
        <div className={cn("w-9 h-9 rounded-xl border flex items-center justify-center shrink-0 p-1.5 shadow-inner", visual.iconBg)}>
          <NodeDisplayIcon data={data} className="w-5 h-5 object-contain" />
        </div>
        <div className="min-w-0 flex-1">
          <p className="text-xs font-bold text-slate-800 dark:text-white tracking-tight truncate">
            {data.name || 'Trigger Event'}
          </p>
          <p className="text-[10px] text-slate-500 dark:text-slate-400 font-medium truncate">
            {data.subtitle || visual.defaultSubtitle}
          </p>
        </div>

        {isCompleted && (
          <div className="w-4 h-4 rounded-full bg-emerald-100 dark:bg-emerald-500/20 border border-emerald-500 text-emerald-600 dark:text-emerald-400 flex items-center justify-center shrink-0">
            <Check className="w-2.5 h-2.5 stroke-[3]" />
          </div>
        )}
      </div>

      {!isRunning && !isCompleted && !isError && !isDisabled && (() => {
        const { ready, missing } = getNodeReadiness(data)
        if (ready) return null
        return (
          <div className="px-3 py-1 border-t border-amber-200 dark:border-amber-500/25 bg-amber-50 dark:bg-amber-500/8 flex items-center gap-1.5 rounded-b-2xl">
            <AlertTriangle className="w-2.5 h-2.5 text-amber-500 shrink-0" />
            <span className="text-[9px] font-semibold text-amber-600 dark:text-amber-400 truncate">
              Config needed: {missing.join(', ')}
            </span>
          </div>
        )
      })()}

      <Handle
        type="source"
        position={Position.Right}
        className="!w-4 !h-4 !-right-2 !bg-white dark:!bg-[#131b2a] !border-2 !border-emerald-500 transition-all hover:!w-4.5 hover:!h-4.5 cursor-crosshair shadow-xs flex items-center justify-center"
      >
        <span className="text-[9px] font-bold text-emerald-500 pointer-events-none">+</span>
      </Handle>
    </div>
  )
}

// ── N8N AGENT NODE (with Tools Port) ──────────────────────────────────────────
function N8nAgentNode({ data, selected }) {
  const isCompleted = data.status === 'completed' || data.executionStatus === 'completed'
  const isRunning   = data.status === 'running'   || data.executionStatus === 'running'
  const isError     = data.status === 'error'     || data.executionStatus === 'error'
  const isDisabled  = data.status === 'disabled'  || data.executionStatus === 'disabled'

  const visual = resolveNodeVisual(data)

  return (
    <div
      className={cn(
        'group relative rounded-2xl transition-all duration-200 min-w-[210px] border shadow-xl overflow-visible select-none',
        'bg-white dark:bg-[#131b2a] text-slate-800 dark:text-white',
        isDisabled  ? 'border-slate-300 dark:border-slate-700/50 opacity-45 grayscale' :
        isError     ? 'border-red-500 shadow-[0_0_20px_rgba(239,68,68,0.5)]' :
        isRunning   ? 'border-blue-500 ring-2 ring-blue-400/50 shadow-[0_0_20px_rgba(59,130,246,0.4)]' :
        isCompleted ? 'border-emerald-500/80 shadow-[0_0_15px_rgba(16,185,129,0.3)]' :
        selected    ? 'border-blue-500 ring-2 ring-blue-500/40' :
                      'border-slate-200 dark:border-[#26354d] hover:border-slate-400 dark:hover:border-slate-500 shadow-sm'
      )}
    >
      <Handle
        type="target"
        position={Position.Left}
        className="!w-3.5 !h-3.5 !-left-2 !bg-white dark:!bg-[#131b2a] !border-2 !border-sky-400 transition-all hover:!w-4 hover:!h-4 cursor-crosshair shadow-xs"
      />

      <div className="p-3.5 pb-3">
        <div className="flex items-center gap-2.5">
          <div className={cn("w-8 h-8 rounded-xl border flex items-center justify-center shrink-0 p-1 shadow-inner", visual.iconBg)}>
            <NodeDisplayIcon data={data} className="w-5 h-5 object-contain" />
          </div>
          <div className="min-w-0 flex-1">
            <p className="text-xs font-bold text-slate-800 dark:text-white tracking-tight truncate">
              {data.name || 'AI Agent'}
            </p>
            <p className="text-[10px] text-slate-500 dark:text-slate-400 font-medium truncate">
              {data.subtitle || visual.defaultSubtitle}
            </p>
          </div>

          {isCompleted && (
            <div className="w-4 h-4 rounded-full bg-emerald-100 dark:bg-emerald-500/20 border border-emerald-500 text-emerald-600 dark:text-emerald-400 flex items-center justify-center shrink-0">
              <Check className="w-2.5 h-2.5 stroke-[3]" />
            </div>
          )}
          {isRunning && (
            <Loader2 className="w-4 h-4 text-blue-500 animate-spin shrink-0" />
          )}
          {isError && (
            <div className="w-4 h-4 rounded-full bg-red-500 text-white flex items-center justify-center text-[10px] font-bold shrink-0">
              ×
            </div>
          )}
        </div>

        {data.tools?.length > 0 && (
          <div className="flex flex-wrap gap-1 mt-2.5 pt-2 border-t border-slate-100 dark:border-slate-800/80">
            {data.tools.map(t => (
              <span key={t} className="inline-flex items-center gap-1 px-1.5 py-0.5 text-[9px] rounded bg-slate-100 dark:bg-[#1e2a3f] text-slate-600 dark:text-slate-300 font-mono border border-slate-200 dark:border-transparent">
                <NodeDisplayIcon type={t} className="w-3 h-3" />
                <span>{t}</span>
              </span>
            ))}
          </div>
        )}
      </div>

      <div className="border-t border-slate-100 dark:border-slate-800/60 py-1 px-3 flex items-center justify-between text-[10px] text-slate-500 dark:text-slate-400 bg-slate-50 dark:bg-[#0d1422]/60 rounded-b-2xl">
        <span className="text-[9px] font-mono font-medium">Tools / Integrations</span>
        <span className="text-[10px] text-blue-500 hover:text-blue-400 font-bold cursor-pointer">+</span>
      </div>

      {!isRunning && !isCompleted && !isError && !isDisabled && (() => {
        const { ready, missing } = getNodeReadiness(data)
        if (ready) return null
        return (
          <div className="px-3 py-1 border-t border-amber-200 dark:border-amber-500/25 bg-amber-50 dark:bg-amber-500/8 flex items-center gap-1.5">
            <AlertTriangle className="w-2.5 h-2.5 text-amber-500 shrink-0" />
            <span className="text-[9px] font-semibold text-amber-600 dark:text-amber-400 truncate">
              Config needed: {missing.join(', ')}
            </span>
          </div>
        )
      })()}

      <Handle
        type="target"
        id="tool-input"
        position={Position.Bottom}
        className="!w-3 !h-3 !-bottom-1.5 !bg-white dark:!bg-[#131b2a] !border-2 !border-slate-400 cursor-pointer"
      />

      <Handle
        type="source"
        position={Position.Right}
        className="!w-4 !h-4 !-right-2 !bg-white dark:!bg-[#131b2a] !border-2 !border-sky-400 transition-all hover:!w-4.5 hover:!h-4.5 cursor-crosshair shadow-xs flex items-center justify-center"
      >
        <span className="text-[9px] font-bold text-sky-500 pointer-events-none">+</span>
      </Handle>
    </div>
  )
}

// ── N8N TOOL NODE ────────────────────────────────────────────────────────────
function N8nToolNode({ data, selected }) {
  const isCompleted = data.status === 'completed' || data.executionStatus === 'completed'
  const isRunning   = data.status === 'running'   || data.executionStatus === 'running'
  const isError     = data.status === 'error'     || data.executionStatus === 'error'
  const isDisabled  = data.status === 'disabled'  || data.executionStatus === 'disabled'

  const visual = resolveNodeVisual(data)

  return (
    <div
      className={cn(
        'group relative rounded-2xl transition-all duration-200 min-w-[190px] border shadow-xl overflow-visible select-none',
        'bg-white dark:bg-[#131b2a] text-slate-800 dark:text-white',
        isDisabled  ? 'border-slate-300 dark:border-slate-700/50 opacity-45 grayscale' :
        isError     ? 'border-red-500 ring-2 ring-red-500/40' :
        isRunning   ? 'border-purple-500 ring-2 ring-purple-400/50 shadow-[0_0_15px_rgba(168,85,247,0.4)]' :
        isCompleted ? 'border-emerald-500/80 shadow-[0_0_15px_rgba(16,185,129,0.3)]' :
        selected    ? 'border-purple-500 ring-2 ring-purple-400/40' :
                      'border-slate-200 dark:border-[#26354d] hover:border-purple-400/60 shadow-sm'
      )}
    >
      <Handle
        type="target"
        position={Position.Left}
        className="!w-3.5 !h-3.5 !-left-2 !bg-white dark:!bg-[#131b2a] !border-2 !border-purple-400 cursor-crosshair"
      />
      <Handle
        type="target"
        id="tool-link-top"
        position={Position.Top}
        className="!w-3 !h-3 !-top-1.5 !bg-white dark:!bg-[#131b2a] !border-2 !border-purple-400 cursor-crosshair"
      />

      <div className="p-3 pl-3.5 pr-3 flex items-center gap-3">
        <div className={cn("w-9 h-9 rounded-xl border flex items-center justify-center shrink-0 p-1.5 shadow-inner", visual.iconBg)}>
          <NodeDisplayIcon data={data} className="w-5 h-5 object-contain" />
        </div>
        <div className="min-w-0 flex-1">
          <p className="text-xs font-bold text-slate-800 dark:text-white tracking-tight truncate">
            {data.name || 'Tool Action'}
          </p>
          <p className="text-[10px] text-purple-600 dark:text-purple-400 font-medium truncate">
            {data.subtitle || visual.defaultSubtitle}
          </p>
        </div>

        {isCompleted && (
          <div className="w-4 h-4 rounded-full bg-emerald-100 dark:bg-emerald-500/20 border border-emerald-500 text-emerald-600 dark:text-emerald-400 flex items-center justify-center shrink-0">
            <Check className="w-2.5 h-2.5 stroke-[3]" />
          </div>
        )}
      </div>

      {!isRunning && !isCompleted && !isError && !isDisabled && (() => {
        const { ready, missing } = getNodeReadiness(data)
        if (ready) return null
        return (
          <div className="px-3 py-1 border-t border-amber-200 dark:border-amber-500/25 bg-amber-50 dark:bg-amber-500/8 flex items-center gap-1.5">
            <AlertTriangle className="w-2.5 h-2.5 text-amber-500 shrink-0" />
            <span className="text-[9px] font-semibold text-amber-600 dark:text-amber-400 truncate">
              Config needed: {missing.join(', ')}
            </span>
          </div>
        )
      })()}

      <Handle
        type="source"
        position={Position.Right}
        className="!w-4 !h-4 !-right-2 !bg-white dark:!bg-[#131b2a] !border-2 !border-purple-400 transition-all hover:!w-4.5 cursor-crosshair flex items-center justify-center"
      >
        <span className="text-[9px] font-bold text-purple-500 pointer-events-none">+</span>
      </Handle>
      <Handle
        type="source"
        id="tool-link-bottom"
        position={Position.Bottom}
        className="!w-3 !h-3 !-bottom-1.5 !bg-white dark:!bg-[#131b2a] !border-2 !border-purple-400 cursor-crosshair"
      />
    </div>
  )
}

// ── N8N LOGIC NODE (Condition / Filter & Approval Gate) ────────────────────────
function N8nLogicNode({ data, selected }) {
  const isCompleted = data.status === 'completed' || data.executionStatus === 'completed'
  const isRunning   = data.status === 'running'   || data.executionStatus === 'running'
  const isDisabled  = data.status === 'disabled'  || data.executionStatus === 'disabled'

  const visual = resolveNodeVisual(data)

  return (
    <div
      className={cn(
        'group relative rounded-2xl transition-all duration-200 min-w-[185px] border shadow-xl overflow-visible select-none',
        'bg-white dark:bg-[#131b2a] text-slate-800 dark:text-white',
        isDisabled  ? 'border-slate-300 dark:border-slate-700/50 opacity-45 grayscale' :
        isRunning   ? 'border-amber-400 ring-2 ring-amber-400/50' :
        isCompleted ? 'border-emerald-500/80 shadow-[0_0_15px_rgba(16,185,129,0.3)]' :
        selected    ? 'border-indigo-400 ring-2 ring-indigo-400/40' :
                      'border-slate-200 dark:border-[#26354d] hover:border-slate-400 shadow-sm'
      )}
    >
      <Handle
        type="target"
        position={Position.Left}
        className="!w-3.5 !h-3.5 !-left-2 !bg-white dark:!bg-[#131b2a] !border-2 !border-indigo-400 cursor-crosshair"
      />

      <div className="p-3 pl-3.5 pr-3 flex items-center gap-2.5">
        <div className={cn("w-8 h-8 rounded-xl border flex items-center justify-center shrink-0 p-1 shadow-inner", visual.iconBg)}>
          <NodeDisplayIcon data={data} className="w-4 h-4 object-contain" />
        </div>
        <div className="min-w-0 flex-1">
          <p className="text-xs font-bold text-slate-800 dark:text-white tracking-tight truncate">
            {data.name || 'Logic Step'}
          </p>
          <p className="text-[10px] text-slate-500 dark:text-slate-400 font-medium truncate">
            {data.subtitle || visual.defaultSubtitle}
          </p>
        </div>

        {isCompleted && (
          <div className="w-4 h-4 rounded-full bg-emerald-100 dark:bg-emerald-500/20 border border-emerald-500 text-emerald-600 dark:text-emerald-400 flex items-center justify-center shrink-0">
            <Check className="w-2.5 h-2.5 stroke-[3]" />
          </div>
        )}
      </div>

      {!isRunning && !isCompleted && !isDisabled && (() => {
        const { ready, missing } = getNodeReadiness(data)
        if (ready) return null
        return (
          <div className="px-3 py-1 border-t border-amber-200 dark:border-amber-500/25 bg-amber-50 dark:bg-amber-500/8 flex items-center gap-1.5 rounded-b-2xl">
            <AlertTriangle className="w-2.5 h-2.5 text-amber-500 shrink-0" />
            <span className="text-[9px] font-semibold text-amber-600 dark:text-amber-400 truncate">
              Config needed: {missing.join(', ')}
            </span>
          </div>
        )
      })()}

      <Handle
        type="source"
        position={Position.Right}
        className="!w-4 !h-4 !-right-2 !bg-white dark:!bg-[#131b2a] !border-2 !border-indigo-400 transition-all hover:!w-4.5 cursor-crosshair flex items-center justify-center"
      >
        <span className="text-[9px] font-bold text-indigo-500 pointer-events-none">+</span>
      </Handle>
    </div>
  )
}

// ── N8N CODE / TRANSFORM NODE ──────────────────────────────────────────────────
function N8nCodeNode({ data, selected }) {
  const isCompleted = data.status === 'completed' || data.executionStatus === 'completed'
  const isRunning   = data.status === 'running'   || data.executionStatus === 'running'
  const isDisabled  = data.status === 'disabled'  || data.executionStatus === 'disabled'

  return (
    <div
      className={cn(
        'group relative rounded-2xl transition-all duration-200 min-w-[180px] border shadow-xl overflow-visible select-none',
        'bg-white dark:bg-[#131b2a] text-slate-800 dark:text-white',
        isDisabled  ? 'border-slate-300 dark:border-slate-700/50 opacity-45 grayscale' :
        isRunning   ? 'border-amber-400 ring-2 ring-amber-400/50' :
        isCompleted ? 'border-emerald-500/80 shadow-[0_0_15px_rgba(16,185,129,0.3)]' :
        selected    ? 'border-amber-400 ring-2 ring-amber-400/40' :
                      'border-slate-200 dark:border-[#26354d] hover:border-slate-400 shadow-sm'
      )}
    >
      <Handle
        type="target"
        position={Position.Left}
        className="!w-3.5 !h-3.5 !-left-2 !bg-white dark:!bg-[#131b2a] !border-2 !border-amber-400 cursor-crosshair"
      />

      <div className="p-3 pl-3.5 pr-3 flex items-center gap-2.5">
        <div className="w-8 h-8 rounded-xl bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-500/40 flex items-center justify-center text-amber-500 font-mono font-bold text-sm shrink-0">
          {`{ }`}
        </div>
        <div className="min-w-0 flex-1">
          <p className="text-xs font-bold text-slate-800 dark:text-white tracking-tight truncate">
            {data.name || 'Combine Emails'}
          </p>
          <p className="text-[10px] text-slate-500 dark:text-slate-400 font-medium truncate">
            {data.subtitle || 'Code Transform'}
          </p>
        </div>

        {isCompleted && (
          <div className="w-4 h-4 rounded-full bg-emerald-100 dark:bg-emerald-500/20 border border-emerald-500 text-emerald-600 dark:text-emerald-400 flex items-center justify-center shrink-0">
            <Check className="w-2.5 h-2.5 stroke-[3]" />
          </div>
        )}
      </div>

      {!isRunning && !isCompleted && !isDisabled && (() => {
        const { ready, missing } = getNodeReadiness(data)
        if (ready) return null
        return (
          <div className="px-3 py-1 border-t border-amber-200 dark:border-amber-500/25 bg-amber-50 dark:bg-amber-500/8 flex items-center gap-1.5 rounded-b-2xl">
            <AlertTriangle className="w-2.5 h-2.5 text-amber-500 shrink-0" />
            <span className="text-[9px] font-semibold text-amber-600 dark:text-amber-400 truncate">
              Config needed: {missing.join(', ')}
            </span>
          </div>
        )
      })()}

      <Handle
        type="source"
        position={Position.Right}
        className="!w-4 !h-4 !-right-2 !bg-white dark:!bg-[#131b2a] !border-2 !border-amber-400 transition-all hover:!w-4.5 cursor-crosshair flex items-center justify-center"
      >
        <span className="text-[9px] font-bold text-amber-500 pointer-events-none">+</span>
      </Handle>
    </div>
  )
}

// ── N8N STICKY SECTION / GROUP BOX NODE ────────────────────────────────────────
function N8nGroupNode({ data }) {
  const [collapsed, setCollapsed] = useState(false)

  return (
    <div
      className="rounded-3xl border border-dashed border-slate-300 dark:border-slate-700/80 bg-slate-50/60 dark:bg-[#121824]/40 p-4 transition-all pointer-events-auto select-none"
      style={{ minWidth: data.width || 480, minHeight: collapsed ? 60 : (data.height || 260) }}
    >
      <div className="flex items-start justify-between gap-2 mb-2">
        <div>
          <h4 className="text-sm font-bold text-slate-700 dark:text-slate-200">{data.label || 'Summarize'}</h4>
          <p className="text-xs text-slate-500 dark:text-slate-400">{data.description || 'Combine the emails into one text and generate an AI digest.'}</p>
        </div>
        <button
          type="button"
          onClick={() => setCollapsed(c => !c)}
          className="p-1 rounded-lg text-slate-400 hover:text-slate-700 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
        >
          <ChevronDown className={cn('w-4 h-4 transition-transform', collapsed && '-rotate-90')} />
        </button>
      </div>
    </div>
  )
}

// ── N8N CONDITION EDGE WITH ITEM BADGES ────────────────────────────────────────
function N8nConditionEdge({ id, sourceX, sourceY, targetX, targetY, sourcePosition, targetPosition, data, markerEnd, style, selected }) {
  // Use React Flow's getBezierPath for proper smooth curves
  const [edgePath, labelX, labelY] = getBezierPath({ sourceX, sourceY, sourcePosition, targetX, targetY, targetPosition })

  // Only show label when there's a real user-set condition — not the default '1 item'
  const hasRealCondition = data?.condition && data.condition !== 'null' && data.condition !== '1 item'
  const labelText = hasRealCondition ? data.condition : null

  const strokeColor = selected ? '#6366F1' : '#10B981'
  const strokeWidth = selected ? 2.5 : 2

  return (
    <>
      {/* Invisible wider hit target so edge is easy to click */}
      <path
        d={edgePath}
        fill="none"
        stroke="transparent"
        strokeWidth={16}
        className="react-flow__edge-interaction"
      />
      <path
        id={id}
        d={edgePath}
        fill="none"
        markerEnd={markerEnd}
        style={{ ...style, stroke: strokeColor, strokeWidth, transition: 'stroke 0.15s, stroke-width 0.15s' }}
        className="react-flow__edge-path"
      />
      {/* Selected glow */}
      {selected && (
        <path
          d={edgePath}
          fill="none"
          stroke="#6366F1"
          strokeWidth={6}
          strokeOpacity={0.18}
          style={{ pointerEvents: 'none' }}
        />
      )}
      {/* Condition label — only when a real condition exists */}
      {labelText && (
        <foreignObject x={labelX - 50} y={labelY - 12} width="100" height="24" className="overflow-visible pointer-events-none">
          <div className="flex items-center justify-center">
            <span className={`px-2 py-0.5 rounded-full text-[10px] font-mono font-semibold shadow-sm whitespace-nowrap ${
              selected
                ? 'bg-indigo-100 dark:bg-indigo-950 border border-indigo-400 dark:border-indigo-500/60 text-indigo-700 dark:text-indigo-300'
                : 'bg-white dark:bg-[#0e1624] border border-slate-200 dark:border-[#233048] text-slate-600 dark:text-slate-300'
            }`}>
              {labelText}
            </span>
          </div>
        </foreignObject>
      )}
    </>
  )
}

const nodeTypes = {
  triggerNode: N8nTriggerNode,
  agentNode:   N8nAgentNode,
  codeNode:    N8nCodeNode,
  toolNode:    N8nToolNode,
  logicNode:   N8nLogicNode,
  groupNode:   N8nGroupNode,
}
const edgeTypes = {
  conditionEdge: N8nConditionEdge,
}

// DAG Helper conversion
function dagToFlow(dag) {
  if (!dag?.nodes?.length) return { nodes: [], edges: [] }

  const nodes = []

  // Create primary workflow nodes
  dag.nodes.forEach((n, i) => {
    let customType = 'agentNode'
    const agentStr = (n.agent || n.type || '').toLowerCase()
    const idStr = (n.id || '').toLowerCase()
    const nameStr = (n.name || '').toLowerCase()

    if (agentStr.startsWith('trigger_') || idStr.includes('trigger') || idStr.includes('morning') || nameStr.includes('trigger')) {
      customType = 'triggerNode'
    } else if (agentStr.startsWith('tool_') || idStr.includes('tool') || idStr.includes('slack') || idStr.includes('stripe') || idStr.includes('sheet') || idStr.includes('hubspot') || idStr.includes('telegram')) {
      customType = 'toolNode'
    } else if (agentStr === 'code_transform' || agentStr.includes('code') || idStr.includes('combine') || idStr.includes('code')) {
      customType = 'codeNode'
    } else if (agentStr.startsWith('logic_') || agentStr === 'approval_gate' || agentStr === 'condition_branch' || idStr.includes('gate') || idStr.includes('condition')) {
      customType = 'logicNode'
    }

    nodes.push({
      id: n.id,
      type: customType,
      position: n.position || { x: i * 260 + 80, y: 140 },
      data: {
        id: n.id,
        name: n.name,
        agentType: n.agent || n.type || 'drafting_agent',
        provider: n.provider || null,
        subtitle: n.subtitle || (customType === 'triggerNode' ? 'Event Trigger' : customType === 'toolNode' ? 'Connected Tool' : customType === 'logicNode' ? 'Logic Step' : 'Response Text'),
        tools: n.tools || [],
        promptFile: n.prompt_file || '',
        description: n.description || '',
        timeout: n.timeout_seconds || 90,
        status: n.status || 'idle',
        // Restore persisted config — defaults to {} for backward compatibility
        // with existing DAG files that predate this field.
        config: n.config || {},
      },
    })
  })

  const edges = (dag.edges || []).map((e, i) => ({
    id: `e-${e.from}-${e.to}-${i}`,
    source: e.from,
    target: e.to,
    type: 'conditionEdge',
    animated: true,
    data: { condition: e.condition || '1 item' },
    markerEnd: { type: MarkerType.ArrowClosed, width: 12, height: 12, color: '#10B981' },
    style: { stroke: '#10B981', strokeWidth: 2 },
  }))

  return { nodes, edges }
}

function flowToDag(nodes, edges, meta) {
  return {
    _meta: meta,
    nodes: nodes.filter(n => n.type !== 'groupNode').map(n => ({
      id: n.id,
      agent: n.data.agentType,
      name: n.data.name || n.id,
      subtitle: n.data.subtitle || '',
      description: n.data.description || '',
      prompt_file: n.data.promptFile || '',
      tools: n.data.tools || [],
      timeout_seconds: n.data.timeout || 90,
      position: n.position,
      // Persist type-specific config so it survives save/reload
      config: n.data.config || {},
    })),
    edges: edges.map(e => ({
      from: e.source,
      to: e.target,
      condition: e.data?.condition === 'null' ? null : (e.data?.condition || null),
    })),
    escalation_config: { sla_hours: meta.sla_hours || 4, resume_after_decision: true },
  }
}

// ── FLOATING N8N CANVAS TOOLBAR ────────────────────────────────────────────────
function N8nCanvasToolbar({ onOpenPalette, onZoomIn, onZoomOut, onFitView, onToggleMiniMap, showMiniMap, onOpenAICopilot }) {
  return (
    <div className="absolute right-4 top-16 z-20 flex flex-col items-center bg-white/95 dark:bg-[#131b2a]/95 border border-slate-200 dark:border-[#233048] rounded-2xl p-1.5 shadow-xl backdrop-blur-md space-y-1">
      <button
        type="button"
        onClick={onOpenPalette}
        className="w-8 h-8 rounded-xl bg-blue-600 hover:bg-blue-500 text-white flex items-center justify-center shadow-md transition-all cursor-pointer"
        title="Add Node or Tool (+)"
      >
        <Plus className="w-4 h-4 stroke-[2.5]" />
      </button>

      <div className="w-5 h-[1px] bg-slate-200 dark:bg-slate-800 my-0.5" />

      <button
        type="button"
        onClick={onZoomIn}
        className="w-8 h-8 rounded-xl hover:bg-slate-100 dark:hover:bg-[#1f2c40] text-slate-500 dark:text-slate-400 hover:text-slate-800 dark:hover:text-white flex items-center justify-center transition-colors cursor-pointer text-xs font-bold"
        title="Zoom In"
      >
        +
      </button>

      <button
        type="button"
        onClick={onZoomOut}
        className="w-8 h-8 rounded-xl hover:bg-slate-100 dark:hover:bg-[#1f2c40] text-slate-500 dark:text-slate-400 hover:text-slate-800 dark:hover:text-white flex items-center justify-center transition-colors cursor-pointer text-xs font-bold"
        title="Zoom Out"
      >
        -
      </button>

      <button
        type="button"
        onClick={onFitView}
        className="w-8 h-8 rounded-xl hover:bg-slate-100 dark:hover:bg-[#1f2c40] text-slate-500 dark:text-slate-400 hover:text-slate-800 dark:hover:text-white flex items-center justify-center transition-colors cursor-pointer"
        title="Fit View"
      >
        <Maximize2 className="w-3.5 h-3.5" />
      </button>

      <button
        type="button"
        onClick={onToggleMiniMap}
        className={cn(
          'w-8 h-8 rounded-xl flex items-center justify-center transition-colors cursor-pointer',
          showMiniMap
            ? 'bg-blue-100 dark:bg-[#1f2c40] text-blue-600 dark:text-blue-400'
            : 'hover:bg-slate-100 dark:hover:bg-[#1f2c40] text-slate-500 dark:text-slate-400 hover:text-slate-800 dark:hover:text-white'
        )}
        title="Toggle MiniMap"
      >
        <Map className="w-3.5 h-3.5" />
      </button>

      <button
        type="button"
        onClick={onOpenAICopilot}
        className="w-8 h-8 rounded-xl hover:bg-indigo-50 dark:hover:bg-indigo-950/80 text-indigo-500 dark:text-indigo-400 hover:text-indigo-700 dark:hover:text-indigo-300 flex items-center justify-center transition-colors cursor-pointer"
        title="AI Copilot Assistant"
      >
        <Sparkles className="w-3.5 h-3.5" />
      </button>
    </div>
  )
}

// ── N8N DRAG & DROP PALETTE DRAWER ─────────────────────────────────────────────
function N8nPaletteDrawer({ open, onClose, onDragStart, onAddItem }) {
  const [activeTab, setActiveTab] = useState('all')
  const [search, setSearch]       = useState('')

  const filtered = useMemo(() => {
    return PALETTE_ITEMS.filter(item => {
      const matchCat = activeTab === 'all' || item.category === activeTab
      const matchQuery = !search || item.name.toLowerCase().includes(search.toLowerCase()) || item.description.toLowerCase().includes(search.toLowerCase())
      return matchCat && matchQuery
    })
  }, [activeTab, search])

  if (!open) return null

  return (
    <motion.div
      initial={{ x: -280, opacity: 0 }}
      animate={{ x: 0, opacity: 1 }}
      exit={{ x: -280, opacity: 0 }}
      className="absolute left-0 top-0 bottom-0 w-72 bg-white dark:bg-[#0f1522] border-r border-slate-200 dark:border-[#233048] flex flex-col z-30 shadow-2xl select-none"
    >
      <div className="p-3.5 border-b border-slate-200 dark:border-[#233048] flex items-center justify-between">
        <div>
          <p className="text-xs font-bold text-slate-800 dark:text-white">Add Node or Tool</p>
          <p className="text-[10px] text-slate-500 dark:text-slate-400">Drag to canvas or click to add</p>
        </div>
        <button onClick={onClose} className="text-slate-400 hover:text-slate-700 dark:hover:text-white p-1 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors">
          <X className="w-4 h-4" />
        </button>
      </div>

      <div className="p-3 space-y-2 border-b border-slate-200 dark:border-[#233048]">
        <div className="relative">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-400" />
          <input
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="Search nodes, agents, triggers..."
            className="w-full pl-8 pr-3 py-1.5 text-xs bg-slate-50 dark:bg-[#162030] border border-slate-200 dark:border-[#2a3850] rounded-lg text-slate-800 dark:text-white placeholder-slate-400 focus:outline-none focus:border-blue-500"
          />
        </div>

        <div className="flex flex-wrap gap-1">
          {PALETTE_CATEGORIES.map(c => (
            <button
              key={c.id}
              onClick={() => setActiveTab(c.id)}
              className={cn(
                'text-[10px] font-semibold px-2 py-1 rounded-md transition-all cursor-pointer',
                activeTab === c.id
                  ? 'bg-blue-600 text-white shadow-xs'
                  : 'bg-slate-100 dark:bg-[#182335] text-slate-600 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-[#202e45]'
              )}
            >
              {c.label}
            </button>
          ))}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-2.5 space-y-1.5">
        {filtered.map(item => {
          const IconComp = item.icon
          return (
            <div
              key={item.type}
              draggable
              onDragStart={(e) => onDragStart(e, item.type)}
              onClick={() => onAddItem(item.type)}
              className="flex items-center gap-2.5 p-2.5 rounded-xl border border-slate-200 dark:border-[#233048] bg-white dark:bg-[#141c2c] hover:border-blue-400 hover:bg-blue-50 dark:hover:bg-[#1a253a] cursor-grab active:cursor-grabbing transition-all group"
            >
              <div
                className="w-8 h-8 rounded-lg flex items-center justify-center shrink-0 shadow-xs p-1"
                style={{ background: item.light, color: item.color }}
              >
                <NodeDisplayIcon data={{ agentType: item.type, name: item.name }} className="w-4 h-4 object-contain" fallback={<IconComp size={16} />} />
              </div>
              <div className="min-w-0 flex-1">
                <p className="text-xs font-bold text-slate-800 dark:text-white truncate group-hover:text-blue-600 dark:group-hover:text-blue-400 transition-colors">
                  {item.name}
                </p>
                <p className="text-[10px] text-slate-500 dark:text-slate-400 truncate">{item.subtitle || item.description}</p>
              </div>
              <Plus className="w-3.5 h-3.5 text-slate-400 opacity-0 group-hover:opacity-100 shrink-0" />
            </div>
          )
        })}
      </div>
    </motion.div>
  )
}

// ── NODE CONFIGURATION INSPECTOR ───────────────────────────────────────────────
function NodeInspector({ node, onSave, onDelete, onDuplicate, onClose, allTools, promptFiles }) {
  const [data, setData] = useState({ ...node.data })
  const set    = (k, v) => setData(p => ({ ...p, [k]: v }))
  const setConfig = (k, v) => setData(p => ({ ...p, config: { ...(p.config || {}), [k]: v } }))

  const toggleTool = (t) => {
    const cur = data.tools || []
    set('tools', cur.includes(t) ? cur.filter(x => x !== t) : [...cur, t])
  }

  const { ready, missing } = getNodeReadiness(data)
  const requiredFields = NODE_REQUIRED_FIELDS[data.agentType] || []
  const config = data.config || {}

  return (
    <motion.div
      initial={{ x: 340, opacity: 0 }}
      animate={{ x: 0, opacity: 1 }}
      exit={{ x: 340, opacity: 0 }}
      transition={{ type: 'spring', damping: 25, stiffness: 320 }}
      className="absolute right-0 top-0 bottom-0 w-88 bg-white dark:bg-[#0f1522] border-l border-slate-200 dark:border-[#233048] z-30 shadow-2xl overflow-y-auto flex flex-col text-slate-700 dark:text-slate-200"
    >
      {/* ── Inspector Header ── */}
      <div className="sticky top-0 bg-white dark:bg-[#0f1522] border-b border-slate-200 dark:border-[#233048] px-4 py-3 flex items-center justify-between z-10">
        <div className="flex items-center gap-2.5 min-w-0">
          <div className={cn("w-7 h-7 rounded-lg border flex items-center justify-center shrink-0 p-1 shadow-inner", resolveNodeVisual(data).iconBg)}>
            <NodeDisplayIcon data={data} className="w-4 h-4 object-contain" />
          </div>
          <div className="min-w-0">
            <h3 className="text-sm font-bold text-slate-900 dark:text-white truncate">{data.name || 'Node Settings'}</h3>
            <p className="text-[10px] text-slate-400 font-mono truncate">{node.id}</p>
          </div>
        </div>
        <div className="flex gap-1 shrink-0">
          <Button size="xs" variant="secondary" icon={<Copy className="w-3 h-3" />} onClick={() => { onDuplicate(node); onClose() }} title="Duplicate node" />
          <Button size="xs" variant="danger" icon={<Trash2 className="w-3 h-3" />} onClick={() => { onDelete(node.id); onClose() }} />
          <Button size="xs" variant="secondary" onClick={onClose} icon={<X className="w-3 h-3" />} />
        </div>
      </div>

      {/* ── Readiness Status Bar ── */}
      <div className={`px-4 py-2 flex items-center gap-2 text-[11px] font-semibold border-b ${
        ready
          ? 'bg-emerald-50 dark:bg-emerald-500/8 border-emerald-200 dark:border-emerald-500/20 text-emerald-700 dark:text-emerald-400'
          : 'bg-amber-50 dark:bg-amber-500/8 border-amber-200 dark:border-amber-500/20 text-amber-700 dark:text-amber-400'
      }`}>
        {ready
          ? <><Check className="w-3 h-3 stroke-[3]" /> Ready — all required fields filled</>
          : <><AlertTriangle className="w-3 h-3" /> Needs configuration: {missing.join(', ')}</>
        }
      </div>

      <div className="p-4 space-y-4 flex-1">

        {requiredFields.length > 0 && (
          <div className="space-y-3 p-3 bg-slate-50 dark:bg-[#162030] border border-slate-200 dark:border-[#2a3850] rounded-xl">
            <p className="text-[10px] font-bold text-slate-500 dark:text-slate-300 uppercase tracking-wider flex items-center gap-1.5">
              <Settings2 className="w-3 h-3 text-blue-500" />
              Configuration
            </p>
            {requiredFields.map(field => (
              <div key={field.key}>
                <label className="flex items-center gap-1 text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1.5">
                  {field.label}
                  <span className="text-amber-500 font-bold text-[10px]">*</span>
                  {config[field.key]?.trim()
                    ? <Check className="w-3 h-3 text-emerald-500 ml-auto" />
                    : <span className="ml-auto text-[9px] font-medium text-amber-500/80">Required</span>
                  }
                </label>
                {field.type === 'textarea' ? (
                  <textarea
                    value={config[field.key] || ''}
                    onChange={e => setConfig(field.key, e.target.value)}
                    placeholder={field.placeholder}
                    rows={3}
                    className="w-full text-xs p-2 bg-white dark:bg-[#0d1422] border border-slate-200 dark:border-[#2a3850] rounded-lg text-slate-800 dark:text-white placeholder-slate-400 focus:outline-none focus:border-blue-500 resize-none font-mono"
                  />
                ) : (
                  <input
                    type="text"
                    value={config[field.key] || ''}
                    onChange={e => setConfig(field.key, e.target.value)}
                    placeholder={field.placeholder}
                    className="w-full text-xs p-2 bg-white dark:bg-[#0d1422] border border-slate-200 dark:border-[#2a3850] rounded-lg text-slate-800 dark:text-white placeholder-slate-400 focus:outline-none focus:border-blue-500"
                  />
                )}
              </div>
            ))}
          </div>
        )}

        <Select
          label="Component Type"
          value={data.agentType || ''}
          onChange={e => set('agentType', e.target.value)}
          options={PALETTE_ITEMS.map(p => ({ value: p.type, label: p.name }))}
        />
        <Input label="Node ID (snake_case)" value={data.id || ''} onChange={e => set('id', e.target.value.replace(/\s/g, '_').toLowerCase())} />
        <Input label="Display Label" value={data.name || ''} onChange={e => set('name', e.target.value)} />
        <Input label="Output Subtitle / Role" value={data.subtitle || ''} onChange={e => set('subtitle', e.target.value)} placeholder="e.g. Response Text, Visual Asset" />
        <Textarea label="Node Purpose & Description" value={data.description || ''} onChange={e => set('description', e.target.value)} rows={2} />

        <div>
          <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1.5">Prompt Template File</label>
          {promptFiles.length > 0 ? (
            <select value={data.promptFile || ''} onChange={e => set('promptFile', e.target.value)} className="w-full text-xs p-2 bg-slate-50 dark:bg-[#162030] border border-slate-200 dark:border-[#2a3850] rounded-lg text-slate-800 dark:text-white">
              <option value="">— system default prompt —</option>
              {promptFiles.map(f => <option key={f.path} value={f.path}>{f.path}</option>)}
            </select>
          ) : (
            <Input value={data.promptFile || ''} onChange={e => set('promptFile', e.target.value)} placeholder="prompts/custom_agent.txt" />
          )}
        </div>

        <div>
          <p className="text-xs font-semibold text-slate-700 dark:text-slate-300 mb-2">Connected Tools & Capabilities</p>
          <div className="flex flex-wrap gap-1.5 max-h-32 overflow-y-auto">
            {allTools.length > 0 ? (
              allTools.map(t => {
                const on = (data.tools || []).includes(t.name || t)
                const name = t.name || t
                return (
                  <button
                    key={name}
                    type="button"
                    onClick={() => toggleTool(name)}
                    className={cn(
                      'px-2.5 py-1 rounded-lg text-[11px] border transition-all font-medium cursor-pointer',
                      on
                        ? 'bg-blue-100 dark:bg-blue-600/30 border-blue-400 text-blue-700 dark:text-blue-300 font-semibold'
                        : 'bg-slate-100 dark:bg-[#182335] border-slate-200 dark:border-[#2a3850] text-slate-600 dark:text-slate-400 hover:border-slate-400 dark:hover:border-slate-500'
                    )}
                  >
                    {name}
                  </button>
                )
              })
            ) : (
              <p className="text-[11px] text-slate-400 italic">No tools loaded</p>
            )}
          </div>
        </div>

        <Input
          label="Execution Timeout (seconds)"
          type="number"
          value={data.timeout || 90}
          onChange={e => set('timeout', parseInt(e.target.value) || 90)}
        />
      </div>

      <div className="p-4 border-t border-slate-200 dark:border-[#233048] bg-slate-50 dark:bg-[#0c121d]">
        <Button
          variant="primary"
          className="w-full"
          onClick={() => { onSave(node.id, data); onClose() }}
          icon={<Save className="w-4 h-4" />}
        >
          Save Node
        </Button>
      </div>
    </motion.div>
  )
}

// ── MAIN N8N STYLE CANVAS ──────────────────────────────────────────────────────
function FlowCanvas({ workflowName, dag, allTools, promptFiles, onSave, isSaving, onTestRun, onOpenAssign, onOpenAICopilot, api }) {
  const [nodes, setNodes, onNodesChange] = useNodesState([])
  const [edges, setEdges, onEdgesChange] = useEdgesState([])
  const [editingNode, setEditingNode]    = useState(null)
  const [activeTab, setActiveTab]        = useState('editor')
  const [paletteOpen, setPaletteOpen]    = useState(false)
  const [showMiniMap, setShowMiniMap]    = useState(true)
  const [selectedEdgeId, setSelectedEdgeId] = useState(null)
  const [isPublished, setIsPublished]    = useState(true)
  const [testingWorkflow, setTestingWorkflow] = useState(false)
  const [testRunResult,   setTestRunResult]   = useState(null)
  const [nodeErrorToast, setNodeErrorToast]   = useState(null)
  const { setDirty }                     = useBuilderStore()
  const { theme, toggle: toggleTheme }   = useTheme()
  const isDark = theme === 'dark'
  const rfWrapper                        = useRef(null)
  const [rfInstance, setRfInstance]      = useState(null)

  const [meta, setMeta] = useState({
    workflow_id: workflowName,
    name: workflowName?.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase()),
    industry: 'saas',
    version: '1.0.0',
    description: '',
    trigger_types: ['manual'],
    sla_hours: 4,
  })

  useEffect(() => {
    if (!dag) return
    const { nodes: n, edges: e } = dagToFlow(dag)
    setNodes(n)
    setEdges(e)
    if (dag._meta) setMeta(m => ({ ...m, ...dag._meta }))
  }, [dag, workflowName])

  const onConnect = useCallback((params) => {
    const edge = {
      ...params,
      type: 'conditionEdge',
      data: { condition: '1 item' },
      markerEnd: { type: MarkerType.ArrowClosed, width: 12, height: 12, color: '#10B981' },
      style: { stroke: '#10B981', strokeWidth: 2 },
    }
    setEdges(eds => addEdge(edge, eds))
    setDirty(true)
  }, [setEdges, setDirty])

  const onDrop = useCallback((event) => {
    event.preventDefault()
    const type = event.dataTransfer.getData('agentType')
    if (!type || !rfWrapper.current || !rfInstance) return
    const bounds = rfWrapper.current.getBoundingClientRect()
    const pos = rfInstance.screenToFlowPosition({ x: event.clientX - bounds.left, y: event.clientY - bounds.top })
    const pItem = PALETTE_ITEMS.find(p => p.type === type)
    const nodeId = `${type.replace('trigger_', '').replace('tool_', '').replace('logic_', '').replace('_agent', '')}_${Date.now().toString(36)}`
    
    let customType = 'agentNode'
    if (type.startsWith('trigger_')) customType = 'triggerNode'
    else if (type.startsWith('tool_')) customType = 'toolNode'
    else if (type === 'code_transform') customType = 'codeNode'
    else if (type.startsWith('logic_')) customType = 'logicNode'
    else if (type === 'group_section') customType = 'groupNode'

    setNodes(ns => {
      const newNode = {
        id: nodeId,
        type: customType,
        position: pos,
        data: {
          id: nodeId,
          agentType: type,
          name: pItem?.name || type,
          subtitle: pItem?.subtitle || 'Response Text',
          tools: [],
          promptFile: '',
          description: pItem?.description || '',
        },
      }
      // Auto-open inspector for the dropped node
      setTimeout(() => setEditingNode(newNode), 0)
      return [...ns, newNode]
    })
    setDirty(true)
  }, [rfInstance, setNodes, setDirty])

  const onDragStart = (e, agentType) => e.dataTransfer.setData('agentType', agentType)

  const onAddItem = (type) => {
    const pItem = PALETTE_ITEMS.find(p => p.type === type)
    const nodeId = `${type.replace('trigger_', '').replace('tool_', '').replace('logic_', '').replace('_agent', '')}_${Date.now().toString(36)}`
    const pos = { x: 100 + (nodes.length * 50), y: 140 }

    let customType = 'agentNode'
    if (type.startsWith('trigger_')) customType = 'triggerNode'
    else if (type.startsWith('tool_')) customType = 'toolNode'
    else if (type === 'code_transform') customType = 'codeNode'
    else if (type.startsWith('logic_')) customType = 'logicNode'
    else if (type === 'group_section') customType = 'groupNode'

    const newNode = {
      id: nodeId,
      type: customType,
      position: pos,
      data: {
        id: nodeId,
        agentType: type,
        name: pItem?.name || type,
        subtitle: pItem?.subtitle || 'Response Text',
        tools: [],
        promptFile: '',
        description: pItem?.description || '',
      },
    }
    setNodes(ns => [...ns, newNode])
    setDirty(true)
    // Auto-open inspector for click-to-add
    setTimeout(() => setEditingNode(newNode), 0)
  }

  // ── Inline Canvas AI Copilot ────────────────────────────────────────────────
  // Calls the same POST /admin/workflows/ai-generate endpoint used by the modal.
  // The response shape differs from dagToFlow's expected format, so a thin
  // adapter normalises nodes (data.agentType → agent) and edges (source/target → from/to)
  // before passing to the existing dagToFlow() conversion.
  const [aiCanvasPrompt, setAiCanvasPrompt] = useState('')
  const [aiCanvasLoading, setAiCanvasLoading] = useState(false)
  const [aiCanvasSuccess, setAiCanvasSuccess] = useState('')

  const handleCanvasAIGenerate = async () => {
    if (!aiCanvasPrompt.trim() || aiCanvasLoading) return

    // Guard: if the canvas already has nodes, confirm before replacing them
    if (nodes.length > 0) {
      const ok = window.confirm(
        `Replace the current ${nodes.length}-node canvas with a new AI-generated workflow?\n\nUnsaved changes will be lost.`
      )
      if (!ok) return
    }

    setAiCanvasLoading(true)
    setAiCanvasSuccess('')

    try {
      // Exact same request body as AICopilotModal.handleGenerate
      const resp = await api.post('/admin/workflows/ai-generate', {
        prompt:   aiCanvasPrompt.trim(),
        industry: 'general',
      })

      // ── Adapt ai-generate response → dagToFlow input format ──────────────
      // The backend returns nodes with shape { id, type, position, data: { name, agentType, ... } }
      // dagToFlow expects                    { id, agent, name, tools, description, position, ... }
      // The backend returns edges with shape { source, target, condition }
      // dagToFlow expects                    { from, to, condition }
      const adaptedDag = {
        nodes: (resp.nodes || []).map(n => ({
          id:              n.id,
          // prefer data.agentType; fall back to the top-level type field
          agent:           n.data?.agentType || n.type || 'drafting_agent',
          name:            n.data?.name      || n.id,
          description:     n.data?.prompt_directive || n.data?.description || '',
          tools:           n.data?.tools     || [],
          timeout_seconds: n.data?.timeout_seconds || 90,
          // keep the pre-calculated 2D layout from the generator
          position:        n.position        || undefined,
        })),
        edges: (resp.edges || []).map(e => ({
          from:      e.source || e.from,
          to:        e.target || e.to,
          condition: e.condition || null,
        })),
      }

      const { nodes: newNodes, edges: newEdges } = dagToFlow(adaptedDag)

      // Replace canvas content
      setNodes(newNodes)
      setEdges(newEdges)

      // Propagate metadata back into the canvas meta state so Save DAG
      // picks up the AI-generated name/key/industry
      setMeta(m => ({
        ...m,
        workflow_id:  resp.key        || m.workflow_id,
        name:         resp.name       || m.name,
        industry:     resp.industry   || m.industry,
        description:  resp.description || m.description,
        trigger_types: resp.trigger_type ? [resp.trigger_type] : m.trigger_types,
        sla_hours:    resp.sla_hours  || m.sla_hours,
      }))

      setDirty(true)

      // Fit the newly loaded workflow into the visible canvas area
      // Small timeout lets React flush the new node positions first
      setTimeout(() => rfInstance?.fitView({ padding: 0.25 }), 50)

      setAiCanvasSuccess(
        `Generated "${resp.name}" — ${newNodes.length} nodes loaded. Click Save DAG to publish.`
      )
      setAiCanvasPrompt('')
      setTimeout(() => setAiCanvasSuccess(''), 6000)
    } catch (err) {
      // Keep existing canvas intact on failure; surface the real backend message
      const detail = err?.message || 'AI generation failed'
      setNodeErrorToast({ nodeName: 'AI Copilot', error: detail })
    } finally {
      setAiCanvasLoading(false)
    }
  }

  const handleSave = () => {
    const currentDag = flowToDag(nodes, edges, meta)
    onSave(currentDag)
    setDirty(false)
  }

  // ── Duplicate a node ────────────────────────────────────────────────────────
  // Creates a new node with a unique ID, copied data, offset 40px down-right.
  const handleDuplicateNode = useCallback((node) => {
    const newId = `${node.id}_copy_${Date.now().toString(36)}`
    const newNode = {
      ...node,
      id: newId,
      selected: false,
      position: {
        x: (node.position?.x ?? 0) + 40,
        y: (node.position?.y ?? 0) + 40,
      },
      data: {
        ...node.data,
        id: newId,
        status: 'idle',
        executionStatus: 'idle',
      },
    }
    setNodes(ns => [...ns, newNode])
    setDirty(true)
  }, [setNodes, setDirty])

  // ── Keyboard shortcuts ───────────────────────────────────────────────────────
  // Backspace → delete selected node (supplement React Flow's Delete key)
  // Escape    → clear selection & close inspector
  // Ctrl/Cmd+S → save DAG
  useEffect(() => {
    const onKeyDown = (e) => {
      // Skip when focus is inside any input/textarea so typing isn't intercepted
      const tag = document.activeElement?.tagName?.toLowerCase()
      const isInput = tag === 'input' || tag === 'textarea' || tag === 'select'
        || document.activeElement?.isContentEditable

      if (e.key === 'Backspace' && !isInput) {
        // Delete currently selected nodes (React Flow's "Delete" key already handles
        // this, but Backspace is also expected in most canvas editors)
        setNodes(ns => {
          const toRemove = new Set(ns.filter(n => n.selected).map(n => n.id))
          if (toRemove.size === 0) return ns
          setEdges(es => es.filter(e => !toRemove.has(e.source) && !toRemove.has(e.target)))
          return ns.filter(n => !toRemove.has(n.id))
        })
        setDirty(true)
        setEditingNode(null)
        return
      }

      if (e.key === 'Escape' && !isInput) {
        setEditingNode(null)
        setSelectedEdgeId(null)
        // Deselect all nodes
        setNodes(ns => ns.map(n => ({ ...n, selected: false })))
        return
      }

      if ((e.ctrlKey || e.metaKey) && e.key === 's') {
        e.preventDefault()
        handleSave()
      }
    }

    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [handleSave, setNodes, setEdges, setDirty])

  // ── Test Workflow — calls the real backend sandbox endpoint ─────────────────
  // Pre-flight: validate all executable nodes before hitting the backend.
  const handleTestWorkflow = async () => {
    if (!workflowName) return

    // ── Pre-flight node validation ────────────────────────────────────────────
    // Skip group_section (visual only). Collect nodes with missing required config.
    const executableNodes = nodes.filter(n => n.type !== 'groupNode')
    const invalidNodes = executableNodes
      .map(n => {
        const { ready, missing } = getNodeReadiness(n.data)
        return ready ? null : { id: n.id, name: n.data.name || n.id, missing }
      })
      .filter(Boolean)

    if (invalidNodes.length > 0) {
      // Block execution — show which nodes need configuration
      const names = invalidNodes.map(n => n.name).join(', ')
      setTestRunResult({
        ok:           false,
        message:      `Workflow cannot run. ${invalidNodes.length} node${invalidNodes.length > 1 ? 's' : ''} require${invalidNodes.length === 1 ? 's' : ''} configuration: ${names}`,
        invalidNodes, // array of { id, name, missing[] }
      })
      return
    }
    // ── End pre-flight ────────────────────────────────────────────────────────

    setTestingWorkflow(true)
    setNodeErrorToast(null)
    setTestRunResult(null)

    // Mark every canvas node as 'running' while the request is in flight
    setNodes(ns => ns.map(n => ({ ...n, data: { ...n.data, status: 'running', executionStatus: 'running' } })))

    try {
      const resp = await api.post(`/admin/workflows/${workflowName}/test-run`, {
        input_payload: { sample_customer: 'Acme Corp', sample_revenue: 120000 },
        mock_mode: true,
      })

      // Build a quick lookup: node_id → step result from backend
      const stepMap = {}
      ;(resp.steps || []).forEach(s => { stepMap[s.node_id] = s })

      // Update each canvas node with its individual step outcome
      setNodes(ns => ns.map(n => {
        const step = stepMap[n.id]
        const outcome = step ? (step.status === 'success' ? 'completed' : 'error') : 'completed'
        return { ...n, data: { ...n.data, status: outcome, executionStatus: outcome } }
      }))

      setTestRunResult({
        ok:             true,
        message:        resp.message || `Dry-run passed — ${resp.total_nodes_executed} node(s) executed.`,
        nodes_executed: resp.total_nodes_executed,
        tokens:         resp.total_simulated_tokens,
        cost:           resp.total_simulated_cost_usd,
        test_run_id:    resp.test_run_id,
      })
    } catch (e) {
      // Reset all nodes back to idle so the canvas doesn't stay "running"
      setNodes(ns => ns.map(n => ({ ...n, data: { ...n.data, status: 'idle', executionStatus: 'idle' } })))

      const detail = e?.message || 'Test run failed'
      setTestRunResult({ ok: false, message: detail })
    } finally {
      setTestingWorkflow(false)
    }
  }

  // Inject selected flag into edges so N8nConditionEdge can highlight the active one
  const displayEdges = useMemo(
    () => edges.map(e => ({ ...e, selected: e.id === selectedEdgeId })),
    [edges, selectedEdgeId]
  )

  return (
    <div className="flex flex-col h-full bg-slate-50 dark:bg-[#0d1117] text-slate-900 dark:text-white relative select-none">
      
      {/* ── Top Bar ── */}
      <div className="px-5 py-2.5 bg-white dark:bg-[#121824] border-b border-slate-200 dark:border-[#233048] flex items-center justify-between shrink-0 z-20 shadow-sm">
        
        {/* Left: Breadcrumb */}
        <div className="flex items-center gap-2.5">
          <div className="flex items-center gap-1.5 text-xs text-slate-500 dark:text-slate-400">
            <span>Personal</span>
            <span className="text-slate-300 dark:text-slate-600">/</span>
            <span className="text-slate-900 dark:text-white font-bold tracking-tight">{meta.name || workflowName}</span>
          </div>
          <span className="w-2 h-2 rounded-full bg-emerald-500 inline-block" />
        </div>

        {/* Center: Editor | Executions | Evaluations Switcher */}
        <div className="flex items-center bg-slate-100 dark:bg-[#090d16] border border-slate-200 dark:border-[#233048] rounded-xl p-0.5 text-xs font-semibold">
          {[
            { id: 'editor',      label: 'Editor' },
            { id: 'executions',  label: 'Executions' },
            { id: 'evaluations', label: 'Evaluations' },
          ].map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={cn(
                'px-3 py-1 rounded-lg transition-all cursor-pointer',
                activeTab === tab.id
                  ? 'bg-white dark:bg-[#1b2538] text-slate-900 dark:text-white shadow-xs font-bold'
                  : 'text-slate-500 dark:text-slate-400 hover:text-slate-800 dark:hover:text-white'
              )}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Right: Theme Toggle + Actions */}
        <div className="flex items-center gap-2">
          {/* Light / Dark Mode Toggle */}
          <button
            type="button"
            onClick={toggleTheme}
            className="w-8 h-8 rounded-xl flex items-center justify-center border border-slate-200 dark:border-[#2a3850] bg-slate-100 dark:bg-[#1b2538] text-slate-500 dark:text-slate-400 hover:text-slate-800 dark:hover:text-white hover:border-slate-300 dark:hover:border-slate-600 transition-all cursor-pointer"
            title={isDark ? 'Switch to Light Mode' : 'Switch to Dark Mode'}
          >
            {isDark ? <Sun className="w-3.5 h-3.5" /> : <Moon className="w-3.5 h-3.5" />}
          </button>

          {/* Test Workflow Button */}
          <button
            type="button"
            disabled={testingWorkflow}
            onClick={handleTestWorkflow}
            className="px-3 py-1.5 rounded-xl bg-slate-100 dark:bg-[#1b2538] hover:bg-slate-200 dark:hover:bg-[#25334c] text-slate-700 dark:text-white border border-slate-200 dark:border-[#2a3850] text-xs font-bold transition-all flex items-center gap-1.5 cursor-pointer disabled:opacity-50"
          >
            {testingWorkflow ? (
              <>
                <Loader2 className="w-3.5 h-3.5 animate-spin text-emerald-500" />
                <span>Running...</span>
              </>
            ) : (
              <>
                <Play className="w-3 h-3 text-emerald-500 fill-emerald-500" />
                <span>Test workflow</span>
              </>
            )}
          </button>

          {/* Publish Toggle */}
          <div className="flex items-center gap-2 bg-slate-100 dark:bg-[#1b2538] border border-slate-200 dark:border-[#2a3850] rounded-xl px-2.5 py-1 text-xs">
            <span className="text-slate-600 dark:text-slate-300 font-semibold text-[11px]">Publish</span>
            <button
              type="button"
              onClick={() => setIsPublished(p => !p)}
              className={cn(
                'w-7 h-4 rounded-full transition-colors relative cursor-pointer',
                isPublished ? 'bg-emerald-500' : 'bg-slate-300 dark:bg-slate-600'
              )}
            >
              <div className={cn(
                'w-3 h-3 rounded-full bg-white transition-transform absolute top-0.5',
                isPublished ? 'left-3.5' : 'left-0.5'
              )} />
            </button>
          </div>

          <button
            type="button"
            onClick={handleSave}
            disabled={isSaving}
            className="px-3.5 py-1.5 rounded-xl bg-blue-600 hover:bg-blue-500 text-white text-xs font-bold transition-all flex items-center gap-1.5 cursor-pointer shadow-xs disabled:opacity-50"
          >
            {isSaving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Save className="w-3.5 h-3.5" />}
            <span>Save DAG</span>
          </button>
        </div>
      </div>

      {/* ── Canvas View ── */}
      <div className="flex-1 relative overflow-hidden" ref={rfWrapper}>
        
        {/* Floating Toolbar on Right */}
        <N8nCanvasToolbar
          onOpenPalette={() => setPaletteOpen(p => !p)}
          onZoomIn={() => rfInstance?.zoomIn()}
          onZoomOut={() => rfInstance?.zoomOut()}
          onFitView={() => rfInstance?.fitView({ padding: 0.25 })}
          onToggleMiniMap={() => setShowMiniMap(m => !m)}
          showMiniMap={showMiniMap}
          onOpenAICopilot={onOpenAICopilot}
        />

        {/* Palette Drawer */}
        <N8nPaletteDrawer
          open={paletteOpen}
          onClose={() => setPaletteOpen(false)}
          onDragStart={onDragStart}
          onAddItem={onAddItem}
        />

        {/* Main ReactFlow Canvas */}
        <ReactFlow
          nodes={nodes}
          edges={displayEdges}
          onNodesChange={(changes) => { onNodesChange(changes); setDirty(true) }}
          onEdgesChange={(changes) => { onEdgesChange(changes); setDirty(true) }}
          onConnect={onConnect}
          onInit={setRfInstance}
          onDrop={onDrop}
          onDragOver={e => e.preventDefault()}
          onNodeClick={(_, node) => { setEditingNode(node); setSelectedEdgeId(null) }}
          onPaneClick={() => { setEditingNode(null); setSelectedEdgeId(null) }}
          onEdgeClick={(_, edge) => setSelectedEdgeId(prev => prev === edge.id ? null : edge.id)}
          nodeTypes={nodeTypes}
          edgeTypes={edgeTypes}
          fitView
          fitViewOptions={{ padding: 0.25 }}
          minZoom={0.2}
          maxZoom={1.5}
          deleteKeyCode={['Delete', 'Backspace']}
          multiSelectionKeyCode="Shift"
          selectionOnDrag={false}
          panOnDrag={[1, 2]}
          zoomOnScroll
          zoomOnPinch
          proOptions={{ hideAttribution: true }}
          className={isDark ? 'bg-[#0d1117]' : 'bg-white'}
        >
          <Background
            variant={BackgroundVariant.Dots}
            gap={24}
            size={1.5}
            color={isDark ? '#2a3a56' : '#bfcad8'}
          />
          <MiniMap
            nodeColor={n => {
              if (n.type === 'triggerNode') return '#10b981'
              if (n.type === 'toolNode') return '#a855f7'
              if (n.type === 'codeNode') return '#f59e0b'
              return '#3b82f6'
            }}
            maskColor={isDark ? 'rgba(10,14,22,0.88)' : 'rgba(248,250,252,0.88)'}
            className={cn(
              'border rounded-xl',
              isDark
                ? '!bg-[#0d1117] !border-[#233048]'
                : '!bg-white !border-slate-200',
              !showMiniMap && '!hidden'
            )}
            pannable
            zoomable
          />
        </ReactFlow>

        {/* Node Inspector Slide-over */}
        <AnimatePresence>
          {editingNode && (
            <NodeInspector
              node={editingNode}
              allTools={allTools}
              promptFiles={promptFiles}
              onClose={() => setEditingNode(null)}
              onDuplicate={(node) => { handleDuplicateNode(node); setEditingNode(null) }}
              onSave={(id, data) => {
                setNodes(ns => ns.map(n => n.id === id ? { ...n, data } : n))
                setDirty(true)
              }}
              onDelete={(id) => {
                setNodes(ns => ns.filter(n => n.id !== id))
                setEdges(es => es.filter(e => e.source !== id && e.target !== id))
                setDirty(true)
              }}
            />
          )}
        </AnimatePresence>

        {/* Floating Real-Time AI Canvas Copilot Command Bar */}
        <div className="absolute bottom-5 left-1/2 -translate-x-1/2 w-full max-w-xl px-4 z-30 pointer-events-auto">
          {aiCanvasSuccess && (
            <div className="mb-2 p-2 px-3.5 bg-emerald-50 dark:bg-emerald-950/90 border border-emerald-300 dark:border-emerald-500/50 rounded-xl text-xs text-emerald-700 dark:text-emerald-300 shadow-xl flex items-center justify-between animate-in fade-in slide-in-from-bottom-2 duration-200">
              <div className="flex items-center gap-2">
                <CheckCircle2 size={13} className="text-emerald-500" />
                <span>{aiCanvasSuccess}</span>
              </div>
              <button onClick={() => setAiCanvasSuccess('')} className="text-emerald-500 hover:text-emerald-700 dark:hover:text-white">×</button>
            </div>
          )}

          <div className="bg-white/95 dark:bg-[#121826]/95 backdrop-blur-md border border-slate-200 dark:border-[#233048] rounded-2xl p-2 shadow-2xl flex items-center gap-2">
            <div className="w-8 h-8 rounded-xl bg-blue-100 dark:bg-blue-600/20 border border-blue-300 dark:border-blue-500/30 text-blue-600 dark:text-blue-400 flex items-center justify-center shrink-0">
              <Sparkles size={16} />
            </div>
            <input
              type="text"
              value={aiCanvasPrompt}
              onChange={e => setAiCanvasPrompt(e.target.value)}
              onKeyDown={e => {
                if (e.key === 'Enter') {
                  e.preventDefault()
                  handleCanvasAIGenerate()
                }
              }}
              placeholder="Describe a workflow to generate (e.g. 'Customer onboarding with email verification, risk review and welcome email')..."
              className="flex-1 bg-transparent text-xs text-slate-800 dark:text-white placeholder-slate-400 focus:outline-none"
              disabled={aiCanvasLoading}
            />
            <button
              onClick={handleCanvasAIGenerate}
              disabled={!aiCanvasPrompt.trim() || aiCanvasLoading}
              className="px-3.5 py-1.5 bg-blue-600 hover:bg-blue-500 disabled:opacity-40 text-white text-xs font-semibold rounded-xl transition-all flex items-center gap-1.5 shrink-0 cursor-pointer shadow-xs"
            >
              {aiCanvasLoading ? <Loader2 size={12} className="animate-spin" /> : <Send size={12} />}
              <span>{aiCanvasLoading ? 'Building...' : 'Apply'}</span>
            </button>
          </div>
        </div>

        {/* Error Notification Toast */}
        {nodeErrorToast && (
          <div className="absolute bottom-5 right-5 z-40 p-3 bg-red-50 dark:bg-[#1e1518] border border-red-300 dark:border-red-500/60 rounded-xl shadow-2xl flex items-center gap-3 text-xs text-red-700 dark:text-red-200 animate-in fade-in duration-200">
            <div className="w-5 h-5 rounded-full bg-red-100 dark:bg-red-500/20 border border-red-400 dark:border-red-500 text-red-600 dark:text-red-400 flex items-center justify-center font-bold">
              !
            </div>
            <div>
              <p className="font-bold text-red-800 dark:text-white">Problem in node '{nodeErrorToast.nodeName}'</p>
              <p className="text-[11px] text-red-500 dark:text-red-300">{nodeErrorToast.error}</p>
            </div>
            <button onClick={() => setNodeErrorToast(null)} className="text-slate-400 hover:text-slate-700 dark:hover:text-white ml-2">
              <X className="w-4 h-4" />
            </button>
          </div>
        )}

        {/* Test-Run Result Toast */}
        {testRunResult && (
          <div className={`absolute bottom-5 right-5 z-40 p-3 rounded-xl shadow-2xl flex items-start gap-3 text-xs animate-in fade-in duration-200 max-w-sm ${
            testRunResult.ok
              ? 'bg-emerald-50 dark:bg-[#0e1f18] border border-emerald-300 dark:border-emerald-500/60 text-emerald-800 dark:text-emerald-200'
              : 'bg-red-50 dark:bg-[#1e1518] border border-red-300 dark:border-red-500/60 text-red-800 dark:text-red-200'
          }`}>
            <div className={`w-5 h-5 rounded-full flex items-center justify-center font-bold shrink-0 mt-0.5 ${
              testRunResult.ok
                ? 'bg-emerald-100 dark:bg-emerald-500/20 border border-emerald-500 text-emerald-600 dark:text-emerald-400'
                : 'bg-red-100 dark:bg-red-500/20 border border-red-500 text-red-600 dark:text-red-400'
            }`}>
              {testRunResult.ok ? <Check className="w-3 h-3 stroke-[3]" /> : <AlertTriangle className="w-3 h-3" />}
            </div>
            <div className="min-w-0 flex-1">
              <p className="font-bold text-slate-900 dark:text-white leading-snug">
                {testRunResult.ok ? 'Test run passed' : 'Cannot run workflow'}
              </p>
              <p className="text-[11px] mt-0.5 leading-relaxed opacity-80">{testRunResult.message}</p>
              {testRunResult.ok && (
                <div className="flex items-center gap-3 mt-1.5 font-mono text-[10px]">
                  <span className="text-slate-500">{testRunResult.nodes_executed} nodes</span>
                  <span className="text-slate-400">·</span>
                  <span className="text-slate-500">{testRunResult.tokens?.toLocaleString()} tok</span>
                  <span className="text-slate-400">·</span>
                  <span className="text-emerald-600 dark:text-emerald-400">${testRunResult.cost}</span>
                </div>
              )}
              {testRunResult.invalidNodes?.length > 0 && (
                <div className="mt-2 space-y-1">
                  {testRunResult.invalidNodes.map(inv => {
                    const canvasNode = nodes.find(n => n.id === inv.id)
                    return (
                      <button
                        key={inv.id}
                        type="button"
                        onClick={() => {
                          if (canvasNode) setEditingNode(canvasNode)
                          setTestRunResult(null)
                        }}
                        className="w-full text-left flex items-start gap-1.5 px-2 py-1.5 rounded-lg bg-amber-50 dark:bg-amber-500/10 border border-amber-200 dark:border-amber-500/25 hover:bg-amber-100 dark:hover:bg-amber-500/20 transition-colors cursor-pointer"
                      >
                        <AlertTriangle className="w-2.5 h-2.5 text-amber-500 shrink-0 mt-0.5" />
                        <span className="text-[10px] text-amber-700 dark:text-amber-200 leading-snug">
                          <span className="font-semibold">{inv.name}</span>
                          {' — '}
                          <span className="opacity-75">{inv.missing.join(', ')}</span>
                        </span>
                      </button>
                    )
                  })}
                  <p className="text-[9px] text-slate-400 mt-1 pl-1">Click a node above to configure it</p>
                </div>
              )}
            </div>
            <button onClick={() => setTestRunResult(null)} className="text-slate-400 hover:text-slate-700 dark:hover:text-white ml-1 shrink-0">
              <X className="w-4 h-4" />
            </button>
          </div>
        )}

      </div>
    </div>
  )
}

// ── TEST RUN DRAWER ────────────────────────────────────────────────────────────
function TestRunDrawer({ open, onClose, workflowKey, api }) {
  const [running, setRunning] = useState(false)
  const [result, setResult]   = useState(null)
  const [error, setError]     = useState('')

  useEffect(() => {
    if (!open) { setResult(null); setError('') }
  }, [open])

  const executeTest = async () => {
    setRunning(true); setError(''); setResult(null)
    try {
      const resp = await api.post(`/admin/workflows/${workflowKey}/test-run`, {
        input_payload: { sample_customer: 'Acme Corp', sample_revenue: 120000 },
        mock_mode: true
      })
      setResult(resp)
    } catch (e) {
      setError(e?.response?.data?.detail || e.message || 'Test run failed')
    } finally {
      setRunning(false)
    }
  }

  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs">
      <div className="bg-white dark:bg-[#121824] rounded-2xl shadow-2xl border border-slate-200 dark:border-[#233048] w-full max-w-xl max-h-[85vh] flex flex-col overflow-hidden text-slate-800 dark:text-white">
        <div className="px-5 py-4 border-b border-slate-200 dark:border-[#233048] flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Terminal className="w-5 h-5 text-blue-500" />
            <div>
              <h3 className="text-sm font-bold text-slate-900 dark:text-white">Execution Logs: {workflowKey}</h3>
              <p className="text-[11px] text-slate-500 dark:text-slate-400">Live DAG telemetry trace</p>
            </div>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-700 dark:hover:text-white text-xl font-bold">×</button>
        </div>

        <div className="p-5 overflow-y-auto flex-1 space-y-4 text-xs">
          {error && (
            <div className="p-3 bg-red-50 dark:bg-red-950/60 border border-red-200 dark:border-red-800 rounded-xl text-red-700 dark:text-red-300">
              {error}
            </div>
          )}

          {result && (
            <div className="space-y-3">
              <div className="grid grid-cols-3 gap-2">
                <div className="p-2.5 bg-slate-50 dark:bg-[#162030] border border-slate-200 dark:border-[#233048] rounded-xl">
                  <span className="text-[10px] text-slate-500 dark:text-slate-400 block font-semibold uppercase">Executed Nodes</span>
                  <span className="text-sm font-bold text-slate-900 dark:text-white">{result.total_nodes_executed}</span>
                </div>
                <div className="p-2.5 bg-slate-50 dark:bg-[#162030] border border-slate-200 dark:border-[#233048] rounded-xl">
                  <span className="text-[10px] text-slate-500 dark:text-slate-400 block font-semibold uppercase">Est. Tokens</span>
                  <span className="text-sm font-bold text-slate-900 dark:text-white">{result.total_simulated_tokens}</span>
                </div>
                <div className="p-2.5 bg-slate-50 dark:bg-[#162030] border border-slate-200 dark:border-[#233048] rounded-xl">
                  <span className="text-[10px] text-slate-500 dark:text-slate-400 block font-semibold uppercase">Simulated Cost</span>
                  <span className="text-sm font-bold text-emerald-600 dark:text-emerald-400">${result.total_simulated_cost_usd}</span>
                </div>
              </div>
            </div>
          )}
        </div>

        <div className="p-4 border-t border-slate-200 dark:border-[#233048] flex justify-end gap-2 bg-slate-50 dark:bg-[#0c121d]">
          <Button variant="secondary" size="sm" onClick={onClose}>Close</Button>
          <Button variant="primary" size="sm" loading={running} onClick={executeTest} icon={<Play size={12} className="fill-white" />}>
            Run Simulation
          </Button>
        </div>
      </div>
    </div>
  )
}

// ── ASSIGN WORKFLOW TO ORGS & PLANS MODAL ──────────────────────────────────────
function AssignWorkflowModal({ open, onClose, workflowKey, workflowName, api, onDone }) {
  const [orgs, setOrgs]       = useState([])
  const [plans, setPlans]     = useState([])
  const [selectedOrgs, setSelOrgs]   = useState([])
  const [selectedPlans, setSelPlans] = useState([])
  const [loading, setLoading] = useState(false)
  const [saving, setSaving]   = useState(false)
  const [error, setError]     = useState('')

  useEffect(() => {
    if (!open) return
    setLoading(true); setError('')
    Promise.all([
      api.get('/admin/organizations').catch(() => []),
      api.get('/admin/plans').catch(() => []),
      api.get('/admin/workflows/catalog').catch(() => []),
    ]).then(([oList, pList, cList]) => {
      setOrgs(Array.isArray(oList) ? oList : [])
      setPlans(Array.isArray(pList) ? pList : [])
      const cat = (cList || []).find(c => c.key === workflowKey)
      if (cat) {
        api.get(`/admin/workflows/assignments`).then(as => {
          const matched = (as || []).filter(a => a.workflow_id === cat.id).map(a => a.organization_id)
          setSelOrgs(matched)
        }).catch(() => {})
      }
    }).finally(() => setLoading(false))
  }, [open, workflowKey, api])

  const toggleOrg = (id) => {
    setSelOrgs(prev => prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id])
  }

  const togglePlan = (slug) => {
    setSelPlans(prev => prev.includes(slug) ? prev.filter(x => x !== slug) : [...prev, slug])
  }

  const handleSaveAssignments = async () => {
    setSaving(true); setError('')
    try {
      const cat = await api.get(`/admin/workflows/catalog`)
      const targetWf = (cat || []).find(c => c.key === workflowKey)
      if (!targetWf) throw new Error("Workflow not registered in catalog yet. Please click 'Save DAG' first.")

      for (const orgId of selectedOrgs) {
        await api.post(`/admin/organizations/${orgId}/workflows/${targetWf.id}/assign`, {
          notes: 'Assigned via Workflow Builder'
        }).catch(() => {})
      }

      for (const p of plans) {
        if (selectedPlans.includes(p.slug)) {
          const curEnt = await api.get(`/admin/plans`).then(ps => ps.find(x => x.id === p.id)?.entitlements || []).catch(() => [])
          const newEnt = Array.from(new Set([...curEnt, targetWf.id]))
          await api.put(`/admin/plans/${p.id}/entitlements`, { workflow_ids: newEnt }).catch(() => {})
        }
      }

      onDone(`Workflow '${workflowName}' successfully assigned to ${selectedOrgs.length} organization(s) and entitled on ${selectedPlans.length} plan(s).`)
      onClose()
    } catch (err) {
      setError(err?.response?.data?.detail || err.message || 'Assignment failed')
    } finally {
      setSaving(false)
    }
  }

  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs">
      <div className="bg-white dark:bg-[#121824] rounded-2xl shadow-2xl border border-slate-200 dark:border-[#233048] w-full max-w-lg max-h-[85vh] flex flex-col overflow-hidden text-slate-800 dark:text-white">
        <div className="px-5 py-4 border-b border-slate-200 dark:border-[#233048] flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Building2 className="w-5 h-5 text-blue-500" />
            <div>
              <h3 className="text-sm font-bold text-slate-900 dark:text-white">Assign Workflow: {workflowName}</h3>
              <p className="text-[11px] text-slate-500 dark:text-slate-400">Configure organization access and subscription plan entitlements</p>
            </div>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-700 dark:hover:text-white text-xl font-bold">×</button>
        </div>

        <div className="p-5 overflow-y-auto flex-1 space-y-4">
          {error && (
            <div className="p-3 bg-red-50 dark:bg-red-950/60 border border-red-200 dark:border-red-800 rounded-xl text-xs text-red-700 dark:text-red-300">
              {error}
            </div>
          )}

          <div>
            <p className="text-xs font-bold text-slate-600 dark:text-slate-300 uppercase tracking-wider mb-2 flex items-center gap-1.5">
              <CreditCard size={13} className="text-blue-500" /> Entitle on Billing Plans
            </p>
            <div className="grid grid-cols-2 gap-2">
              {plans.map(p => (
                <label
                  key={p.id}
                  className={cn(
                    'flex items-center gap-2 p-2.5 rounded-xl border text-xs cursor-pointer transition-all',
                    selectedPlans.includes(p.slug)
                      ? 'bg-blue-50 dark:bg-blue-600/20 border-blue-400 dark:border-blue-500 text-blue-700 dark:text-blue-300 font-semibold'
                      : 'bg-slate-50 dark:bg-[#162030] border-slate-200 dark:border-[#233048] text-slate-600 dark:text-slate-400 hover:border-slate-300 dark:hover:border-slate-500'
                  )}
                >
                  <input
                    type="checkbox"
                    checked={selectedPlans.includes(p.slug)}
                    onChange={() => togglePlan(p.slug)}
                    className="rounded border-slate-300 dark:border-slate-700 text-blue-600 focus:ring-0"
                  />
                  <span>{p.name}</span>
                </label>
              ))}
            </div>
          </div>

          <div>
            <p className="text-xs font-bold text-slate-600 dark:text-slate-300 uppercase tracking-wider mb-2 flex items-center gap-1.5">
              <Building2 size={13} className="text-blue-500" /> Assign to Organizations
            </p>
            <div className="space-y-1.5 max-h-48 overflow-y-auto">
              {orgs.map(o => (
                <label
                  key={o.id}
                  className={cn(
                    'flex items-center justify-between p-2.5 rounded-xl border text-xs cursor-pointer transition-all',
                    selectedOrgs.includes(o.id)
                      ? 'bg-blue-50 dark:bg-blue-600/20 border-blue-400 dark:border-blue-500 text-blue-700 dark:text-blue-300 font-semibold'
                      : 'bg-slate-50 dark:bg-[#162030] border-slate-200 dark:border-[#233048] text-slate-600 dark:text-slate-400 hover:border-slate-300 dark:hover:border-slate-500'
                  )}
                >
                  <div className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={selectedOrgs.includes(o.id)}
                      onChange={() => toggleOrg(o.id)}
                      className="rounded border-slate-300 dark:border-slate-700 text-blue-600 focus:ring-0"
                    />
                    <span>{o.name}</span>
                  </div>
                  <span className="text-[10px] text-slate-400 font-mono">{o.plan || 'starter'}</span>
                </label>
              ))}
            </div>
          </div>
        </div>

        <div className="p-4 border-t border-slate-200 dark:border-[#233048] flex justify-end gap-2 bg-slate-50 dark:bg-[#0c121d]">
          <Button variant="secondary" size="sm" onClick={onClose}>Cancel</Button>
          <Button variant="primary" size="sm" loading={saving} onClick={handleSaveAssignments} icon={<CheckCircle2 size={12} />}>
            Save Assignments
          </Button>
        </div>
      </div>
    </div>
  )
}

// ── AI WORKFLOW COPILOT MODAL ──────────────────────────────────────────────────
function AICopilotModal({ open, onClose, api, onWorkflowGenerated }) {
  const [prompt, setPrompt]         = useState('')
  const [industry, setIndustry]     = useState('general')
  const [generating, setGenerating] = useState(false)
  const [stepIndex, setStepIndex]   = useState(0)
  const [error, setError]           = useState('')

  const STEPS = [
    '🧠 Analyzing prompt semantics & business rules...',
    '🤖 Selecting multi-agent roles (Research, Reasoning, Drafting, Verification)...',
    '🔀 Constructing branching logic & HITL approval gates...',
    '🎨 Calculating 2D layout & compiling DAG...',
  ]

  useEffect(() => {
    let timer
    if (generating) {
      setStepIndex(0)
      timer = setInterval(() => {
        setStepIndex(prev => (prev < STEPS.length - 1 ? prev + 1 : prev))
      }, 600)
    }
    return () => clearInterval(timer)
  }, [generating])

  const PROMPT_SUGGESTIONS = [
    { label: '🛡️ Fraud & Invoice Triage', text: 'Build an automated invoice fraud detector that parses vendor PDFs, queries past purchase orders, flags suspicious amounts > $5,000 for SME Manager approval, and notifies accounting.' },
    { label: '🏥 Patient Clinic Triage', text: 'Create a patient clinic booking & reminder workflow that ingests calendar appointments, verifies patient SMS consent, crafts WhatsApp reminders, routes rescheduling to receptionist HITL gate, and updates clinic DB.' },
    { label: '📉 SaaS Churn Prevention', text: 'Build a B2B SaaS customer churn prevention workflow that detects high drop-off risk, queries CRM data, reasons on retention strategies, requests manager approval for discounts > 20%, and sends a customized email offer.' },
  ]

  const handleGenerate = async (e) => {
    e?.preventDefault()
    if (!prompt.trim()) { setError('Please enter a description of the workflow'); return }
    setGenerating(true); setError('')
    try {
      const resp = await api.post('/admin/workflows/ai-generate', {
        prompt: prompt.trim(),
        industry: industry,
      })
      onWorkflowGenerated(resp)
      onClose()
    } catch (err) {
      setError(err?.response?.data?.detail || err.message || 'AI synthesis failed')
    } finally {
      setGenerating(false)
    }
  }

  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs">
      <div className="bg-white dark:bg-[#121824] rounded-2xl shadow-2xl border border-slate-200 dark:border-[#233048] w-full max-w-xl flex flex-col overflow-hidden text-slate-800 dark:text-white animate-scale-in">
        <div className="px-5 py-4 bg-gradient-to-r from-blue-600 via-indigo-600 to-purple-600 text-white flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-white/15 flex items-center justify-center backdrop-blur-xs">
              <Sparkles className="w-5 h-5 text-white" />
            </div>
            <div>
              <h3 className="text-sm font-bold tracking-tight">Isolate AI Workflow Copilot</h3>
              <p className="text-[11px] text-white/80">Generate complete multi-agent DAG automations from natural language</p>
            </div>
          </div>
          <button onClick={onClose} className="text-white/70 hover:text-white text-xl font-bold">×</button>
        </div>

        <form onSubmit={handleGenerate} className="p-5 space-y-4">
          {error && (
            <div className="p-3 bg-red-50 dark:bg-red-950/60 border border-red-200 dark:border-red-800 rounded-xl text-xs text-red-700 dark:text-red-300">
              {error}
            </div>
          )}

          <div>
            <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1.5">
              Describe the workflow you want to create
            </label>
            <textarea
              value={prompt}
              onChange={e => setPrompt(e.target.value)}
              disabled={generating}
              rows={3}
              placeholder="e.g. Build an automated medical appointment reminder and triage workflow that ingests calendar bookings, verifies patient details, reasons on priority, alerts nurse SME if urgent, and sends SMS notifications."
              className="w-full text-xs p-3 rounded-xl bg-slate-50 dark:bg-[#162030] border border-slate-200 dark:border-[#2a3850] text-slate-800 dark:text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500/30 focus:border-blue-400 resize-none font-medium leading-relaxed"
            />
          </div>

          <div>
            <p className="text-[11px] font-semibold text-slate-500 dark:text-slate-400 mb-1.5 uppercase tracking-wider">
              Prompt Inspirations
            </p>
            <div className="grid grid-cols-2 gap-1.5">
              {PROMPT_SUGGESTIONS.map((item, idx) => (
                <button
                  key={idx}
                  type="button"
                  onClick={() => setPrompt(item.text)}
                  className="text-left p-2 rounded-lg border border-slate-200 dark:border-[#233048] bg-slate-50 dark:bg-[#162030] hover:bg-blue-50 dark:hover:bg-[#1f2c42] hover:border-blue-300 dark:hover:border-blue-400 transition-all text-[11px] text-slate-600 dark:text-slate-300 font-medium truncate"
                >
                  {item.label}
                </button>
              ))}
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3 pt-1">
            <Select
              label="Target Industry"
              value={industry}
              onChange={e => setIndustry(e.target.value)}
              options={INDUSTRIES.map(i => ({ value: i, label: i.charAt(0).toUpperCase() + i.slice(1) }))}
            />
            <div className="flex flex-col justify-end">
              <p className="text-[11px] text-slate-500 dark:text-slate-400 pb-1">
                AI will automatically pick triggers, agents, HITL gates &amp; tool connectors.
              </p>
            </div>
          </div>

          {generating && (
            <div className="p-4 bg-indigo-50 dark:bg-indigo-950/60 border border-indigo-200 dark:border-indigo-800 rounded-xl space-y-2">
              <div className="flex items-center gap-2 text-xs font-bold text-indigo-700 dark:text-indigo-300">
                <Spinner size="sm" />
                <span>Generating Multi-Agent Workflow...</span>
              </div>
              <p className="text-xs text-indigo-600 dark:text-indigo-200 font-medium pl-6">
                {STEPS[stepIndex]}
              </p>
            </div>
          )}

          <div className="flex justify-end gap-2 pt-3 border-t border-slate-200 dark:border-[#233048]">
            <Button variant="secondary" size="sm" type="button" onClick={onClose} disabled={generating}>
              Cancel
            </Button>
            <Button
              variant="primary"
              size="sm"
              type="submit"
              loading={generating}
              icon={<Sparkles size={13} />}
              className="bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700 text-white font-semibold"
            >
              Synthesize &amp; Load to Canvas
            </Button>
          </div>
        </form>
      </div>
    </div>
  )
}

// ── MAIN WORKFLOW BUILDER PAGE ─────────────────────────────────────────────────
export default function WorkflowBuilder() {
  const navigate          = useNavigate()
  const [searchParams]    = useSearchParams()
  const { api, user }     = useAuth()
  const [workflows, setWorkflows]     = useState([])
  const [selected, setSelected]       = useState(null)
  const [dag, setDag]                 = useState(null)
  const [allTools, setAllTools]       = useState([])
  const [promptFiles, setPromptFiles] = useState([])
  const [loading, setLoading]         = useState(true)
  const [saving, setSaving]           = useState(false)
  const [error, setError]             = useState('')
  const [success, setSuccess]         = useState('')
  const [showCreate, setShowCreate]   = useState(false)
  const [aiCopilotOpen, setAiCopilotOpen] = useState(false)
  const [testDrawerOpen, setTestDrawerOpen] = useState(false)
  const [assignModalOpen, setAssignModalOpen] = useState(false)

  // Form state for creating new custom workflow
  const [formName, setFormName]         = useState('')
  const [formKey, setFormKey]           = useState('')
  const [formIndustry, setFormIndustry] = useState(user?.industry || 'general')
  const [formCategory, setFormCategory] = useState('operations')
  const [formTrigger, setFormTrigger]   = useState('manual')
  const [formDesc, setFormDesc]         = useState('')

  const load = useCallback(async () => {
    try {
      const [wfs, tools, ptree] = await Promise.all([
        api.get('/config/workflows'),
        api.get('/admin/tools/library').catch(() => ({ triggers: [], agents: [], logic: [], tools: [] })),
        api.get('/config/prompt-tree').catch(() => ({ files: [] })),
      ])
      setWorkflows(Array.isArray(wfs) ? wfs : [])
      setAllTools(tools.tools || [])
      setPromptFiles(ptree.files || [])
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [api])

  useEffect(() => { load() }, [load])

  const selectWorkflow = async (name) => {
    try {
      const d = await api.get(`/config/dag/${name}`)
      setSelected(name)
      setDag(d)
    } catch (e) {
      setError(e.message)
    }
  }

  const didPreselectRef = useRef(false)
  useEffect(() => {
    if (didPreselectRef.current || loading || !workflows.length) return
    const wf = searchParams.get('wf')
    if (wf && workflows.some(w => w.name === wf)) {
      didPreselectRef.current = true
      selectWorkflow(wf)
    } else if (!selected) {
      didPreselectRef.current = true
      // Auto-load the first active workflow (e.g. product_launch_sprint or inbox triage)
      const target = workflows.find(w => w.name === 'product_launch_sprint') || workflows[0]
      if (target) selectWorkflow(target.name)
    }
  }, [searchParams, loading, workflows, selected])

  const handleSaveDAG = async (dagData) => {
    setSaving(true); setError(''); setSuccess('')
    try {
      const resp = await api.post('/admin/workflows/custom', {
        name: dagData._meta?.name || selected,
        key: selected,
        description: dagData._meta?.description || '',
        category: dagData._meta?.category || 'operations',
        industry: dagData._meta?.industry || 'general',
        scope: 'GLOBAL',
        trigger_type: dagData._meta?.trigger?.type || 'manual',
        sla_hours: dagData._meta?.sla_hours || 4,
        dag: dagData,
      })
      setSuccess(resp?.message || 'Workflow published and saved to catalog!')
      await load()
      setTimeout(() => setSuccess(''), 4000)
    } catch (e) {
      setError(e?.response?.data?.detail || e.message || 'Save failed')
    } finally {
      setSaving(false)
    }
  }

  const handleWorkflowGenerated = async (generatedWf) => {
    const initialDag = {
      _meta: {
        workflow_id: generatedWf.key,
        name: generatedWf.name,
        industry: generatedWf.industry,
        category: generatedWf.category,
        version: '1.0.0',
        description: generatedWf.description,
        trigger: { type: generatedWf.trigger_type, source: 'ai_copilot' },
        trigger_types: [generatedWf.trigger_type],
        sla_hours: generatedWf.sla_hours || 4,
        is_custom: true,
      },
      nodes: generatedWf.nodes.map(n => ({
        id: n.id,
        agent: n.data?.agentType || n.type || 'reasoning_agent',
        name: n.data?.name || n.id,
        description: n.data?.prompt_directive || n.data?.description || '',
        timeout_seconds: n.data?.timeout_seconds || 60,
        tools: n.data?.tools || [],
      })),
      edges: generatedWf.edges.map(e => ({
        from: e.source,
        to: e.target,
        condition: e.condition || null,
      })),
      escalation_config: { sla_hours: generatedWf.sla_hours || 4, resume_after_decision: true },
    }

    try {
      setSaving(true)
      await api.post('/admin/workflows/custom', {
        name: generatedWf.name,
        key: generatedWf.key,
        description: generatedWf.description,
        category: generatedWf.category,
        industry: generatedWf.industry,
        scope: generatedWf.scope || 'GLOBAL',
        trigger_type: generatedWf.trigger_type,
        sla_hours: generatedWf.sla_hours || 4,
        dag: initialDag,
      })
      await load()
      selectWorkflow(generatedWf.key)
    } catch (err) {
      setError(err?.response?.data?.detail || err.message || 'Failed to save generated workflow')
    } finally {
      setSaving(false)
    }
  }

  const createWorkflow = async (e) => {
    e.preventDefault()
    if (!formKey || !formName) return
    setSaving(true); setError('')

    const initialDag = {
      _meta: {
        workflow_id: formKey,
        name: formName,
        industry: formIndustry,
        category: formCategory,
        version: '1.0.0',
        description: formDesc,
        trigger: { type: formTrigger, source: 'manual' },
        trigger_types: [formTrigger],
        sla_hours: 4,
        is_custom: true,
      },
      nodes: [
        { id: 'trigger_1', agent: `trigger_${formTrigger}`, name: formTrigger === 'scheduled' ? 'Every Morning' : formTrigger === 'email' ? 'Inbound Email Ingest' : formTrigger === 'webhook' ? 'REST Webhook Ingest' : 'Manual Run', description: 'Trigger', timeout_seconds: 60, tools: [] },
        { id: 'agent_process', agent: formTrigger === 'email' ? 'drafting_agent' : 'reasoning_agent', name: formTrigger === 'email' ? 'Summarize Emails' : 'Reasoning & Logic', description: 'AI Agent', timeout_seconds: 60, tools: formTrigger === 'email' ? ['tool_email_dispatch'] : [] },
      ],
      edges: [{ from: 'trigger_1', to: 'agent_process', condition: '1 item' }],
      escalation_config: { sla_hours: 4, resume_after_decision: true },
    }

    try {
      await api.post('/admin/workflows/custom', {
        name: formName,
        key: formKey,
        description: formDesc,
        category: formCategory,
        industry: formIndustry,
        scope: 'GLOBAL',
        trigger_type: formTrigger,
        sla_hours: 4,
        dag: initialDag,
      })
      setShowCreate(false)
      await load()
      selectWorkflow(formKey)
    } catch (err) {
      setError(err?.response?.data?.detail || err.message || 'Creation failed')
    } finally {
      setSaving(false)
    }
  }

  if (loading) {
    return (
      <div className="h-full flex items-center justify-center bg-slate-50 dark:bg-[#0d1117]">
        <Spinner size="lg" />
      </div>
    )
  }

  return (
    <div className="h-[calc(100vh-4rem)] flex flex-col bg-slate-50 dark:bg-[#0d1117] overflow-hidden">
      {error && (
        <div className="px-4 py-2 bg-red-50 dark:bg-red-950/80 border-b border-red-200 dark:border-red-800 text-xs text-red-700 dark:text-red-200 flex items-center justify-between">
          <span>{error}</span>
          <button onClick={() => setError('')} className="font-bold">×</button>
        </div>
      )}
      {success && (
        <div className="px-4 py-2 bg-emerald-50 dark:bg-emerald-950/80 border-b border-emerald-200 dark:border-emerald-800 text-xs text-emerald-700 dark:text-emerald-200 flex items-center justify-between">
          <span>{success}</span>
          <button onClick={() => setSuccess('')} className="font-bold">×</button>
        </div>
      )}

      <div className="flex-1 flex min-h-0 relative">
        
        {/* ── Left Workflow List Sidebar ── */}
        <div className="w-56 shrink-0 bg-white dark:bg-[#0f1522] border-r border-slate-200 dark:border-[#233048] flex flex-col h-full z-10 select-none">
          <div className="p-3 border-b border-slate-200 dark:border-[#233048] flex items-center justify-between">
            <span className="text-xs font-bold text-slate-700 dark:text-slate-300">Workflows</span>
            <button
              onClick={() => setShowCreate(true)}
              className="p-1 rounded-lg bg-blue-600 hover:bg-blue-500 text-white"
              title="Create Custom Workflow"
            >
              <Plus className="w-3.5 h-3.5" />
            </button>
          </div>

          <div className="flex-1 overflow-y-auto p-2 space-y-1">
            {workflows.map(w => {
              const active = selected === w.name
              return (
                <button
                  key={w.name}
                  onClick={() => selectWorkflow(w.name)}
                  className={cn(
                    'w-full text-left p-2.5 rounded-xl border text-xs transition-all flex items-center justify-between gap-2',
                    active
                      ? 'bg-blue-50 dark:bg-[#1b2538] border-blue-400 dark:border-blue-500/80 text-blue-700 dark:text-white font-bold shadow-xs'
                      : 'bg-white dark:bg-[#141c2c] border-slate-200 dark:border-[#233048] text-slate-600 dark:text-slate-300 hover:border-slate-300 dark:hover:border-slate-500 hover:bg-slate-50 dark:hover:bg-[#182335]'
                  )}
                >
                  <span className="truncate">{w.display_name || w.name}</span>
                  <ChevronRight className={cn('w-3 h-3 text-slate-400 shrink-0', active && 'text-blue-500 dark:text-blue-400')} />
                </button>
              )
            })}
          </div>
        </div>

        {/* Center / Right Canvas */}
        <div className="flex-1 min-w-0 min-h-0">
          {selected && dag ? (
            <ReactFlowProvider>
              <FlowCanvas
                workflowName={selected}
                dag={dag}
                allTools={allTools}
                promptFiles={promptFiles}
                onSave={handleSaveDAG}
                isSaving={saving}
                onTestRun={() => setTestDrawerOpen(true)}
                onOpenAssign={() => setAssignModalOpen(true)}
                onOpenAICopilot={() => setAiCopilotOpen(true)}
                api={api}
              />
            </ReactFlowProvider>
          ) : (
            <div className="h-full flex items-center justify-center p-8 bg-white dark:bg-[#0d1117]">
              <div className="text-center max-w-sm">
                <div className="w-14 h-14 rounded-2xl bg-slate-100 dark:bg-[#162030] border border-slate-200 dark:border-[#2a3850] text-blue-500 flex items-center justify-center mx-auto mb-3 shadow-md">
                  <Sparkles size={24} />
                </div>
                <h3 className="text-sm font-bold text-slate-900 dark:text-white mb-1">Select Workflow or Generate with AI Copilot</h3>
                <p className="text-xs text-slate-500 dark:text-slate-400 mb-4 leading-relaxed">
                  Open an existing workflow or use natural language to generate a connected multi-agent automation.
                </p>
                <div className="flex items-center justify-center gap-2">
                  <Button
                    variant="primary"
                    size="sm"
                    onClick={() => setAiCopilotOpen(true)}
                    icon={<Sparkles size={14} />}
                    className="bg-gradient-to-r from-blue-600 to-indigo-600 font-semibold"
                  >
                    AI Copilot
                  </Button>
                  <Button variant="secondary" size="sm" onClick={() => setShowCreate(true)} icon={<Plus size={14} />}>
                    Blank Canvas
                  </Button>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* AI Copilot Modal */}
      <AICopilotModal
        open={aiCopilotOpen}
        onClose={() => setAiCopilotOpen(false)}
        api={api}
        onWorkflowGenerated={handleWorkflowGenerated}
      />

      {/* Test Run Drawer */}
      <TestRunDrawer
        open={testDrawerOpen}
        onClose={() => setTestDrawerOpen(false)}
        workflowKey={selected}
        api={api}
      />

      {/* Assign Orgs & Plans Modal */}
      <AssignWorkflowModal
        open={assignModalOpen}
        onClose={() => setAssignModalOpen(false)}
        workflowKey={selected}
        workflowName={dag?._meta?.name || selected}
        api={api}
        onDone={(msg) => {
          setSuccess(msg)
          setTimeout(() => setSuccess(''), 5000)
        }}
      />

      {/* Create Custom Workflow Modal */}
      <Modal open={showCreate} onClose={() => setShowCreate(false)} title="Create New Custom Workflow" width="max-w-md">
        <form onSubmit={createWorkflow} className="space-y-3.5">
          <Input
            label="Workflow Display Name"
            value={formName}
            onChange={e => {
              setFormName(e.target.value)
              if (!formKey || formKey === formName.toLowerCase().replace(/\s+/g, '_')) {
                setFormKey(e.target.value.toLowerCase().replace(/\s+/g, '_'))
              }
            }}
            placeholder="e.g. Lead Qualification & Scoring"
            required
          />
          <Input
            label="Workflow Identifier Key (snake_case)"
            value={formKey}
            onChange={e => setFormKey(e.target.value.replace(/\s+/g, '_').toLowerCase())}
            placeholder="lead_qualification_scoring"
            hint="Used in API and DAG filename"
            required
          />
          <div className="grid grid-cols-2 gap-2">
            <Select
              label="Category"
              value={formCategory}
              onChange={e => setFormCategory(e.target.value)}
              options={CATEGORIES.map(c => ({ value: c, label: c.charAt(0).toUpperCase() + c.slice(1) }))}
            />
            <Select
              label="Primary Trigger"
              value={formTrigger}
              onChange={e => setFormTrigger(e.target.value)}
              options={[
                { value: 'manual',    label: 'Manual Run' },
                { value: 'email',     label: 'Inbound Email' },
                { value: 'scheduled', label: 'Scheduled Cron' },
                { value: 'webhook',   label: 'REST Webhook' },
              ]}
            />
          </div>
          <Select
            label="Target Industry"
            value={formIndustry}
            onChange={e => setFormIndustry(e.target.value)}
            options={INDUSTRIES.map(i => ({ value: i, label: i.charAt(0).toUpperCase() + i.slice(1) }))}
          />
          <Textarea
            label="Workflow Description"
            value={formDesc}
            onChange={e => setFormDesc(e.target.value)}
            placeholder="Describe what this multi-agent workflow accomplishes..."
            rows={2}
          />
          <div className="flex justify-end gap-2 pt-2 border-t border-slate-200 dark:border-slate-700">
            <Button variant="secondary" size="sm" type="button" onClick={() => setShowCreate(false)}>Cancel</Button>
            <Button variant="primary" size="sm" type="submit" loading={saving}>Create &amp; Open Canvas</Button>
          </div>
        </form>
      </Modal>
    </div>
  )
}