// frontend/src/components/common/ToolLogo.jsx
// ─────────────────────────────────────────────────────────────────────────────
// Universal Tool & Model Logo Component
// Renders official asset images (/assets/tools/{name}.png) with reactive fallbacks
// to authentic, clean, precision vector SVGs for Gemini, Claude, OpenAI, Telegram,
// PostgreSQL, Sheets, Calendar, Gmail, Slack, HubSpot, LinkedIn, X/Twitter, etc.
// ─────────────────────────────────────────────────────────────────────────────

import React, { useState, useEffect, useMemo } from 'react'
import { Zap } from 'lucide-react'

export function normalizeToolKey(name) {
  if (!name) return ''
  const s = String(name).toLowerCase().trim()

  if (s.includes('gemini') || s.includes('google_ai') || s.includes('google ai') || s === 'google') return 'gemini'
  if (s.includes('claude') || s.includes('anthropic')) return 'claude'
  if (s.includes('openai') || s.includes('gpt') || s.includes('chatgpt') || s.includes('dall-e') || s.includes('dalle')) return 'openai'
  if (s.includes('telegram') || s.includes('tg_bot') || s.includes('tgbot')) return 'telegram'
  if (s.includes('postgres') || s.includes('pgvector') || s.includes('postgresql') || s.includes('database') || s.includes('sql')) return 'postgres'
  if (s.includes('sheet') || s.includes('spreadsheet')) return 'sheet'
  if (s.includes('calendar') || s.includes('booking') || s.includes('appointment')) return 'calendar'
  if (s.includes('gmail') || s.includes('inbound email') || s.includes('email') || s.includes('mail')) return 'gmail'
  if (s.includes('slack')) return 'slack'
  if (s.includes('hubspot') || s.includes('crm')) return 'hubspot'
  if (s.includes('stripe') || s.includes('billing')) return 'stripe'
  if (s.includes('linkedin')) return 'linkedin'
  if (s.includes('twitter') || s.includes('tweet') || s === 'x') return 'twitter'
  if (s.includes('instagram')) return 'instagram'
  if (s.includes('youtube')) return 'youtube'
  if (s.includes('imagerouter') || s.includes('flux') || s.includes('image_gen')) return 'imagerouter'
  if (s.includes('action_center') || s.includes('action center') || s.includes('escalat') || s.includes('hitl') || s.includes('approval')) return 'action_center'
  if (s.includes('switch') || s.includes('filter') || s.includes('classifier') || s.includes('router') || s.includes('branch')) return 'switch'
  if (s.includes('spec') || s.includes('brief') || s.includes('doc')) return 'spec'
  if (s.includes('webhook') || s.includes('api') || s.includes('http') || s.includes('rest')) return 'webhook'
  if (s.includes('clearbit')) return 'clearbit'
  if (s.includes('quickbooks')) return 'quickbooks'

  return s.replace(/[^a-z0-9_-]/g, '')
}

