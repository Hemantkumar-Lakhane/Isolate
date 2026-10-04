// frontend/src/pages/client/ProductLaunchPage.jsx
// ─────────────────────────────────────────────────────────────────────────────
// SMBFlow — Dynamic Active Pipeline Canvas & Conversational Workflow Runner
// Features:
//   • Live Interactive SVG Node Canvas (n8n-style) with animated bezier pulse wires
//   • Switchable Active Pipelines: Product Launch, Process Invoices, Email Triage
//   • Real-Time Interactive Parameter Ingestion Agent (asks questions step-by-step)
//   • Integration Connection Status Check & Connect Modal
//   • Live Node Schema & Payload Inspector Drawer
//   • Clean, cost-optimized text outputs without raw markdown artifacts or emojis
//   • Dual-theme dot grid canvas background (#0b0f17 obsidian & slate light)
// ─────────────────────────────────────────────────────────────────────────────

import React, { useState, useEffect, useRef, useMemo } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useAuth } from '../../contexts/AuthContext'
import {
  Send, Bot, Play, CheckCircle2, RefreshCw, Copy, Check,
  X, Plus, Paperclip, FileText, ArrowRight, ArrowLeft,
  Calendar, Clock, Download, Share2, Layers, Terminal,
  ExternalLink, Mic, Square, ArrowUp, Edit3, Shield, Sliders,
  ZoomIn, ZoomOut, Maximize2, Minimize2, Sparkles, ChevronRight,
  Eye, CheckCircle, AlertCircle, MessageSquare, Link2, CheckSquare
} from 'lucide-react'

// ── Tool Logo Loader with Vector Fallback ────────────────────────────────────
function ToolLogo({ name, className = 'w-4 h-4' }) {
  const [imgSrc, setImgSrc] = useState(() => {
    if (!name) return null
    if (name === 'sheets' || name === 'sheet') return '/assets/tools/sheet.png'
    return `/assets/tools/${name}.png`
  })
  const [useFallback, setUseFallback] = useState(false)

  const svgFallbacks = {
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
    sheet: (
      <svg className={className} viewBox="0 0 24 24" fill="none">
        <rect x="3" y="3" width="18" height="18" rx="3" fill="#0F9D58" fillOpacity="0.2" stroke="#0F9D58" strokeWidth="1.5" />
        <path d="M7 8H17M7 12H17M7 16H17M12 8V16" stroke="#0F9D58" strokeWidth="1.5" strokeLinecap="round" />
      </svg>
    ),
    slack: (
      <svg className={className} viewBox="0 0 24 24" fill="none">
        <rect x="3" y="3" width="18" height="18" rx="4" fill="#EC4899" fillOpacity="0.15" stroke="#EC4899" strokeWidth="1.5" />
        <path d="M8 12H16M12 8V16" stroke="#EC4899" strokeWidth="2" strokeLinecap="round" />
      </svg>
    ),
    gmail: (
      <svg className={className} viewBox="0 0 24 24" fill="none">
        <path d="M22 6C22 4.9 21.1 4 20 4H4C2.9 4 2 4.9 2 6V18C2 19.1 2.9 20 4 20H20C21.1 20 22 19.1 22 18V6Z" fill="#EA4335" fillOpacity="0.15" />
        <path d="M20 4H4C2.9 4 2 4.9 2 6L12 13L22 6C22 4.9 21.1 4 20 4Z" fill="#EA4335" />
      </svg>
    ),
    hubspot: (
      <svg className={className} viewBox="0 0 24 24" fill="none">
        <circle cx="12" cy="12" r="5" fill="#FF7A59" fillOpacity="0.2" stroke="#FF7A59" strokeWidth="1.5" />
        <path d="M12 3V7M12 17V21M3 12H7M17 12H21" stroke="#FF7A59" strokeWidth="1.5" strokeLinecap="round" />
      </svg>
    ),
  }

  function handleError() {
    setUseFallback(true)
  }

  if (!useFallback && imgSrc) {
    return (
      <img
        src={imgSrc}
        alt={name}
        className={`${className} object-contain`}
        onError={handleError}
      />
    )
  }

  return svgFallbacks[name] || <Terminal className={className} />
}

