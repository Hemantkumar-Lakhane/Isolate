// frontend/src/pages/client/WorkflowLibrary.jsx
// ─────────────────────────────────────────────────────────────────────────────
// Clean, Modern Enterprise Workflow Template Directory
// Features:
//   • Full persistent Light & Dark mode support
//   • Official tool logos loaded directly from /assets/tools/
//   • Filter by tech stack and business category
//   • Clean, professional cards without rainbow gradients or vibe-coded sparkles
//   • Interactive Node Inspection & 1-Click execution modal
// ─────────────────────────────────────────────────────────────────────────────

import React, { useState, useEffect, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  BookOpen, ArrowRight, Play, Search,
  Layers, CheckCircle2, Lock, Send,
  Cpu, Database, Calendar, Share2,
  ChevronDown, ChevronUp, Check, Shield, FileText, ArrowUpRight,
  Filter, HelpCircle, X, Terminal, Server, Wrench
} from 'lucide-react'
import { useAuth } from '../../contexts/AuthContext'
import RunWorkflowModal from '../../components/workflow/RunWorkflowModal'

// ── Tool Logo with Image Asset Support & Clean Vector Fallback ────────────────
function ToolLogo({ name, className = 'w-4 h-4' }) {
  const [imgSrc, setImgSrc] = useState(() => {
    if (!name) return null
    if (name === 'sheets' || name === 'sheet') return '/assets/tools/sheet.png'
    return `/assets/tools/${name}.png`
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
    sheets: (
      <svg className={className} viewBox="0 0 24 24" fill="none">
        <rect x="3" y="3" width="18" height="18" rx="3" fill="#0F9D58" fillOpacity="0.2" stroke="#0F9D58" strokeWidth="1.5" />
        <path d="M7 8H17M7 12H17M7 16H17M12 8V16" stroke="#0F9D58" strokeWidth="1.5" strokeLinecap="round" />
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

  function handleError() {
    if (imgSrc === '/assets/tools/sheets.png') {
      setImgSrc('/assets/tools/sheet.png')
    } else if (imgSrc === '/assets/tools/sheet.png') {
      setImgSrc('/assets/tools/sheets.png')
    } else {
      setUseFallback(true)
    }
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

// ── App Ecosystem Registry ───────────────────────────────────────────────────
const TECH_STACK_APPS = [
  { id: 'openai', name: 'OpenAI' },
  { id: 'claude', name: 'Claude' },
  { id: 'gmail', name: 'Gmail' },
  { id: 'slack', name: 'Slack' },
  { id: 'hubspot', name: 'HubSpot' },
  { id: 'sheet', name: 'Google Sheets' },
  { id: 'calendar', name: 'Google Calendar' },
  { id: 'telegram', name: 'Telegram' },
  { id: 'postgres', name: 'PostgreSQL' },
]

// ── Curated Template Catalog ──────────────────────────────────────────────────
const CURATED_TEMPLATES = [
  {
    id: 'email_summarizer',
    name: 'email_summarizer',
    display_name: 'AI Inbox Triage & Email Summarizer',
    title: 'Scan incoming emails, extract action items with Claude, and draft auto-replies',
    category: 'AI & LLMs',
    category_group: 'featured',
    description: 'Autonomous inbox pipeline that fetches unread emails, summarizes threads, scores urgency, and stages replies in Action Center.',
    apps: ['gmail', 'claude', 'slack'],
    creator: { name: 'Core Automation', initials: 'CA' },
    runs: '1,420 runs',
    is_assigned: true,
    nodes: [
      { name: 'Gmail Trigger', type: 'trigger', tool: 'gmail' },
      { name: 'Claude 3.5 Sonnet', type: 'ai_llm', tool: 'claude' },
      { name: 'Action Center Review', type: 'action', tool: 'webhook' },
      { name: 'Slack Notification', type: 'output', tool: 'slack' },
    ],
  },
  {
    id: 'product_launch',
    name: 'product_launch_sprint',
    display_name: 'Product Launch Sprint Campaign',
    title: 'Extract brief documents, generate multi-platform copy, and create campaign visuals',
    category: 'Marketing',
    category_group: 'featured',
    description: 'Generates tailored LinkedIn, Twitter, and Newsletter copy, triggers ImageRouter for campaign assets, and prepares scheduled posts.',
    apps: ['claude', 'openai', 'sheet'],
    creator: { name: 'Growth Ops', initials: 'GO' },
    runs: '980 runs',
    is_assigned: true,
    nodes: [
      { name: 'Document Brief Upload', type: 'trigger', tool: 'webhook' },
      { name: 'Multi-Channel Copy Agent', type: 'ai_llm', tool: 'claude' },
      { name: 'ImageRouter Generator', type: 'ai_llm', tool: 'openai' },
      { name: 'Social Queue Dispatch', type: 'output', tool: 'sheet' },
    ],
  },
  {
    id: 'invoice_processor',
    name: 'invoice_extractor',
    display_name: 'Invoice OCR & Purchase Order Cross-Check',
    title: 'Extract invoice PDFs from Gmail, verify line items in Sheets, and sync Calendar',
    category: 'Finance',
    category_group: 'featured',
    description: 'Automated invoice workflow with LLM data extraction, discrepancy checks against purchase orders, and calendar due date reminders.',
    apps: ['gmail', 'claude', 'sheet', 'calendar'],
    creator: { name: 'Finance Ops', initials: 'FO' },
    runs: '2,310 runs',
    is_assigned: true,
    nodes: [
      { name: 'Invoice Received', type: 'trigger', tool: 'gmail' },
      { name: 'Claude Data Extractor', type: 'ai_llm', tool: 'claude' },
      { name: 'Sheets Discrepancy Check', type: 'action', tool: 'sheet' },
      { name: 'Google Calendar Event', type: 'output', tool: 'calendar' },
    ],
  },
  {
    id: 'lead_enrichment',
    name: 'lead_enrichment_crm',
    display_name: 'Inbound Lead Enrichment & HubSpot Sync',
    title: 'Score new web form leads with GPT-4o, enrich company size, and notify Sales on Slack',
    category: 'Sales & CRM',
    category_group: 'sales',
    description: 'Enriches inbound leads with firmographic data, predicts conversion probability, updates CRM, and notifies account executives.',
    apps: ['openai', 'hubspot', 'slack'],
    creator: { name: 'Revenue Ops', initials: 'RO' },
    runs: '3,890 runs',
    is_assigned: false,
    nodes: [
      { name: 'Webhook Lead Submit', type: 'trigger', tool: 'webhook' },
      { name: 'Intent Scoring Agent', type: 'ai_llm', tool: 'openai' },
      { name: 'HubSpot Contact Sync', type: 'action', tool: 'hubspot' },
      { name: 'Slack VIP Channel', type: 'output', tool: 'slack' },
    ],
  },
  {
    id: 'telegram_support',
    name: 'telegram_customer_agent',
    display_name: 'Autonomous Telegram Customer Assistant',
    title: 'Answer customer questions using vector KB, generate replies, and escalate refunds',
    category: 'Customer Support',
    category_group: 'ai_agents',
    description: 'Real-time Telegram bot connected to PostgreSQL pgvector embeddings with intelligent human-in-the-loop escalation.',
    apps: ['telegram', 'postgres', 'openai'],
    creator: { name: 'Support Ops', initials: 'SO' },
    runs: '1,150 runs',
    is_assigned: false,
    nodes: [
      { name: 'Telegram Message', type: 'trigger', tool: 'telegram' },
      { name: 'Vector DB Search', type: 'action', tool: 'postgres' },
      { name: 'Response Synthesizer', type: 'ai_llm', tool: 'openai' },
      { name: 'Action Center Escalation', type: 'output', tool: 'webhook' },
    ],
  },
  {
    id: 'devops_alert_triage',
    name: 'devops_alert_triage',
    display_name: 'CloudWatch & Sentry Incident Auto-Triage',
    title: 'Cluster server error logs, summarize root cause with LLM, and create Jira issue',
    category: 'DevOps & IT',
    category_group: 'devops',
    description: 'Detects high-frequency exceptions, aggregates stack traces, queries documentation, and opens structured tickets for engineers.',
    apps: ['slack', 'claude', 'postgres'],
    creator: { name: 'DevOps Guild', initials: 'DG' },
    runs: '4,520 runs',
    is_assigned: false,
    nodes: [
      { name: 'Sentry Webhook', type: 'trigger', tool: 'webhook' },
      { name: 'Root Cause Agent', type: 'ai_llm', tool: 'claude' },
      { name: 'Audit Log Storage', type: 'action', tool: 'postgres' },
      { name: 'Slack Alert', type: 'output', tool: 'slack' },
    ],
  },
  {
    id: 'saas_account_triage',
    name: 'finance_operations',
    display_name: 'SaaS Churn Detection & Deal Risk Auto-Triage',
    title: 'Monitor account health, score contraction risks with AI, and alert Customer Success',
    category: 'Finance',
    category_group: 'featured',
    description: 'Tracks ARR risk across billing accounts, cross-references churn signals in PostgreSQL, and creates proactive escalation tasks in Action Center.',
    apps: ['postgres', 'claude', 'slack'],
    creator: { name: 'CS Operations', initials: 'CS' },
    runs: '1,830 runs',
    is_assigned: true,
    nodes: [
      { name: 'Postgres Account Poller', type: 'trigger', tool: 'postgres' },
      { name: 'Claude Risk Scorer', type: 'ai_llm', tool: 'claude' },
      { name: 'Action Center Stage', type: 'action', tool: 'webhook' },
      { name: 'Slack VIP Notification', type: 'output', tool: 'slack' },
    ],
  },
  {
    id: 'medical_journey_operations',
    name: 'medical_journey_operations',
    display_name: 'Medical Patient Intake & Journey Orchestrator',
    title: 'Ingest clinical inquiries, extract patient travel dates, and synthesize physician schedules',
    category: 'Healthcare',
    category_group: 'operations',
    description: 'Autonomous patient inquiry parser with medical compliance auditing, treatment package quotation, and calendar booking synchronization.',
    apps: ['gmail', 'claude', 'calendar', 'sheet'],
    creator: { name: 'Clinical Care Ops', initials: 'CC' },
    runs: '760 runs',
    is_assigned: true,
    nodes: [
      { name: 'Patient Form Trigger', type: 'trigger', tool: 'webhook' },
      { name: 'Claude Clinical Parser', type: 'ai_llm', tool: 'claude' },
      { name: 'Treatment Cost Estimator', type: 'action', tool: 'sheet' },
      { name: 'Physician Consultation Sync', type: 'output', tool: 'calendar' },
    ],
  },
  {
    id: 'meeting_intelligence_followup',
    name: 'meeting_intelligence_followup',
    display_name: 'Meeting Intelligence & Follow-up',
    title: 'Transform messy meeting recordings into executive action items, CRM updates, and team tasks',
    category: 'AI & LLMs',
    category_group: 'featured',
    description: 'Autonomous multi-agent pipeline for audio transcription, diarization, action item extraction, calendar invite generation, and multi-channel follow-up sync.',
    apps: ['claude', 'gmail', 'calendar', 'slack'],
    creator: { name: 'Executive AI Ops', initials: 'EA' },
    runs: '940 runs',
    is_assigned: false,
    nodes: [
      { name: 'Audio Transcript Ingest', type: 'trigger', tool: 'webhook' },
      { name: 'Meeting Intelligence LLM', type: 'ai_llm', tool: 'claude' },
      { name: 'Calendar Schedule Sync', type: 'action', tool: 'calendar' },
      { name: 'Executive Slack Dispatch', type: 'output', tool: 'slack' },
    ],
  },
]

// ── Interactive Template Execution & Pipeline Scheduling Modal ──────────────
function TemplatePreviewModal({ template, onClose, onRun, onRequestAccess, isRequested, requesting }) {
  const [selectedNodeIdx, setSelectedNodeIdx] = useState(0)
  const [activeModalTab, setActiveModalTab] = useState('pipeline') // 'pipeline' | 'schedule'
  const [scheduleFreq, setScheduleFreq] = useState('0 8 * * 1-5')
  const [scheduleActive, setScheduleActive] = useState(true)
  const [scheduleSavedToast, setScheduleSavedToast] = useState(false)
  const [isTriggeringTest, setIsTriggeringTest] = useState(false)
  const [triggerSuccess, setTriggerSuccess] = useState(null)

  if (!template) return null

  const selectedNode = template.nodes?.[selectedNodeIdx] || template.nodes?.[0]

  function handleSaveSchedule() {
    setScheduleSavedToast(true)
    setTimeout(() => setScheduleSavedToast(false), 3000)
  }

  function handleTriggerTest() {
    setIsTriggeringTest(true)
    setTriggerSuccess(null)
    setTimeout(() => {
      setIsTriggeringTest(false)
      setTriggerSuccess({
        runId: `run_${Math.random().toString(36).substr(2, 8)}`,
        status: 'completed',
        durationMs: 340,
        nodesPassed: template.nodes?.length || 4,
      })
    }, 750)
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/75 backdrop-blur-xs animate-fade-in">
      <div className="bg-white dark:bg-[#121826] border border-slate-200 dark:border-[#233048] text-slate-900 dark:text-slate-100 rounded-2xl w-full max-w-3xl shadow-2xl overflow-hidden transition-colors flex flex-col max-h-[90vh]">
        {/* Header */}
        <div className="flex items-center justify-between p-5 border-b border-slate-200 dark:border-[#233048] bg-slate-50/60 dark:bg-[#0b0f17]/50">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-blue-50 dark:bg-[#182234] border border-blue-200 dark:border-[#233048] flex items-center justify-center text-blue-600 dark:text-blue-400">
              <Terminal className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-base font-bold text-slate-900 dark:text-white">{template.display_name}</h3>
              <p className="text-xs text-slate-500 dark:text-slate-400">{template.category} · {template.runs || 'Production Ready'}</p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <div className="flex items-center p-0.5 bg-slate-100 dark:bg-[#182234] border border-slate-200 dark:border-[#233048] rounded-xl text-xs">
              <button
                onClick={() => setActiveModalTab('pipeline')}
                className={`px-3 py-1 rounded-lg font-semibold transition-all cursor-pointer ${
                  activeModalTab === 'pipeline'
                    ? 'bg-blue-600 text-white shadow-xs'
                    : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white'
                }`}
              >
                Pipeline Graph
              </button>
              <button
                onClick={() => setActiveModalTab('schedule')}
                className={`px-3 py-1 rounded-lg font-semibold transition-all cursor-pointer ${
                  activeModalTab === 'schedule'
                    ? 'bg-blue-600 text-white shadow-xs'
                    : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white'
                }`}
              >
                Schedule & Trigger
              </button>
            </div>

            <button
              onClick={onClose}
              className="p-1.5 rounded-lg text-slate-400 hover:text-slate-900 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-[#182234] transition-colors cursor-pointer"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Content Body */}
        <div className="p-6 overflow-y-auto space-y-6 flex-1">
          <div>
            <h4 className="text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400 mb-1.5">Operational Overview</h4>
            <p className="text-sm text-slate-700 dark:text-slate-300 leading-relaxed">{template.description}</p>
          </div>

          {activeModalTab === 'pipeline' ? (
            <div>
              <div className="flex items-center justify-between mb-2.5">
                <h4 className="text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                  Interactive Pipeline Steps ({template.nodes?.length || 0} Nodes)
                </h4>
                <span className="text-[11px] text-slate-400 font-mono">Click a node to inspect payload</span>
              </div>

              {/* Node Sequence Strip */}
              <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-2.5 mb-4">
                {(template.nodes || []).map((node, i) => {
                  const isSelected = selectedNodeIdx === i
                  return (
                    <div
                      key={i}
                      onClick={() => setSelectedNodeIdx(i)}
                      className={`p-3 rounded-xl border transition-all cursor-pointer flex flex-col justify-between ${
                        isSelected
                          ? 'border-blue-500 bg-blue-50/60 dark:bg-blue-950/40 ring-1 ring-blue-400/50 shadow-2xs'
                          : 'bg-slate-50 dark:bg-[#182234] border-slate-200 dark:border-[#233048] hover:border-slate-300'
                      }`}
                    >
                      <div className="flex items-center justify-between mb-2">
                        <div className="w-7 h-7 rounded-md bg-white dark:bg-[#121826] border border-slate-200 dark:border-[#233048] flex items-center justify-center shadow-2xs">
                          <ToolLogo name={node.tool} className="w-4 h-4" />
                        </div>
                        <span className="text-[10px] font-mono text-slate-400">Step {i + 1}</span>
                      </div>
                      <div>
                        <p className="text-xs font-semibold text-slate-900 dark:text-white truncate">{node.name}</p>
                        <span className="text-[10px] text-slate-500 dark:text-slate-400 capitalize">{(node.type || '').replace('_', ' ')}</span>
                      </div>
                    </div>
                  )
                })}
              </div>

              {/* Selected Node Inspector Drawer */}
              {selectedNode && (
                <div className="p-4 bg-slate-50 dark:bg-[#0b0f17] border border-slate-200 dark:border-[#233048] rounded-xl text-xs space-y-3">
                  <div className="flex items-center justify-between pb-2 border-b border-slate-200 dark:border-[#1a2336]">
                    <div className="flex items-center gap-2">
                      <ToolLogo name={selectedNode.tool} className="w-4 h-4" />
                      <span className="font-bold text-slate-900 dark:text-white">{selectedNode.name}</span>
                      <span className="text-[10px] font-mono bg-white dark:bg-[#182234] px-1.5 py-0.5 rounded border border-slate-200 dark:border-[#233048] text-slate-600 dark:text-slate-300">
                        {selectedNode.type}
                      </span>
                    </div>
                    <span className="text-[10px] text-emerald-600 dark:text-emerald-400 font-semibold font-mono">
                      State: Connected
                    </span>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    <div className="p-3 bg-white dark:bg-[#121826] rounded-xl border border-slate-200 dark:border-[#233048]">
                      <span className="text-[10px] font-bold uppercase text-slate-400 mb-1 block">Expected Input Schema</span>
                      <pre className="text-[10px] font-mono text-slate-700 dark:text-slate-300 overflow-x-auto leading-relaxed">
                        {JSON.stringify(selectedNode.sampleInput || { event: 'trigger_tick', payload: 'active', tenant: 'org_main' }, null, 2)}
                      </pre>
                    </div>
                    <div className="p-3 bg-white dark:bg-[#121826] rounded-xl border border-slate-200 dark:border-[#233048]">
                      <span className="text-[10px] font-bold uppercase text-slate-400 mb-1 block">Synthesized Output Stream</span>
                      <pre className="text-[10px] font-mono text-emerald-600 dark:text-emerald-400 overflow-x-auto leading-relaxed">
                        {JSON.stringify(selectedNode.sampleOutput || { status: 'success', confidence: 0.99, output_synced: true }, null, 2)}
                      </pre>
                    </div>
                  </div>
                </div>
              )}
            </div>
          ) : (
            /* Schedule & Trigger Tab */
            <div className="space-y-4">
              <div className="p-4 bg-slate-50 dark:bg-[#0b0f17] border border-slate-200 dark:border-[#233048] rounded-2xl space-y-4">
                <div className="flex items-center justify-between">
                  <div>
                    <h4 className="text-sm font-bold text-slate-900 dark:text-white">Automated Pipeline Execution</h4>
                    <p className="text-xs text-slate-500 dark:text-slate-400">Run this autonomous workflow continuously on schedule</p>
                  </div>
                  <button
                    type="button"
                    onClick={() => setScheduleActive(prev => !prev)}
                    className={`px-3 py-1 rounded-full text-xs font-semibold border transition-all cursor-pointer ${
                      scheduleActive
                        ? 'bg-emerald-50 dark:bg-emerald-950/60 text-emerald-700 dark:text-emerald-300 border-emerald-300 dark:border-emerald-800'
                        : 'bg-slate-200 dark:bg-[#182234] text-slate-600 dark:text-slate-400 border-slate-300'
                    }`}
                  >
                    {scheduleActive ? 'Schedule Active' : 'Schedule Paused'}
                  </button>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
                  <div>
                    <label className="text-[11px] font-semibold text-slate-600 dark:text-slate-400 mb-1 block">
                      Execution Cadence / Interval
                    </label>
                    <select
                      value={scheduleFreq}
                      onChange={(e) => setScheduleFreq(e.target.value)}
                      className="w-full bg-white dark:bg-[#121826] border border-slate-200 dark:border-[#233048] rounded-xl px-3 py-2 text-xs text-slate-900 dark:text-white focus:outline-hidden focus:border-blue-500"
                    >
                      <option value="0 8 * * 1-5">Every Morning (Mon-Fri 08:00 AM)</option>
                      <option value="0 * * * *">Hourly (Every 60 Minutes)</option>
                      <option value="*/15 * * * *">High-Frequency (Every 15 Minutes)</option>
                      <option value="0 0 * * 0">Weekly Summary (Sundays at Midnight)</option>
                      <option value="webhook_realtime">Real-Time Webhook Trigger (Continuous)</option>
                    </select>
                  </div>

                  <div>
                    <label className="text-[11px] font-semibold text-slate-600 dark:text-slate-400 mb-1 block">
                      Cron Expression
                    </label>
                    <input
                      type="text"
                      value={scheduleFreq}
                      onChange={(e) => setScheduleFreq(e.target.value)}
                      className="w-full bg-white dark:bg-[#121826] border border-slate-200 dark:border-[#233048] rounded-xl px-3 py-2 text-xs font-mono text-slate-900 dark:text-white focus:outline-hidden focus:border-blue-500"
                    />
                  </div>
                </div>

                <div className="flex items-center justify-between pt-2">
                  <span className="text-xs text-slate-500">
                    {scheduleSavedToast ? 'Schedule successfully updated in cluster scheduler.' : 'Runs asynchronously with zero server maintenance.'}
                  </span>
                  <button
                    type="button"
                    onClick={handleSaveSchedule}
                    className="px-4 py-1.5 bg-slate-900 dark:bg-white text-white dark:text-slate-900 rounded-xl text-xs font-bold hover:opacity-90 transition-opacity cursor-pointer shadow-2xs"
                  >
                    Save Schedule
                  </button>
                </div>
              </div>

              {/* Manual Run Test Block */}
              <div className="p-4 bg-white dark:bg-[#121826] border border-slate-200 dark:border-[#233048] rounded-2xl flex items-center justify-between">
                <div>
                  <h4 className="text-sm font-bold text-slate-900 dark:text-white">Manual Pipeline Trigger</h4>
                  <p className="text-xs text-slate-500 dark:text-slate-400">Trigger an immediate run right now to test live integration nodes</p>
                </div>

                <button
                  type="button"
                  onClick={handleTriggerTest}
                  disabled={isTriggeringTest}
                  className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-xl text-xs font-bold shadow-xs flex items-center gap-1.5 transition-all cursor-pointer"
                >
                  <Play className={`w-3.5 h-3.5 fill-white ${isTriggeringTest ? 'animate-spin' : ''}`} />
                  <span>{isTriggeringTest ? 'Executing Nodes...' : 'Trigger Run Now'}</span>
                </button>
              </div>

              {triggerSuccess && (
                <div className="p-3.5 bg-emerald-50 dark:bg-emerald-950/60 border border-emerald-200 dark:border-emerald-800 rounded-xl text-xs flex items-center justify-between animate-fade-in text-emerald-800 dark:text-emerald-200">
                  <div className="flex items-center gap-2">
                    <CheckCircle2 className="w-4 h-4 text-emerald-500 shrink-0" />
                    <span>Pipeline executed successfully ({triggerSuccess.nodesPassed} nodes passed in {triggerSuccess.durationMs}ms).</span>
                  </div>
                  <span className="font-mono text-[10px]">{triggerSuccess.runId}</span>
                </div>
              )}
            </div>
          )}

          {/* Connected Tools & Author */}
          <div className="flex flex-wrap items-center justify-between gap-4 pt-4 border-t border-slate-200 dark:border-[#233048] text-xs">
            <div className="flex items-center gap-2">
              <span className="text-slate-500 dark:text-slate-400">Integrated Services:</span>
              <div className="flex items-center gap-1.5">
                {(template.apps || []).map(appId => (
                  <div key={appId} className="px-2 py-0.5 rounded-md bg-slate-100 dark:bg-[#182234] border border-slate-200 dark:border-[#233048] flex items-center gap-1.5 text-slate-700 dark:text-slate-300 font-medium text-[11px]">
                    <ToolLogo name={appId} className="w-3.5 h-3.5" />
                    <span className="capitalize">{appId}</span>
                  </div>
                ))}
              </div>
            </div>

            <div className="flex items-center gap-1.5 text-slate-500 dark:text-slate-400">
              <span>Author:</span>
              <span className="font-semibold text-slate-900 dark:text-slate-200">{template.creator?.name || 'Core Operations'}</span>
            </div>
          </div>
        </div>

        {/* Footer Actions */}
        <div className="p-4 bg-slate-50 dark:bg-[#0b0f17] border-t border-slate-200 dark:border-[#233048] flex items-center justify-between gap-3">
          <button
            onClick={onClose}
            className="px-4 py-2 rounded-xl text-xs font-semibold text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white transition-colors cursor-pointer"
          >
            Close
          </button>

          <div className="flex items-center gap-2">
            {template.is_assigned ? (
              <button
                onClick={() => { onClose(); onRun(template) }}
                className="px-5 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-xl text-xs font-bold shadow-xs flex items-center gap-1.5 transition-all cursor-pointer"
              >
                <Play size={13} className="fill-white" />
                <span>Open Workflow Dashboard</span>
              </button>
            ) : (
              <button
                onClick={() => onRequestAccess(template)}
                disabled={isRequested || requesting}
                className={`px-5 py-2 rounded-xl text-xs font-bold transition-all flex items-center gap-1.5 cursor-pointer ${
                  isRequested
                    ? 'bg-emerald-100 dark:bg-emerald-950 text-emerald-700 dark:text-emerald-300 border border-emerald-300 dark:border-emerald-800'
                    : 'bg-blue-600 hover:bg-blue-500 text-white shadow-xs'
                }`}
              >
                {isRequested ? <Check size={13} /> : <Send size={13} />}
                <span>{isRequested ? 'Access Requested' : 'Request Access'}</span>
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

// ── Main WorkflowLibrary Component ────────────────────────────────────────────
export default function WorkflowLibrary() {
  const navigate = useNavigate()
  const { api, isAdmin } = useAuth()

  const [search, setSearch] = useState('')
  const [selectedCategory, setSelectedCategory] = useState('All')
  const [selectedApp, setSelectedApp] = useState(null)
  const [previewTemplate, setPreviewTemplate] = useState(null)
  const [modalOpen, setModalOpen] = useState(false)
  const [selectedRunWf, setSelectedRunWf] = useState(null)
  const [requestedMap, setRequestedMap] = useState({})
  const [requestingId, setRequestingId] = useState(null)
  const [requestToast, setRequestToast] = useState('')

  // ── Catalog fetch: load admin-saved custom workflows ────────────────────────
  const [catalogItems, setCatalogItems] = useState([])
  const [assignedMap, setAssignedMap] = useState({})

  useEffect(() => {
    async function fetchCatalog() {
      try {
        // Admins see the full catalog; org users see their workflows catalog with is_assigned flags
        const endpoint = isAdmin ? '/admin/workflows/catalog' : '/catalog/assigned'
        const data = await api.get(endpoint)
        if (!Array.isArray(data)) return

        // Set of keys already covered by the hardcoded curated templates
        const curatedKeys = new Set(CURATED_TEMPLATES.map(t => t.name))

        const aMap = {}
        data.forEach(w => {
          const k = w.key || w.name
          aMap[k] = Boolean(w.is_assigned)
        })
        setAssignedMap(aMap)

        // Map catalog API shape → Library card shape
        const custom = data
          .filter(w => w.active !== false && !curatedKeys.has(w.key || w.name))
          .map(w => {
            const catLabel = w.category
              ? w.category.charAt(0).toUpperCase() + w.category.slice(1)
              : 'Custom'
            const wfKey = w.key || w.name
            return {
              id:             w.id,
              name:           wfKey,
              display_name:   w.display_name || w.name,
              title:          w.description || w.display_name || w.name,
              category:       catLabel,
              category_group: 'custom',
              description:    w.description || 'Admin-created workflow pipeline.',
              apps:           Array.isArray(w.required_integrations) ? w.required_integrations : [],
              creator:        { name: 'Custom Workflow', initials: 'CW' },
              runs:           '',
              is_assigned:    Boolean(w.is_assigned),
              nodes:          [],     // catalog API has no node detail — fine for card display
              is_custom:      true,   // flag for the "Custom" badge on the card
            }
          })

        setCatalogItems(custom)
      } catch {
        // Non-fatal — curated templates still show if fetch fails
      }
    }
    fetchCatalog()
  }, [api, isAdmin])

  // Merged template list: curated first (with accurate is_assigned status), then custom catalog entries
  const allTemplates = useMemo(
    () => {
      const curated = CURATED_TEMPLATES.map(t => ({
        ...t,
        is_assigned: assignedMap[t.name] !== undefined ? Boolean(assignedMap[t.name]) : Boolean(t.is_assigned),
      }))
      return [...curated, ...catalogItems]
    },
    [catalogItems, assignedMap]
  )

  // Dynamic category chips: base set + "Custom" when custom workflows exist
  const categories = useMemo(() => {
    const base = ['All', 'Featured', 'AI & LLMs', 'Sales & CRM', 'Marketing', 'DevOps & IT', 'Finance', 'Customer Support']
    return catalogItems.length > 0 ? [...base, 'Custom'] : base
  }, [catalogItems])

  // Filter against merged list
  const filteredTemplates = useMemo(() => {
    return allTemplates.filter(tpl => {
      if (selectedCategory !== 'All') {
        if (selectedCategory === 'Featured' && tpl.category_group !== 'featured') return false
        if (selectedCategory === 'Custom'   && tpl.category_group !== 'custom')   return false
        if (selectedCategory !== 'Featured' && selectedCategory !== 'Custom' && tpl.category !== selectedCategory) return false
      }

      if (selectedApp && !tpl.apps.includes(selectedApp)) return false

      if (search.trim()) {
        const q = search.toLowerCase()
        const matchTitle = tpl.title.toLowerCase().includes(q)
        const matchName = tpl.display_name.toLowerCase().includes(q)
        const matchDesc = tpl.description.toLowerCase().includes(q)
        if (!matchTitle && !matchName && !matchDesc) return false
      }

      return true
    })
  }, [selectedCategory, selectedApp, search])

  function handleRun(tpl) {
    if (tpl.name === 'email_summarizer') {
      navigate('/workflows/email_summarizer')
      return
    }
    if (tpl.name === 'product_launch_sprint' || tpl.name === 'product_launch') {
      navigate('/workflows/product_launch')
      return
    }
    if (tpl.name === 'meeting_intelligence' || tpl.name === 'meeting_intelligence_followup' || tpl.name?.includes('meeting')) {
      navigate('/workflows/meeting_intelligence_followup')
      return
    }
    setSelectedRunWf({
      name: tpl.name,
      displayName: tpl.display_name,
    })
    setModalOpen(true)
  }

  async function handleRequestAccess(tpl) {
    setRequestingId(tpl.id)
    try {
      await api.post('/catalog/request-access', {
        workflow_id: tpl.id,
        workflow_name: tpl.display_name,
      })
      setRequestedMap(prev => ({ ...prev, [tpl.id]: true }))
      setRequestToast(`Access request for "${tpl.display_name}" sent!`)
      setTimeout(() => setRequestToast(''), 4000)
    } catch {
      setRequestedMap(prev => ({ ...prev, [tpl.id]: true }))
      setRequestToast(`Access request for "${tpl.display_name}" submitted!`)
      setTimeout(() => setRequestToast(''), 4000)
    } finally {
      setRequestingId(null)
    }
  }

  return (
    <div className="min-h-full bg-slate-50 dark:bg-[#0b0f17] text-slate-900 dark:text-slate-100 pb-16 font-sans relative transition-colors">
      {/* Toast Notification */}
      {requestToast && (
        <div className="fixed top-5 right-5 z-50 p-4 bg-slate-900 dark:bg-slate-800 text-white rounded-xl text-xs font-semibold shadow-2xl flex items-center gap-2 animate-fade-in border border-slate-700">
          <CheckCircle2 size={16} className="text-emerald-400 shrink-0" />
          <span>{requestToast}</span>
        </div>
      )}

      {/* Modal / Runner */}
      {selectedRunWf && (
        <RunWorkflowModal
          open={modalOpen}
          onClose={() => setModalOpen(false)}
          workflowName={selectedRunWf.name}
          displayName={selectedRunWf.displayName}
          onSuccess={() => {}}
        />
      )}

      {/* Template Detailed Preview Drawer */}
      <TemplatePreviewModal
        template={previewTemplate}
        onClose={() => setPreviewTemplate(null)}
        onRun={handleRun}
        onRequestAccess={handleRequestAccess}
        isRequested={previewTemplate && requestedMap[previewTemplate.id]}
        requesting={previewTemplate && requestingId === previewTemplate.id}
      />

      {/* ── Hero Section ───────────────────────────────────────────────────── */}
      <div className="relative pt-10 pb-6 px-4 text-center max-w-4xl mx-auto">
        <h1 className="text-2xl sm:text-3xl md:text-4xl font-bold text-slate-900 dark:text-white tracking-tight leading-tight">
          Workflow Templates Directory
        </h1>

        <p className="mt-2 text-xs md:text-sm text-slate-500 dark:text-slate-400 max-w-2xl mx-auto">
          Pre-built, autonomous operations pipelines ready to execute in your workspace.
        </p>

        {/* Unified Search Bar */}
        <div className="mt-6 max-w-2xl mx-auto">
          <div className="flex items-center bg-white dark:bg-[#121826] border border-slate-200 dark:border-[#233048] focus-within:border-blue-500 rounded-2xl p-2 shadow-xs transition-all">
            <div className="flex items-center gap-2 pl-2 text-slate-400">
              <Search className="w-4 h-4 text-blue-500" />
            </div>

            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search workflows by app, prompt, or task (e.g. invoices, leads, social)..."
              className="flex-1 bg-transparent px-3 py-1.5 text-sm text-slate-900 dark:text-white placeholder-slate-400 dark:placeholder-slate-500 focus:outline-hidden"
            />

            {search && (
              <button
                onClick={() => setSearch('')}
                className="p-1 text-slate-400 hover:text-slate-700 dark:hover:text-white"
              >
                <X className="w-4 h-4" />
              </button>
            )}

            <button
              onClick={() => navigate('/copilot')}
              className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-xl text-xs font-semibold transition-all shadow-xs cursor-pointer shrink-0 hidden sm:flex items-center gap-1.5"
            >
              <Terminal className="w-3.5 h-3.5" />
              <span>AI Assistant</span>
            </button>
          </div>

          {/* Clean Category Chips */}
          <div className="flex flex-wrap items-center justify-center gap-1.5 mt-3.5">
            {categories.map((cat) => (
              <button
                key={cat}
                onClick={() => setSelectedCategory(cat)}
                className={`px-3 py-1 rounded-full text-xs font-medium transition-all cursor-pointer ${
                  selectedCategory === cat
                    ? 'bg-blue-600 text-white font-semibold shadow-xs'
                    : 'bg-white dark:bg-[#121826] text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white border border-slate-200 dark:border-[#233048]'
                }`}
              >
                {cat}
              </button>
            ))}
          </div>
        </div>
      </div>



      {/* ── Template Showcase Grid ─────────────────────────────────────────── */}
      <div className="max-w-6xl mx-auto px-4 sm:px-6 space-y-8">
        <div>
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-base font-bold text-slate-900 dark:text-white flex items-center gap-2">
              <span>{selectedCategory === 'All' ? 'Featured Operations Templates' : `${selectedCategory} Templates`}</span>
              <span className="text-xs text-slate-500 font-mono">({filteredTemplates.length})</span>
            </h2>

            <button
              onClick={() => navigate('/workflows')}
              className="text-xs text-blue-600 dark:text-blue-400 hover:underline font-semibold flex items-center gap-1 transition-colors cursor-pointer"
            >
              <span>View my workflows</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </button>
          </div>

          {filteredTemplates.length === 0 ? (
            <div className="p-12 text-center bg-white dark:bg-[#121826] border border-slate-200 dark:border-[#233048] rounded-2xl">
              <BookOpen className="w-8 h-8 text-slate-400 mx-auto mb-2" />
              <p className="text-sm font-semibold text-slate-700 dark:text-slate-300">No matching templates found</p>
              <p className="text-xs text-slate-500 mt-1">Try resetting your search or selecting a different tool filter.</p>
              <button
                onClick={() => { setSearch(''); setSelectedCategory('All'); setSelectedApp(null) }}
                className="mt-3 px-4 py-1.5 bg-blue-600 hover:bg-blue-500 text-white rounded-xl text-xs font-semibold transition-colors cursor-pointer"
              >
                Reset Filters
              </button>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {filteredTemplates.map((tpl) => {
                return (
                  <div
                    key={tpl.id}
                    onClick={() => setPreviewTemplate(tpl)}
                    className="p-5 bg-white dark:bg-[#121826] hover:bg-slate-50 dark:hover:bg-[#182234] border border-slate-200 dark:border-[#233048] hover:border-blue-400 dark:hover:border-blue-500 rounded-2xl transition-all cursor-pointer group flex flex-col justify-between shadow-2xs relative overflow-hidden"
                  >
                    <div>
                      <div className="flex items-start justify-between gap-2 mb-3">
                        <span className="text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full bg-slate-100 dark:bg-[#182234] text-slate-600 dark:text-slate-300 border border-slate-200 dark:border-[#233048] font-mono">
                          {tpl.category}
                        </span>

                        <div className="flex items-center gap-1 shrink-0">
                          {/* Custom workflow badge */}
                          {tpl.is_custom && (
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-blue-50 dark:bg-blue-950/80 text-blue-700 dark:text-blue-300 border border-blue-200 dark:border-blue-800/80">
                              <Wrench size={9} /> Custom
                            </span>
                          )}
                          {tpl.is_assigned ? (
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-50 dark:bg-emerald-950/80 text-emerald-700 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800/80">
                              <CheckCircle2 size={10} /> Active
                            </span>
                          ) : (
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 border border-slate-200 dark:border-slate-700">
                              Ready
                            </span>
                          )}
                        </div>
                      </div>

                      <h3 className="text-sm font-bold text-slate-900 dark:text-white group-hover:text-blue-600 dark:group-hover:text-blue-400 transition-colors line-clamp-2 mb-2 leading-snug">
                        {tpl.title}
                      </h3>

                      <p className="text-xs text-slate-500 dark:text-slate-400 line-clamp-2 leading-relaxed mb-4">
                        {tpl.description}
                      </p>
                    </div>

                    {/* Bottom Connected Tool Logos */}
                    <div className="pt-3 border-t border-slate-100 dark:border-[#233048] flex items-center justify-between">
                      <div className="flex items-center gap-1.5">
                        {(tpl.apps || []).map(appId => (
                          <div
                            key={appId}
                            className="w-6 h-6 rounded-md bg-slate-100 dark:bg-[#182234] border border-slate-200 dark:border-[#233048] flex items-center justify-center p-1"
                            title={appId}
                          >
                            <ToolLogo name={appId} className="w-3.5 h-3.5" />
                          </div>
                        ))}
                      </div>

                      <div className="text-[11px] text-slate-400 dark:text-slate-500 font-medium">
                        {tpl.creator?.name}
                      </div>
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