export default function ToolLogo({ name, className = 'w-4 h-4' }) {
  const toolKey = useMemo(() => normalizeToolKey(name), [name])
  const [useFallback, setUseFallback] = useState(false)

  // Map known tool keys to public png assets if they exist
  const imgSrc = useMemo(() => {
    if (!toolKey) return null
    const assetsWithPng = [
      'aichatbot', 'calendar', 'claude', 'conversasionai', 'gmail',
      'instagram', 'openai', 'postgres', 'sheet', 'slack', 'telegram',
      'webhook', 'youtube'
    ]
    if (toolKey === 'sheet' || toolKey === 'sheets') return '/assets/tools/sheet.png'
    if (assetsWithPng.includes(toolKey)) return `/assets/tools/${toolKey}.png`
    return null
  }, [toolKey])

  // Reset fallback state when tool changes
  useEffect(() => {
    setUseFallback(false)
  }, [toolKey])

  // Authentic vector SVGs
  const svgFallbacks = {
    gemini: (
      <svg className={className} viewBox="0 0 24 24" fill="none" aria-label="Google Gemini">
        <defs>
          <linearGradient id="tool-gemini-grad" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#1BA1E3" />
            <stop offset="45%" stopColor="#5B68E4" />
            <stop offset="100%" stopColor="#9C40FF" />
          </linearGradient>
        </defs>
        <path
          d="M12 2C12 7.52 7.52 12 2 12C7.52 12 12 16.48 12 22C12 16.48 16.48 12 22 12C16.48 12 12 7.52 12 2Z"
          fill="url(#tool-gemini-grad)"
        />
      </svg>
    ),
    claude: (
      <svg className={className} viewBox="0 0 24 24" fill="#D97706" aria-label="Anthropic Claude">
        <path d="M12 2L14.2 8.4L21 9.8L16 14.2L17.5 21L12 17.5L6.5 21L8 14.2L3 9.8L9.8 8.4L12 2Z" fill="#D97706" />
      </svg>
    ),
    openai: (
      <svg className={className} viewBox="0 0 24 24" fill="none" stroke="#10A37F" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-label="OpenAI">
        <path d="M12 2a10 10 0 0 1 10 10 10 10 0 0 1-10 10A10 10 0 0 1 2 12 10 10 0 0 1 12 2z" fill="#10A37F" fillOpacity="0.15" />
        <path d="M12 6v12M6 12h12M7.75 7.75l8.5 8.5M7.75 16.25l8.5-8.5" />
      </svg>
    ),
    telegram: (
      <svg className={className} viewBox="0 0 24 24" fill="none" aria-label="Telegram">
        <circle cx="12" cy="12" r="11" fill="#229ED9" />
        <path d="M17.5 7L5.5 11.5L9.5 13L15.5 8.5L11 14.5L15 17.5L17.5 7Z" fill="#FFFFFF" stroke="#FFFFFF" strokeWidth="0.5" strokeLinejoin="round" />
      </svg>
    ),
    postgres: (
      <svg className={className} viewBox="0 0 24 24" fill="none" stroke="#336791" strokeWidth="1.6" aria-label="PostgreSQL">
        <ellipse cx="12" cy="5" rx="8" ry="3" fill="#336791" fillOpacity="0.2" />
        <path d="M20 12c0 1.66-3.58 3-8 3s-8-1.34-8-3" />
        <path d="M4 5v14c0 1.66 3.58 3 8 3s8-1.34 8-3V5" />
      </svg>
    ),
    sheet: (
      <svg className={className} viewBox="0 0 24 24" fill="none" aria-label="Google Sheets">
        <rect x="3" y="3" width="18" height="18" rx="3" fill="#0F9D58" fillOpacity="0.2" stroke="#0F9D58" strokeWidth="1.6" />
        <path d="M7 8H17M7 12H17M7 16H17M12 8V16" stroke="#0F9D58" strokeWidth="1.6" strokeLinecap="round" />
      </svg>
    ),
    calendar: (
      <svg className={className} viewBox="0 0 24 24" fill="none" aria-label="Google Calendar">
        <rect x="3" y="4" width="18" height="17" rx="3" fill="#4285F4" fillOpacity="0.2" stroke="#4285F4" strokeWidth="1.6" />
        <path d="M16 2V6M8 2V6M3 9H21" stroke="#4285F4" strokeWidth="1.6" strokeLinecap="round" />
        <rect x="7" y="12" width="3" height="3" rx="0.5" fill="#4285F4" />
        <rect x="14" y="12" width="3" height="3" rx="0.5" fill="#4285F4" />
      </svg>
    ),
    gmail: (
      <svg className={className} viewBox="0 0 24 24" fill="none" aria-label="Gmail">
        <rect x="3" y="4" width="18" height="16" rx="3" fill="#EA4335" fillOpacity="0.15" stroke="#EA4335" strokeWidth="1.5" />
        <path d="M3 6L12 13L21 6" stroke="#EA4335" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    ),
    slack: (
      <svg className={className} viewBox="0 0 24 24" fill="none" aria-label="Slack">
        <rect x="3" y="3" width="18" height="18" rx="4" fill="#EC4899" fillOpacity="0.15" stroke="#EC4899" strokeWidth="1.6" />
        <path d="M8 12H16M12 8V16" stroke="#EC4899" strokeWidth="2" strokeLinecap="round" />
      </svg>
    ),
    hubspot: (
      <svg className={className} viewBox="0 0 24 24" fill="none" aria-label="HubSpot">
        <circle cx="12" cy="12" r="5" fill="#FF7A59" fillOpacity="0.2" stroke="#FF7A59" strokeWidth="1.6" />
        <path d="M12 3V7M12 17V21M3 12H7M17 12H21" stroke="#FF7A59" strokeWidth="1.6" strokeLinecap="round" />
      </svg>
    ),
    stripe: (
      <svg className={className} viewBox="0 0 24 24" fill="none" aria-label="Stripe">
        <rect x="3" y="4" width="18" height="16" rx="3.5" fill="#635BFF" fillOpacity="0.2" stroke="#635BFF" strokeWidth="1.5" />
        <path d="M8 13.5C8 12.1 9.2 11.2 11.3 11.2C13 11.2 14.5 11.7 15.5 12.3V9.8C14.3 9.3 12.9 9 11.4 9C7.8 9 5.5 10.9 5.5 14C5.5 18.8 12.2 18 12.2 20.2C12.2 21 11.4 21.3 10.2 21.3C8.4 21.3 6.6 20.5 5.5 19.8V22.4C6.8 23 8.5 23.4 10.2 23.4C14 23.4 16.5 21.5 16.5 18.3C16.5 13.3 8 14.2 8 13.5Z" fill="#635BFF" transform="scale(0.7) translate(3, 1)" />
      </svg>
    ),
    linkedin: (
      <svg className={className} viewBox="0 0 24 24" fill="#0A66C2" aria-label="LinkedIn">
        <rect width="24" height="24" rx="4" fill="#0A66C2" />
        <path d="M6 9.5H8.8V18H6V9.5ZM7.4 5.5C6.5 5.5 5.8 6.2 5.8 7.1C5.8 8 6.5 8.7 7.4 8.7C8.3 8.7 9 8 9 7.1C9 6.2 8.3 5.5 7.4 5.5ZM10.5 9.5H13.2V10.7C13.6 10 14.6 9.3 16 9.3C18.8 9.3 19.3 11.1 19.3 13.5V18H16.5V14.1C16.5 13.1 16.5 11.9 15.1 11.9C13.6 11.9 13.4 13.1 13.4 14V18H10.5V9.5Z" fill="#FFFFFF" />
      </svg>
    ),
    twitter: (
      <svg className={className} viewBox="0 0 24 24" fill="currentColor" aria-label="X / Twitter">
        <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z" />
      </svg>
    ),
    instagram: (
      <svg className={className} viewBox="0 0 24 24" fill="none" aria-label="Instagram">
        <rect x="3" y="3" width="18" height="18" rx="5" fill="#E1306C" fillOpacity="0.15" stroke="#E1306C" strokeWidth="1.6" />
        <circle cx="12" cy="12" r="4" stroke="#E1306C" strokeWidth="1.6" />
        <circle cx="17.5" cy="6.5" r="1" fill="#E1306C" />
      </svg>
    ),
    youtube: (
      <svg className={className} viewBox="0 0 24 24" fill="none" aria-label="YouTube">
        <rect x="2" y="5" width="20" height="14" rx="4" fill="#FF0000" fillOpacity="0.15" stroke="#FF0000" strokeWidth="1.6" />
        <polygon points="10,8 16,12 10,16" fill="#FF0000" />
      </svg>
    ),
    action_center: (
      <svg className={className} viewBox="0 0 24 24" fill="none" stroke="#6366F1" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-label="Action Center">
        <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" fill="#6366F1" fillOpacity="0.15" />
        <polyline points="9 12 11 14 15 10" />
      </svg>
    ),
    switch: (
      <svg className={className} viewBox="0 0 24 24" fill="none" stroke="#10B981" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-label="Conditional Router">
        <circle cx="6" cy="12" r="3" fill="#10B981" fillOpacity="0.2" />
        <circle cx="18" cy="6" r="3" fill="#10B981" fillOpacity="0.2" />
        <circle cx="18" cy="18" r="3" fill="#10B981" fillOpacity="0.2" />
        <path d="M9 12H12M12 12L15 6M12 12L15 18" />
      </svg>
    ),
    imagerouter: (
      <svg className={className} viewBox="0 0 24 24" fill="none" stroke="#EC4899" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-label="ImageRouter">
        <rect x="3" y="3" width="18" height="18" rx="4" fill="#EC4899" fillOpacity="0.15" />
        <circle cx="8.5" cy="8.5" r="2" fill="#EC4899" />
        <path d="M21 15l-5-5L5 21" />
      </svg>
    ),
    spec: (
      <svg className={className} viewBox="0 0 24 24" fill="none" stroke="#3B82F6" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-label="Specification">
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" fill="#3B82F6" fillOpacity="0.15" />
        <polyline points="14 2 14 8 20 8" />
        <line x1="16" y1="13" x2="8" y2="13" />
        <line x1="16" y1="17" x2="8" y2="17" />
      </svg>
    ),
    webhook: (
      <svg className={className} viewBox="0 0 24 24" fill="none" stroke="#14B8A6" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-label="Webhook">
        <circle cx="12" cy="12" r="4" fill="#14B8A6" fillOpacity="0.2" />
        <path d="M12 2v6M12 16v6M2 12h6M16 12h6" />
      </svg>
    ),
    clearbit: (
      <svg className={className} viewBox="0 0 24 24" fill="none" stroke="#3B82F6" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-label="Clearbit">
        <circle cx="12" cy="12" r="8" fill="#3B82F6" fillOpacity="0.15" />
        <path d="M12 8v8M8 12h8" />
      </svg>
    ),
    quickbooks: (
      <svg className={className} viewBox="0 0 24 24" fill="none" stroke="#2CA01C" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-label="QuickBooks">
        <circle cx="12" cy="12" r="9" fill="#2CA01C" fillOpacity="0.15" />
        <path d="M9 10a3 3 0 1 1 3 3H9V7" />
      </svg>
    ),
  }

  if (!useFallback && imgSrc) {
    return (
      <img
        src={imgSrc}
        alt={name || 'Tool Logo'}
        className={`${className} object-contain`}
        onError={() => setUseFallback(true)}
      />
    )
  }

  return svgFallbacks[toolKey] || <Zap className={className} />
}