// ── Workflow Presets ─────────────────────────────────────────────────────────
const WORKFLOW_PRESETS = [
  {
    id: 'product_launch',
    title: 'Product Launch Sprint',
    description: 'Autonomous multi-platform marketing strategy, social copy, and launch calendar synthesis.',
    initialPrompt: 'Welcome to the Product Launch Sprint pipeline. What is the product or feature name you would like to launch?',
    firstQuestion: 'What is the product name?',
    nodes: [
      { id: 'p1', title: 'Brief & Spec Ingestion', subtitle: 'Dynamic Prompt & File Intake', type: 'Trigger', tool: 'gmail', latency: '18ms', input: { source: 'User Brief' }, output: { status: 'Ingested' } },
      { id: 'p2', title: 'Market & Audience Intel', subtitle: 'OpenAI GPT-4o Positioning', type: 'AI Agent', tool: 'openai', latency: '110ms', input: { task: 'Persona Matrix' }, output: { score: 0.98 } },
      { id: 'p3', title: 'Multi-Channel Copywriting', subtitle: 'Claude 3.5 Sonnet Strategy', type: 'AI LLM', tool: 'claude', latency: '280ms', input: { tone: 'Professional' }, output: { variants: 4 } },
      { id: 'p4', title: 'Visual Assets & Polls', subtitle: 'Engagement Synthesizer', type: 'Transform', tool: 'sheet', latency: '65ms', input: { formats: ['16:9', '1:1'] }, output: { polls: 2 } },
      { id: 'p5', title: 'Timeline & Multi-Channel Queue', subtitle: 'Automated Dispatcher', type: 'Integration', tool: 'slack', latency: '40ms', input: { schedule: 'Day 1-7' }, output: { queued: 4 } },
      { id: 'p6', title: 'Consensus & HITL Review Gate', subtitle: 'Action Center Safeguard', type: 'Approval', tool: 'shield', latency: '15ms', input: { riskScore: 0.01 }, output: { status: 'Approved' } },
    ],
  },
  {
    id: 'process_invoices',
    title: 'Process Invoices & PO Cross-Check',
    description: 'Scans vendor bills with OCR, matches against Google Sheets POs, flags discrepancies to Action Center.',
    initialPrompt: 'Welcome to the Invoice OCR & Reconciliation pipeline. Which vendor mailbox or account should we monitor for incoming invoices?',
    firstQuestion: 'Which vendor email address or domain should we scan?',
    nodes: [
      { id: 'i1', title: 'Inbound Mailbox Monitor', subtitle: 'Gmail Attachment Listener', type: 'Trigger', tool: 'gmail', latency: '22ms', input: { filter: 'has:pdf invoice' }, output: { count: 3 } },
      { id: 'i2', title: 'Vision OCR Extraction', subtitle: 'Claude 3.5 Sonnet Vision', type: 'AI LLM', tool: 'claude', latency: '240ms', input: { format: 'PDF' }, output: { fieldsExtracted: 8 } },
      { id: 'i3', title: 'Google Sheets PO Match', subtitle: 'Database Ledger Verification', type: 'Integration', tool: 'sheet', latency: '95ms', input: { sheet: 'Purchase_Orders_2026' }, output: { matchConfidence: 0.99 } },
      { id: 'i4', title: 'Variance & Threshold Check', subtitle: 'Audit Filter ($50 Limit)', type: 'Transform', tool: 'openai', latency: '35ms', input: { tolerance: 50.0 }, output: { varianceDetected: false } },
      { id: 'i5', title: 'Action Center Approval Gate', subtitle: 'Supervisor HITL Sign-off', type: 'Approval', tool: 'shield', latency: '12ms', input: { requireManualReview: true }, output: { queuedForReview: 1 } },
      { id: 'i6', title: 'Calendar & Payment Schedule', subtitle: 'Google Calendar Dispatch', type: 'Integration', tool: 'slack', latency: '50ms', input: { paymentDate: 'Net-30' }, output: { calendarEventCreated: true } },
    ],
  },
  {
    id: 'email_triage',
    title: 'AI Email Inbox Triage',
    description: 'Scans Gmail unread threads, categorizes urgency with LLM, drafts replies, and notifies Slack.',
    initialPrompt: 'Welcome to the Email Inbox Triage pipeline. What is your primary support or operations mailbox?',
    firstQuestion: 'What is your team mailbox address?',
    nodes: [
      { id: 'e1', title: 'Gmail Unread Poller', subtitle: 'Cron Schedule (0 8 * * 1-5)', type: 'Trigger', tool: 'gmail', latency: '20ms', input: { query: 'is:unread' }, output: { unreadFound: 5 } },
      { id: 'e2', title: 'Intent & Urgency Classification', subtitle: 'Claude 3.5 Sonnet Classifier', type: 'AI LLM', tool: 'claude', latency: '190ms', input: { scoreRange: '0-100' }, output: { urgencyScore: 88 } },
      { id: 'e3', title: 'Draft Reply Synthesizer', subtitle: 'Contextual Response Engine', type: 'AI Agent', tool: 'openai', latency: '210ms', input: { tone: 'Empathetic & Direct' }, output: { draftReady: true } },
      { id: 'e4', title: 'Action Center Review Gate', subtitle: 'Human Verification Gate', type: 'Approval', tool: 'shield', latency: '15ms', input: { holdForSignoff: true }, output: { staged: true } },
      { id: 'e5', title: 'Slack Urgent Alert Channel', subtitle: 'Real-time Webhook Push', type: 'Integration', tool: 'slack', latency: '45ms', input: { channel: '#urgent-inbox' }, output: { messageSent: true } },
    ],
  },
]

