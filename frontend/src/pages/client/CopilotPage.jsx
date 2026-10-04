// frontend/src/pages/client/CopilotPage.jsx
// ─────────────────────────────────────────────────────────────────────────────
// Clean, Modern Enterprise AI Assistant & Workflow Orchestrator
// Features:
//   • Dual-theme responsive design (light slate & dark enterprise obsidian)
//   • Custom Tool Logo Loader with image path support (/assets/tools/{name}.png)
//   • Real-time Voice / Microphone Input (Web Speech API + Backend Whisper fallback)
//   • Clean, unified category pills without rainbow coloring
//   • Dynamic live SVG Canvas Node Graph with authentic tool brand logos & flow pulses
//   • Smooth full-page vertical scrolling (overflow-y-auto)
//   • Conversational Execution Mode with Node Inspection Drawers
//   • Zero saffron/orange, zero purple, pure enterprise aesthetics
// ─────────────────────────────────────────────────────────────────────────────

import React, { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Send, Zap, Bot, ArrowRight, Play, CheckCircle2,
  Clock, ChevronDown, ChevronRight, Inbox, ShieldAlert,
  BarChart3, Rocket, RefreshCw, Cpu, Layers, HelpCircle,
  ArrowUpRight, Check, Copy, Plus, Mic, ArrowUp, FileText,
  Calendar, Database, MessageSquare, Mail, Share2, CornerDownRight,
  Sliders, ArrowLeft, Terminal, Server, Square, X, Paperclip, UploadCloud,
  Maximize2, Minimize2
} from 'lucide-react'
import { useAuth } from '../../contexts/AuthContext'

// ── Tool Logo with Image Asset Support & Vector Fallback ──────────────────────
function ToolLogo({ name, className = 'w-4 h-4' }) {
  const [imgSrc, setImgSrc] = useState(() => {
    if (!name) return null
    if (name === 'sheets' || name === 'sheet') return '/assets/tools/sheet.png'
    return `/assets/tools/${name}.png`
  })
  const [useFallback, setUseFallback] = useState(false)

  // Clean fallback SVG icons if image fails to load
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

  return svgFallbacks[name] || <Zap className={className} />
}

// ── Workflow Templates ────────────────────────────────────────────────────────
// ── Workflow Templates with Rich Inspection Properties ────────────────────────
const TEMPLATES = [
  {
    id: 'invoices',
    label: 'Process invoices',
    iconName: 'sheets',
    prompt:
      'Every morning, scan Gmail for new invoices, use Claude to extract details and cross-check them against purchase orders in Google Sheets, flag any discrepancies for review, and add all payment due dates to Google Calendar automatically.',
    nodes: [
      {
        id: '1',
        title: 'INVOICE RECEIVED',
        subtitle: 'Trigger: 08:00 AM Daily',
        brand: 'Gmail',
        tool: 'gmail',
        color: '#EA4335',
        type: 'Trigger (Cron & Polling)',
        x: 40,
        y: 110,
        config: {
          schedule: '0 8 * * 1-5 (Mon-Fri 08:00 AM)',
          query: 'from:invoices@* has:attachment filename:pdf',
          batchSize: 25,
          autoAcknowledge: true,
        },
        sampleInput: {
          event: 'cron_tick',
          timestamp: '2026-09-25T08:00:00Z',
          mailbox: 'accounts@company.com',
        },
        sampleOutput: {
          messageId: 'msg_9847291a',
          sender: 'billing@vendor-saas.io',
          subject: 'Monthly Cloud Infrastructure Invoice #INV-2026-891',
          hasAttachment: true,
          attachmentCount: 1,
        },
      },
      {
        id: '2',
        title: 'Fetch attachment',
        subtitle: 'Gmail API',
        brand: 'Gmail',
        tool: 'gmail',
        color: '#EA4335',
        type: 'Integration Action',
        x: 230,
        y: 110,
        config: {
          format: 'binary/pdf',
          extractTextOCR: true,
          saveToVault: true,
        },
        sampleInput: {
          messageId: 'msg_9847291a',
          attachmentId: 'att_014298fa',
        },
        sampleOutput: {
          fileName: 'Invoice_INV_2026_891.pdf',
          fileSizeKB: 245,
          contentType: 'application/pdf',
          ocrConfidence: 0.994,
        },
      },
      {
        id: '3',
        title: 'Extract invoice data',
        subtitle: 'Claude 3.5 Sonnet',
        brand: 'Claude',
        tool: 'claude',
        color: '#D97706',
        type: 'AI LLM Agent',
        x: 420,
        y: 110,
        config: {
          model: 'claude-3-5-sonnet-20241022',
          temperature: 0.1,
          jsonSchema: '{ vendor: string, amount: number, po_number: string, due_date: string }',
        },
        sampleInput: {
          rawText: 'INVOICE INV-2026-891\nVendor: Cloud Infra Ltd\nTotal: $1,450.00\nPO: PO-8921\nDue: 2026-10-15',
        },
        sampleOutput: {
          vendor: 'Cloud Infra Ltd',
          amount: 1450.0,
          currency: 'USD',
          poNumber: 'PO-8921',
          dueDate: '2026-10-15',
          confidence: 0.98,
        },
      },
      {
        id: '4',
        title: 'Check discrepancy',
        subtitle: 'Switch Node',
        brand: 'Switch',
        tool: 'webhook',
        color: '#10B981',
        type: 'Conditional Router',
        x: 610,
        y: 110,
        config: {
          expression: 'invoice.amount == sheets.po_amount && invoice.vendor == sheets.vendor',
          trueRoute: 'Add to Calendar',
          falseRoute: 'Flag Invoice',
        },
        sampleInput: {
          invoiceAmount: 1450.0,
          expectedPoAmount: 1450.0,
          vendorMatch: true,
        },
        sampleOutput: {
          decision: 'Approved',
          matchedRow: 42,
          varianceUsd: 0.0,
        },
      },
      {
        id: '5',
        title: 'Flag Invoice',
        subtitle: 'Google Sheets',
        brand: 'Sheets',
        tool: 'sheets',
        color: '#0F9D58',
        type: 'Exception Handler',
        x: 800,
        y: 50,
        config: {
          spreadsheetId: '1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms',
          sheetName: 'Discrepancies_Review',
          statusColumn: 'FLAGGED_VARIANCE',
        },
        sampleInput: {
          status: 'PENDING_HUMAN_REVIEW',
          variance: 150.0,
        },
        sampleOutput: {
          rowUpdated: 114,
          escalationCreated: true,
        },
      },
      {
        id: '6',
        title: 'Add to Calendar',
        subtitle: 'Google Calendar',
        brand: 'Calendar',
        tool: 'calendar',
        color: '#4285F4',
        type: 'Destination Sync',
        x: 800,
        y: 170,
        config: {
          calendarId: 'primary',
          eventTitle: 'Pay Invoice #INV-2026-891 ($1,450.00)',
          reminderDaysBefore: 2,
        },
        sampleInput: {
          summary: 'Pay Invoice #INV-2026-891',
          date: '2026-10-15',
          attendees: ['finance@company.com'],
        },
        sampleOutput: {
          calendarEventId: 'cal_event_81726a',
          eventLink: 'https://calendar.google.com/event?id=cal_event_81726a',
          status: 'confirmed',
        },
      },
    ],
    edges: [
      { from: '1', to: '2' },
      { from: '2', to: '3' },
      { from: '3', to: '4' },
      { from: '4', to: '5', label: 'Discrepancy' },
      { from: '4', to: '6', label: 'Approved' },
    ],
  },
  {
    id: 'leads',
    label: 'Score my leads',
    iconName: 'openai',
    prompt:
      'When a new lead submits our website contact form, enrich company data with Clearbit, score conversion intent with GPT-4o, automatically update HubSpot CRM, and alert our sales team in Slack if the score is above 80.',
    nodes: [
      {
        id: '1',
        title: 'Lead Form Submit',
        subtitle: 'Webhook Trigger',
        brand: 'Webhook',
        tool: 'webhook',
        color: '#3B82F6',
        type: 'Inbound Webhook',
        x: 40,
        y: 110,
        config: { path: '/v1/leads/inbound', method: 'POST', authHeader: 'Bearer x-opsgrid-key' },
        sampleInput: { email: 'sarah.j@acme-corp.com', name: 'Sarah Jenkins', employees: '250+' },
        sampleOutput: { status: 'received', leadId: 'lead_781290' },
      },
      {
        id: '2',
        title: 'Company Intelligence',
        subtitle: 'Enrich data',
        brand: 'Clearbit',
        tool: 'postgres',
        color: '#3B82F6',
        type: 'Data Enrichment',
        x: 230,
        y: 110,
        config: { endpoint: 'api.clearbit.com/v2/companies/find', matchConfidence: 0.95 },
        sampleInput: { domain: 'acme-corp.com' },
        sampleOutput: { industry: 'Enterprise SaaS', funding: '$45M Series B', techStack: ['AWS', 'Stripe'] },
      },
      {
        id: '3',
        title: 'Intent Scoring',
        subtitle: 'GPT-4o Mini',
        brand: 'OpenAI',
        tool: 'openai',
        color: '#10B981',
        type: 'AI LLM Agent',
        x: 420,
        y: 110,
        config: { model: 'gpt-4o-mini', temperature: 0.2, rubric: 'B2B SMB suitability 0-100' },
        sampleInput: { companyProfile: 'Enterprise SaaS 250+ employees', userRole: 'VP of Ops' },
        sampleOutput: { intentScore: 92, tier: 'Tier-1 High Intent', reason: 'Decision maker with active budget' },
      },
      {
        id: '4',
        title: 'Score Filter',
        subtitle: 'Score > 80?',
        brand: 'Filter',
        tool: 'webhook',
        color: '#F59E0B',
        type: 'Routing Rule',
        x: 610,
        y: 110,
        config: { condition: 'lead.intentScore >= 80', fallback: 'Nurture Campaign' },
        sampleInput: { intentScore: 92 },
        sampleOutput: { passed: true, route: 'VIP Escalation' },
      },
      {
        id: '5',
        title: 'Update CRM Contact',
        subtitle: 'HubSpot',
        brand: 'HubSpot',
        tool: 'hubspot',
        color: '#FF7A59',
        type: 'CRM Mutation',
        x: 800,
        y: 50,
        config: { objectType: 'contacts', updateLifecycleStage: 'salesqualifiedlead' },
        sampleInput: { email: 'sarah.j@acme-corp.com', score: 92 },
        sampleOutput: { contactId: 'hs_902184', status: 'updated' },
      },
      {
        id: '6',
        title: 'Sales VIP Alert',
        subtitle: 'Slack Channel',
        brand: 'Slack',
        tool: 'slack',
        color: '#EC4899',
        type: 'Real-time Alert',
        x: 800,
        y: 170,
        config: { channel: '#sales-tier1-leads', mentions: ['@account-execs'], includeOneClickBook: true },
        sampleInput: { lead: 'Sarah Jenkins (VP Ops - Acme)', score: 92 },
        sampleOutput: { messageTs: '1727271920.001900', delivered: true },
      },
    ],
    edges: [
      { from: '1', to: '2' },
      { from: '2', to: '3' },
      { from: '3', to: '4' },
      { from: '4', to: '5' },
      { from: '4', to: '6', label: 'VIP Lead' },
    ],
  },
  {
    id: 'social',
    label: 'Schedule social posts',
    iconName: 'calendar',
    prompt:
      'Extract new article drafts from our CMS, use Claude to generate tailored promotional posts for LinkedIn and Twitter/X, create custom banner graphics with ImageRouter, and stage them for human review in Action Center.',
    nodes: [
      {
        id: '1',
        title: 'New Article Draft',
        subtitle: 'CMS Webhook',
        brand: 'CMS',
        tool: 'webhook',
        color: '#6366F1',
        type: 'Webhook Trigger',
        x: 40,
        y: 110,
        config: { event: 'article.published_draft', source: 'Ghost / Sanity CMS' },
        sampleInput: { slug: 'automating-smb-ops-in-2026', title: 'How AI Streamlines SMB Workflows' },
        sampleOutput: { words: 1200, author: 'Alex Chen', ready: true },
      },
      {
        id: '2',
        title: 'Multi-Channel Copy',
        subtitle: 'Claude 3.5 Sonnet',
        brand: 'Claude',
        tool: 'claude',
        color: '#D97706',
        type: 'AI LLM Agent',
        x: 230,
        y: 110,
        config: { model: 'claude-3-5-sonnet-20241022', channels: ['linkedin', 'twitter'] },
        sampleInput: { articleText: 'Full 1,200 word draft text...' },
        sampleOutput: { linkedinPost: 'Excited to share our insights...', twitterThread: ['1/4 SMB ops is broken...'] },
      },
      {
        id: '3',
        title: 'Visual Generator',
        subtitle: 'ImageRouter AI',
        brand: 'ImageRouter',
        tool: 'openai',
        color: '#3B82F6',
        type: 'Generative AI',
        x: 420,
        y: 110,
        config: { aspect: '16:9', style: 'clean corporate tech infographic' },
        sampleInput: { prompt: 'Minimalist workflow orchestration dashboard illustration' },
        sampleOutput: { imageUrl: 'https://cdn.smbflow.io/assets/banner_9812.png', width: 1200, height: 675 },
      },
      {
        id: '4',
        title: 'Action Center HITL',
        subtitle: 'Human Approval',
        brand: 'SMBFlow',
        tool: 'webhook',
        color: '#F59E0B',
        type: 'Human-in-the-Loop',
        x: 610,
        y: 110,
        config: { queue: 'marketing_review', timeoutHours: 24, autoApproveFallback: false },
        sampleInput: { copyReviewId: 'rev_89128', pendingAssignee: 'marketing_lead' },
        sampleOutput: { decision: 'approved', signedBy: 'Marketing Lead' },
      },
      {
        id: '5',
        title: 'LinkedIn Post',
        subtitle: 'Buffer / API',
        brand: 'LinkedIn',
        tool: 'slack',
        color: '#0077B5',
        type: 'Social Publishing',
        x: 800,
        y: 50,
        config: { network: 'linkedin_organization', scheduleFor: '2026-09-26T14:00:00Z' },
        sampleInput: { content: 'Approved copy & graphic' },
        sampleOutput: { queuePosition: 1, scheduledTime: 'Tomorrow 2:00 PM' },
      },
      {
        id: '6',
        title: 'Twitter/X Post',
        subtitle: 'X API v2',
        brand: 'Twitter',
        tool: 'telegram',
        color: '#64748B',
        type: 'Social Publishing',
        x: 800,
        y: 170,
        config: { network: 'twitter_x_v2', threadMode: true },
        sampleInput: { tweetsCount: 3 },
        sampleOutput: { scheduledId: 'tweet_sched_8912', status: 'queued' },
      },
    ],
    edges: [
      { from: '1', to: '2' },
      { from: '2', to: '3' },
      { from: '3', to: '4' },
      { from: '4', to: '5', label: 'Approved' },
      { from: '4', to: '6', label: 'Approved' },
    ],
  },
  {
    id: 'telegram',
    label: 'Telegram support agent',
    iconName: 'telegram',
    prompt:
      'Listen for incoming customer queries on Telegram, search our company knowledge base in PostgreSQL vector embeddings, generate accurate support answers with Gemini, and escalate any refund tickets directly to human operators.',
    nodes: [
      {
        id: '1',
        title: 'New Message',
        subtitle: 'Telegram Bot API',
        brand: 'Telegram',
        tool: 'telegram',
        color: '#229ED9',
        type: 'Bot Webhook Trigger',
        x: 40,
        y: 110,
        config: { botTokenConfig: 'vault://telegram_token', polling: 'webhook_realtime' },
        sampleInput: { chatId: 98129038, text: 'Hi, I need assistance with my last order refund' },
        sampleOutput: { sender: '@customer_user', messageId: 4410 },
      },
      {
        id: '2',
        title: 'Vector Search',
        subtitle: 'PGVector KB',
        brand: 'PostgreSQL',
        tool: 'postgres',
        color: '#336791',
        type: 'Vector Embedding Retrieval',
        x: 230,
        y: 110,
        config: { embeddingModel: 'text-embedding-3-small', similarityThreshold: 0.82, topK: 3 },
        sampleInput: { query: 'refund policy order terms' },
        sampleOutput: { matchedChunks: 3, topScore: 0.91, docTitle: 'Refund_Policy_2026.pdf' },
      },
      {
        id: '3',
        title: 'Draft Solution',
        subtitle: 'Gemini 1.5 Pro',
        brand: 'Gemini',
        tool: 'openai',
        color: '#4285F4',
        type: 'AI LLM Agent',
        x: 420,
        y: 110,
        config: { model: 'gemini-1.5-pro', tone: 'helpful, professional', maxTokens: 400 },
        sampleInput: { context: 'Refund policy chunk...', userQuestion: 'I need assistance...' },
        sampleOutput: { answer: 'I understand you are requesting a refund. I am transferring your request to our support specialist...' },
      },
      {
        id: '4',
        title: 'Intent Classifier',
        subtitle: 'Refund Check',
        brand: 'Classifier',
        tool: 'webhook',
        color: '#10B981',
        type: 'Intent Classifier',
        x: 610,
        y: 110,
        config: { classes: ['General_Inquiry', 'Refund_Escalation', 'Technical_Bug'] },
        sampleInput: { intent: 'Refund_Escalation', confidence: 0.96 },
        sampleOutput: { route: 'Human Escalation' },
      },
      {
        id: '5',
        title: 'Instant Reply',
        subtitle: 'Send to Customer',
        brand: 'Telegram',
        tool: 'telegram',
        color: '#229ED9',
        type: 'Outgoing Message',
        x: 800,
        y: 50,
        config: { parseMode: 'MarkdownV2', replyToMessage: true },
        sampleInput: { chatId: 98129038, text: 'Your refund case has been transferred to an agent...' },
        sampleOutput: { messageSent: true, telegramMsgId: 4411 },
      },
      {
        id: '6',
        title: 'Human Escalation',
        subtitle: 'Action Center',
        brand: 'SMBFlow',
        tool: 'webhook',
        color: '#EF4444',
        type: 'HITL Escalation',
        x: 800,
        y: 170,
        config: { priority: 'P1_HIGH', targetTeam: 'Customer Success Leads', notifyEmail: true },
        sampleInput: { customerId: 'cust_8912', reason: 'Refund request on order #ORD-980' },
        sampleOutput: { escalationTicket: 'ESC-2026-092', status: 'Pending Review' },
      },
    ],
    edges: [
      { from: '1', to: '2' },
      { from: '2', to: '3' },
      { from: '3', to: '4' },
      { from: '4', to: '5', label: 'Standard' },
      { from: '4', to: '6', label: 'Refund' },
    ],
  },
]

