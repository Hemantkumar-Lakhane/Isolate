// frontend/src/pages/LandingPage.jsx
// ─────────────────────────────────────────────────────────────────────────────
// SMBFlow — Clean, High-Precision Enterprise Architecture
// Autonomous Multi-Agent Workflow & Orchestration Engine
// Real workflows, interactive live SVG canvas, zero fake icons.
// ─────────────────────────────────────────────────────────────────────────────
import React, { useState, useRef } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useTheme } from '../contexts/ThemeContext'
import {
  ArrowRight,
  Play,
  Check,
  Shield,
  Zap,
  Mail,
  Receipt,
  CreditCard,
  Layers,
  Sparkles,
  ChevronDown,
  Lock,
  Database,
  RefreshCw,
  Cpu,
  BrainCircuit,
  MessageSquare,
  FileText,
  Sun,
  Moon,
  AlertTriangle,
  UserCheck,
  Workflow,
  Sliders,
  CheckCircle2,
  KeyRound,
  History,
  Terminal,
  ExternalLink,
  ChevronRight,
  Maximize2,
  Minimize2
} from 'lucide-react'

// ── Tool Logo with Asset Image Support & Vector Fallbacks ─────────────────────
function ToolLogo({ name, className = 'w-4 h-4' }) {
  const [imgSrc, setImgSrc] = useState(() => {
    if (!name) return null
    const n = name.toLowerCase().replace(/[^a-z0-9]/g, '')
    if (n.includes('sheet')) return '/assets/tools/sheet.png'
    if (n.includes('gmail') || n.includes('email') || n.includes('mail')) return '/assets/tools/gmail.png'
    if (n.includes('openai') || n.includes('gpt')) return '/assets/tools/openai.png'
    if (n.includes('claude') || n.includes('anthropic')) return '/assets/tools/claude.png'
    if (n.includes('slack')) return '/assets/tools/slack.png'
    if (n.includes('calendar')) return '/assets/tools/calendar.png'
    if (n.includes('telegram')) return '/assets/tools/telegram.png'
    if (n.includes('postgres') || n.includes('sql') || n.includes('database')) return '/assets/tools/postgres.png'
    if (n.includes('webhook') || n.includes('api')) return '/assets/tools/webhook.png'
    return `/assets/tools/${n}.png`
  })
  const [useFallback, setUseFallback] = useState(false)

  const svgFallbacks = {
    gmail: (
      <svg className={className} viewBox="0 0 24 24" fill="none">
        <path d="M22 6C22 4.9 21.1 4 20 4H4C2.9 4 2 4.9 2 6V18C2 19.1 2.9 20 4 20H20C21.1 20 22 19.1 22 18V6Z" fill="#EA4335" fillOpacity="0.15" />
        <path d="M20 4H4C2.9 4 2 4.9 2 6L12 13L22 6C22 4.9 21.1 4 20 4Z" fill="#EA4335" />
        <path d="M2 18V6L12 13L22 6V18C22 19.1 21.1 20 20 20H4C2.9 20 2 19.1 2 18Z" stroke="#EA4335" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    ),
    sheet: (
      <svg className={className} viewBox="0 0 24 24" fill="none">
        <rect x="3" y="3" width="18" height="18" rx="3" fill="#0F9D58" fillOpacity="0.2" stroke="#0F9D58" strokeWidth="1.5" />
        <path d="M7 8H17M7 12H17M7 16H17M12 8V16" stroke="#0F9D58" strokeWidth="1.5" strokeLinecap="round" />
      </svg>
    ),
    calendar: (
      <svg className={className} viewBox="0 0 24 24" fill="none">
        <rect x="3" y="4" width="18" height="17" rx="3" fill="#4285F4" fillOpacity="0.2" stroke="#4285F4" strokeWidth="1.5" />
        <path d="M16 2V6M8 2V6M3 9H21" stroke="#4285F4" strokeWidth="1.5" strokeLinecap="round" />
        <circle cx="12" cy="14" r="1.5" fill="#4285F4" />
      </svg>
    ),
    claude: (
      <svg className={className} viewBox="0 0 24 24" fill="currentColor">
        <path d="M13.5 3L11.5 8L15 11.5L9.5 13L8 21L11.5 15.5L16 17L14.5 11L19.5 9.5L13.5 3Z" fill="#D97706" />
      </svg>
    ),
    openai: (
      <svg className={className} viewBox="0 0 24 24" fill="none" stroke="#10B981" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <path d="M12 2a10 10 0 0 1 10 10 10 10 0 0 1-10 10A10 10 0 0 1 2 12 10 10 0 0 1 12 2z" fill="#10B981" fillOpacity="0.15" />
        <path d="M12 6v12M6 12h12M7.75 7.75l8.5 8.5M7.75 16.25l8.5-8.5" />
      </svg>
    ),
    slack: (
      <svg className={className} viewBox="0 0 24 24" fill="none">
        <rect x="3" y="3" width="18" height="18" rx="4" fill="#EC4899" fillOpacity="0.15" stroke="#EC4899" strokeWidth="1.5" />
        <path d="M8 12H16M12 8V16" stroke="#EC4899" strokeWidth="2" strokeLinecap="round" />
      </svg>
    ),
    telegram: (
      <svg className={className} viewBox="0 0 24 24" fill="none">
        <path d="M21.5 3.5L2 11.5L8.5 14.5L18 6.5L11 16.5L17.5 20.5L21.5 3.5Z" fill="#229ED9" fillOpacity="0.2" stroke="#229ED9" strokeWidth="1.5" strokeLinejoin="round" />
      </svg>
    ),
    hubspot: (
      <svg className={className} viewBox="0 0 24 24" fill="none">
        <circle cx="12" cy="12" r="5" fill="#FF7A59" fillOpacity="0.2" stroke="#FF7A59" strokeWidth="1.5" />
        <path d="M12 3V7M12 17V21M3 12H7M17 12H21" stroke="#FF7A59" strokeWidth="1.5" strokeLinecap="round" />
      </svg>
    ),
    stripe: (
      <svg className={className} viewBox="0 0 24 24" fill="none">
        <rect x="3" y="4" width="18" height="16" rx="3" fill="#6366F1" fillOpacity="0.2" stroke="#6366F1" strokeWidth="1.5" />
        <path d="M8 12h8M12 9v6" stroke="#6366F1" strokeWidth="2" strokeLinecap="round" />
      </svg>
    ),
    quickbooks: (
      <svg className={className} viewBox="0 0 24 24" fill="none">
        <circle cx="12" cy="12" r="9" fill="#2CA01C" fillOpacity="0.2" stroke="#2CA01C" strokeWidth="1.5" />
        <path d="M8 12a4 4 0 1 1 8 0M12 8v8" stroke="#2CA01C" strokeWidth="1.5" />
      </svg>
    ),
    shopify: (
      <svg className={className} viewBox="0 0 24 24" fill="none">
        <rect x="4" y="5" width="16" height="15" rx="3" fill="#95BF47" fillOpacity="0.2" stroke="#95BF47" strokeWidth="1.5" />
        <path d="M9 5l3-2 3 2v4H9V5z" stroke="#95BF47" strokeWidth="1.5" strokeLinejoin="round" />
      </svg>
    ),
    googledrive: (
      <svg className={className} viewBox="0 0 24 24" fill="none">
        <polygon points="12 3 20 17 16 21 4 7" fill="#0F9D58" fillOpacity="0.2" stroke="#0F9D58" strokeWidth="1.5" />
        <polygon points="4 7 12 3 8 17 2 17" fill="#4285F4" fillOpacity="0.3" stroke="#4285F4" strokeWidth="1.5" />
        <polygon points="16 21 20 17 8 17 4 21" fill="#F4B400" fillOpacity="0.3" stroke="#F4B400" strokeWidth="1.5" />
      </svg>
    ),
    postgres: (
      <svg className={className} viewBox="0 0 24 24" fill="none" stroke="#336791" strokeWidth="1.5">
        <ellipse cx="12" cy="5" rx="9" ry="3" fill="#336791" fillOpacity="0.2" />
        <path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3" />
        <path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5" />
      </svg>
    ),
    webhook: (
      <svg className={className} viewBox="0 0 24 24" fill="none" stroke="#3B82F6" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="6" cy="12" r="3" fill="#3B82F6" fillOpacity="0.2" />
        <circle cx="18" cy="6" r="3" fill="#3B82F6" fillOpacity="0.2" />
        <circle cx="18" cy="18" r="3" fill="#3B82F6" fillOpacity="0.2" />
        <path d="M9 12H12M12 12L15 6M12 12L15 18" />
      </svg>
    ),
  }

  const key = name ? name.toLowerCase().replace(/[^a-z0-9]/g, '') : 'webhook'

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

  return svgFallbacks[key] || svgFallbacks.webhook || <Zap className={className} />
}