export default function ProductLaunchPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const { user, api } = useAuth()

  // Preset Selection
  const initialPresetId = searchParams.get('wf') || 'product_launch'
  const [activePreset, setActivePreset] = useState(() => {
    return WORKFLOW_PRESETS.find(p => p.id === initialPresetId) || WORKFLOW_PRESETS[0]
  })

  // Dynamic Nodes
  const [pipelineNodes, setPipelineNodes] = useState(() => activePreset.nodes.map(n => ({ ...n, status: 'idle' })))
  const [selectedNode, setSelectedNode] = useState(null)
  const [canvasZoom, setCanvasZoom] = useState(0.85)
  const [isCanvasFullscreen, setIsCanvasFullscreen] = useState(false)

  // Integration Connection State
  const [showConnectModal, setShowConnectModal] = useState(false)
  const [connectingTool, setConnectingTool] = useState('Gmail')
  const [connectedTools, setConnectedTools] = useState({ Gmail: true, GoogleSheets: true, Slack: true, HubSpot: false })

  // Launch Spec State
  const [spec, setSpec] = useState({
    name: '',
    description: '',
    targetAudience: '',
    launchDate: 'Next Wednesday',
    channels: ['LinkedIn', 'X', 'Newsletter'],
    status: 'drafting',
  })

  // Chat Conversation State
  const [messages, setMessages] = useState([
    {
      id: 'init-1',
      role: 'assistant',
      content: activePreset.initialPrompt,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    },
  ])

  const [inputText, setInputText] = useState('')
  const [loading, setLoading] = useState(false)
  const [synthesizing, setSynthesizing] = useState(false)
  const [stepIndex, setStepIndex] = useState(0)

  // File Upload State
  const [attachedFiles, setAttachedFiles] = useState([])
  const [isUploading, setIsUploading] = useState(false)
  const fileInputRef = useRef(null)

  // Voice State
  const [isListening, setIsListening] = useState(false)
  const [liveTranscript, setLiveTranscript] = useState('')
  const recognitionRef = useRef(null)
  const textareaRef = useRef(null)
  const messagesEndRef = useRef(null)

  // Generated Output State
  const [campaignData, setCampaignData] = useState(null)
  const [activeOutputTab, setActiveOutputTab] = useState('copy')
  const [copiedId, setCopiedId] = useState(null)

  // Switch Preset Handler
  function handleSwitchPreset(preset) {
    setActivePreset(preset)
    setPipelineNodes(preset.nodes.map(n => ({ ...n, status: 'idle' })))
    setSpec({ name: '', description: '', targetAudience: '', launchDate: 'Next Wednesday', channels: ['LinkedIn', 'X'], status: 'drafting' })
    setCampaignData(null)
    setStepIndex(0)
    setMessages([
      {
        id: String(Date.now()),
        role: 'assistant',
        content: preset.initialPrompt,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      },
    ])
  }

  // Auto-scroll chat
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading, synthesizing])

  // Auto-expand textarea
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
      const newHeight = Math.max(38, Math.min(textareaRef.current.scrollHeight, 180))
      textareaRef.current.style.height = `${newHeight}px`
    }
  }, [inputText])

  // Speech-to-text initialization
  useEffect(() => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition
    if (SpeechRecognition) {
      const recognizer = new SpeechRecognition()
      recognizer.continuous = true
      recognizer.interimResults = true
      recognizer.lang = 'en-US'
      recognizer.onstart = () => { setIsListening(true); setLiveTranscript('') }
      recognizer.onresult = (event) => {
        let finalStr = ''
        for (let i = event.resultIndex; i < event.results.length; i++) {
          finalStr += event.results[i][0].transcript + ' '
        }
        if (finalStr.trim()) {
          setLiveTranscript(finalStr.trim())
          setInputText(finalStr.trim())
        }
      }
      recognizer.onerror = () => setIsListening(false)
      recognizer.onend = () => setIsListening(false)
      recognitionRef.current = recognizer
    }
  }, [])

  function toggleVoiceInput() {
    if (isListening) {
      try { recognitionRef.current?.stop() } catch {}
      setIsListening(false)
    } else {
      try {
        recognitionRef.current?.start()
        setIsListening(true)
      } catch {
        setIsListening(false)
      }
    }
  }

  // File Upload
  async function handleFileUpload(e) {
    const files = Array.from(e.target.files || [])
    if (!files.length) return
    setIsUploading(true)

    try {
      for (const f of files) {
        let extractedText = ''
        if (f.type.includes('text') || f.name.endsWith('.txt') || f.name.endsWith('.md') || f.name.endsWith('.json') || f.name.endsWith('.csv')) {
          extractedText = await f.text()
        } else {
          extractedText = `Document: ${f.name} (${Math.round(f.size / 1024)} KB)`
        }

        const newFile = {
          id: String(Date.now() + Math.random()),
          name: f.name,
          size: `${Math.round(f.size / 1024)} KB`,
          rawText: extractedText.slice(0, 5000),
        }
        setAttachedFiles(prev => [...prev, newFile])

        if (!spec.name && f.name) {
          const guessed = f.name.replace(/\.[^/.]+$/, '').replace(/[-_]/g, ' ')
          setSpec(prev => ({ ...prev, name: guessed, description: extractedText.slice(0, 200) || prev.description }))
        }

        setMessages(prev => [
          ...prev,
          {
            id: String(Date.now()),
            role: 'assistant',
            content: `Ingested document: ${f.name}. What is your target timeline or trigger cadence for this pipeline?`,
            timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          },
        ])
        setStepIndex(2)
      }
    } finally {
      setIsUploading(false)
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  // Chat Submission Handler
  async function handleSend(customText = null) {
    const text = (customText !== null ? customText : inputText).trim()
    if (!text && attachedFiles.length === 0) return

    if (isListening) toggleVoiceInput()

    const userMsg = {
      id: String(Date.now()),
      role: 'user',
      content: text || `Uploaded ${attachedFiles.length} file(s)`,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    }

    setMessages(prev => [...prev, userMsg])
    setInputText('')
    setLiveTranscript('')
    setLoading(true)

    // Check if user requested direct run
    if (text.toLowerCase().includes('run active pipeline') || text.toLowerCase().includes('execute') || text.toLowerCase().includes('start now')) {
      setLoading(false)
      await executePipelineRun()
      return
    }

    setTimeout(() => {
      let nextContent = ''
      let updatedSpec = { ...spec }

      if (stepIndex === 0) {
        updatedSpec.name = text
        setSpec(updatedSpec)
        setStepIndex(1)
        nextContent = activePreset.id === 'process_invoices'
          ? `Monitoring mailbox configured: ${text}. Where is your purchase order tracking spreadsheet located?`
          : `Got it. Target product: ${text}. What is a short description of the product and who is your target audience?`
      } else if (stepIndex === 1) {
        updatedSpec.description = text
        setSpec(updatedSpec)
        setStepIndex(2)
        nextContent = activePreset.id === 'process_invoices'
          ? `Google Sheet verified. What is your invoice variance discrepancy threshold? (Default: $50.00)`
          : `Captured. When is your planned launch date? (e.g. Next Wednesday, Oct 15, In 2 Weeks)`
      } else if (stepIndex === 2) {
        updatedSpec.launchDate = text
        updatedSpec.status = 'ready'
        setSpec(updatedSpec)
        setStepIndex(3)
        nextContent = `All parameters locked for ${updatedSpec.name || 'this workflow'}. Click "Run Active Pipeline" below to execute across all connected canvas nodes.`
      } else {
        nextContent = `Parameters updated. Ready to trigger active pipeline execution.`
      }

      setLoading(false)
      setMessages(prev => [
        ...prev,
        {
          id: String(Date.now() + 1),
          role: 'assistant',
          content: nextContent,
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        },
      ])
    }, 400)
  }

  // Pipeline Execution Simulator across Canvas Nodes
  async function executePipelineRun() {
    setSynthesizing(true)
    const pName = spec.name || 'Enterprise Automation'
    const desc = spec.description || 'Autonomous workflow execution engine.'
    const lDate = spec.launchDate || 'Next Sprint'

    // Node-by-node visual execution
    for (let i = 0; i < pipelineNodes.length; i++) {
      setPipelineNodes(nodes => nodes.map((n, idx) => idx === i ? { ...n, status: 'running' } : n))
      await new Promise(r => setTimeout(r, 400 + i * 50))
      setPipelineNodes(nodes => nodes.map((n, idx) => idx === i ? { ...n, status: 'completed' } : n))
    }

    // Generated Campaign / Output Data
    const generated = {
      productName: pName,
      description: desc,
      launchDate: lDate,
      posts: [
        {
          id: 'li-1',
          platform: 'LinkedIn',
          category: 'Official Launch Announcement',
          scheduledTime: `Day 1 (${lDate}) · 09:00 AM`,
          caption: `We are officially announcing ${pName} — ${desc}.\n\nBuilt to eliminate manual coordination and streamline team execution with zero setup overhead.\n\nLearn more: https://${pName.toLowerCase().replace(/[^a-z0-9]/g, '')}.io`,
          hashtags: ['#ProductLaunch', '#Operations', '#EnterpriseAI'],
        },
        {
          id: 'x-1',
          platform: 'X / Twitter',
          category: 'Launch Day Hook & Thread',
          scheduledTime: `Day 1 (${lDate}) · 09:15 AM`,
          caption: `Why is team execution still fragmented across browser tabs?\n\nIntroducing ${pName} — ${desc}.\n\nTry it free: https://${pName.toLowerCase().replace(/[^a-z0-9]/g, '')}.io`,
          hashtags: ['#BuildInPublic', '#Productivity'],
        },
        {
          id: 'email-1',
          platform: 'Newsletter / Email',
          category: 'Subscriber VIP Announcement',
          scheduledTime: 'Day 2 · 10:00 AM',
          caption: `Subject: Introducing ${pName} — a smarter way to run operations.\n\nHey team,\n\nWe are thrilled to unveil ${pName}. If you have been struggling with fragmented workflows, this was built specifically for you.`,
          hashtags: ['#VIPAnnouncement'],
        },
      ],
      visualPolls: [
        {
          id: 'poll-1',
          title: 'Launch Engagement Benchmark',
          question: 'What is the biggest operational bottleneck in your team today?',
          options: ['Fragmented tools & manual sync', 'Missed task deadlines', 'Lack of real-time visibility', 'Too many alignment meetings'],
          votesTotal: '1,420 votes target',
        },
      ],
      scheduleQueue: [
        { id: 's-1', date: lDate, time: '09:00 AM', platform: 'LinkedIn', status: 'Scheduled' },
        { id: 's-2', date: lDate, time: '09:15 AM', platform: 'X / Twitter', status: 'Scheduled' },
        { id: 's-3', date: 'Day 2', time: '10:00 AM', platform: 'Newsletter', status: 'Scheduled' },
      ],
    }

    setCampaignData(generated)
    setSpec(prev => ({ ...prev, status: 'completed' }))
    setSynthesizing(false)

    setMessages(prev => [
      ...prev,
      {
        id: String(Date.now() + 2),
        role: 'assistant',
        content: `Active Pipeline execution completed successfully for ${pName}. All nodes executed in 1.48s with 0 errors. You can inspect the generated deliverables deck below.`,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      },
    ])
  }

  function handleCopyText(id, text) {
    navigator.clipboard.writeText(text)
    setCopiedId(id)
    setTimeout(() => setCopiedId(null), 2500)
  }

  return (
    <div className="min-h-full bg-slate-50 dark:bg-[#0b0f17] bg-dot-pattern text-slate-900 dark:text-slate-100 pb-16 font-sans relative transition-colors flex flex-col">
      {/* ── Top Bar ──────────────────────────────────────────────────────────── */}
      <div className="px-6 py-3.5 border-b border-slate-200 dark:border-[#233048] bg-white/95 dark:bg-[#121826]/95 backdrop-blur-xs flex items-center justify-between shrink-0 sticky top-0 z-20 transition-colors">
        <div className="flex items-center gap-3">
          <button
            onClick={() => navigate('/workflows')}
            className="p-1.5 rounded-lg bg-slate-100 dark:bg-[#182234] hover:bg-slate-200 dark:hover:bg-[#233048] text-slate-700 dark:text-slate-300 transition-colors cursor-pointer"
            title="Back to Workflows"
          >
            <ArrowLeft className="w-4 h-4" />
          </button>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-sm font-bold text-slate-900 dark:text-white tracking-tight flex items-center gap-1.5">
                <Layers className="w-4 h-4 text-blue-500" />
                <span>Active Pipeline: {activePreset.title}</span>
              </span>
              <span className={`text-[10px] uppercase font-bold px-2 py-0.5 rounded-full font-mono border ${
                campaignData
                  ? 'bg-emerald-50 dark:bg-emerald-950/60 text-emerald-700 dark:text-emerald-300 border-emerald-200 dark:border-emerald-800'
                  : 'bg-blue-50 dark:bg-blue-950/60 text-blue-700 dark:text-blue-300 border-blue-200 dark:border-blue-800/60'
              }`}>
                {campaignData ? 'Executed' : 'Live Canvas & Agent'}
              </span>
            </div>
            <p className="text-[11px] text-slate-400 hidden sm:block">
              {activePreset.description}
            </p>
          </div>
        </div>

        {/* Preset Selector Dropdown & Connect Integration */}
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1 bg-slate-100 dark:bg-[#182234] p-1 rounded-xl border border-slate-200 dark:border-[#233048]">
            {WORKFLOW_PRESETS.map((p) => (
              <button
                key={p.id}
                onClick={() => handleSwitchPreset(p)}
                className={`px-2.5 py-1 rounded-lg text-xs font-semibold transition-colors cursor-pointer ${
                  activePreset.id === p.id
                    ? 'bg-white dark:bg-[#121826] text-blue-600 dark:text-blue-400 shadow-2xs'
                    : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white'
                }`}
              >
                {p.id === 'product_launch' ? 'Product Launch' : p.id === 'process_invoices' ? 'Invoices' : 'Email Triage'}
              </button>
            ))}
          </div>

          <button
            onClick={() => { setShowConnectModal(true); setConnectingTool('Gmail') }}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-100 dark:bg-[#182234] hover:bg-slate-200 dark:hover:bg-[#233048] text-slate-700 dark:text-slate-200 text-xs font-semibold rounded-xl transition-colors cursor-pointer border border-slate-200 dark:border-[#233048]"
          >
            <Link2 className="w-3.5 h-3.5 text-blue-500" />
            <span>Connect Tool</span>
          </button>
        </div>
      </div>

      {/* ── Section 1: n8n-Style Interactive Workflow Canvas ─────────────────── */}
      <div className="max-w-7xl mx-auto w-full px-4 md:px-6 pt-5">
        <div className={`bg-white dark:bg-[#121826] border border-slate-200 dark:border-[#233048] rounded-2xl shadow-2xs overflow-hidden transition-all relative ${
          isCanvasFullscreen ? 'fixed inset-4 z-50 flex flex-col' : ''
        }`}>
          {/* Canvas Toolbar */}
          <div className="px-4 py-2.5 border-b border-slate-200 dark:border-[#233048] bg-slate-50/80 dark:bg-[#0b0f17]/70 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="text-xs font-bold uppercase tracking-wider text-slate-800 dark:text-slate-200">
                Workflow Topology
              </span>
              <span className="text-[11px] text-slate-400 font-mono">
                ({pipelineNodes.length} Connected Nodes)
              </span>
            </div>

            <div className="flex items-center gap-1.5">
              <button
                onClick={() => setCanvasZoom(z => Math.max(0.6, z - 0.1))}
                className="p-1 rounded bg-white dark:bg-[#182234] border border-slate-200 dark:border-[#233048] text-slate-600 dark:text-slate-300 hover:text-blue-500 cursor-pointer text-xs"
                title="Zoom Out"
              >
                <ZoomOut className="w-3.5 h-3.5" />
              </button>
              <span className="text-[10px] font-mono text-slate-400 px-1">{Math.round(canvasZoom * 100)}%</span>
              <button
                onClick={() => setCanvasZoom(z => Math.min(1.2, z + 0.1))}
                className="p-1 rounded bg-white dark:bg-[#182234] border border-slate-200 dark:border-[#233048] text-slate-600 dark:text-slate-300 hover:text-blue-500 cursor-pointer text-xs"
                title="Zoom In"
              >
                <ZoomIn className="w-3.5 h-3.5" />
              </button>
              <button
                onClick={() => setCanvasZoom(0.85)}
                className="px-1.5 py-1 rounded bg-white dark:bg-[#182234] border border-slate-200 dark:border-[#233048] text-[10px] font-mono text-slate-600 dark:text-slate-300 hover:text-blue-500 cursor-pointer"
                title="Fit Canvas"
              >
                Fit
              </button>
              <button
                onClick={() => setIsCanvasFullscreen(f => !f)}
                className="p-1 rounded bg-white dark:bg-[#182234] border border-slate-200 dark:border-[#233048] text-slate-600 dark:text-slate-300 hover:text-blue-500 cursor-pointer text-xs ml-1"
                title={isCanvasFullscreen ? 'Exit Fullscreen' : 'Fullscreen Canvas'}
              >
                {isCanvasFullscreen ? <Minimize2 className="w-3.5 h-3.5" /> : <Maximize2 className="w-3.5 h-3.5" />}
              </button>
            </div>
          </div>

          {/* Connected SVG Node Canvas */}
          <div className="relative overflow-x-auto overflow-y-hidden bg-slate-50/50 dark:bg-[#0b0f17]/90 min-h-[220px] p-6 flex items-center">
            <div
              style={{ transform: `scale(${canvasZoom})`, transformOrigin: 'left center' }}
              className="relative transition-transform duration-150 flex items-center gap-8 min-w-[1300px]"
            >
              {/* SVG Connecting Bezier Paths */}
              <svg className="absolute inset-0 w-full h-full pointer-events-none" style={{ minWidth: '1300px', minHeight: '190px' }}>
                <defs>
                  <linearGradient id="activeWfGrad" x1="0%" y1="0%" x2="100%" y2="0%">
                    <stop offset="0%" stopColor="#3B82F6" />
                    <stop offset="100%" stopColor="#10B981" />
                  </linearGradient>
                </defs>
                {pipelineNodes.map((_, idx) => {
                  if (idx >= pipelineNodes.length - 1) return null
                  const startX = 30 + idx * 230 + 190
                  const startY = 90
                  const endX = 30 + (idx + 1) * 230
                  const endY = 90
                  const isNodeActive = pipelineNodes[idx]?.status === 'completed' || pipelineNodes[idx]?.status === 'running'
                  return (
                    <g key={idx}>
                      <path
                        d={`M ${startX} ${startY} C ${startX + 20} ${startY}, ${endX - 20} ${endY}, ${endX} ${endY}`}
                        fill="none"
                        stroke={isNodeActive ? 'url(#activeWfGrad)' : '#334155'}
                        strokeWidth="2"
                        strokeDasharray={isNodeActive ? '6 4' : 'none'}
                        className={isNodeActive ? 'animate-pulse' : 'opacity-40'}
                      />
                    </g>
                  )
                })}
              </svg>

              {/* Render Nodes */}
              {pipelineNodes.map((node) => {
                const isSelected = selectedNode?.id === node.id
                const isRunning = node.status === 'running'
                const isCompleted = node.status === 'completed'

                return (
                  <div
                    key={node.id}
                    onClick={() => setSelectedNode(node)}
                    className={`w-[190px] shrink-0 rounded-xl border transition-all cursor-pointer relative shadow-2xs select-none ${
                      isSelected
                        ? 'border-blue-500 ring-2 ring-blue-500/20 bg-white dark:bg-[#161f30]'
                        : isCompleted
                        ? 'border-emerald-500/60 bg-white dark:bg-[#121826] hover:border-emerald-400'
                        : isRunning
                        ? 'border-blue-400 bg-blue-50/20 dark:bg-blue-950/20 ring-1 ring-blue-400 animate-pulse'
                        : 'border-slate-200 dark:border-[#233048] bg-white dark:bg-[#121826] hover:border-slate-300 dark:hover:border-[#2e3e5b]'
                    }`}
                  >
                    <div className="p-3 border-b border-slate-100 dark:border-[#1a2336] flex items-center justify-between">
                      <div className="flex items-center gap-1.5">
                        <ToolLogo name={node.tool} className="w-4 h-4" />
                        <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                          {node.type}
                        </span>
                      </div>
                      <div>
                        {isRunning ? (
                          <RefreshCw className="w-3.5 h-3.5 text-blue-500 animate-spin" />
                        ) : isCompleted ? (
                          <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" />
                        ) : (
                          <span className="w-2 h-2 rounded-full bg-slate-300 dark:bg-slate-600 block" />
                        )}
                      </div>
                    </div>

                    <div className="p-3">
                      <h4 className="text-xs font-bold text-slate-900 dark:text-white truncate">
                        {node.title}
                      </h4>
                      <p className="text-[10px] text-slate-400 line-clamp-2 mt-1 leading-snug">
                        {node.subtitle}
                      </p>
                      <div className="mt-2.5 pt-2 border-t border-slate-100 dark:border-[#1a2336] flex items-center justify-between text-[9px] font-mono text-slate-400">
                        <span>Latency: {node.latency}</span>
                        <span className={isCompleted ? 'text-emerald-500 font-semibold' : ''}>
                          {isCompleted ? 'OK' : isRunning ? 'Running' : 'Idle'}
                        </span>
                      </div>
                    </div>
                  </div>
                )
              })}
            </div>
          </div>

          {/* Node Inspector Drawer */}
          {selectedNode && (
            <div className="px-5 py-3 bg-slate-50 dark:bg-[#0f1523] border-t border-slate-200 dark:border-[#233048] flex items-center justify-between gap-3 text-xs">
              <div className="flex items-center gap-3">
                <ToolLogo name={selectedNode.tool} className="w-4 h-4" />
                <div>
                  <span className="font-bold text-slate-900 dark:text-white">{selectedNode.title}</span>
                  <p className="text-[11px] text-slate-400">{selectedNode.subtitle}</p>
                </div>
              </div>
              <div className="flex items-center gap-4 text-[11px] font-mono">
                <div><span className="text-slate-400">Input:</span> <span className="text-slate-700 dark:text-slate-300">{JSON.stringify(selectedNode.input)}</span></div>
                <div><span className="text-slate-400">Output:</span> <span className="text-emerald-600 dark:text-emerald-400">{JSON.stringify(selectedNode.output)}</span></div>
                <button onClick={() => setSelectedNode(null)} className="p-1 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 cursor-pointer">
                  <X className="w-4 h-4" />
                </button>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* ── Section 2: Conversational Parameter Ingestion Agent & Deck ──────── */}
      <div className="flex-1 max-w-7xl mx-auto w-full p-4 md:p-6 grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column: AI Agent Chat (5 cols) */}
        <div className="lg:col-span-5 flex flex-col bg-white dark:bg-[#121826] border border-slate-200 dark:border-[#233048] rounded-2xl shadow-2xs overflow-hidden h-[640px] transition-colors">
          <div className="px-4 py-3 border-b border-slate-200 dark:border-[#233048] bg-slate-50/70 dark:bg-[#0b0f17]/50 flex items-center justify-between">
            <div className="flex items-center gap-2 text-xs font-bold text-slate-800 dark:text-slate-200">
              <Bot className="w-4 h-4 text-blue-500" />
              <span>Workflow Parameter Agent</span>
            </div>
            <span className="text-[10px] text-slate-400 font-mono">Real-time Ingestion</span>
          </div>

          <div className="flex-1 overflow-y-auto p-4 space-y-4">
            {messages.map((m) => {
              const isUser = m.role === 'user'
              return (
                <div key={m.id} className={`flex flex-col ${isUser ? 'items-end' : 'items-start'} max-w-full`}>
                  <div className="flex items-start gap-2 max-w-[90%]">
                    {!isUser && (
                      <div className="w-6 h-6 rounded-full bg-blue-600 text-white flex items-center justify-center shrink-0 mt-0.5 text-xs font-bold shadow-2xs">
                        <Bot className="w-3.5 h-3.5" />
                      </div>
                    )}
                    <div className={`p-3.5 rounded-2xl text-xs leading-relaxed transition-all ${
                      isUser
                        ? 'bg-blue-600 text-white rounded-tr-xs'
                        : 'bg-slate-100 dark:bg-[#182234] text-slate-800 dark:text-slate-100 rounded-tl-xs border border-slate-200 dark:border-[#233048]'
                    }`}>
                      <p className="whitespace-pre-wrap">{m.content}</p>
                    </div>
                  </div>
                  <span className="text-[9px] text-slate-400 mt-1 px-1 font-mono">{m.timestamp}</span>
                </div>
              )
            })}

            {loading && (
              <div className="flex items-center gap-2 text-xs text-slate-400 p-2">
                <RefreshCw className="w-3.5 h-3.5 animate-spin text-blue-500" />
                <span>Agent analyzing response...</span>
              </div>
            )}

            {synthesizing && (
              <div className="flex items-center gap-2 text-xs text-blue-500 p-2 animate-pulse font-mono">
                <Sparkles className="w-4 h-4 animate-spin" />
                <span>Executing active pipeline across canvas nodes...</span>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          {/* Chat Input */}
          <div className="p-3 border-t border-slate-200 dark:border-[#233048] bg-white dark:bg-[#121826]">
            <input
              type="file"
              ref={fileInputRef}
              onChange={handleFileUpload}
              multiple
              accept=".txt,.md,.pdf,.json,.csv,.doc,.docx"
              className="hidden"
            />

            {attachedFiles.length > 0 && (
              <div className="flex flex-wrap gap-1.5 mb-2">
                {attachedFiles.map((file) => (
                  <div key={file.id} className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-blue-50 dark:bg-[#182234] border border-blue-200 dark:border-blue-900/60 text-blue-700 dark:text-blue-300 text-xs">
                    <Paperclip className="w-3 h-3 text-blue-500" />
                    <span className="font-medium max-w-[140px] truncate">{file.name}</span>
                    <button type="button" onClick={() => setAttachedFiles(f => f.filter(x => x.id !== file.id))} className="p-0.5 hover:text-red-500">
                      <X className="w-3 h-3" />
                    </button>
                  </div>
                ))}
              </div>
            )}

            <div className="bg-slate-50 dark:bg-[#0b0f17] border border-slate-200 dark:border-[#233048] focus-within:border-blue-500 rounded-xl p-2 transition-all">
              <textarea
                ref={textareaRef}
                rows={1}
                value={inputText}
                onChange={(e) => setInputText(e.target.value)}
                placeholder="Type your response to the agent..."
                className="w-full bg-transparent text-xs text-slate-900 dark:text-slate-100 placeholder-slate-400 resize-none border-0 focus:border-0 outline-none ring-0 shadow-none px-1 py-1"
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault()
                    handleSend()
                  }
                }}
              />

              <div className="flex items-center justify-between pt-1 border-t border-slate-200 dark:border-[#1a2336] mt-1">
                <button
                  type="button"
                  onClick={() => fileInputRef.current?.click()}
                  disabled={isUploading}
                  className="w-6 h-6 rounded-md bg-white dark:bg-[#182234] border border-slate-200 dark:border-[#233048] hover:border-blue-400 text-slate-600 dark:text-slate-300 flex items-center justify-center transition-colors cursor-pointer"
                  title="Attach file"
                >
                  <Plus className="w-3.5 h-3.5" />
                </button>

                <div className="flex items-center gap-1.5">
                  <button
                    type="button"
                    onClick={toggleVoiceInput}
                    className={`p-1 rounded-md ${isListening ? 'text-red-500 animate-pulse' : 'text-slate-500'} hover:text-slate-900 dark:hover:text-slate-200 cursor-pointer`}
                    title="Voice input"
                  >
                    <Mic className="w-3.5 h-3.5" />
                  </button>
                  <button
                    type="button"
                    onClick={() => handleSend()}
                    disabled={(!inputText.trim() && attachedFiles.length === 0) || loading || synthesizing}
                    className="px-3 py-1 bg-blue-600 hover:bg-blue-500 disabled:opacity-40 text-white rounded-lg text-xs font-semibold flex items-center gap-1 transition-all cursor-pointer shadow-2xs"
                  >
                    <span>Send</span>
                    <Send className="w-3 h-3" />
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Right Column: Live Parameters & Output Deck (7 cols) */}
        <div className="lg:col-span-7 flex flex-col space-y-4">
          <div className="bg-white dark:bg-[#121826] border border-slate-200 dark:border-[#233048] rounded-2xl p-4 shadow-2xs transition-colors">
            <div className="flex items-center justify-between mb-3 border-b border-slate-100 dark:border-[#1a2336] pb-2.5">
              <div className="flex items-center gap-2">
                <Sliders className="w-4 h-4 text-blue-500" />
                <h3 className="text-xs font-bold uppercase tracking-wider text-slate-800 dark:text-slate-200">
                  Live Parameters
                </h3>
              </div>
              <span className={`px-2 py-0.5 rounded-full text-[10px] font-semibold border ${
                spec.name
                  ? 'bg-emerald-50 dark:bg-emerald-950/60 text-emerald-700 dark:text-emerald-300 border-emerald-200 dark:border-emerald-800'
                  : 'bg-slate-100 dark:bg-[#182234] text-slate-500 border-slate-200 dark:border-[#233048]'
              }`}>
                {spec.name ? 'Parameters Captured' : 'Awaiting Input'}
              </span>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
              <div>
                <span className="text-[10px] font-medium text-slate-400 uppercase">Target Item</span>
                <p className="font-semibold text-slate-900 dark:text-white truncate mt-0.5">{spec.name || '—'}</p>
              </div>
              <div>
                <span className="text-[10px] font-medium text-slate-400 uppercase">Context / Filter</span>
                <p className="font-semibold text-slate-900 dark:text-white truncate mt-0.5">{spec.description || '—'}</p>
              </div>
              <div>
                <span className="text-[10px] font-medium text-slate-400 uppercase">Schedule / Trigger</span>
                <p className="font-semibold text-slate-900 dark:text-white truncate mt-0.5">{spec.launchDate || '08:00 AM Daily'}</p>
              </div>
              <div>
                <span className="text-[10px] font-medium text-slate-400 uppercase">Status</span>
                <p className="font-semibold text-slate-900 dark:text-white truncate mt-0.5">{spec.status}</p>
              </div>
            </div>

            {!campaignData && (
              <div className="mt-3 pt-3 border-t border-slate-100 dark:border-[#1a2336] flex items-center justify-between">
                <span className="text-[11px] text-slate-400">
                  {spec.name ? 'Parameters captured. Click to trigger active execution.' : 'Answer the agent prompts in chat to enable run.'}
                </span>
                <button
                  type="button"
                  onClick={() => executePipelineRun()}
                  disabled={synthesizing}
                  className="flex items-center gap-1.5 px-4 py-1.5 bg-blue-600 hover:bg-blue-500 disabled:opacity-40 text-white rounded-lg text-xs font-semibold shadow-xs transition-all cursor-pointer"
                >
                  <Play className="w-3.5 h-3.5 fill-white" />
                  <span>Run Active Pipeline</span>
                </button>
              </div>
            )}
          </div>

          {/* Deliverables Deck */}
          {campaignData ? (
            <div className="bg-white dark:bg-[#121826] border border-slate-200 dark:border-[#233048] rounded-2xl p-5 shadow-2xs transition-colors flex-1 flex flex-col">
              <div className="flex items-center justify-between border-b border-slate-200 dark:border-[#233048] pb-3 mb-4">
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => setActiveOutputTab('copy')}
                    className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors cursor-pointer ${
                      activeOutputTab === 'copy' ? 'bg-blue-600 text-white' : 'bg-slate-100 dark:bg-[#182234] text-slate-600 dark:text-slate-300'
                    }`}
                  >
                    Synthesized Outputs ({campaignData.posts.length})
                  </button>
                  <button
                    onClick={() => setActiveOutputTab('schedule')}
                    className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors cursor-pointer ${
                      activeOutputTab === 'schedule' ? 'bg-blue-600 text-white' : 'bg-slate-100 dark:bg-[#182234] text-slate-600 dark:text-slate-300'
                    }`}
                  >
                    Schedule Timeline ({campaignData.scheduleQueue.length})
                  </button>
                </div>

                <button
                  onClick={() => {
                    const txt = campaignData.posts.map(p => `### ${p.platform} (${p.category})\n${p.caption}`).join('\n\n---\n\n')
                    handleCopyText('all', txt)
                  }}
                  className="flex items-center gap-1 text-xs text-blue-600 hover:underline font-semibold cursor-pointer"
                >
                  {copiedId === 'all' ? <Check className="w-3.5 h-3.5 text-emerald-500" /> : <Copy className="w-3.5 h-3.5" />}
                  <span>{copiedId === 'all' ? 'Copied' : 'Copy All'}</span>
                </button>
              </div>

              {activeOutputTab === 'copy' && (
                <div className="space-y-3 overflow-y-auto max-h-[440px]">
                  {campaignData.posts.map((post) => (
                    <div key={post.id} className="p-3.5 rounded-xl bg-slate-50 dark:bg-[#161f30] border border-slate-200 dark:border-[#233048] space-y-2">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <span className="text-[10px] font-bold uppercase px-2 py-0.5 rounded bg-blue-100 dark:bg-blue-900/60 text-blue-700 dark:text-blue-300 font-mono">
                            {post.platform}
                          </span>
                          <span className="text-xs font-semibold text-slate-800 dark:text-slate-200">{post.category}</span>
                        </div>
                        <span className="text-[10px] text-slate-400 font-mono flex items-center gap-1">
                          <Clock className="w-3 h-3" /> {post.scheduledTime}
                        </span>
                      </div>
                      <p className="text-xs text-slate-700 dark:text-slate-200 whitespace-pre-wrap leading-relaxed">{post.caption}</p>
                      <div className="flex items-center justify-between pt-2 border-t border-slate-200/60 dark:border-[#233048]">
                        <div className="flex gap-1">
                          {post.hashtags.map((h, i) => <span key={i} className="text-[10px] text-blue-600 dark:text-blue-400 font-mono">{h}</span>)}
                        </div>
                        <button onClick={() => handleCopyText(post.id, post.caption)} className="px-2 py-1 rounded bg-white dark:bg-[#182234] border border-slate-200 dark:border-[#233048] text-[11px] font-medium text-slate-700 dark:text-slate-300 cursor-pointer">
                          {copiedId === post.id ? 'Copied' : 'Copy'}
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {activeOutputTab === 'schedule' && (
                <div className="space-y-2 overflow-y-auto max-h-[440px]">
                  {campaignData.scheduleQueue.map((item) => (
                    <div key={item.id} className="p-3 rounded-xl bg-slate-50 dark:bg-[#161f30] border border-slate-200 dark:border-[#233048] flex items-center justify-between text-xs">
                      <div className="flex items-center gap-3">
                        <Calendar className="w-4 h-4 text-blue-500" />
                        <div>
                          <p className="font-semibold text-slate-900 dark:text-white">{item.platform}</p>
                          <p className="text-[11px] text-slate-400">{item.date} at {item.time}</p>
                        </div>
                      </div>
                      <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-50 dark:bg-emerald-950/60 text-emerald-700 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800 font-mono">
                        {item.status}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ) : (
            <div className="flex-1 bg-white dark:bg-[#121826] border border-dashed border-slate-300 dark:border-[#233048] rounded-2xl p-8 flex flex-col items-center justify-center text-center">
              <Layers className="w-8 h-8 text-slate-400 mb-2" />
              <h4 className="text-sm font-bold text-slate-900 dark:text-white">Active Deliverables Output</h4>
              <p className="text-xs text-slate-400 max-w-sm mt-1 leading-relaxed">
                Provide parameters to the AI Assistant on the left to execute the pipeline and view synthesized outputs.
              </p>
            </div>
          )}
        </div>
      </div>

      {/* ── Connect Tool Integration Modal ───────────────────────────────────── */}
      {showConnectModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4">
          <div className="bg-white dark:bg-[#121826] border border-slate-200 dark:border-[#233048] rounded-2xl p-6 max-w-md w-full shadow-xl space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Link2 className="w-5 h-5 text-blue-500" />
                <h3 className="text-sm font-bold text-slate-900 dark:text-white">Connect {connectingTool} OAuth</h3>
              </div>
              <button onClick={() => setShowConnectModal(false)} className="text-slate-400 hover:text-slate-600">
                <X className="w-4 h-4" />
              </button>
            </div>

            <p className="text-xs text-slate-500 dark:text-slate-400 leading-relaxed">
              Connect your {connectingTool} account to enable autonomous read/write access for this workflow. Authentication is encrypted with enterprise tenant isolation.
            </p>

            <div className="p-3 bg-slate-50 dark:bg-[#161f30] rounded-xl border border-slate-200 dark:border-[#233048] text-xs space-y-2">
              <div className="flex items-center justify-between">
                <span className="font-semibold text-slate-800 dark:text-slate-200">OAuth Scopes:</span>
                <span className="text-[10px] font-mono text-slate-400">Read & Write</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="font-semibold text-slate-800 dark:text-slate-200">Security Vault:</span>
                <span className="text-[10px] font-mono text-emerald-500">AES-256 Encrypted</span>
              </div>
            </div>

            <div className="flex items-center justify-end gap-2 pt-2">
              <button
                onClick={() => setShowConnectModal(false)}
                className="px-4 py-2 rounded-xl text-xs font-semibold text-slate-600 dark:text-slate-400 hover:text-slate-900 cursor-pointer"
              >
                Cancel
              </button>
              <button
                onClick={() => {
                  setConnectedTools(prev => ({ ...prev, [connectingTool]: true }))
                  setShowConnectModal(false)
                }}
                className="px-5 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-xl text-xs font-bold transition-all cursor-pointer shadow-xs"
              >
                Authenticate & Connect
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