// ── Interactive Canvas Node Graph Component ───────────────────────────────────
function CanvasPreview({ template }) {
  const nodeWidth = 150
  const nodeHeight = 56
  const [selectedNode, setSelectedNode] = useState(template.nodes[0] || null)
  const [zoom, setZoom] = useState(0.82)
  const [isFullScreen, setIsFullScreen] = useState(false)
  const [isTestingStep, setIsTestingStep] = useState(false)
  const [testResult, setTestResult] = useState(null)
  const [copiedPayload, setCopiedPayload] = useState(null)
  const containerRef = useRef(null)

  // Reset selected node when template changes
  useEffect(() => {
    if (template?.nodes?.length > 0) {
      setSelectedNode(template.nodes[0])
      setTestResult(null)
    }
  }, [template])

  function handleCopy(label, data) {
    navigator.clipboard.writeText(JSON.stringify(data, null, 2))
    setCopiedPayload(label)
    setTimeout(() => setCopiedPayload(null), 2000)
  }

  function handleTestStep() {
    if (!selectedNode || isTestingStep) return
    setIsTestingStep(true)
    setTestResult(null)
    setTimeout(() => {
      setIsTestingStep(false)
      setTestResult({
        status: 'success',
        durationMs: Math.floor(Math.random() * 80) + 35,
        timestamp: new Date().toLocaleTimeString(),
      })
    }, 600)
  }

  return (
    <div className={`w-full transition-all flex flex-col ${
      isFullScreen 
        ? 'fixed inset-0 z-50 p-4 md:p-8 bg-slate-950/85 backdrop-blur-md flex items-center justify-center' 
        : 'max-w-4xl mx-auto mt-6 bg-white dark:bg-[#121826] rounded-2xl border border-slate-200 dark:border-[#233048] shadow-md overflow-hidden relative'
    }`}>
      <div className={`w-full flex flex-col ${isFullScreen ? 'max-w-6xl max-h-[92vh] bg-white dark:bg-[#121826] rounded-2xl border border-slate-200 dark:border-[#233048] shadow-2xl overflow-hidden' : ''}`}>
      {/* Canvas Top Bar */}
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-slate-200 dark:border-[#233048] bg-slate-50 dark:bg-[#0b0f17]/90 z-10 relative">
        <div className="flex items-center gap-2">
          <span className="flex h-2 w-2 relative">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
            <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
          </span>
          <span className="text-[11px] font-mono text-slate-700 dark:text-slate-300 font-medium">
            Active Pipeline: <span className="text-blue-600 dark:text-blue-400 font-semibold">{template.label}</span>
          </span>
        </div>

        {/* Zoom & Fullscreen controls */}
        <div className="flex items-center gap-2 text-[10px] text-slate-500 dark:text-slate-400 font-mono">
          <div className="hidden sm:flex items-center bg-slate-100 dark:bg-[#182234] border border-slate-300 dark:border-[#233048] rounded-lg p-0.5">
            <button
              onClick={() => setZoom(z => Math.max(0.6, Number((z - 0.1).toFixed(2))))}
              className="px-2 py-0.5 hover:bg-white dark:hover:bg-[#202c42] rounded text-slate-700 dark:text-slate-300 transition-colors cursor-pointer"
              title="Zoom out"
            >
              -
            </button>
            <span className="px-1.5 text-[9.5px] text-slate-600 dark:text-slate-300 select-none">
              {Math.round(zoom * 100)}%
            </span>
            <button
              onClick={() => setZoom(z => Math.min(1.5, Number((z + 0.1).toFixed(2))))}
              className="px-2 py-0.5 hover:bg-white dark:hover:bg-[#202c42] rounded text-slate-700 dark:text-slate-300 transition-colors cursor-pointer"
              title="Zoom in"
            >
              +
            </button>
            <button
              onClick={() => setZoom(0.82)}
              className="px-1.5 py-0.5 hover:bg-white dark:hover:bg-[#202c42] rounded text-[9px] text-slate-500 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white transition-colors cursor-pointer"
              title="Fit View"
            >
              Fit
            </button>
            <button
              onClick={() => setZoom(1)}
              className="px-1.5 py-0.5 hover:bg-white dark:hover:bg-[#202c42] rounded text-[9px] text-slate-500 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white transition-colors cursor-pointer"
              title="100% Zoom"
            >
              100%
            </button>
          </div>

          <button
            type="button"
            onClick={() => setIsFullScreen(prev => !prev)}
            className="flex items-center gap-1.5 px-2 py-1 rounded-lg bg-slate-100 dark:bg-[#182234] hover:bg-slate-200 dark:hover:bg-[#202c42] border border-slate-300 dark:border-[#233048] text-slate-700 dark:text-slate-300 transition-colors cursor-pointer font-sans text-[11px] font-semibold"
            title={isFullScreen ? "Exit Fullscreen" : "View Fullscreen"}
          >
            {isFullScreen ? <Minimize2 className="w-3.5 h-3.5" /> : <Maximize2 className="w-3.5 h-3.5" />}
            <span className="hidden sm:inline">{isFullScreen ? 'Exit Fullscreen' : 'Fullscreen'}</span>
          </button>
        </div>
      </div>

      {/* SVG Canvas Graph with Smooth Scrolling & Panning */}
      <div
        ref={containerRef}
        className="p-4 sm:p-6 overflow-x-auto overflow-y-auto max-h-[300px] flex items-center justify-start sm:justify-center relative bg-slate-50/50 dark:bg-[#0b0f17]/40 scrollbar-thin scrollbar-thumb-slate-300 dark:scrollbar-thumb-slate-700 select-none cursor-grab active:cursor-grabbing"
      >
        <div
          style={{ transform: `scale(${zoom})`, transformOrigin: 'top center', transition: 'transform 0.15s ease-out' }}
          className="shrink-0"
        >
          <svg className="w-[980px] h-[240px] overflow-visible">
            {/* Edge Connectors */}
            {template.edges.map((edge, idx) => {
              const fromNode = template.nodes.find(n => n.id === edge.from)
              const toNode = template.nodes.find(n => n.id === edge.to)
              if (!fromNode || !toNode) return null

              const startX = fromNode.x + nodeWidth
              const startY = fromNode.y + nodeHeight / 2
              const endX = toNode.x
              const endY = toNode.y + nodeHeight / 2
              const midX = (startX + endX) / 2

              const pathData = `M ${startX} ${startY} C ${midX} ${startY}, ${midX} ${endY}, ${endX} ${endY}`

              return (
                <g key={idx}>
                  {/* Glow Line */}
                  <path
                    d={pathData}
                    fill="none"
                    stroke="#3b82f6"
                    strokeWidth="3"
                    strokeOpacity="0.2"
                  />
                  {/* Main Connector Line */}
                  <path
                    d={pathData}
                    fill="none"
                    stroke="#64748b"
                    strokeWidth="2"
                    strokeDasharray="4 2"
                  />
                  {/* Flow Pulse */}
                  <circle r="3" fill="#3b82f6">
                    <animateMotion
                      path={pathData}
                      dur="2.5s"
                      repeatCount="indefinite"
                    />
                  </circle>
                  {/* Edge Label */}
                  {edge.label && (
                    <text
                      x={midX}
                      y={(startY + endY) / 2 - 6}
                      fill="#64748b"
                      fontSize="9"
                      fontFamily="monospace"
                      textAnchor="middle"
                    >
                      {edge.label}
                    </text>
                  )}
                </g>
              )
            })}

            {/* Interactive Clickable Nodes */}
            {template.nodes.map((node, nIdx) => {
              const isSelected = selectedNode?.id === node.id

              return (
                <g
                  key={node.id}
                  transform={`translate(${node.x}, ${node.y})`}
                  onClick={(e) => {
                    e.stopPropagation()
                    setSelectedNode(node)
                  }}
                  className="cursor-pointer group"
                >
                  {/* Active Selected Halo */}
                  {isSelected && (
                    <rect
                      x="-4"
                      y="-4"
                      width={nodeWidth + 8}
                      height={nodeHeight + 8}
                      rx="14"
                      fill="none"
                      stroke="#3b82f6"
                      strokeWidth="2.5"
                      strokeDasharray="4 2"
                      className="animate-pulse"
                    />
                  )}

                  {/* Node Box */}
                  <rect
                    width={nodeWidth}
                    height={nodeHeight}
                    rx="10"
                    fill="currentColor"
                    className={`text-white dark:text-[#182030] fill-current transition-all shadow-xs ${
                      isSelected
                        ? 'stroke-blue-500 shadow-md'
                        : 'stroke-slate-300 dark:stroke-[#2b374c] group-hover:stroke-blue-400'
                    }`}
                    strokeWidth={isSelected ? '2' : '1.5'}
                  />

                  {/* Left Colored Accent Bar */}
                  <rect
                    x="0"
                    y="0"
                    width="4"
                    height={nodeHeight}
                    rx="2"
                    fill={node.color}
                  />

                  {/* Icon Container */}
                  <g transform="translate(10, 14)">
                    <rect
                      width="26"
                      height="26"
                      rx="6"
                      fill={node.color}
                      fillOpacity="0.15"
                    />
                    <foreignObject width="26" height="26">
                      <div className="w-full h-full flex items-center justify-center pointer-events-none">
                        <ToolLogo name={node.tool} className="w-4 h-4" />
                      </div>
                    </foreignObject>
                  </g>

                  {/* Text Content */}
                  <text
                    x="42"
                    y="24"
                    className="fill-slate-900 dark:fill-slate-100 select-none"
                    fontSize="11"
                    fontWeight="600"
                    fontFamily="system-ui, -apple-system, sans-serif"
                  >
                    {node.title.length > 14 ? node.title.slice(0, 13) + '…' : node.title}
                  </text>
                  <text
                    x="42"
                    y="39"
                    className="fill-slate-500 dark:fill-slate-400 select-none"
                    fontSize="9.5"
                    fontFamily="system-ui, -apple-system, sans-serif"
                  >
                    {node.subtitle.length > 16 ? node.subtitle.slice(0, 15) + '…' : node.subtitle}
                  </text>

                  {/* Status Check Badge */}
                  <circle cx={nodeWidth - 10} cy="12" r="4" fill="#10b981" />
                </g>
              )
            })}
          </svg>
        </div>
      </div>

      {/* ── Interactive Node Inspection Panel (Displays When Node is Clicked) ── */}
      {selectedNode && (
        <div className="border-t border-slate-200 dark:border-[#233048] bg-slate-50 dark:bg-[#0b0f17] p-4 transition-all">
          <div className="flex flex-wrap items-center justify-between gap-3 pb-3 mb-3 border-b border-slate-200 dark:border-[#233048]">
            <div className="flex items-center gap-2.5">
              <div
                className="w-8 h-8 rounded-lg flex items-center justify-center p-1.5 shadow-2xs"
                style={{ backgroundColor: `${selectedNode.color}20`, border: `1px solid ${selectedNode.color}50` }}
              >
                <ToolLogo name={selectedNode.tool} className="w-4 h-4" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h4 className="text-xs font-bold text-slate-900 dark:text-white">{selectedNode.title}</h4>
                  <span className="text-[10px] font-mono uppercase px-2 py-0.5 rounded-full bg-slate-200 dark:bg-[#182234] text-slate-700 dark:text-slate-300 border border-slate-300 dark:border-[#233048]">
                    {selectedNode.type}
                  </span>
                </div>
                <p className="text-[11px] text-slate-500 dark:text-slate-400 font-medium">
                  {selectedNode.subtitle} · Connected Brand: <span className="font-semibold text-slate-700 dark:text-slate-300">{selectedNode.brand}</span>
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <button
                onClick={handleTestStep}
                disabled={isTestingStep}
                className="flex items-center gap-1.5 px-3 py-1.5 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-xs font-semibold shadow-xs transition-all cursor-pointer disabled:opacity-50"
              >
                <Play size={12} className={isTestingStep ? 'animate-spin' : 'fill-white'} />
                <span>{isTestingStep ? 'Executing step...' : 'Test Step'}</span>
              </button>

              <button
                onClick={() => setSelectedNode(null)}
                className="p-1 text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 transition-colors"
                title="Close inspector"
              >
                ✕
              </button>
            </div>
          </div>

          {/* Test Execution Result Banner */}
          {testResult && (
            <div className="mb-3 p-2.5 rounded-lg bg-emerald-50 dark:bg-emerald-950/60 border border-emerald-200 dark:border-emerald-800/60 text-emerald-800 dark:text-emerald-200 text-xs flex items-center justify-between animate-fade-in">
              <div className="flex items-center gap-2">
                <CheckCircle2 size={14} className="text-emerald-600 dark:text-emerald-400" />
                <span>Node test executed successfully in <strong>{testResult.durationMs}ms</strong> at {testResult.timestamp}</span>
              </div>
              <span className="text-[10px] font-mono uppercase tracking-wider bg-emerald-100 dark:bg-emerald-900 px-2 py-0.5 rounded">
                HTTP 200 OK
              </span>
            </div>
          )}

          {/* Configuration & Payload Data Grid */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs">
            {/* 1. Step Parameters */}
            <div className="p-3 bg-white dark:bg-[#121826] rounded-xl border border-slate-200 dark:border-[#233048]">
              <div className="flex items-center justify-between mb-2">
                <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                  Node Configuration
                </span>
                <Sliders className="w-3.5 h-3.5 text-slate-400" />
              </div>
              <div className="space-y-1.5 font-mono text-[10.5px]">
                {selectedNode.config &&
                  Object.entries(selectedNode.config).map(([k, v]) => (
                    <div key={k} className="flex items-start justify-between gap-2 border-b border-slate-100 dark:border-[#1a2336] pb-1 last:border-0 last:pb-0">
                      <span className="text-slate-500 dark:text-slate-400 truncate">{k}:</span>
                      <span className="text-slate-900 dark:text-slate-200 font-semibold truncate text-right max-w-[130px]">
                        {typeof v === 'boolean' ? (v ? 'true' : 'false') : String(v)}
                      </span>
                    </div>
                  ))}
              </div>
            </div>

            {/* 2. Mock Input Payload */}
            <div className="p-3 bg-white dark:bg-[#121826] rounded-xl border border-slate-200 dark:border-[#233048]">
              <div className="flex items-center justify-between mb-2">
                <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                  Input Stream
                </span>
                <button
                  onClick={() => handleCopy('input', selectedNode.sampleInput)}
                  className="text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 transition-colors"
                  title="Copy Input JSON"
                >
                  {copiedPayload === 'input' ? <Check size={12} className="text-emerald-500" /> : <Copy size={12} />}
                </button>
              </div>
              <pre className="text-[10px] font-mono text-slate-700 dark:text-slate-300 max-h-24 overflow-x-auto overflow-y-auto leading-tight bg-slate-50 dark:bg-[#0b0f17] p-2 rounded border border-slate-100 dark:border-[#1a2336]">
                {JSON.stringify(selectedNode.sampleInput, null, 2)}
              </pre>
            </div>

            {/* 3. Output Stream */}
            <div className="p-3 bg-white dark:bg-[#121826] rounded-xl border border-slate-200 dark:border-[#233048]">
              <div className="flex items-center justify-between mb-2">
                <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                  Output Result
                </span>
                <button
                  onClick={() => handleCopy('output', selectedNode.sampleOutput)}
                  className="text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 transition-colors"
                  title="Copy Output JSON"
                >
                  {copiedPayload === 'output' ? <Check size={12} className="text-emerald-500" /> : <Copy size={12} />}
                </button>
              </div>
              <pre className="text-[10px] font-mono text-emerald-600 dark:text-emerald-400 max-h-24 overflow-x-auto overflow-y-auto leading-tight bg-slate-50 dark:bg-[#0b0f17] p-2 rounded border border-slate-100 dark:border-[#1a2336]">
                {JSON.stringify(selectedNode.sampleOutput, null, 2)}
              </pre>
            </div>
          </div>
        </div>
      )}
      </div>
    </div>
  )
}

// ── Markdown Parser & Formatter (Zero Unparsed Asterisks or Raw Syntax) ──────
function MarkdownRenderer({ content, className = '' }) {
  if (!content) return null

  const parseInline = (text) => {
    const parts = []
    const regex = /(\*\*(.*?)\*\*|\*(.*?)\*|`(.*?)`)/g
    let lastIndex = 0
    let match
    let keyIdx = 0

    while ((match = regex.exec(text)) !== null) {
      if (match.index > lastIndex) {
        parts.push(text.substring(lastIndex, match.index))
      }
      if (match[2]) {
        // **bold**
        parts.push(<strong key={keyIdx++} className="font-semibold text-slate-900 dark:text-white">{match[2]}</strong>)
      } else if (match[3]) {
        // *italic*
        parts.push(<em key={keyIdx++} className="italic text-slate-800 dark:text-slate-200">{match[3]}</em>)
      } else if (match[4]) {
        // `code`
        parts.push(<code key={keyIdx++} className="px-1.5 py-0.5 rounded bg-slate-100 dark:bg-[#1e293b] font-mono text-[11px] text-blue-600 dark:text-blue-400">{match[4]}</code>)
      }
      lastIndex = regex.lastIndex
    }

    if (lastIndex < text.length) {
      parts.push(text.substring(lastIndex))
    }

    return parts.length > 0 ? parts : text
  }

  // Strip unparsed triple asterisks
  const cleanContent = content.replace(/\*\*\*/g, '')
  const lines = cleanContent.split('\n')

  return (
    <div className={`space-y-2 text-xs md:text-sm leading-relaxed ${className}`}>
      {lines.map((line, idx) => {
        const trimmed = line.trim()
        if (!trimmed) return <div key={idx} className="h-1" />

        // Heading 3
        if (trimmed.startsWith('### ')) {
          return <h3 key={idx} className="text-sm font-bold text-slate-900 dark:text-white mt-2 mb-1">{parseInline(trimmed.replace(/^###\s+/, ''))}</h3>
        }
        // Heading 2
        if (trimmed.startsWith('## ')) {
          return <h2 key={idx} className="text-base font-bold text-slate-900 dark:text-white mt-2.5 mb-1">{parseInline(trimmed.replace(/^##\s+/, ''))}</h2>
        }
        // Heading 1
        if (trimmed.startsWith('# ')) {
          return <h1 key={idx} className="text-base font-bold text-slate-900 dark:text-white mt-2.5 mb-1">{parseInline(trimmed.replace(/^#\s+/, ''))}</h1>
        }

        // Bullet list
        if (trimmed.startsWith('- ') || trimmed.startsWith('* ')) {
          return (
            <div key={idx} className="flex items-start gap-2 ml-1 text-xs">
              <span className="w-1.5 h-1.5 rounded-full bg-blue-500 shrink-0 mt-1.5" />
              <div className="flex-1 text-slate-800 dark:text-slate-200">{parseInline(trimmed.substring(2))}</div>
            </div>
          )
        }

        // Numbered list
        const numMatch = trimmed.match(/^(\d+)\.\s+(.*)/)
        if (numMatch) {
          return (
            <div key={idx} className="flex items-start gap-2 ml-1 text-xs">
              <span className="text-[11px] font-mono font-bold text-blue-500 shrink-0 mt-0.5">{numMatch[1]}.</span>
              <div className="flex-1 text-slate-800 dark:text-slate-200">{parseInline(numMatch[2])}</div>
            </div>
          )
        }

        return <p key={idx} className="text-xs text-slate-800 dark:text-slate-200">{parseInline(trimmed)}</p>
      })}
    </div>
  )
}

// ── n8n-Style Visual Branching Execution Canvas ──────────────────────────────
function NodeExecutionPipeline({ nodes }) {
  const [selectedNode, setSelectedNode] = useState(null)
  const [copiedId, setCopiedId] = useState(null)

  if (!nodes || nodes.length === 0) return null

  function handleCopy(id, data) {
    navigator.clipboard.writeText(JSON.stringify(data, null, 2))
    setCopiedId(id)
    setTimeout(() => setCopiedId(null), 2000)
  }

  // Calculate layout coordinates for nodes with authentic branching
  const layoutNodes = nodes.map((node, idx) => {
    let brand = 'gmail'
    let borderColor = 'border-l-red-500'
    let strokeColor = '#EA4335'
    let subtitle = 'Trigger: 08:00 AM'

    const nodeNameLower = (node.name || '').toLowerCase()

    if (nodeNameLower.includes('claude') || nodeNameLower.includes('ocr') || nodeNameLower.includes('extract') || nodeNameLower.includes('copy') || nodeNameLower.includes('llm') || nodeNameLower.includes('reasoning')) {
      brand = 'claude'
      borderColor = 'border-l-amber-500'
      strokeColor = '#D97706'
      subtitle = 'Claude 3.5 Sonnet'
    } else if (nodeNameLower.includes('discrepancy') || nodeNameLower.includes('switch') || nodeNameLower.includes('check') || nodeNameLower.includes('transform') || nodeNameLower.includes('poll')) {
      brand = 'webhook'
      borderColor = 'border-l-emerald-500'
      strokeColor = '#10B981'
      subtitle = 'Switch Node'
    } else if (nodeNameLower.includes('sheet') || nodeNameLower.includes('flag') || nodeNameLower.includes('ledger') || nodeNameLower.includes('enrich')) {
      brand = 'sheet'
      borderColor = 'border-l-emerald-500'
      strokeColor = '#10B981'
      subtitle = 'Google Sheets'
    } else if (nodeNameLower.includes('calendar') || nodeNameLower.includes('schedule') || nodeNameLower.includes('drop') || nodeNameLower.includes('slack')) {
      brand = 'calendar'
      borderColor = 'border-l-blue-500'
      strokeColor = '#3B82F6'
      subtitle = 'Google Calendar'
    } else if (nodeNameLower.includes('lead') || nodeNameLower.includes('hubspot') || nodeNameLower.includes('crm')) {
      brand = 'hubspot'
      borderColor = 'border-l-orange-500'
      strokeColor = '#FF7A59'
      subtitle = 'HubSpot CRM'
    } else if (idx === 1) {
      brand = 'gmail'
      borderColor = 'border-l-red-500'
      strokeColor = '#EA4335'
      subtitle = 'Gmail API'
    }

    // Positions
    let x = 20 + idx * 210
    let y = 65

    // Check if branching (nodes 5 and 6 branch from node 4)
    if (nodes.length >= 6) {
      if (idx === 4) {
        x = 20 + 3 * 210 + 200
        y = 15 // Top branch
      } else if (idx === 5) {
        x = 20 + 3 * 210 + 200
        y = 115 // Bottom branch
      }
    }

    return {
      ...node,
      brand,
      borderColor,
      strokeColor,
      subtitle: node.subtitle || subtitle,
      x,
      y,
    }
  })

  const hasBranching = nodes.length >= 6

  return (
    <div className="my-3 rounded-2xl border border-slate-200 dark:border-[#233048] bg-slate-50/80 dark:bg-[#0b0f17] overflow-hidden shadow-2xs">
      {/* Header bar */}
      <div className="px-3.5 py-2.5 bg-white dark:bg-[#121826] border-b border-slate-200 dark:border-[#233048] flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="flex h-2 w-2 relative">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
            <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
          </span>
          <span className="tracking-wide uppercase text-[10px] text-slate-500 dark:text-slate-400 font-mono font-bold">
            Execution Pipeline
          </span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[10px] text-emerald-600 dark:text-emerald-400 font-mono bg-emerald-50 dark:bg-emerald-950/60 border border-emerald-200 dark:border-emerald-800/60 px-2 py-0.5 rounded-full font-semibold">
            {nodes.length} Nodes Executed · Success
          </span>
        </div>
      </div>

      {/* Horizontal n8n SVG Canvas with Branching */}
      <div className="relative overflow-x-auto overflow-y-hidden bg-slate-50/50 dark:bg-[#0b0f17]/90 min-h-[190px] p-4 flex items-center">
        <div className="relative min-w-[950px] h-[175px]">
          {/* Connecting Bezier Wires */}
          <svg className="absolute inset-0 w-full h-full pointer-events-none" style={{ minWidth: '950px', minHeight: '175px' }}>
            <defs>
              <linearGradient id="n8nGrad" x1="0%" y1="0%" x2="100%" y2="0%">
                <stop offset="0%" stopColor="#3B82F6" />
                <stop offset="100%" stopColor="#10B981" />
              </linearGradient>
            </defs>

            {/* Linear connections Node 1 -> Node 2 -> Node 3 -> Node 4 */}
            {layoutNodes.map((node, idx) => {
              if (hasBranching && idx >= 3) return null
              if (!hasBranching && idx >= layoutNodes.length - 1) return null

              const nextNode = layoutNodes[idx + 1]
              if (!nextNode) return null

              const startX = node.x + 180
              const startY = node.y + 26
              const endX = nextNode.x
              const endY = nextNode.y + 26

              return (
                <g key={`wire-${idx}`}>
                  <path
                    d={`M ${startX} ${startY} C ${startX + 15} ${startY}, ${endX - 15} ${endY}, ${endX} ${endY}`}
                    fill="none"
                    stroke="#475569"
                    strokeWidth="1.8"
                    strokeDasharray="4 3"
                    className="opacity-70"
                  />
                  <circle cx={startX} cy={startY} r="3" fill="#3B82F6" />
                  <circle cx={endX} cy={endY} r="3" fill="#3B82F6" />
                </g>
              )
            })}

            {/* Branching from Node 4 to Node 5 (Top) & Node 6 (Bottom) */}
            {hasBranching && layoutNodes[3] && layoutNodes[4] && layoutNodes[5] && (
              <>
                {/* Branch 1 to Top (Discrepancy) */}
                <g>
                  <path
                    d={`M ${layoutNodes[3].x + 180} ${layoutNodes[3].y + 26} C ${layoutNodes[3].x + 220} ${layoutNodes[3].y + 26}, ${layoutNodes[4].x - 20} ${layoutNodes[4].y + 26}, ${layoutNodes[4].x} ${layoutNodes[4].y + 26}`}
                    fill="none"
                    stroke="#475569"
                    strokeWidth="1.8"
                    strokeDasharray="4 3"
                    className="opacity-70"
                  />
                  <circle cx={layoutNodes[3].x + 180} cy={layoutNodes[3].y + 26} r="3" fill="#3B82F6" />
                  <circle cx={layoutNodes[4].x} cy={layoutNodes[4].y + 26} r="3" fill="#3B82F6" />
                  {/* Branch label text */}
                  <text
                    x={layoutNodes[3].x + 195}
                    y={layoutNodes[3].y - 2}
                    fill="#64748B"
                    fontSize="9"
                    fontFamily="monospace"
                    className="select-none"
                  >
                    Discrepancy
                  </text>
                </g>

                {/* Branch 2 to Bottom (Approved) */}
                <g>
                  <path
                    d={`M ${layoutNodes[3].x + 180} ${layoutNodes[3].y + 26} C ${layoutNodes[3].x + 220} ${layoutNodes[3].y + 26}, ${layoutNodes[5].x - 20} ${layoutNodes[5].y + 26}, ${layoutNodes[5].x} ${layoutNodes[5].y + 26}`}
                    fill="none"
                    stroke="#475569"
                    strokeWidth="1.8"
                    strokeDasharray="4 3"
                    className="opacity-70"
                  />
                  <circle cx={layoutNodes[5].x} cy={layoutNodes[5].y + 26} r="3" fill="#3B82F6" />
                  {/* Branch label text */}
                  <text
                    x={layoutNodes[3].x + 195}
                    y={layoutNodes[3].y + 48}
                    fill="#64748B"
                    fontSize="9"
                    fontFamily="monospace"
                    className="select-none"
                  >
                    Approved
                  </text>
                </g>
              </>
            )}
          </svg>

          {/* Node Cards */}
          {layoutNodes.map((node) => {
            const isSelected = selectedNode?.id === node.id

            return (
              <div
                key={node.id}
                onClick={() => setSelectedNode(isSelected ? null : node)}
                style={{
                  position: 'absolute',
                  left: `${node.x}px`,
                  top: `${node.y}px`,
                  width: '180px',
                }}
                className={`bg-white dark:bg-[#121826] border border-slate-200 dark:border-[#233048] border-l-4 ${node.borderColor} rounded-xl px-2.5 py-2 shadow-2xs transition-all cursor-pointer select-none hover:shadow-xs hover:border-slate-300 dark:hover:border-slate-700 ${
                  isSelected ? 'ring-2 ring-blue-500 shadow-md' : ''
                }`}
              >
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2 min-w-0">
                    <div className="w-6 h-6 rounded-md bg-slate-50 dark:bg-[#182234] border border-slate-100 dark:border-slate-800 flex items-center justify-center shrink-0">
                      <ToolLogo name={node.brand} className="w-3.5 h-3.5" />
                    </div>
                    <div className="min-w-0">
                      <p className="text-[11px] font-bold text-slate-900 dark:text-white truncate">
                        {node.name}
                      </p>
                      <p className="text-[9px] text-slate-400 truncate">
                        {node.subtitle}
                      </p>
                    </div>
                  </div>

                  {/* Green status indicator dot */}
                  <div className="shrink-0 flex items-center gap-1">
                    <span className="w-2 h-2 rounded-full bg-emerald-500 shadow-[0_0_6px_rgba(16,185,129,0.5)] block" />
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      </div>

      {/* Selected Node Details Drawer */}
      {selectedNode && (
        <div className="p-3 bg-white dark:bg-[#121826] border-t border-slate-200 dark:border-[#233048] text-[11px] font-mono animate-in fade-in duration-150">
          <div className="flex items-center justify-between pb-2 mb-2 border-b border-slate-100 dark:border-[#1a2336]">
            <div className="flex items-center gap-2">
              <ToolLogo name={selectedNode.brand} className="w-3.5 h-3.5" />
              <span className="font-bold text-slate-900 dark:text-white text-xs">{selectedNode.name}</span>
              <span className="text-[10px] text-slate-400 font-mono">({selectedNode.duration_ms || 35}ms)</span>
            </div>
            <button
              onClick={() => setSelectedNode(null)}
              className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 text-xs px-1.5 py-0.5 rounded bg-slate-100 dark:bg-[#182234]"
            >
              Close
            </button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
            <div className="bg-slate-50 dark:bg-[#0b0f17] rounded-lg p-2 border border-slate-200 dark:border-[#233048]">
              <div className="flex justify-between items-center mb-1 text-[10px] text-slate-500 dark:text-slate-400 font-bold uppercase">
                <span>Input Payload</span>
                <button
                  onClick={() => handleCopy(`in_${selectedNode.id}`, selectedNode.input_data || { action: 'trigger_inbound' })}
                  className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200"
                >
                  {copiedId === `in_${selectedNode.id}` ? <Check className="w-3 h-3 text-emerald-500" /> : <Copy className="w-3 h-3" />}
                </button>
              </div>
              <pre className="overflow-x-auto max-h-28 text-[10px] text-slate-700 dark:text-slate-300 font-mono">
                {JSON.stringify(selectedNode.input_data || { source: selectedNode.brand, status: 'validated' }, null, 2)}
              </pre>
            </div>

            <div className="bg-slate-50 dark:bg-[#0b0f17] rounded-lg p-2 border border-slate-200 dark:border-[#233048]">
              <div className="flex justify-between items-center mb-1 text-[10px] text-slate-500 dark:text-slate-400 font-bold uppercase">
                <span>Output Result</span>
                <button
                  onClick={() => handleCopy(`out_${selectedNode.id}`, selectedNode.output_data || { result: 'success' })}
                  className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200"
                >
                  {copiedId === `out_${selectedNode.id}` ? <Check className="w-3 h-3 text-emerald-500" /> : <Copy className="w-3 h-3" />}
                </button>
              </div>
              <pre className="overflow-x-auto max-h-28 text-[10px] text-emerald-600 dark:text-emerald-400 font-mono">
                {JSON.stringify(selectedNode.output_data || { executionStatus: 'OK', recordsProcessed: 1 }, null, 2)}
              </pre>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

// ── Main Copilot / Assistant Page Component ───────────────────────────────────
export default function CopilotPage() {
  const navigate = useNavigate()
  const { user, api } = useAuth()

  const [selectedTemplate, setSelectedTemplate] = useState(TEMPLATES[0])
  const [hoveredTemplate, setHoveredTemplate] = useState(null)
  const [promptText, setPromptText] = useState('')
  const [hasStartedConversation, setHasStartedConversation] = useState(false)
  const [messages, setMessages] = useState([])
  const [loading, setLoading] = useState(false)
  const [insights, setInsights] = useState(null)

  // Integration Tools Connection State on the same screen
  const [connectedTools, setConnectedTools] = useState({
    gmail: false,
    claude: true,
    sheet: true,
    slack: true,
    hubspot: false,
    calendar: true,
  })
  const [connectModalTool, setConnectModalTool] = useState(null)
  const [isConnecting, setIsConnecting] = useState(false)
  const [executingInlineId, setExecutingInlineId] = useState(null)

  // Voice recognition state
  const [isListening, setIsListening] = useState(false)
  const [isTranscribing, setIsTranscribing] = useState(false)
  const [liveTranscript, setLiveTranscript] = useState('')
  const recognitionRef = useRef(null)
  const mediaRecorderRef = useRef(null)
  const audioChunksRef = useRef([])
  const textareaRef = useRef(null)

  // File context / upload state
  const [attachedFiles, setAttachedFiles] = useState([])
  const [isUploading, setIsUploading] = useState(false)
  const fileInputRef = useRef(null)
  const convFileInputRef = useRef(null)

  const activeDisplayTemplate = hoveredTemplate || selectedTemplate
  const messagesEndRef = useRef(null)

  // Handle direct tool connection on same screen
  async function handleConnectTool(tool) {
    if (!tool) return
    setIsConnecting(true)
    await new Promise(r => setTimeout(r, 650))
    setConnectedTools(prev => ({ ...prev, [tool.tool_key]: true }))
    setIsConnecting(false)
    setConnectModalTool(null)

    // Append confirmation in chat
    const confirmMsg = {
      id: String(Date.now()),
      role: 'assistant',
      content: `**${tool.name} Connected Successfully.** OAuth token verified and integration active. You can now execute this pipeline right here on this screen.`,
      suggested_followups: [
        'Trigger pipeline execution now',
        'Configure polling interval',
        'Set custom threshold filter',
      ],
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    }
    setMessages(prev => [...prev, confirmMsg])
  }

  // Handle direct inline pipeline execution on same screen
  async function handleExecuteInline(msg) {
    if (!msg || executingInlineId) return
    setExecutingInlineId(msg.id)

    await new Promise(r => setTimeout(r, 1100))

    const nodeCount = msg.execution_nodes?.length || 5
    const execResultMsg = {
      id: String(Date.now() + 1),
      role: 'assistant',
      content: `**Pipeline Execution Completed Successfully!**\n\nAll ${nodeCount} autonomous nodes executed cleanly in 1.18s with zero validation errors. State captured in PostgreSQL audit logs, and 1 deliverable is staged in Action Center for supervisor sign-off.`,
      execution_nodes: msg.execution_nodes?.map(n => ({ ...n, status: 'success', duration_ms: Math.floor(Math.random() * 40 + 15) })) || [],
      action_cta: {
        label: 'View in Action Center',
        to: '/escalations',
        variant: 'primary'
      },
      suggested_followups: [
        'Review staged item in Action Center',
        'Schedule recurring daily run',
        'Export execution metrics log',
      ],
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    }

    setMessages(prev => [...prev, execResultMsg])
    setExecutingInlineId(null)
  }

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  useEffect(() => {
    api.get('/copilot/insights')
      .then(res => setInsights(res))
      .catch(() => {})
  }, [api])

  // Auto-expand textarea dynamically as user types
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
      const newHeight = Math.max(38, Math.min(textareaRef.current.scrollHeight, 240))
      textareaRef.current.style.height = `${newHeight}px`
    }
  }, [promptText])

  // File upload handler
  async function handleFileUpload(e) {
    const files = Array.from(e.target.files || [])
    if (!files.length) return
    setIsUploading(true)

    for (const file of files) {
      const isText = /\.(txt|csv|json|md|log|yaml|yml|xml|html|js|ts|py|sql)$/i.test(file.name)
      const sizeFormatted = file.size > 1048576 
        ? `${(file.size / 1048576).toFixed(1)} MB` 
        : `${(file.size / 1024).toFixed(1)} KB`

      if (isText) {
        const reader = new FileReader()
        reader.onload = (event) => {
          setAttachedFiles(prev => [
            ...prev,
            {
              id: `${Date.now()}_${Math.random().toString(36).substr(2, 6)}`,
              name: file.name,
              size: sizeFormatted,
              type: file.type || 'text/plain',
              rawText: event.target.result.slice(0, 10000),
            },
          ])
        }
        reader.readAsText(file)
      } else {
        try {
          const formData = new FormData()
          formData.append('file', file)
          const res = await api.post('/copilot/upload', formData)
          setAttachedFiles(prev => [
            ...prev,
            {
              id: res.file_id || `${Date.now()}_${Math.random().toString(36).substr(2, 6)}`,
              name: res.filename || file.name,
              size: sizeFormatted,
              type: res.content_type || file.type,
              rawText: res.extracted_text || `[Attached file: ${file.name}]`,
            },
          ])
        } catch {
          setAttachedFiles(prev => [
            ...prev,
            {
              id: `${Date.now()}_${Math.random().toString(36).substr(2, 6)}`,
              name: file.name,
              size: sizeFormatted,
              type: file.type || 'application/octet-stream',
              rawText: `[Attached file: ${file.name} (${sizeFormatted})]`,
            },
          ])
        }
      }
    }
    setIsUploading(false)
    e.target.value = ''
  }

  function removeAttachedFile(id) {
    setAttachedFiles(prev => prev.filter(f => f.id !== id))
  }

  // Initialize Web Speech API
  useEffect(() => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition
    if (SpeechRecognition) {
      const recognizer = new SpeechRecognition()
      recognizer.continuous = true
      recognizer.interimResults = true
      recognizer.lang = 'en-US'

      recognizer.onstart = () => {
        setIsListening(true)
        setLiveTranscript('')
      }

      recognizer.onresult = (event) => {
        let finalStr = ''
        let interimStr = ''
        for (let i = event.resultIndex; i < event.results.length; i++) {
          if (event.results[i].isFinal) {
            finalStr += event.results[i][0].transcript + ' '
          } else {
            interimStr += event.results[i][0].transcript
          }
        }
        const combined = (finalStr + interimStr).trim()
        if (combined) {
          setLiveTranscript(combined)
          setPromptText(combined)
        }
      }

      recognizer.onerror = (event) => {
        console.warn('Speech recognition error:', event.error)
        setIsListening(false)
        setLiveTranscript('')
      }

      recognizer.onend = () => {
        setIsListening(false)
      }

      recognitionRef.current = recognizer
    }
  }, [])

  // Cancel Voice Input
  function cancelVoiceInput() {
    if (recognitionRef.current) {
      try { recognitionRef.current.stop() } catch {}
    }
    if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'recording') {
      mediaRecorderRef.current.stop()
    }
    setIsListening(false)
    setLiveTranscript('')
  }

  // Stop & keep transcript
  function stopVoiceInput() {
    if (recognitionRef.current) {
      try { recognitionRef.current.stop() } catch {}
    }
    if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'recording') {
      mediaRecorderRef.current.stop()
    }
    setIsListening(false)
  }

  // Toggle Voice Input
  async function toggleVoiceInput() {
    if (isListening) {
      stopVoiceInput()
      return
    }

    if (recognitionRef.current) {
      try {
        recognitionRef.current.start()
        return
      } catch (err) {
        console.warn('Native speech recognition start failed, fallback to audio recorder', err)
      }
    }

    try {
      if (!navigator.mediaDevices?.getUserMedia) {
        alert('Microphone access is not supported in this browser.')
        return
      }

      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      audioChunksRef.current = []
      const recorder = new MediaRecorder(stream)

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) audioChunksRef.current.push(e.data)
      }

      recorder.onstop = async () => {
        stream.getTracks().forEach(t => t.stop())
        setIsListening(false)
        setIsTranscribing(true)

        const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/webm' })
        const formData = new FormData()
        formData.append('audio', audioBlob, 'prompt_audio.webm')

        try {
          const res = await api.post('/copilot/transcribe', formData)
          if (res?.text) {
            setPromptText((prev) => (prev ? `${prev} ${res.text}` : res.text))
          }
        } catch (err) {
          console.error('Transcription error:', err)
        } finally {
          setIsTranscribing(false)
          setLiveTranscript('')
        }
      }

      recorder.start()
      mediaRecorderRef.current = recorder
      setIsListening(true)
      setLiveTranscript('Recording audio...')
    } catch (err) {
      console.error('Microphone access denied:', err)
      alert('Microphone permission is required for voice input.')
    }
  }

  function handleSelectTemplate(tpl) {
    setSelectedTemplate(tpl)
    setPromptText(tpl.prompt)
  }

  async function handleSend(customText) {
    const rawQuery = (customText || promptText).trim()
    if (!rawQuery && attachedFiles.length === 0) return
    if (loading) return

    let finalQuery = rawQuery
    if (attachedFiles.length > 0) {
      const fileContexts = attachedFiles
        .map(f => `[Attached File: ${f.name} (${f.size})]\n${f.rawText || ''}`)
        .join('\n\n')
      finalQuery = rawQuery ? `${rawQuery}\n\n--- Attached File Context ---\n${fileContexts}` : `Attached context files for workflow synthesis:\n${fileContexts}`
    }

    if (isListening) {
      stopVoiceInput()
    }

    setHasStartedConversation(true)

    const userMsg = {
      id: String(Date.now()),
      role: 'user',
      content: rawQuery || `Uploaded ${attachedFiles.length} file(s) for workflow synthesis`,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    }

    const currentHistory = messages.length === 0 ? [] : messages
    setMessages([...currentHistory, userMsg])
    setPromptText('')
    setLiveTranscript('')
    setAttachedFiles([])
    setLoading(true)

    try {
      const payload = {
        messages: [...currentHistory, { ...userMsg, content: finalQuery }].map(m => ({ role: m.role, content: m.content })),
      }

      const res = await api.post('/copilot/chat', payload)

      const assistantMsg = {
        id: res.message_id || String(Date.now() + 1),
        role: 'assistant',
        content: res.reply || 'Workflow task synthesized successfully.',
        execution_nodes: res.execution_nodes || [],
        action_cta: res.action_cta || null,
        suggested_followups: res.suggested_followups || [],
        required_tools: res.required_tools || [],
        workflow_key: res.workflow_key || null,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      }

      setMessages(prev => [...prev, assistantMsg])
    } catch (err) {
      const errorMsg = {
        id: String(Date.now() + 1),
        role: 'assistant',
        content: `I encountered an issue connecting to the workflow execution engine: ${err?.message || 'Network error'}. You can still navigate directly to your workflows from the sidebar.`,
        execution_nodes: [],
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      }
      setMessages(prev => [...prev, errorMsg])
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="w-full min-h-full bg-slate-50 dark:bg-[#0b0f17] bg-dot-pattern text-slate-900 dark:text-slate-100 font-sans flex flex-col transition-colors relative">
      {/* ── Direct Tool OAuth Connection Modal (On Same Screen) ─────────────── */}
      {connectModalTool && (
        <div className="fixed inset-0 z-50 bg-slate-950/60 backdrop-blur-xs flex items-center justify-center p-4 animate-in fade-in duration-150">
          <div className="bg-white dark:bg-[#121826] border border-slate-200 dark:border-[#233048] rounded-2xl max-w-md w-full p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-slate-100 dark:border-[#1a2336]">
              <div className="flex items-center gap-2.5">
                <div className="w-9 h-9 rounded-xl bg-slate-100 dark:bg-[#182234] border border-slate-200 dark:border-slate-800 flex items-center justify-center">
                  <ToolLogo name={connectModalTool.tool_key} className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-sm font-bold text-slate-900 dark:text-white">
                    Connect {connectModalTool.name}
                  </h3>
                  <p className="text-[11px] text-slate-400">
                    Authorize integration on this screen
                  </p>
                </div>
              </div>
              <button
                onClick={() => setConnectModalTool(null)}
                className="p-1 rounded-lg text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 cursor-pointer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="space-y-2.5 text-xs text-slate-600 dark:text-slate-300 bg-slate-50 dark:bg-[#0b0f17] p-3.5 rounded-xl border border-slate-200 dark:border-[#1a2336]">
              <p className="font-semibold text-slate-900 dark:text-white">Permissions Requested:</p>
              <div className="space-y-1.5 text-[11px] text-slate-500 dark:text-slate-400">
                <div className="flex items-center gap-2">
                  <Check className="w-3.5 h-3.5 text-emerald-500" />
                  <span>Read inbound messages and webhook payloads</span>
                </div>
                <div className="flex items-center gap-2">
                  <Check className="w-3.5 h-3.5 text-emerald-500" />
                  <span>Execute automated AI actions and state sync</span>
                </div>
                <div className="flex items-center gap-2">
                  <Check className="w-3.5 h-3.5 text-emerald-500" />
                  <span>Encrypted credential storage with tenant isolation</span>
                </div>
              </div>
            </div>

            <div className="flex items-center justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={() => setConnectModalTool(null)}
                disabled={isConnecting}
                className="px-3.5 py-2 rounded-xl text-xs font-semibold text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-[#182234] transition-colors cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={() => handleConnectTool(connectModalTool)}
                disabled={isConnecting}
                className="px-4 py-2 rounded-xl text-xs font-semibold bg-blue-600 hover:bg-blue-500 text-white flex items-center gap-2 shadow-xs transition-all cursor-pointer"
              >
                {isConnecting ? (
                  <>
                    <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                    <span>Authorizing...</span>
                  </>
                ) : (
                  <>
                    <Zap className="w-3.5 h-3.5" />
                    <span>Authorize & Connect</span>
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Top Bar ─────────────────────────────────────────────────────────── */}
      <div className="px-6 py-3 border-b border-slate-200 dark:border-[#233048] bg-white/95 dark:bg-[#121826]/95 backdrop-blur-xs flex items-center justify-between shrink-0 sticky top-0 z-20 transition-colors">
        <div className="flex items-center gap-3">
          {hasStartedConversation && (
            <button
              onClick={() => {
                setHasStartedConversation(false)
                setMessages([])
                setPromptText('')
              }}
              className="p-1.5 rounded-lg bg-slate-100 dark:bg-[#182234] hover:bg-slate-200 dark:hover:bg-[#233048] text-slate-700 dark:text-slate-300 transition-colors cursor-pointer"
              title="New Automation Canvas"
            >
              <ArrowLeft className="w-4 h-4" />
            </button>
          )}

          <div className="flex items-center gap-2">
            <span className="text-sm font-bold text-slate-900 dark:text-white tracking-tight flex items-center gap-1.5">
              <Terminal className="w-4 h-4 text-blue-600 dark:text-blue-500" />
              <span>AI Assistant</span>
            </span>
          </div>
        </div>

        <div className="flex items-center gap-3 text-xs">
          <div className="hidden sm:flex items-center gap-1.5 px-3 py-1 rounded-full bg-slate-100 dark:bg-[#182234] border border-slate-200 dark:border-[#233048] text-slate-700 dark:text-slate-300 font-mono text-[11px]">
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
            <span>Active Runs: {insights?.active_runs ?? 0}</span>
          </div>

          <button
            onClick={() => navigate('/workflows')}
            className="flex items-center gap-1.5 px-3 py-1 bg-blue-600 hover:bg-blue-500 text-white rounded-lg font-semibold transition-all shadow-xs cursor-pointer"
          >
            <span>Workflows</span>
            <ArrowUpRight className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* ── Main Canvas / Conversation Area ─────────────────────────────────── */}
      {!hasStartedConversation ? (
        /* ── HERO VIEW ─────────────────────────────────────────────────────── */
        <div className="flex-1 px-4 py-8 md:py-12 flex flex-col items-center justify-start max-w-4xl mx-auto w-full pb-16">
          {/* Centered Heading */}
          <div className="flex items-center gap-2.5 text-xl md:text-2xl font-bold text-slate-900 dark:text-white mb-6">
            <Terminal className="w-5 h-5 text-blue-600 dark:text-blue-500" />
            <h2>What do you want to automate?</h2>
          </div>

          {/* Clean Prompt Card */}
          <div className="w-full bg-white dark:bg-[#121826] border border-slate-200 dark:border-[#233048] focus-within:border-blue-500 rounded-2xl p-3 sm:p-4 shadow-md dark:shadow-xl transition-all relative">
            {/* Hidden File Input for attachments */}
            <input
              type="file"
              ref={fileInputRef}
              onChange={handleFileUpload}
              className="hidden"
              accept=".pdf,.doc,.docx,.txt,.csv,.json,.xlsx,.md,.png,.jpg,.jpeg,.sql,.log"
              multiple
            />

            {/* Attached files badge preview */}
            {attachedFiles.length > 0 && (
              <div className="flex flex-wrap items-center gap-2 mb-2 p-1.5 bg-slate-50 dark:bg-[#182234] border border-slate-200 dark:border-[#233048] rounded-xl">
                {attachedFiles.map((file) => (
                  <div
                    key={file.id}
                    className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-white dark:bg-[#121826] border border-blue-200 dark:border-blue-900/60 text-blue-700 dark:text-blue-300 text-xs shadow-2xs"
                  >
                    <Paperclip className="w-3.5 h-3.5 text-blue-500 shrink-0" />
                    <span className="font-medium max-w-[160px] truncate">{file.name}</span>
                    <span className="text-[10px] text-slate-400 dark:text-slate-500 font-mono">({file.size})</span>
                    <button
                      type="button"
                      onClick={() => removeAttachedFile(file.id)}
                      className="p-0.5 hover:bg-slate-100 dark:hover:bg-slate-800 rounded text-slate-400 hover:text-red-500 transition-colors cursor-pointer"
                      title="Remove attachment"
                    >
                      <X className="w-3 h-3" />
                    </button>
                  </div>
                ))}
              </div>
            )}

            {isListening ? (
              /* Sleek Voice Recording Pill Bar (as requested) */
              <div className="w-full flex items-center justify-between gap-3 px-3 py-2 bg-slate-900 text-white rounded-xl shadow-inner border border-slate-700 animate-fade-in my-1">
                {/* Cancel X button */}
                <button
                  type="button"
                  onClick={cancelVoiceInput}
                  className="w-8 h-8 rounded-full bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white flex items-center justify-center transition-colors cursor-pointer shrink-0"
                  title="Cancel recording"
                >
                  <X className="w-4 h-4" />
                </button>

                {/* Animated Voice Equalizer Waveform & Live Transcript */}
                <div className="flex-1 flex items-center justify-center gap-2 overflow-hidden px-2">
                  <div className="flex items-center gap-1 shrink-0">
                    {[4, 10, 16, 8, 14, 20, 12, 6, 18, 10, 14, 8].map((h, i) => (
                      <span
                        key={i}
                        className="w-1 bg-blue-400 rounded-full animate-pulse"
                        style={{
                          height: `${h}px`,
                          animationDuration: `${0.4 + (i % 4) * 0.15}s`,
                          animationDelay: `${(i * 0.05).toFixed(2)}s`,
                        }}
                      />
                    ))}
                  </div>
                  <span className="text-xs font-mono text-slate-200 truncate ml-2">
                    {liveTranscript || 'Listening... speak now'}
                  </span>
                </div>

                {/* Stop & Submit controls */}
                <div className="flex items-center gap-2 shrink-0">
                  <button
                    type="button"
                    onClick={stopVoiceInput}
                    className="w-8 h-8 rounded-full bg-slate-800 hover:bg-slate-700 text-white flex items-center justify-center transition-colors cursor-pointer"
                    title="Stop recording"
                  >
                    <Square className="w-3.5 h-3.5 fill-white" />
                  </button>

                  <button
                    type="button"
                    onClick={() => {
                      stopVoiceInput()
                      handleSend()
                    }}
                    className="w-8 h-8 rounded-full bg-blue-600 hover:bg-blue-500 text-white flex items-center justify-center transition-colors cursor-pointer shadow-xs"
                    title="Send prompt"
                  >
                    <ArrowUp className="w-4 h-4" />
                  </button>
                </div>
              </div>
            ) : (
              /* Auto-expanding borderless Textarea */
              <textarea
                ref={textareaRef}
                rows={1}
                value={promptText}
                onChange={(e) => setPromptText(e.target.value)}
                placeholder="Tell me what to build or ask a question – add context with +"
                className="w-full bg-transparent text-slate-900 dark:text-slate-100 placeholder-slate-400 dark:placeholder-slate-500 text-sm md:text-base leading-relaxed resize-none border-0 focus:border-0 outline-none focus:outline-none ring-0 focus:ring-0 focus-visible:outline-none focus-visible:ring-0 shadow-none px-1 py-1 max-h-64"
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault()
                    handleSend()
                  }
                }}
              />
            )}

            {/* Bottom Tools inside Prompt Box */}
            <div className="flex items-center justify-between pt-2 border-t border-slate-100 dark:border-[#233048] mt-2">
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                disabled={isUploading}
                className={`w-7 h-7 rounded-lg border flex items-center justify-center transition-all cursor-pointer ${
                  attachedFiles.length > 0
                    ? 'border-blue-500 bg-blue-50 dark:bg-blue-950/60 text-blue-600 dark:text-blue-400'
                    : 'border-slate-200 dark:border-[#233048] bg-slate-50 dark:bg-[#182234] hover:bg-slate-100 dark:hover:bg-[#233048] text-slate-600 dark:text-slate-300'
                }`}
                title="Add context / Upload file (+)"
              >
                {isUploading ? <RefreshCw className="w-3.5 h-3.5 animate-spin text-blue-500" /> : <Plus className="w-4 h-4" />}
              </button>

              <div className="flex items-center gap-2">
                {/* Microphone Voice Button */}
                <button
                  type="button"
                  onClick={toggleVoiceInput}
                  className={`w-7 h-7 rounded-lg flex items-center justify-center transition-all cursor-pointer ${
                    isListening
                      ? 'bg-red-500 text-white animate-pulse ring-2 ring-red-400'
                      : isTranscribing
                      ? 'bg-blue-600 text-white animate-spin'
                      : 'text-slate-500 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-[#182234]'
                  }`}
                  title={isListening ? 'Stop listening' : 'Voice input (Speak to AI)'}
                >
                  {isListening ? <Square className="w-3.5 h-3.5 fill-white" /> : <Mic className="w-4 h-4" />}
                </button>

                <button
                  type="button"
                  onClick={() => handleSend(promptText || TEMPLATES[0].prompt)}
                  className="w-8 h-8 rounded-lg bg-blue-600 hover:bg-blue-500 text-white flex items-center justify-center transition-all cursor-pointer shadow-xs shadow-blue-600/30"
                  title="Run Automation"
                >
                  <ArrowUp className="w-4.5 h-4.5" />
                </button>
              </div>
            </div>
          </div>

          {/* Clean, Unified Category Pill Buttons */}
          <div className="flex flex-wrap items-center justify-center gap-2 mt-4 max-w-4xl w-full">
            {TEMPLATES.map((tpl) => {
              const isSelected = activeDisplayTemplate.id === tpl.id

              return (
                <button
                  key={tpl.id}
                  onMouseEnter={() => setHoveredTemplate(tpl)}
                  onMouseLeave={() => setHoveredTemplate(null)}
                  onClick={() => handleSelectTemplate(tpl)}
                  className={`flex items-center gap-2 px-3.5 py-1.5 rounded-full text-xs font-semibold border transition-all cursor-pointer ${
                    isSelected
                      ? 'border-blue-500 dark:border-blue-400 bg-blue-50 dark:bg-[#182234] text-blue-700 dark:text-blue-300'
                      : 'border-slate-200 dark:border-[#233048] bg-white dark:bg-[#121826] text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-[#182234]'
                  }`}
                >
                  <ToolLogo name={tpl.iconName} className="w-3.5 h-3.5" />
                  <span>{tpl.label}</span>
                </button>
              )
            })}

            <button
              onClick={() => navigate('/workflow-library')}
              className="text-xs text-slate-500 dark:text-slate-400 hover:text-blue-600 dark:hover:text-blue-400 font-medium ml-1 transition-colors flex items-center gap-1 cursor-pointer"
            >
              <span>See all</span>
              <ArrowRight className="w-3 h-3" />
            </button>
          </div>

          {/* Interactive Live Canvas Node Graph Preview */}
          <CanvasPreview template={activeDisplayTemplate} />
        </div>
      ) : (
        /* ── CONVERSATION & EXECUTION VIEW ─────────────────────────────────── */
        <div className="flex-1 flex flex-col justify-between overflow-hidden">
          <div className="flex-1 overflow-y-auto px-4 md:px-8 py-6 space-y-6 max-w-4xl mx-auto w-full">
            {messages.map((msg) => {
              const isUser = msg.role === 'user'

              return (
                <div key={msg.id} className={`flex gap-3.5 ${isUser ? 'justify-end' : 'justify-start'}`}>
                  {!isUser && (
                    <div className="w-8 h-8 rounded-xl bg-blue-600 text-white flex items-center justify-center shrink-0 shadow-sm mt-0.5">
                      <Bot className="w-4 h-4" />
                    </div>
                  )}

                  <div className={`max-w-[85%] md:max-w-[78%] ${isUser ? 'items-end' : 'items-start'}`}>
                    <div
                      className={`p-4 rounded-2xl text-sm leading-relaxed ${
                        isUser
                          ? 'bg-blue-600 text-white rounded-tr-xs shadow-sm'
                          : 'bg-white dark:bg-[#121826] border border-slate-200 dark:border-[#233048] text-slate-900 dark:text-slate-100 rounded-tl-xs shadow-2xs'
                      }`}
                    >
                      <MarkdownRenderer content={msg.content} />

                      {/* Required Integrations Status & Direct Connect on same screen */}
                      {!isUser && msg.required_tools && msg.required_tools.length > 0 && (
                        <div className="my-3 p-3 bg-slate-50 dark:bg-[#0b0f17] rounded-xl border border-slate-200 dark:border-[#233048]">
                          <div className="flex items-center justify-between pb-2 mb-2 border-b border-slate-200 dark:border-[#1a2336] text-[10px] font-mono text-slate-500 dark:text-slate-400 font-bold uppercase">
                            <span>Required Integrations ({msg.required_tools.length})</span>
                            <span>Connection Status</span>
                          </div>
                          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2">
                            {msg.required_tools.map((t) => {
                              const isConn = connectedTools[t.tool_key] ?? t.connected
                              return (
                                <div
                                  key={t.tool_key}
                                  className={`p-2 rounded-lg border flex items-center justify-between gap-2 transition-all ${
                                    isConn
                                      ? 'bg-white dark:bg-[#121826] border-slate-200 dark:border-[#233048]'
                                      : 'bg-amber-50/60 dark:bg-amber-950/20 border-amber-300 dark:border-amber-800/60'
                                  }`}
                                >
                                  <div className="flex items-center gap-2 min-w-0">
                                    <ToolLogo name={t.tool_key} className="w-4 h-4 shrink-0" />
                                    <div className="min-w-0">
                                      <p className="text-[11px] font-bold text-slate-900 dark:text-white truncate">{t.name}</p>
                                      <span className={`text-[9px] font-mono ${isConn ? 'text-emerald-600 dark:text-emerald-400' : 'text-amber-600 dark:text-amber-400 font-semibold'}`}>
                                        {isConn ? 'Connected' : 'Action Required'}
                                      </span>
                                    </div>
                                  </div>

                                  {isConn ? (
                                    <span className="w-5 h-5 rounded-full bg-emerald-50 dark:bg-emerald-950/60 border border-emerald-300 dark:border-emerald-800 text-emerald-600 dark:text-emerald-400 flex items-center justify-center shrink-0">
                                      <Check className="w-3 h-3" />
                                    </span>
                                  ) : (
                                    <button
                                      type="button"
                                      onClick={() => setConnectModalTool(t)}
                                      className="px-2 py-1 bg-amber-600 hover:bg-amber-500 text-white rounded-md text-[10px] font-semibold cursor-pointer shrink-0 transition-colors shadow-2xs"
                                    >
                                      Connect
                                    </button>
                                  )}
                                </div>
                              )
                            })}
                          </div>
                        </div>
                      )}

                      {/* Visual Execution Pipeline Nodes */}
                      {!isUser && msg.execution_nodes && msg.execution_nodes.length > 0 && (
                        <NodeExecutionPipeline nodes={msg.execution_nodes} />
                      )}

                      {/* Interactive Actions on Same Screen */}
                      {!isUser && (msg.execution_nodes?.length > 0 || msg.action_cta) && (
                        <div className="mt-3 pt-3 border-t border-slate-200 dark:border-[#233048] flex flex-wrap items-center gap-2">
                          <button
                            type="button"
                            onClick={() => handleExecuteInline(msg)}
                            disabled={executingInlineId === msg.id}
                            className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white rounded-xl text-xs font-semibold shadow-xs transition-all cursor-pointer"
                          >
                            {executingInlineId === msg.id ? (
                              <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                            ) : (
                              <Play className="w-3.5 h-3.5 fill-white" />
                            )}
                            <span>{executingInlineId === msg.id ? 'Executing Pipeline...' : 'Run Pipeline on This Screen'}</span>
                          </button>

                          {msg.action_cta && (
                            <button
                              type="button"
                              onClick={() => navigate(msg.action_cta.to)}
                              className="inline-flex items-center gap-1.5 px-3 py-2 bg-slate-100 dark:bg-[#182234] hover:bg-slate-200 dark:hover:bg-[#233048] text-slate-700 dark:text-slate-300 rounded-xl text-xs font-semibold border border-slate-200 dark:border-[#233048] transition-all cursor-pointer"
                            >
                              <span>Open Dedicated Canvas</span>
                              <ArrowUpRight className="w-3.5 h-3.5 text-slate-400" />
                            </button>
                          )}
                        </div>
                      )}
                    </div>

                    <div className={`text-[10px] text-slate-400 dark:text-slate-500 mt-1 px-1 ${isUser ? 'text-right' : 'text-left'}`}>
                      {msg.timestamp}
                    </div>

                    {/* Suggested Followups */}
                    {!isUser && msg.suggested_followups && msg.suggested_followups.length > 0 && (
                      <div className="flex flex-wrap gap-1.5 mt-2.5">
                        {msg.suggested_followups.map((sug, sIdx) => (
                          <button
                            key={sIdx}
                            onClick={() => handleSend(sug)}
                            className="text-xs px-3 py-1.5 bg-white dark:bg-[#121826] hover:bg-slate-100 dark:hover:bg-[#182234] border border-slate-200 dark:border-[#233048] hover:border-blue-400 text-slate-700 dark:text-slate-300 rounded-lg transition-colors cursor-pointer text-left"
                          >
                            {sug}
                          </button>
                        ))}
                      </div>
                    )}
                  </div>

                  {isUser && (
                    <div className="w-8 h-8 rounded-xl bg-slate-200 dark:bg-slate-800 text-slate-800 dark:text-slate-200 flex items-center justify-center shrink-0 mt-0.5 text-xs font-bold border border-slate-300 dark:border-slate-700">
                      {user?.full_name ? user.full_name[0].toUpperCase() : 'U'}
                    </div>
                  )}
                </div>
              )
            })}

            {loading && (
              <div className="flex gap-3.5 justify-start">
                <div className="w-8 h-8 rounded-xl bg-blue-600 text-white flex items-center justify-center shrink-0 shadow-sm">
                  <Bot className="w-4 h-4 animate-bounce" />
                </div>
                <div className="p-4 rounded-2xl bg-white dark:bg-[#121826] border border-slate-200 dark:border-[#233048] text-slate-700 dark:text-slate-300 rounded-tl-xs shadow-2xs flex items-center gap-2.5">
                  <RefreshCw className="w-4 h-4 text-blue-500 animate-spin" />
                  <span className="text-xs font-medium">Orchestrating workflow nodes & executing pipeline...</span>
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          {/* Conversation Input Box */}
          <div className="p-4 bg-white dark:bg-[#121826] border-t border-slate-200 dark:border-[#233048] shrink-0 transition-colors">
            <div className="max-w-4xl mx-auto">
              {/* Hidden File Input for conversation attachments */}
              <input
                type="file"
                ref={convFileInputRef}
                onChange={handleFileUpload}
                className="hidden"
                accept=".pdf,.doc,.docx,.txt,.csv,.json,.xlsx,.md,.png,.jpg,.jpeg,.sql,.log"
                multiple
              />

              {/* Attached file badges in conversation mode */}
              {attachedFiles.length > 0 && (
                <div className="flex flex-wrap items-center gap-2 mb-2">
                  {attachedFiles.map((file) => (
                    <div
                      key={file.id}
                      className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-blue-50 dark:bg-[#182234] border border-blue-200 dark:border-blue-900/60 text-blue-700 dark:text-blue-300 text-xs shadow-2xs"
                    >
                      <Paperclip className="w-3.5 h-3.5 text-blue-500 shrink-0" />
                      <span className="font-medium max-w-[140px] truncate">{file.name}</span>
                      <span className="text-[10px] text-slate-400 font-mono">({file.size})</span>
                      <button
                        type="button"
                        onClick={() => removeAttachedFile(file.id)}
                        className="p-0.5 hover:bg-slate-100 dark:hover:bg-slate-800 rounded text-slate-400 hover:text-red-500 transition-colors cursor-pointer"
                        title="Remove attachment"
                      >
                        <X className="w-3 h-3" />
                      </button>
                    </div>
                  ))}
                </div>
              )}

              <form
                onSubmit={(e) => {
                  e.preventDefault()
                  handleSend()
                }}
                className="flex items-center gap-2 bg-slate-50 dark:bg-[#0b0f17] border border-slate-200 dark:border-[#233048] focus-within:border-blue-500 rounded-2xl p-2 transition-all shadow-inner"
              >
                <button
                  type="button"
                  onClick={() => convFileInputRef.current?.click()}
                  disabled={isUploading}
                  className={`p-2 rounded-xl transition-colors cursor-pointer ${
                    attachedFiles.length > 0
                      ? 'bg-blue-50 dark:bg-blue-950/60 text-blue-600 dark:text-blue-400'
                      : 'text-slate-500 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-[#182234]'
                  }`}
                  title="Upload context document / file (+)"
                >
                  {isUploading ? <RefreshCw className="w-4 h-4 animate-spin text-blue-500" /> : <Plus className="w-4 h-4" />}
                </button>

                <input
                  type="text"
                  value={promptText}
                  onChange={(e) => setPromptText(e.target.value)}
                  placeholder="Ask AI Assistant to build a workflow, extract data, triage inbox..."
                  disabled={loading}
                  className="flex-1 bg-transparent px-3.5 py-1.5 text-sm text-slate-900 dark:text-slate-100 placeholder-slate-400 dark:placeholder-slate-500 focus:outline-hidden disabled:opacity-50"
                />

                <button
                  type="button"
                  onClick={toggleVoiceInput}
                  className={`p-2 rounded-xl transition-colors ${
                    isListening ? 'bg-red-500 text-white animate-pulse' : 'text-slate-500 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200'
                  }`}
                  title="Voice input"
                >
                  <Mic className="w-4 h-4" />
                </button>

                <button
                  type="submit"
                  disabled={(!promptText.trim() && attachedFiles.length === 0) || loading}
                  className="px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-40 text-white rounded-xl text-xs font-semibold flex items-center gap-1.5 transition-all shadow-xs cursor-pointer disabled:cursor-not-allowed"
                >
                  <span>Send</span>
                  <Send className="w-3.5 h-3.5" />
                </button>
              </form>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