// ── Interactive Canvas Pipeline Presets ────────────────────────────────────────
const LANDING_WORKFLOWS = [
  {
    id: 'invoices',
    name: 'Invoice OCR & Discrepancy Gate',
    category: 'Finance Operations',
    description: 'Scans Gmail for vendor invoice PDFs, uses Claude 3.5 to parse line items, checks purchase order totals in Sheets, and stages discrepancies in Action Center.',
    nodes: [
      { id: '1', title: 'Invoice Received', subtitle: 'Gmail Daily Poll', tool: 'gmail', type: 'Trigger', x: 20, y: 80, config: { schedule: '0 8 * * 1-5', mailbox: 'invoices@company.com' }, sampleInput: { event: 'new_attachment', type: 'pdf' }, sampleOutput: { sender: 'billing@vendor-saas.io', subject: 'Cloud Invoice #INV-2026-891' } },
      { id: '2', title: 'Extract Line Items', subtitle: 'Claude 3.5 Sonnet', tool: 'claude', type: 'LLM Agent', x: 200, y: 80, config: { model: 'claude-3-5-sonnet', temperature: 0.1 }, sampleInput: { rawText: 'Invoice #891: $1,450.00' }, sampleOutput: { vendor: 'Cloud Infra Ltd', amountUsd: 1450.0, po: 'PO-8921' } },
      { id: '3', title: 'Verify Against PO', subtitle: 'Sheets Matcher', tool: 'sheet', type: 'Data Router', x: 380, y: 80, config: { sheet: 'Procurement_Log', matchKeys: ['po_number', 'amount'] }, sampleInput: { po: 'PO-8921', amount: 1450.0 }, sampleOutput: { matched: true, varianceUsd: 0.0 } },
      { id: '4', title: 'Action Center Gate', subtitle: 'Human Sign-off', tool: 'webhook', type: 'HITL Review', x: 560, y: 30, config: { escalationQueue: 'Finance_Approvals' }, sampleInput: { status: 'PENDING_SIGNOFF' }, sampleOutput: { approvedBy: 'Lead Accountant' } },
      { id: '5', title: 'Schedule Due Date', subtitle: 'Google Calendar', tool: 'calendar', type: 'Destination Sync', x: 560, y: 130, config: { calendarId: 'primary', reminderDays: 2 }, sampleInput: { date: '2026-10-15', title: 'Pay Vendor Invoice' }, sampleOutput: { eventCreated: true, id: 'cal_9812' } },
    ],
    edges: [
      { from: '1', to: '2' },
      { from: '2', to: '3' },
      { from: '3', to: '4', label: 'Discrepancy' },
      { from: '3', to: '5', label: 'Match Verified' },
    ]
  },
  {
    id: 'email_triage',
    name: 'AI Inbox Triage & Email Summarizer',
    category: 'Executive Comms',
    description: 'Autonomous inbox pipeline that fetches unread emails, summarizes threads, scores urgency, drafts structured responses, and notifies Slack.',
    nodes: [
      { id: '1', title: 'Gmail Trigger', subtitle: 'Unread Poller', tool: 'gmail', type: 'Trigger', x: 20, y: 80, config: { query: 'is:unread label:inbox' }, sampleInput: { unreadCount: 14 }, sampleOutput: { subject: 'Urgent: Q3 Contract Renewal Terms' } },
      { id: '2', title: 'Intent & Urgency', subtitle: 'Claude 3.5 Sonnet', tool: 'claude', type: 'LLM Agent', x: 200, y: 80, config: { classification: 'Priority_Executive' }, sampleInput: { bodyText: 'Need signoff before EOD Friday...' }, sampleOutput: { score: 95, category: 'High Urgency Contract' } },
      { id: '3', title: 'Action Center Review', subtitle: 'Draft Verification', tool: 'webhook', type: 'HITL Review', x: 380, y: 80, config: { autoDraftReply: true }, sampleInput: { draft: 'Hi Team, reviewed and approved...' }, sampleOutput: { signedOff: true } },
      { id: '4', title: 'Slack VIP Alert', subtitle: 'Executive Channel', tool: 'slack', type: 'Real-time Alert', x: 560, y: 80, config: { channel: '#exec-briefs' }, sampleInput: { priority: 'P1' }, sampleOutput: { delivered: true } },
    ],
    edges: [
      { from: '1', to: '2' },
      { from: '2', to: '3' },
      { from: '3', to: '4' },
    ]
  },
  {
    id: 'product_launch',
    name: 'Product Launch Sprint Campaign',
    category: 'Marketing Operations',
    description: 'Coordinates multi-channel launch preparation: generates tailored LinkedIn and Twitter copy, triggers ImageRouter banner graphics, and queues social feeds.',
    nodes: [
      { id: '1', title: 'Campaign Intake', subtitle: 'Brief Hook', tool: 'webhook', type: 'Trigger', x: 20, y: 80, config: { type: 'marketing_brief' }, sampleInput: { launchName: 'SMBFlow 3.0' }, sampleOutput: { targetAudience: 'B2B SaaS Founders' } },
      { id: '2', title: 'Multi-Channel Copy', subtitle: 'Claude Sonnet', tool: 'claude', type: 'LLM Agent', x: 200, y: 80, config: { channels: ['linkedin', 'twitter', 'newsletter'] }, sampleInput: { brief: 'Autonomous workflow engine' }, sampleOutput: { postsReady: 3 } },
      { id: '3', title: 'Banner Generation', subtitle: 'ImageRouter DALL-E', tool: 'openai', type: 'Visual AI', x: 380, y: 80, config: { ratio: '16:9' }, sampleInput: { prompt: 'Clean tech workflow interface' }, sampleOutput: { assetUrl: 'https://cdn.smbflow.io/banner.png' } },
      { id: '4', title: 'Social Queue Sync', subtitle: 'Google Sheets', tool: 'sheet', type: 'Destination Sync', x: 560, y: 80, config: { queueName: 'Launch_Q4' }, sampleInput: { items: 3 }, sampleOutput: { scheduled: true } },
    ],
    edges: [
      { from: '1', to: '2' },
      { from: '2', to: '3' },
      { from: '3', to: '4' },
    ]
  }
]

export default function LandingPage() {
  const navigate = useNavigate()
  const { theme, toggle: toggleTheme, isDark } = useTheme()

  // Mouse spotlight coordinates
  const [mousePos, setMousePos] = useState({ x: -1000, y: -1000 })
  const heroRef = useRef(null)

  const handleMouseMove = (e) => {
    if (!heroRef.current) return
    const rect = heroRef.current.getBoundingClientRect()
    setMousePos({
      x: e.clientX - rect.left,
      y: e.clientY - rect.top
    })
  }

  // Interactive Canvas State
  const [activeWorkflowId, setActiveWorkflowId] = useState('invoices')
  const currentWorkflow = LANDING_WORKFLOWS.find(w => w.id === activeWorkflowId) || LANDING_WORKFLOWS[0]
  const [selectedNode, setSelectedNode] = useState(currentWorkflow.nodes[0])

  // Update selected node when workflow switches
  const handleSelectWorkflow = (wfId) => {
    setActiveWorkflowId(wfId)
    const wf = LANDING_WORKFLOWS.find(w => w.id === wfId) || LANDING_WORKFLOWS[0]
    setSelectedNode(wf.nodes[0])
  }

  // Pricing state
  const [billingCycle, setBillingCycle] = useState('monthly')
  const [openFaqIndex, setOpenFaqIndex] = useState(null)
  const [ctaEmail, setCtaEmail] = useState('')

  const handleCtaSubmit = (e) => {
    e.preventDefault()
    if (ctaEmail.trim()) {
      navigate('/auth/signup', { state: { email: ctaEmail.trim() } })
    } else {
      navigate('/auth/signup')
    }
  }

  const INTEGRATION_TOOLS = [
    { name: 'Gmail', id: 'gmail' },
    { name: 'Google Drive', id: 'googledrive' },
    { name: 'QuickBooks Online', id: 'quickbooks' },
    { name: 'Stripe', id: 'stripe' },
    { name: 'HubSpot CRM', id: 'hubspot' },
    { name: 'Slack', id: 'slack' },
    { name: 'Shopify', id: 'shopify' },
    { name: 'PostgreSQL', id: 'postgres' },
    { name: 'Custom Webhooks', id: 'webhook' },
  ]

  const faqs = [
    {
      q: "How does SMBFlow execute multi-agent workflows?",
      a: "SMBFlow uses Directed Acyclic Graphs (DAGs) powered by an asynchronous state engine. Each node represents a discrete task (LLM reasoning, deterministic rule routing, human sign-off, or external API execution) executed in verified sequence with full PostgreSQL audit persistence."
    },
    {
      q: "What is Human-in-the-Loop (HITL) Safe Mode?",
      a: "For sensitive operations (such as high-value payouts, outgoing executive communications, or clinical intake records), execution pauses at a designated Approval Gate. An item is staged in the Action Center for one-click team verification before downstream APIs are invoked."
    },
    {
      q: "Which AI models and providers are supported?",
      a: "SMBFlow supports Anthropic (Claude 3.7 / 3.5 Sonnet), OpenAI (GPT-4o / GPT-4o mini), Google Gemini, and open-source models via Groq (Llama 3.3). You can supply your own API keys via the encrypted Key Vault."
    },
    {
      q: "Is data isolated between client organizations?",
      a: "Yes. SMBFlow enforces complete multi-tenant database isolation at the schema and query layer. Credentials, workflow execution history, and client data are cryptographically partitioned."
    },
    {
      q: "Can I schedule workflows or trigger them via webhooks?",
      a: "Yes. Workflows support automated scheduling (configurable cron intervals: daily, hourly, 15-minute, or custom cron expressions) as well as continuous inbound webhook triggers and manual one-click runs."
    }
  ]

  return (
    <div className={`min-h-screen transition-colors duration-200 ${
      isDark
        ? 'bg-[#0b0f17] text-slate-100 selection:bg-blue-600 selection:text-white'
        : 'bg-slate-50 text-slate-900 selection:bg-blue-600 selection:text-white font-sans'
    }`}>

      {/* ── Top Header Navigation ───────────────────────────────────────────── */}
      <header className={`sticky top-0 z-50 w-full backdrop-blur-md border-b transition-colors ${
        isDark
          ? 'bg-[#0b0f17]/90 border-[#233048] text-white'
          : 'bg-white/90 border-slate-200 text-slate-900'
      }`}>
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          {/* Logo */}
          <Link to="/" className="flex items-center gap-2.5 group">
            <div className="w-8 h-8 rounded-lg bg-blue-600 flex items-center justify-center text-white shadow-xs">
              <BrainCircuit className="w-4 h-4" />
            </div>
            <div className="flex items-center gap-2">
              <span className={`font-bold text-base tracking-tight ${isDark ? 'text-white' : 'text-slate-900'}`}>
                SMBFlow
              </span>
              <span className={`text-[10px] px-1.5 py-0.5 rounded font-mono font-semibold uppercase tracking-wider ${
                isDark ? 'bg-[#182234] text-slate-300 border border-[#233048]' : 'bg-slate-100 text-slate-600 border border-slate-200'
              }`}>
                v3.0
              </span>
            </div>
          </Link>

          {/* Desktop Nav Links */}
          <nav className={`hidden md:flex items-center gap-7 text-sm font-medium ${isDark ? 'text-slate-300' : 'text-slate-600'}`}>
            <a href="#workflows" className={`transition-colors ${isDark ? 'hover:text-white' : 'hover:text-slate-900'}`}>Workflows</a>
            <a href="#architecture" className={`transition-colors ${isDark ? 'hover:text-white' : 'hover:text-slate-900'}`}>Architecture</a>
            <a href="#integrations" className={`transition-colors ${isDark ? 'hover:text-white' : 'hover:text-slate-900'}`}>Integrations</a>
            <a href="#pricing" className={`transition-colors ${isDark ? 'hover:text-white' : 'hover:text-slate-900'}`}>Pricing</a>
            <a href="#faq" className={`transition-colors ${isDark ? 'hover:text-white' : 'hover:text-slate-900'}`}>Docs & FAQ</a>
          </nav>

          {/* Nav Actions + Theme Toggle */}
          <div className="flex items-center gap-3">
            <button
              onClick={toggleTheme}
              className={`p-2 rounded-xl border transition-all cursor-pointer ${
                isDark
                  ? 'bg-[#121826] border-[#233048] text-amber-300 hover:bg-[#182234]'
                  : 'bg-white border-slate-200 text-slate-700 hover:bg-slate-100 shadow-2xs'
              }`}
              title={isDark ? "Switch to Light Mode" : "Switch to Dark Mode"}
            >
              {isDark ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
            </button>

            <Link
              to="/auth"
              className={`text-sm font-medium px-3 py-2 transition-colors ${
                isDark ? 'text-slate-300 hover:text-white' : 'text-slate-700 hover:text-slate-900'
              }`}
            >
              Sign in
            </Link>
            <Link
              to="/auth/signup"
              className="inline-flex items-center justify-center gap-1.5 px-4 py-2 rounded-xl text-sm font-semibold text-white bg-blue-600 hover:bg-blue-500 shadow-xs transition-all duration-150"
            >
              <span>Get Started</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          </div>
        </div>
      </header>

      <main className="w-full">
        {/* ── Hero Section ─────────────────────────────────────────────────── */}
        <section
          ref={heroRef}
          onMouseMove={handleMouseMove}
          className={`relative pt-20 pb-20 md:pt-28 md:pb-28 overflow-hidden transition-colors border-b ${
            isDark
              ? 'bg-[#0b0f17] border-[#233048] bg-dot-pattern'
              : 'bg-white border-slate-200 bg-dot-pattern'
          }`}
        >
          {/* Subtle Spotlight */}
          <div
            className="absolute inset-0 pointer-events-none transition-all duration-100 ease-out"
            style={{
              background: isDark
                ? `radial-gradient(550px circle at ${mousePos.x}px ${mousePos.y}px, rgba(37, 99, 235, 0.12) 0%, transparent 65%)`
                : `radial-gradient(500px circle at ${mousePos.x}px ${mousePos.y}px, rgba(37, 99, 235, 0.08) 0%, transparent 60%)`
            }}
          />

          <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col items-center text-center relative z-10">
            {/* Tag Badge */}
            <div className={`inline-flex items-center gap-2 px-3.5 py-1 rounded-full text-xs font-semibold mb-8 border shadow-2xs ${
              isDark
                ? 'bg-[#121826] border-[#233048] text-blue-400'
                : 'bg-slate-50 border-slate-200 text-blue-700'
            }`}>
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse"></span>
              <span>Autonomous Multi-Agent Workflow Engine</span>
            </div>

            {/* Headline */}
            <h1 className={`text-4xl sm:text-5xl md:text-6xl font-bold tracking-tight max-w-3xl leading-[1.15] ${
              isDark ? 'text-white' : 'text-slate-950'
            }`}>
              Autonomous workflows with{' '}
              <span className="text-blue-600 dark:text-blue-400">
                human-in-the-loop
              </span>{' '}
              precision.
            </h1>

            {/* Subtitle */}
            <p className={`mt-6 text-base sm:text-lg max-w-2xl font-normal leading-relaxed ${
              isDark ? 'text-slate-400' : 'text-slate-600'
            }`}>
              SMBFlow coordinates intelligent multi-agent pipelines for invoice processing, inbound email triage, CRM lead enrichment, and campaign execution with verifiable state execution.
            </p>

            {/* Actions */}
            <div className="mt-8 flex flex-col sm:flex-row items-center gap-3.5 w-full sm:w-auto">
              <Link
                to="/auth/signup"
                className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-6 py-3 rounded-xl font-bold text-sm text-white bg-blue-600 hover:bg-blue-500 shadow-xs transition-all"
              >
                <span>Create Free Workspace</span>
                <ArrowRight className="w-4 h-4" />
              </Link>
              <a
                href="#workflows"
                className={`w-full sm:w-auto inline-flex items-center justify-center gap-2 px-5 py-3 rounded-xl font-semibold text-sm border transition-all ${
                  isDark
                    ? 'bg-[#121826] text-slate-200 border-[#233048] hover:bg-[#182234]'
                    : 'bg-white text-slate-700 border-slate-200 hover:bg-slate-50 shadow-2xs'
                }`}
              >
                <Workflow className="w-4 h-4 text-blue-500" />
                <span>Explore Interactive Pipelines</span>
              </a>
            </div>

            {/* Verification Strip */}
            <div className={`mt-12 flex flex-wrap items-center justify-center gap-6 text-xs font-medium ${
              isDark ? 'text-slate-400' : 'text-slate-500'
            }`}>
              <span className="flex items-center gap-1.5"><Check className="w-4 h-4 text-emerald-500" /> Deterministic DAG Execution</span>
              <span className="flex items-center gap-1.5"><Check className="w-4 h-4 text-emerald-500" /> Human Approval Gates</span>
              <span className="flex items-center gap-1.5"><Check className="w-4 h-4 text-emerald-500" /> Multi-Tenant Isolation</span>
            </div>
          </div>
        </section>

        {/* ── Interactive Live Workflow Canvas (Real Graph Engine) ─────────── */}
        <section className="py-20 px-4 sm:px-6 lg:px-8 max-w-7xl mx-auto" id="workflows">
          <div className="mb-10 text-center max-w-2xl mx-auto">
            <h2 className={`text-2xl sm:text-3xl font-bold tracking-tight ${isDark ? 'text-white' : 'text-slate-950'}`}>
              Production Pipelines Built In
            </h2>
            <p className={`mt-2 text-xs sm:text-sm ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
              Select a workflow below to inspect live execution nodes, inputs, and synthesized data schemas.
            </p>
          </div>

          {/* Workflow Selector Tabs */}
          <div className="flex flex-wrap items-center justify-center gap-2 mb-8">
            {LANDING_WORKFLOWS.map((wf) => {
              const isSelected = activeWorkflowId === wf.id
              return (
                <button
                  key={wf.id}
                  onClick={() => handleSelectWorkflow(wf.id)}
                  className={`px-4 py-2 rounded-xl text-xs font-semibold flex items-center gap-2 border transition-all cursor-pointer ${
                    isSelected
                      ? 'bg-blue-600 border-blue-600 text-white shadow-xs'
                      : isDark
                        ? 'bg-[#121826] border-[#233048] text-slate-300 hover:bg-[#182234]'
                        : 'bg-white border-slate-200 text-slate-700 hover:bg-slate-50 shadow-2xs'
                  }`}
                >
                  <ToolLogo name={wf.nodes[0]?.tool} className="w-3.5 h-3.5" />
                  <span>{wf.name}</span>
                </button>
              )
            })}
          </div>

          {/* Interactive Canvas Graph Card */}
          <div className={`rounded-2xl border shadow-md overflow-hidden transition-colors ${
            isDark ? 'bg-[#121826] border-[#233048]' : 'bg-white border-slate-200'
          }`}>
            {/* Canvas Header */}
            <div className={`px-6 py-4 border-b flex flex-wrap items-center justify-between gap-4 ${
              isDark ? 'bg-[#0b0f17]/80 border-[#233048]' : 'bg-slate-50/70 border-slate-200'
            }`}>
              <div>
                <div className="flex items-center gap-2">
                  <span className={`font-bold text-sm ${isDark ? 'text-white' : 'text-slate-900'}`}>
                    {currentWorkflow.name}
                  </span>
                  <span className={`text-[10px] px-2 py-0.5 rounded-full font-mono font-semibold border ${
                    isDark ? 'bg-[#182234] text-blue-300 border-[#233048]' : 'bg-blue-50 text-blue-700 border-blue-200'
                  }`}>
                    {currentWorkflow.category}
                  </span>
                </div>
                <p className={`text-xs mt-1 max-w-2xl ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
                  {currentWorkflow.description}
                </p>
              </div>

              <Link
                to="/auth/signup"
                className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-bold text-white bg-blue-600 hover:bg-blue-500 shadow-xs transition-colors"
              >
                <span>Deploy Workflow</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </Link>
            </div>

            {/* Live SVG Graph Canvas */}
            <div className="p-6 md:p-8 bg-slate-50/40 dark:bg-[#0b0f17]/40 overflow-x-auto">
              <div className="min-w-[760px] pb-4">
                <svg className="w-full h-[180px] overflow-visible">
                  {/* Connectors */}
                  {currentWorkflow.edges.map((edge, idx) => {
                    const fromNode = currentWorkflow.nodes.find(n => n.id === edge.from)
                    const toNode = currentWorkflow.nodes.find(n => n.id === edge.to)
                    if (!fromNode || !toNode) return null

                    const startX = fromNode.x + 150
                    const startY = fromNode.y + 26
                    const endX = toNode.x
                    const endY = toNode.y + 26
                    const midX = (startX + endX) / 2
                    const pathData = `M ${startX} ${startY} C ${midX} ${startY}, ${midX} ${endY}, ${endX} ${endY}`

                    return (
                      <g key={idx}>
                        <path d={pathData} fill="none" stroke="#3b82f6" strokeWidth="3" strokeOpacity="0.2" />
                        <path d={pathData} fill="none" stroke="#64748b" strokeWidth="2" strokeDasharray="4 2" />
                        <circle r="3" fill="#3b82f6">
                          <animateMotion path={pathData} dur="2.8s" repeatCount="indefinite" />
                        </circle>
                        {edge.label && (
                          <text x={midX} y={(startY + endY) / 2 - 6} fill="#64748b" fontSize="9" fontFamily="monospace" textAnchor="middle">
                            {edge.label}
                          </text>
                        )}
                      </g>
                    )
                  })}

                  {/* Render Node Rectangles */}
                  {currentWorkflow.nodes.map((node) => {
                    const isSelected = selectedNode?.id === node.id

                    return (
                      <g
                        key={node.id}
                        transform={`translate(${node.x}, ${node.y})`}
                        onClick={() => setSelectedNode(node)}
                        className="cursor-pointer group"
                      >
                        <rect
                          width="150"
                          height="52"
                          rx="10"
                          fill={isDark ? '#121826' : '#ffffff'}
                          stroke={isSelected ? '#3b82f6' : isDark ? '#233048' : '#e2e8f0'}
                          strokeWidth={isSelected ? '2' : '1'}
                          className="transition-all drop-shadow-xs group-hover:stroke-blue-400"
                        />
                        <foreignObject x="8" y="8" width="134" height="36">
                          <div className="flex items-center gap-2 h-full">
                            <div className="w-6 h-6 rounded-md bg-slate-100 dark:bg-[#182234] border border-slate-200 dark:border-[#233048] flex items-center justify-center shrink-0">
                              <ToolLogo name={node.tool} className="w-3.5 h-3.5" />
                            </div>
                            <div className="min-w-0">
                              <p className={`text-[11px] font-bold truncate leading-tight ${isDark ? 'text-white' : 'text-slate-900'}`}>
                                {node.title}
                              </p>
                              <span className="text-[9px] text-slate-500 dark:text-slate-400 truncate block">
                                {node.subtitle}
                              </span>
                            </div>
                          </div>
                        </foreignObject>
                      </g>
                    )
                  })}
                </svg>
              </div>

              {/* Node Payload Inspector Drawer */}
              {selectedNode && (
                <div className={`mt-4 p-4 rounded-xl border text-xs transition-colors ${
                  isDark ? 'bg-[#0f141f] border-[#233048]' : 'bg-white border-slate-200 shadow-2xs'
                }`}>
                  <div className="flex items-center justify-between pb-3 border-b border-slate-100 dark:border-[#1a2336] mb-3">
                    <div className="flex items-center gap-2">
                      <ToolLogo name={selectedNode.tool} className="w-4 h-4" />
                      <span className={`font-bold ${isDark ? 'text-white' : 'text-slate-900'}`}>
                        {selectedNode.title}
                      </span>
                      <span className={`text-[10px] font-mono px-2 py-0.5 rounded border ${
                        selectedNode.type === 'HITL Review'
                          ? 'bg-amber-50 dark:bg-amber-950/60 text-amber-700 dark:text-amber-300 border-amber-300 dark:border-amber-800'
                          : 'bg-slate-100 dark:bg-[#182234] text-slate-600 dark:text-slate-300 border-slate-200 dark:border-[#233048]'
                      }`}>
                        {selectedNode.type}
                      </span>
                    </div>
                    <span className="text-[10px] text-emerald-600 dark:text-emerald-400 font-mono font-semibold">
                      State: Verified
                    </span>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    <div className="p-3 bg-slate-50 dark:bg-[#121826] rounded-xl border border-slate-200 dark:border-[#233048]">
                      <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 block mb-1">
                        Node Configuration & Input
                      </span>
                      <pre className="text-[10px] font-mono text-slate-700 dark:text-slate-300 overflow-x-auto leading-relaxed">
                        {JSON.stringify(selectedNode.sampleInput, null, 2)}
                      </pre>
                    </div>

                    <div className="p-3 bg-slate-50 dark:bg-[#121826] rounded-xl border border-slate-200 dark:border-[#233048]">
                      <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 block mb-1">
                        Synthesized Output Stream
                      </span>
                      <pre className="text-[10px] font-mono text-emerald-600 dark:text-emerald-400 overflow-x-auto leading-relaxed">
                        {JSON.stringify(selectedNode.sampleOutput, null, 2)}
                      </pre>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>
        </section>

        {/* ── Core Architectural Pillars ───────────────────────────────────── */}
        <section className={`py-20 border-t transition-colors ${
          isDark ? 'bg-[#080b11] border-[#233048]' : 'bg-slate-50/80 border-slate-200'
        }`} id="architecture">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="text-center max-w-2xl mx-auto mb-14">
              <h2 className={`text-2xl sm:text-3xl font-bold tracking-tight ${isDark ? 'text-white' : 'text-slate-950'}`}>
                Engineered for Enterprise Reliability
              </h2>
              <p className={`mt-2 text-xs sm:text-sm ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
                Designed specifically for SMB teams requiring verifiable state machines and security governance.
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              {/* Card 1 */}
              <div className={`p-6 rounded-2xl border transition-all shadow-2xs ${
                isDark ? 'bg-[#121826] border-[#233048]' : 'bg-white border-slate-200'
              }`}>
                <div className="w-10 h-10 rounded-xl bg-blue-50 dark:bg-blue-950/60 text-blue-600 dark:text-blue-400 border border-blue-200 dark:border-blue-800 flex items-center justify-center mb-4">
                  <Cpu className="w-5 h-5" />
                </div>
                <h3 className={`font-bold text-base ${isDark ? 'text-white' : 'text-slate-900'}`}>
                  Multi-LLM Router
                </h3>
                <p className={`text-xs mt-2 leading-relaxed ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
                  Route tasks to optimal foundation models: Claude 3.5 Sonnet for reasoning, GPT-4o for complex JSON synthesis, and Groq/Llama for high-throughput classification.
                </p>
              </div>

              {/* Card 2 */}
              <div className={`p-6 rounded-2xl border transition-all shadow-2xs ${
                isDark ? 'bg-[#121826] border-[#233048]' : 'bg-white border-slate-200'
              }`}>
                <div className="w-10 h-10 rounded-xl bg-amber-50 dark:bg-amber-950/60 text-amber-600 dark:text-amber-400 border border-amber-200 dark:border-amber-800 flex items-center justify-center mb-4">
                  <UserCheck className="w-5 h-5" />
                </div>
                <h3 className={`font-bold text-base ${isDark ? 'text-white' : 'text-slate-900'}`}>
                  Action Center Approvals
                </h3>
                <p className={`text-xs mt-2 leading-relaxed ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
                  Set confidence thresholds. Any financial transactions, customer-facing emails, or booking requests pause safely for 1-click human verification before API commits.
                </p>
              </div>

              {/* Card 3 */}
              <div className={`p-6 rounded-2xl border transition-all shadow-2xs ${
                isDark ? 'bg-[#121826] border-[#233048]' : 'bg-white border-slate-200'
              }`}>
                <div className="w-10 h-10 rounded-xl bg-emerald-50 dark:bg-emerald-950/60 text-emerald-600 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-800 flex items-center justify-center mb-4">
                  <KeyRound className="w-5 h-5" />
                </div>
                <h3 className={`font-bold text-base ${isDark ? 'text-white' : 'text-slate-900'}`}>
                  Encrypted Key Vault
                </h3>
                <p className={`text-xs mt-2 leading-relaxed ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
                  Store OpenAI, Anthropic, Google, and SaaS integration credentials with AES-256 fernet encryption. API keys are masked in the UI and never exposed in logs.
                </p>
              </div>
            </div>
          </div>
        </section>

        {/* ── Integrations Section (Real Tool Logos) ───────────────────────── */}
        <section className={`py-16 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 border-b ${
          isDark ? 'border-[#233048]' : 'border-slate-200'
        }`} id="integrations">
          <div className="text-center max-w-2xl mx-auto mb-10">
            <h2 className={`text-xl sm:text-2xl font-bold tracking-tight ${isDark ? 'text-white' : 'text-slate-900'}`}>
              Connects with Your Operational Stack
            </h2>
            <p className={`text-xs mt-1.5 ${isDark ? 'text-slate-400' : 'text-slate-500'}`}>
              Native API connectors and event listeners for core business platforms.
            </p>
          </div>

          <div className="flex flex-wrap items-center justify-center gap-3">
            {INTEGRATION_TOOLS.map((tool) => (
              <div
                key={tool.id}
                className={`px-4 py-2.5 rounded-xl border text-xs font-semibold flex items-center gap-2.5 transition-all shadow-2xs ${
                  isDark
                    ? 'bg-[#121826] border-[#233048] text-slate-200 hover:border-slate-600'
                    : 'bg-white border-slate-200 text-slate-800 hover:border-slate-300'
                }`}
              >
                <div className="w-5 h-5 rounded flex items-center justify-center shrink-0">
                  <ToolLogo name={tool.id} className="w-4 h-4" />
                </div>
                <span>{tool.name}</span>
              </div>
            ))}
          </div>
        </section>

        {/* ── Transparent Pricing ─────────────────────────────────────────── */}
        <section className="py-20 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8" id="pricing">
          <div className="text-center max-w-2xl mx-auto mb-12">
            <h2 className={`text-2xl sm:text-3xl font-bold tracking-tight ${isDark ? 'text-white' : 'text-slate-950'}`}>
              Simple, Predictable Plans
            </h2>
            <p className={`text-xs sm:text-sm mt-2 ${isDark ? 'text-slate-400' : 'text-slate-600'}`}>
              Get started for free or scale your workflow capacity as operations expand.
            </p>

            <div className={`mt-6 inline-flex items-center gap-2 p-1 rounded-xl border ${
              isDark ? 'bg-[#121826] border-[#233048]' : 'bg-slate-100 border-slate-200'
            }`}>
              <button
                onClick={() => setBillingCycle('monthly')}
                className={`px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-all cursor-pointer ${
                  billingCycle === 'monthly'
                    ? isDark ? 'bg-[#182234] text-white shadow-xs' : 'bg-white text-slate-900 shadow-xs'
                    : isDark ? 'text-slate-400' : 'text-slate-600'
                }`}
              >
                Monthly
              </button>
              <button
                onClick={() => setBillingCycle('annual')}
                className={`px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-all cursor-pointer ${
                  billingCycle === 'annual'
                    ? isDark ? 'bg-[#182234] text-white shadow-xs' : 'bg-white text-slate-900 shadow-xs'
                    : isDark ? 'text-slate-400' : 'text-slate-600'
                }`}
              >
                Annual (20% off)
              </button>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 max-w-5xl mx-auto">
            {/* Free */}
            <div className={`p-6 rounded-2xl border flex flex-col justify-between shadow-2xs ${
              isDark ? 'bg-[#121826] border-[#233048]' : 'bg-white border-slate-200'
            }`}>
              <div>
                <span className="text-xs font-bold uppercase tracking-wider text-slate-400 font-mono">Free Tier</span>
                <div className="mt-3 flex items-baseline gap-1">
                  <span className={`text-3xl font-bold ${isDark ? 'text-white' : 'text-slate-950'}`}>$0</span>
                  <span className="text-xs text-slate-500">/ month</span>
                </div>
                <p className="text-xs text-slate-500 mt-2">Explore multi-agent workflows with pre-built templates.</p>

                <ul className="mt-6 space-y-2.5 text-xs text-slate-600 dark:text-slate-300">
                  <li className="flex items-center gap-2"><Check className="w-3.5 h-3.5 text-emerald-500" /> 1 Team Seat</li>
                  <li className="flex items-center gap-2"><Check className="w-3.5 h-3.5 text-emerald-500" /> 2 Active Workflows</li>
                  <li className="flex items-center gap-2"><Check className="w-3.5 h-3.5 text-emerald-500" /> Standard Email & Webhook Connectors</li>
                  <li className="flex items-center gap-2"><Check className="w-3.5 h-3.5 text-emerald-500" /> Action Center Approvals</li>
                </ul>
              </div>

              <div className="mt-6 pt-4 border-t border-slate-100 dark:border-[#182234]">
                <Link
                  to="/auth/signup"
                  className={`w-full inline-flex items-center justify-center py-2 rounded-xl border text-xs font-semibold ${
                    isDark ? 'border-[#233048] text-white hover:bg-[#182234]' : 'border-slate-300 text-slate-800 hover:bg-slate-50'
                  }`}
                >
                  Start Free
                </Link>
              </div>
            </div>

            {/* Starter */}
            <div className={`p-6 rounded-2xl border-2 flex flex-col justify-between relative shadow-md ${
              isDark ? 'bg-[#121826] border-blue-500' : 'bg-white border-blue-600'
            }`}>
              <div className="absolute -top-3 left-1/2 -translate-x-1/2 text-[10px] font-bold px-2.5 py-0.5 rounded-full uppercase tracking-wider text-white bg-blue-600 font-mono">
                Recommended
              </div>
              <div>
                <span className="text-xs font-bold uppercase tracking-wider text-blue-600 dark:text-blue-400 font-mono">
                  Starter Plan
                </span>
                <div className="mt-3 flex items-baseline gap-1">
                  <span className={`text-3xl font-bold ${isDark ? 'text-white' : 'text-slate-950'}`}>
                    {billingCycle === 'monthly' ? '$49' : '$39'}
                  </span>
                  <span className="text-xs text-slate-500">/ month</span>
                </div>
                <p className="text-xs text-slate-500 mt-2">For growing businesses automating day-to-day operations.</p>

                <ul className="mt-6 space-y-2.5 text-xs text-slate-600 dark:text-slate-300">
                  <li className="flex items-center gap-2"><Check className="w-3.5 h-3.5 text-emerald-500" /> 5 Team Seats</li>
                  <li className="flex items-center gap-2"><Check className="w-3.5 h-3.5 text-emerald-500" /> Unlimited Active Workflows</li>
                  <li className="flex items-center gap-2"><Check className="w-3.5 h-3.5 text-emerald-500" /> Multi-Model Routing (Claude + GPT)</li>
                  <li className="flex items-center gap-2"><Check className="w-3.5 h-3.5 text-emerald-500" /> Automated Cron Scheduling</li>
                  <li className="flex items-center gap-2"><Check className="w-3.5 h-3.5 text-emerald-500" /> Encrypted Key Vault Access</li>
                </ul>
              </div>

              <div className="mt-6 pt-4 border-t border-slate-100 dark:border-[#182234]">
                <Link
                  to="/auth/signup"
                  className="w-full inline-flex items-center justify-center py-2.5 rounded-xl text-xs font-bold text-white bg-blue-600 hover:bg-blue-500 shadow-xs"
                >
                  Start 14-Day Free Trial
                </Link>
              </div>
            </div>

            {/* Enterprise */}
            <div className={`p-6 rounded-2xl border flex flex-col justify-between shadow-2xs ${
              isDark ? 'bg-[#121826] border-[#233048]' : 'bg-white border-slate-200'
            }`}>
              <div>
                <span className="text-xs font-bold uppercase tracking-wider text-slate-400 font-mono">Enterprise</span>
                <div className="mt-3 flex items-baseline gap-1">
                  <span className={`text-3xl font-bold ${isDark ? 'text-white' : 'text-slate-950'}`}>Custom</span>
                </div>
                <p className="text-xs text-slate-500 mt-2">For teams requiring dedicated VPCs, custom ERPs, and SLAs.</p>

                <ul className="mt-6 space-y-2.5 text-xs text-slate-600 dark:text-slate-300">
                  <li className="flex items-center gap-2"><Check className="w-3.5 h-3.5 text-emerald-500" /> Unlimited Seats & Workflows</li>
                  <li className="flex items-center gap-2"><Check className="w-3.5 h-3.5 text-emerald-500" /> Custom NetSuite / ERP Integrations</li>
                  <li className="flex items-center gap-2"><Check className="w-3.5 h-3.5 text-emerald-500" /> Single-Tenant Isolation & Audit Vault</li>
                  <li className="flex items-center gap-2"><Check className="w-3.5 h-3.5 text-emerald-500" /> 99.99% Uptime Guarantee & Support</li>
                </ul>
              </div>

              <div className="mt-6 pt-4 border-t border-slate-100 dark:border-[#182234]">
                <a
                  href="#faq"
                  className={`w-full inline-flex items-center justify-center py-2 rounded-xl border text-xs font-semibold ${
                    isDark ? 'border-[#233048] text-white hover:bg-[#182234]' : 'border-slate-300 text-slate-800 hover:bg-slate-50'
                  }`}
                >
                  Contact Sales
                </a>
              </div>
            </div>
          </div>
        </section>

        {/* ── FAQ ──────────────────────────────────────────────────────────── */}
        <section className={`py-20 border-t transition-colors ${
          isDark ? 'bg-[#080b11] border-[#233048]' : 'bg-slate-50/80 border-slate-200'
        }`} id="faq">
          <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="text-center mb-10">
              <h2 className={`text-2xl font-bold tracking-tight ${isDark ? 'text-white' : 'text-slate-950'}`}>
                Frequently Asked Questions
              </h2>
            </div>

            <div className="space-y-3">
              {faqs.map((faq, idx) => {
                const isOpen = openFaqIndex === idx
                return (
                  <div key={idx} className={`rounded-xl border overflow-hidden transition-colors shadow-2xs ${
                    isDark ? 'bg-[#121826] border-[#233048]' : 'bg-white border-slate-200'
                  }`}>
                    <button
                      onClick={() => setOpenFaqIndex(isOpen ? null : idx)}
                      className={`w-full p-4 text-left flex items-center justify-between font-semibold text-sm cursor-pointer ${
                        isDark ? 'text-white' : 'text-slate-900'
                      }`}
                    >
                      <span>{faq.q}</span>
                      <ChevronDown className={`w-4 h-4 transition-transform duration-200 ${
                        isOpen ? 'rotate-180' : ''
                      } ${isDark ? 'text-slate-400' : 'text-slate-500'}`} />
                    </button>
                    {isOpen && (
                      <div className={`px-4 pb-4 text-xs leading-relaxed border-t border-slate-100 dark:border-[#182234] pt-3 ${
                        isDark ? 'text-slate-400' : 'text-slate-600'
                      }`}>
                        {faq.a}
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          </div>
        </section>

        {/* ── Closing CTA ──────────────────────────────────────────────────── */}
        <section className="py-16 max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
          <div className={`rounded-2xl p-8 sm:p-12 border shadow-lg ${
            isDark
              ? 'bg-[#121826] border-[#233048] text-white'
              : 'bg-slate-950 border-slate-900 text-white'
          }`}>
            <h2 className="text-2xl sm:text-3xl font-bold tracking-tight">
              Automate your business operations with precision.
            </h2>
            <p className="text-xs sm:text-sm text-slate-300 mt-2 max-w-md mx-auto">
              Create your workspace in seconds. Connect your providers and run your first autonomous agentic workflow.
            </p>

            <form onSubmit={handleCtaSubmit} className="mt-6 flex flex-col sm:flex-row items-center justify-center gap-2 max-w-sm mx-auto">
              <input
                type="email"
                value={ctaEmail}
                onChange={(e) => setCtaEmail(e.target.value)}
                placeholder="Enter work email"
                required
                className="w-full px-3.5 py-2.5 rounded-xl bg-white/10 border border-white/20 text-white placeholder:text-slate-400 text-xs focus:outline-hidden focus:ring-1 focus:ring-blue-500"
              />
              <button
                type="submit"
                className="w-full sm:w-auto px-5 py-2.5 rounded-xl bg-blue-600 hover:bg-blue-500 text-white font-bold text-xs whitespace-nowrap transition-all cursor-pointer"
              >
                Get Started
              </button>
            </form>
          </div>
        </section>
      </main>

      {/* ── Footer ───────────────────────────────────────────────────────── */}
      <footer className={`border-t py-12 transition-colors ${
        isDark ? 'bg-[#080b11] border-[#233048] text-slate-400' : 'bg-white border-slate-200 text-slate-500'
      }`}>
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col sm:flex-row items-center justify-between gap-4 text-xs">
          <div className="flex items-center gap-2">
            <div className="w-5 h-5 rounded bg-blue-600 flex items-center justify-center text-white">
              <BrainCircuit className="w-3 h-3" />
            </div>
            <span className="font-semibold text-slate-700 dark:text-slate-200">SMBFlow</span>
            <span>— Autonomous Multi-Tenant Workflow Engine</span>
          </div>
          <p>© 2026 SMBFlow. All rights reserved.</p>
        </div>
      </footer>
    </div>
  )
}
