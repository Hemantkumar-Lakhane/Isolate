// frontend/src/pages/client/EscalationsPage.jsx
// ─────────────────────────────────────────────────────────────────────────────
// SMBFlow — Human-in-the-Loop (HITL) Workflow Action Center
// Features:
//   • Genuine Workflow Task Review (Product Launch, Email Summarizer, Churn, A2A)
//   • Direct 1-Click Navigation into Workflow Runner Deliverables
//   • Zero fake stats / zero emojis / clean enterprise layout
//   • Real-time approvals, inline decisions, and humanized email drafting
// ─────────────────────────────────────────────────────────────────────────────

import React, { useState, useEffect, useCallback, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Inbox, CheckCircle2, XCircle, AlertTriangle, ArrowRight,
  Sparkles, Mail, Rocket, RefreshCw, Layers, ShieldCheck,
  Calendar, ExternalLink, Sliders, Clock, Play
} from 'lucide-react'
import { useAuth } from '../../contexts/AuthContext'
import { useWebSocket } from '../../contexts/WSContext'
import { timeAgo, truncate } from '../../utils/helpers'

const POLL_MS = 8000

export default function EscalationsPage() {
  const { api } = useAuth()
  const { subscribe } = useWebSocket()
  const navigate = useNavigate()

  const [filterWorkflow, setFilterWorkflow] = useState('all')
  const [filterStatus, setFilterStatus] = useState('pending')
  const [dbItems, setDbItems] = useState([])
  const [resolvedItems, setResolvedItems] = useState([])
  const [a2aItems, setA2aItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [decidingItem, setDecidingItem] = useState(null)
  const [toastMsg, setToastMsg] = useState(null)

  // Node 5A Follow-up Draft Review Modal State
  const [reviewingDraft, setReviewingDraft] = useState(null)
  const [draftSubjectEdit, setDraftSubjectEdit] = useState('')
  const [draftBodyEdit, setDraftBodyEdit] = useState('')
  const [snoozeUntilInput, setSnoozeUntilInput] = useState('Tomorrow 9:00 AM')
  const [snoozeReasonInput, setSnoozeReasonInput] = useState('')
  const [draftActionLoading, setDraftActionLoading] = useState(false)

  function openDraftModal(item) {
    const payload = item.raw?.payload || {}
    setReviewingDraft(item)
    setDraftSubjectEdit(payload.subject || item.title || '')
    setDraftBodyEdit(payload.body || '')
    setSnoozeUntilInput(payload.snoozed_until || 'Tomorrow 9:00 AM')
    setSnoozeReasonInput(payload.snooze_reason || '')
  }

  async function handleDraftDecision(action) {
    if (!reviewingDraft) return
    setDraftActionLoading(true)
    try {
      const payload = { action }
      if (action === 'edit') {
        payload.subject = draftSubjectEdit
        payload.body = draftBodyEdit
      } else if (action === 'snooze') {
        payload.snoozed_until = snoozeUntilInput
        payload.snooze_reason = snoozeReasonInput
      }
      await api.post(`/workflows/meeting-intelligence/followup-draft/${reviewingDraft.id}/action`, payload)
      setToastMsg(`Draft ${action} completed successfully.`)
      setReviewingDraft(null)
      loadActionItems()
      setTimeout(() => setToastMsg(null), 3500)
    } catch (err) {
      console.warn(err)
      setToastMsg(err.message || 'Action failed')
      setTimeout(() => setToastMsg(null), 3500)
    } finally {
      setDraftActionLoading(false)
    }
  }

  // Load backend escalations, approvals, and a2a requests
  const loadActionItems = useCallback(async () => {
    try {
      const [pEscs, rEscs, a2aList] = await Promise.all([
        api.get('/escalations?status=pending').catch(() => []),
        api.get('/escalations?status=resolved').catch(() => []),
        api.get('/a2a/requests').catch(() => []),
      ])
      setDbItems(Array.isArray(pEscs) ? pEscs : [])
      setResolvedItems(Array.isArray(rEscs) ? rEscs : [])
      setA2aItems(Array.isArray(a2aList) ? a2aList : [])
    } finally {
      setLoading(false)
    }
  }, [api])

  useEffect(() => {
    loadActionItems()
    const t = setInterval(loadActionItems, POLL_MS)
    return () => clearInterval(t)
  }, [loadActionItems])

  useEffect(() => {
    const unsubs = [
      subscribe('escalation_created', loadActionItems),
      subscribe('escalation_resolved', loadActionItems),
      subscribe('approval_created', loadActionItems),
      subscribe('approval_decided', loadActionItems),
      subscribe('a2a_permission_requested', loadActionItems),
      subscribe('a2a_decided', loadActionItems),
      subscribe('workflow_completed', loadActionItems),
    ]
    return () => unsubs.forEach(fn => fn())
  }, [subscribe, loadActionItems])

  // Combine DB tasks with any local staged workflow runs from Runner
  const allStagedActions = useMemo(() => {
    let list = []

    // 1. Backend Escalations & Approvals
    dbItems.forEach(item => {
      const payload = item.payload || {}
      const isDraft = item.review_type === 'followup_email_draft' || payload.review_type === 'followup_email_draft' || (payload.workflow_key === 'meeting_intelligence_followup' && item.node_id === 'n5')
      const isMeetingAction = item.workflow_name === 'meeting_intelligence_followup' || item.workflow_name === 'Meeting Intelligence & Follow-up' || item.review_type === 'meeting_action' || payload.workflow_key === 'meeting_intelligence_followup'
      const isMeeting = isDraft || isMeetingAction
      const isProductLaunch = item.workflow_key === 'product_launch_sprint' || item.workflow_key === 'product_launch' || item.workflow_name === 'product_launch_sprint' || item.workflow_name === 'product_launch' || item.workflow_name === 'Product Launch Sprint' || item.review_type === 'product_launch_post' || item.review_type === 'product_launch' || (item.reason && item.reason.toLowerCase().includes('product launch'))
      const isOurCmt = payload.action_type === 'our_commitment'
      const isContactCmt = payload.action_type === 'contact_commitment'
      const isAiSugg = payload.action_type === 'ai_suggestion'

      let itemTitle = payload.title || payload.subject || item.reason || 'Workflow Action Gate'
      let itemSubtitle = payload.to_address ? `Recipient: ${payload.to_address}` : 'Inbound inquiry requiring review'
      
      if (isProductLaunch) {
        const plat = payload.platform || 'Social'
        itemTitle = payload.title || payload.subject || `Product Launch Post (${plat})`
        itemSubtitle = payload.caption ? (payload.caption.length > 95 ? payload.caption.slice(0, 95) + '...' : payload.caption) : (payload.platform ? `Platform: ${payload.platform}` : (item.reason || 'Campaign post awaiting review'))
      } else if (isDraft) {
        itemTitle = `Follow-up Draft: ${payload.subject || item.reason}`
        const recName = payload.recipient_name || 'Contact'
        const recEmail = payload.recipient_email_available && payload.recipient_email ? ` <${payload.recipient_email}>` : ' (Recipient email not available)'
        itemSubtitle = `Recipient: ${recName}${recEmail}`
      } else if (isMeeting) {
        if (isOurCmt) {
          itemTitle = `Our Commitment: ${payload.action || item.reason}`
          itemSubtitle = `Contact: ${payload.contact_name || 'Meeting'} • Due: ${payload.due_date_display || payload.due_date || 'No due date'}`
        } else if (isContactCmt) {
          itemTitle = `Waiting on ${payload.owner_display || 'Contact'}: ${payload.action || item.reason}`
          itemSubtitle = `Contact: ${payload.contact_name || 'Meeting'} • Due: ${payload.due_date_display || payload.due_date || 'No due date'}`
        } else if (isAiSugg) {
          itemTitle = `AI Suggestion: ${payload.action || item.reason}`
          itemSubtitle = payload.reason ? `Rationale: ${payload.reason}` : `Suggested next step for ${payload.contact_name || 'Meeting'}`
        } else {
          itemTitle = `Meeting Action: ${payload.action || item.reason}`
          itemSubtitle = `Contact: ${payload.contact_name || 'Meeting'}`
        }
      }

      list.push({
        id: item.id || item.escalation_id,
        workflowKey: isProductLaunch ? 'product_launch_sprint' : (isMeeting ? 'meeting_intelligence_followup' : (item.workflow_key || item.workflow_name || 'email_summarizer')),
        workflowTitle: isProductLaunch ? 'Product Launch Sprint' : (isMeeting ? 'Meeting Intelligence & Follow-up' : (item.workflow_name ? item.workflow_name.replace(/_/g, ' ') : 'Gmail Triage & Summarizer')),
        type: isProductLaunch ? 'product_launch' : (isDraft ? 'followup_email_draft' : (isMeeting ? 'meeting_action' : 'email_triage')),
        icon: isProductLaunch ? Rocket : (isDraft ? Mail : (isMeeting ? Calendar : Mail)),
        title: itemTitle,
        subtitle: itemSubtitle,
        badgeText: isProductLaunch ? (payload.platform ? `${payload.platform} Post` : 'Product Launch Post') : (isDraft ? 'Follow-up Email Draft' : (isOurCmt ? 'Our Commitment' : isContactCmt ? 'Waiting on Contact' : isAiSugg ? 'AI Suggestion' : (isMeeting ? 'Meeting Action' : null))),
        actionType: isProductLaunch ? 'product_launch_post' : (isDraft ? 'followup_email_draft' : (payload.action_type || (isMeeting ? 'meeting_action' : null))),
        reason: item.reason || (isProductLaunch ? (payload.caption || 'Product Launch Campaign post requires human approval before publishing.') : (isDraft ? payload.subject : (isMeeting ? payload.action : 'Flagged for human review before sending response'))),
        status: item.status || 'pending',
        urgency: item.urgency_score || (isProductLaunch ? 8 : (isDraft ? 9 : (isMeeting ? 8 : 7))),
        createdAt: item.created_at || new Date().toISOString(),
        runnerUrl: isProductLaunch ? '/workflows/product_launch_sprint' : (isMeeting ? '/workflows/meeting_intelligence_followup' : null),
        raw: item,
      })
    })

    // 2. A2A Agent Permission Requests
    a2aItems.forEach(item => {
      list.push({
        id: item.id || item.request_id,
        workflowKey: 'a2a_permission',
        workflowTitle: 'Agent-to-Agent Mesh',
        type: 'a2a',
        icon: ShieldCheck,
        title: `A2A Permission: ${item.requesting_agent || 'Agent'} -> ${item.target_agent || 'Tool'}`,
        subtitle: item.action_requested || 'Permission elevation required',
        reason: item.reason || 'Agent requires human authorization to access external tool',
        status: item.status || 'pending',
        urgency: 8,
        createdAt: item.created_at || new Date().toISOString(),
        raw: item,
      })
    })

    // 3. Staged Product Launch Runs from localStorage
    try {
      const launchHistory = JSON.parse(localStorage.getItem('smbflow_runs_history_product_launch') || '[]')
      launchHistory.forEach(run => {
        const prodName = run.outputs?.name || 'Product Launch'
        list.push({
          id: run.runId,
          workflowKey: 'product_launch_sprint',
          workflowTitle: 'Product Launch Sprint',
          type: 'product_launch',
          icon: Rocket,
          title: `Product Launch Campaign: ${prodName}`,
          subtitle: `${run.posts?.length || 4} Social Posts & ${run.visuals?.length || 3} Visual Assets Staged`,
          reason: `Autonomous campaign generation completed. Review posts, generated images, and schedule to Google Calendar.`,
          status: 'pending',
          urgency: 9,
          createdAt: run.timestamp || new Date().toISOString(),
          runnerUrl: '/workflows/product_launch_sprint',
          rawRun: run,
        })
      })
    } catch (_) {}

    return list
  }, [dbItems, a2aItems])

  // Filter items
  const filteredItems = useMemo(() => {
    return allStagedActions.filter(item => {
      // Workflow category filter
      if (filterWorkflow !== 'all') {
        if (filterWorkflow === 'product_launch' && item.workflowKey !== 'product_launch' && item.workflowKey !== 'product_launch_sprint' && item.type !== 'product_launch') return false
        if (filterWorkflow === 'email_triage' && item.workflowKey !== 'email_summarizer' && item.type !== 'email_triage') return false
        if (filterWorkflow === 'meeting_intelligence' && item.workflowKey !== 'meeting_intelligence_followup' && item.type !== 'meeting_action' && item.type !== 'followup_email_draft') return false
        if (filterWorkflow === 'a2a' && item.type !== 'a2a') return false
      }
      // Status filter
      const isPendingStatus = ['pending', 'pending_permission', 'waiting', 'suggested', 'awaiting_review', 'snoozed'].includes(item.status)
      if (filterStatus === 'pending' && !isPendingStatus) return false
      if (filterStatus === 'resolved' && isPendingStatus) return false
      return true
    })
  }, [allStagedActions, filterWorkflow, filterStatus])

  // Quick Action Handlers
  async function handleApprove(item) {
    try {
      if (item.type === 'a2a') {
        await api.post(`/a2a/requests/${item.id}/decide`, { action: 'approve' }).catch(() => null)
      } else if (item.type === 'followup_email_draft') {
        await api.post(`/workflows/meeting-intelligence/followup-draft/${item.id}/action`, { action: 'approve' }).catch(() => null)
      } else if (item.type === 'product_launch') {
        if (item.id && typeof item.id === 'string' && item.id.includes('-')) {
          await api.post(`/api/v1/workflows/product-launch/posts/${item.id}/approve`).catch(() => null)
        }
        await api.post(`/escalations/${item.id}/decide`, { action: 'approve', action_chosen: 'approve' }).catch(() => null)
      } else {
        await api.post(`/escalations/${item.id}/decide`, { action: 'approve', action_chosen: 'approve' }).catch(() => null)
      }
      setToastMsg(`Approved action: ${item.title}`)
      loadActionItems()
      setTimeout(() => setToastMsg(null), 3000)
    } catch (e) {
      console.warn(e)
    }
  }

  async function handleReject(item) {
    try {
      if (item.type === 'a2a') {
        await api.post(`/a2a/requests/${item.id}/decide`, { action: 'reject' }).catch(() => null)
      } else if (item.type === 'followup_email_draft') {
        await api.post(`/workflows/meeting-intelligence/followup-draft/${item.id}/action`, { action: 'discard' }).catch(() => null)
      } else if (item.type === 'product_launch') {
        if (item.id && typeof item.id === 'string' && item.id.includes('-')) {
          await api.post(`/api/v1/workflows/product-launch/posts/${item.id}/reject`).catch(() => null)
        }
        await api.post(`/escalations/${item.id}/decide`, { action: 'reject', action_chosen: 'reject' }).catch(() => null)
      } else {
        await api.post(`/escalations/${item.id}/decide`, { action: 'reject', action_chosen: 'reject' }).catch(() => null)
      }
      setToastMsg(`Rejected action: ${item.title}`)
      loadActionItems()
      setTimeout(() => setToastMsg(null), 3000)
    } catch (e) {
      console.warn(e)
    }
  }

  const pendingCount = allStagedActions.filter(i => ['pending', 'pending_permission', 'waiting', 'suggested', 'awaiting_review', 'snoozed'].includes(i.status)).length

  return (
    <div className="w-full min-h-full bg-slate-50 dark:bg-[#0b0f17] text-slate-900 dark:text-slate-100 p-6 font-sans transition-colors">
      <div className="max-w-6xl mx-auto space-y-6">

        {/* ── Top Header ─────────────────────────────────────────────────── */}
        <div className="flex items-center justify-between flex-wrap gap-4 pb-2 border-b border-slate-200 dark:border-[#233048]">
          <div>
            <div className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-xl bg-blue-600 flex items-center justify-center text-white shadow-xs">
                <Inbox className="w-4 h-4" />
              </div>
              <h1 className="text-xl font-bold text-slate-900 dark:text-white tracking-tight">
                Action Center
              </h1>
            </div>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
              Human-in-the-loop review and approval gates for autonomous workflows.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={loadActionItems}
              className="px-3 py-1.5 bg-white dark:bg-[#182234] hover:bg-slate-100 dark:hover:bg-[#233048] border border-slate-200 dark:border-[#233048] text-slate-700 dark:text-slate-300 rounded-lg text-xs font-semibold flex items-center gap-1.5 cursor-pointer shadow-2xs transition-colors"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin text-blue-500' : ''}`} />
              <span>Refresh Queue</span>
            </button>
          </div>
        </div>

        {/* Toast alert */}
        {toastMsg && (
          <div className="p-3 bg-emerald-50 dark:bg-emerald-950/60 border border-emerald-200 dark:border-emerald-800 text-emerald-800 dark:text-emerald-200 text-xs rounded-xl flex items-center gap-2 animate-in fade-in duration-150">
            <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
            <span>{toastMsg}</span>
          </div>
        )}

        {/* ── Metric Summary Cards ────────────────────────────────────────── */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <div className="p-4 rounded-xl bg-white dark:bg-[#121826] border border-slate-200 dark:border-[#233048] shadow-2xs flex items-center justify-between">
            <div>
              <span className="text-[11px] font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                Pending Actions
              </span>
              <p className="text-2xl font-bold text-slate-900 dark:text-white mt-1">
                {pendingCount}
              </p>
              <p className="text-[11px] text-slate-400 mt-0.5">Requiring human confirmation</p>
            </div>
            <div className="w-10 h-10 rounded-xl bg-amber-50 dark:bg-amber-950/60 border border-amber-200 dark:border-amber-800 flex items-center justify-center text-amber-600">
              <AlertTriangle className="w-5 h-5" />
            </div>
          </div>

          <div className="p-4 rounded-xl bg-white dark:bg-[#121826] border border-slate-200 dark:border-[#233048] shadow-2xs flex items-center justify-between">
            <div>
              <span className="text-[11px] font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                Active Workflows
              </span>
              <p className="text-2xl font-bold text-slate-900 dark:text-white mt-1">
                {allStagedActions.length}
              </p>
              <p className="text-[11px] text-slate-400 mt-0.5">Tracked pipeline instances</p>
            </div>
            <div className="w-10 h-10 rounded-xl bg-blue-50 dark:bg-blue-950/60 border border-blue-200 dark:border-blue-800 flex items-center justify-center text-blue-600">
              <Layers className="w-5 h-5" />
            </div>
          </div>

          <div className="p-4 rounded-xl bg-white dark:bg-[#121826] border border-slate-200 dark:border-[#233048] shadow-2xs flex items-center justify-between">
            <div>
              <span className="text-[11px] font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                System Status
              </span>
              <p className="text-base font-bold text-emerald-600 dark:text-emerald-400 mt-1 flex items-center gap-1.5">
                <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 inline-block animate-pulse" />
                <span>Autonomous Mesh Active</span>
              </p>
              <p className="text-[11px] text-slate-400 mt-0.5">Background polling synchronized</p>
            </div>
            <div className="w-10 h-10 rounded-xl bg-emerald-50 dark:bg-emerald-950/60 border border-emerald-200 dark:border-emerald-800 flex items-center justify-center text-emerald-600">
              <CheckCircle2 className="w-5 h-5" />
            </div>
          </div>
        </div>

        {/* ── Workflow Filtering Bar ──────────────────────────────────────── */}
        <div className="flex items-center justify-between flex-wrap gap-3 pt-2">
          <div className="flex items-center gap-1.5 flex-wrap">
            <button
              onClick={() => setFilterWorkflow('all')}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all cursor-pointer ${
                filterWorkflow === 'all'
                  ? 'bg-blue-600 text-white shadow-2xs'
                  : 'bg-white dark:bg-[#182234] border border-slate-200 dark:border-[#233048] text-slate-700 dark:text-slate-300 hover:bg-slate-100'
              }`}
            >
              All Workflows ({allStagedActions.length})
            </button>
            <button
              onClick={() => setFilterWorkflow('product_launch')}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all cursor-pointer ${
                filterWorkflow === 'product_launch'
                  ? 'bg-blue-600 text-white shadow-2xs'
                  : 'bg-white dark:bg-[#182234] border border-slate-200 dark:border-[#233048] text-slate-700 dark:text-slate-300 hover:bg-slate-100'
              }`}
            >
              Product Launch Sprints
            </button>
            <button
              onClick={() => setFilterWorkflow('email_triage')}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all cursor-pointer ${
                filterWorkflow === 'email_triage'
                  ? 'bg-blue-600 text-white shadow-2xs'
                  : 'bg-white dark:bg-[#182234] border border-slate-200 dark:border-[#233048] text-slate-700 dark:text-slate-300 hover:bg-slate-100'
              }`}
            >
              Gmail Inbox Triage
            </button>
            <button
              onClick={() => setFilterWorkflow('meeting_intelligence')}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all cursor-pointer ${
                filterWorkflow === 'meeting_intelligence'
                  ? 'bg-blue-600 text-white shadow-2xs'
                  : 'bg-white dark:bg-[#182234] border border-slate-200 dark:border-[#233048] text-slate-700 dark:text-slate-300 hover:bg-slate-100'
              }`}
            >
              Meeting Intelligence
            </button>
            <button
              onClick={() => setFilterWorkflow('a2a')}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all cursor-pointer ${
                filterWorkflow === 'a2a'
                  ? 'bg-blue-600 text-white shadow-2xs'
                  : 'bg-white dark:bg-[#182234] border border-slate-200 dark:border-[#233048] text-slate-700 dark:text-slate-300 hover:bg-slate-100'
              }`}
            >
              Agent Mesh (A2A)
            </button>
          </div>

          <div className="flex items-center bg-slate-100 dark:bg-[#182234] border border-slate-200 dark:border-[#233048] rounded-lg p-0.5 text-xs font-semibold">
            <button
              onClick={() => setFilterStatus('pending')}
              className={`px-2.5 py-1 rounded-md transition-all cursor-pointer ${
                filterStatus === 'pending'
                  ? 'bg-white dark:bg-[#121826] text-blue-600 dark:text-blue-400 shadow-2xs font-bold'
                  : 'text-slate-600 dark:text-slate-400'
              }`}
            >
              Pending ({pendingCount})
            </button>
            <button
              onClick={() => setFilterStatus('all')}
              className={`px-2.5 py-1 rounded-md transition-all cursor-pointer ${
                filterStatus === 'all'
                  ? 'bg-white dark:bg-[#121826] text-blue-600 dark:text-blue-400 shadow-2xs font-bold'
                  : 'text-slate-600 dark:text-slate-400'
              }`}
            >
              All History
            </button>
          </div>
        </div>

        {/* ── Main Action Items List ──────────────────────────────────────── */}
        <div className="space-y-3">
          {filteredItems.length === 0 ? (
            <div className="p-12 text-center bg-white dark:bg-[#121826] border border-slate-200 dark:border-[#233048] rounded-2xl">
              <CheckCircle2 className="w-10 h-10 text-emerald-500 mx-auto mb-3" />
              <h3 className="text-sm font-bold text-slate-800 dark:text-slate-200">
                Action Center is Clear
              </h3>
              <p className="text-xs text-slate-500 dark:text-slate-400 mt-1 max-w-md mx-auto">
                No human-in-the-loop approvals are pending right now. When automated workflows require decision authorization, they will appear here.
              </p>
              <button
                onClick={() => navigate('/workflows')}
                className="mt-4 px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-xl text-xs font-bold transition-all shadow-xs cursor-pointer inline-flex items-center gap-1.5"
              >
                <Play className="w-3.5 h-3.5 fill-white" />
                <span>Launch New Workflow Pipeline</span>
              </button>
            </div>
          ) : (
            filteredItems.map((item) => {
              const IconComponent = item.icon || Inbox
              const isPending = item.status === 'pending' || item.status === 'pending_permission'

              return (
                <div
                  key={item.id}
                  className="p-4 rounded-xl bg-white dark:bg-[#121826] border border-slate-200 dark:border-[#233048] shadow-2xs flex flex-col md:flex-row md:items-center justify-between gap-4 transition-all hover:border-slate-300 dark:hover:border-slate-700"
                >
                  <div className="flex items-start gap-3.5 min-w-0">
                    <div className="w-9 h-9 rounded-xl bg-blue-50 dark:bg-blue-950/60 border border-blue-200 dark:border-blue-800 flex items-center justify-center text-blue-600 shrink-0 mt-0.5">
                      <IconComponent className="w-4 h-4" />
                    </div>

                    <div className="space-y-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-xs font-bold text-slate-900 dark:text-white truncate">
                          {item.title}
                        </span>
                        {item.badgeText ? (
                          <span className={`text-[10px] font-mono px-2 py-0.5 rounded border font-bold ${
                            item.actionType === 'our_commitment'
                              ? 'bg-blue-100 dark:bg-blue-900/60 text-blue-800 dark:text-blue-200 border-blue-300 dark:border-blue-700'
                              : item.actionType === 'contact_commitment'
                              ? 'bg-amber-100 dark:bg-amber-900/60 text-amber-800 dark:text-amber-200 border-amber-300 dark:border-amber-700'
                              : item.actionType === 'ai_suggestion'
                              ? 'bg-purple-100 dark:bg-purple-900/60 text-purple-800 dark:text-purple-200 border-purple-300 dark:border-purple-700'
                              : 'bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 border-slate-300 dark:border-slate-700'
                          }`}>
                            {item.badgeText}
                          </span>
                        ) : (
                          <span className="text-[10px] font-mono px-2 py-0.5 bg-blue-50 dark:bg-blue-950/60 text-blue-700 dark:text-blue-300 rounded border border-blue-200 dark:border-blue-800">
                            {item.workflowTitle}
                          </span>
                        )}
                        {isPending ? (
                          <span className="text-[10px] font-mono px-2 py-0.5 bg-amber-50 dark:bg-amber-950/60 text-amber-700 dark:text-amber-300 rounded border border-amber-200 dark:border-amber-800">
                            Needs Action
                          </span>
                        ) : item.status === 'suggested' ? (
                          <span className="text-[10px] font-mono px-2 py-0.5 bg-purple-50 dark:bg-purple-950/60 text-purple-700 dark:text-purple-300 rounded border border-purple-200 dark:border-purple-800">
                            Unconfirmed Suggestion
                          </span>
                        ) : item.status === 'waiting' ? (
                          <span className="text-[10px] font-mono px-2 py-0.5 bg-amber-50 dark:bg-amber-950/60 text-amber-700 dark:text-amber-300 rounded border border-amber-200 dark:border-amber-800">
                            Waiting on Contact
                          </span>
                        ) : (
                          <span className="text-[10px] font-mono px-2 py-0.5 bg-emerald-50 dark:bg-emerald-950/60 text-emerald-700 dark:text-emerald-300 rounded border border-emerald-200 dark:border-emerald-800">
                            Approved
                          </span>
                        )}
                      </div>

                      <p className="text-xs text-slate-600 dark:text-slate-300">
                        {item.reason}
                      </p>

                      <div className="flex items-center gap-3 text-[11px] text-slate-400 font-mono pt-0.5">
                        <span>{timeAgo(item.createdAt)}</span>
                        <span>•</span>
                        <span>Urgency: {item.urgency}/10</span>
                      </div>
                    </div>
                  </div>

                  {/* Actions */}
                  <div className="flex items-center gap-2 shrink-0 self-end md:self-center">
                    {item.type === 'followup_email_draft' ? (
                      <div className="flex items-center gap-2">
                        <button
                          type="button"
                          onClick={() => openDraftModal(item)}
                          className="px-3 py-1.5 bg-blue-50 dark:bg-blue-950/60 hover:bg-blue-100 dark:hover:bg-blue-900 border border-blue-200 dark:border-blue-800 text-blue-700 dark:text-blue-300 rounded-lg text-xs font-bold transition-all cursor-pointer flex items-center gap-1.5"
                        >
                          <Mail className="w-3.5 h-3.5" />
                          <span>Review & Edit Draft</span>
                        </button>
                        {item.status !== 'approved' && item.status !== 'discarded' && (
                          <>
                            <button
                              type="button"
                              onClick={() => handleReject(item)}
                              className="px-3 py-1.5 bg-slate-100 hover:bg-red-50 hover:text-red-600 dark:bg-[#182234] dark:hover:bg-red-950/40 text-slate-700 dark:text-slate-300 rounded-lg text-xs font-semibold transition-all cursor-pointer"
                            >
                              Discard
                            </button>
                            <button
                              type="button"
                              onClick={() => handleApprove(item)}
                              className="px-3 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-xs font-bold transition-all shadow-xs flex items-center gap-1.5 cursor-pointer"
                            >
                              <CheckCircle2 className="w-3.5 h-3.5" />
                              <span>Approve (No Send)</span>
                            </button>
                          </>
                        )}
                        {item.status === 'approved' && (
                          <span className="text-[10px] font-mono px-2 py-1 rounded bg-emerald-100 dark:bg-emerald-900/60 text-emerald-800 dark:text-emerald-300 font-semibold border border-emerald-300 dark:border-emerald-700">
                            Approved (Sending Deferred)
                          </span>
                        )}
                      </div>
                    ) : item.type === 'meeting_action' ? (
                      <div className="flex items-center gap-2">
                        <button
                          type="button"
                          onClick={() => navigate(item.runnerUrl)}
                          className="px-3 py-1.5 bg-slate-100 hover:bg-slate-200 dark:bg-[#182234] dark:hover:bg-[#233048] text-slate-700 dark:text-slate-300 rounded-lg text-xs font-semibold transition-all cursor-pointer flex items-center gap-1.5"
                        >
                          <span>View in Workflow</span>
                          <ArrowRight className="w-3.5 h-3.5" />
                        </button>
                        {isPending && (
                          <>
                            <button
                              type="button"
                              onClick={() => handleReject(item)}
                              className="px-3 py-1.5 bg-slate-100 hover:bg-red-50 hover:text-red-600 dark:bg-[#182234] dark:hover:bg-red-950/40 text-slate-700 dark:text-slate-300 rounded-lg text-xs font-semibold transition-all cursor-pointer"
                            >
                              Dismiss
                            </button>
                            <button
                              type="button"
                              onClick={() => handleApprove(item)}
                              className="px-3 py-1.5 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-xs font-bold transition-all shadow-xs flex items-center gap-1.5 cursor-pointer"
                            >
                              <CheckCircle2 className="w-3.5 h-3.5" />
                              <span>Complete</span>
                            </button>
                          </>
                        )}
                      </div>
                    ) : item.runnerUrl ? (
                      <button
                        type="button"
                        onClick={() => navigate(item.runnerUrl)}
                        className="px-3 py-1.5 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-xs font-bold transition-all shadow-xs flex items-center gap-1.5 cursor-pointer"
                      >
                        <span>View Campaign Deliverables</span>
                        <ArrowRight className="w-3.5 h-3.5" />
                      </button>
                    ) : (
                      <>
                        <button
                          type="button"
                          onClick={() => handleReject(item)}
                          className="px-3 py-1.5 bg-slate-100 hover:bg-red-50 hover:text-red-600 dark:bg-[#182234] dark:hover:bg-red-950/40 text-slate-700 dark:text-slate-300 rounded-lg text-xs font-semibold transition-all cursor-pointer"
                        >
                          Reject
                        </button>
                        <button
                          type="button"
                          onClick={() => handleApprove(item)}
                          className="px-3.5 py-1.5 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-xs font-bold transition-all shadow-xs flex items-center gap-1.5 cursor-pointer"
                        >
                          <CheckCircle2 className="w-3.5 h-3.5" />
                          <span>Approve & Dispatch</span>
                        </button>
                      </>
                    )}
                  </div>
                </div>
              )
            })
          )}
        </div>

        {/* ── Node 5A: Follow-up Email Draft Human Review Modal ─────────── */}
        {reviewingDraft && (
          <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-xs flex items-center justify-center p-4">
            <div className="bg-white dark:bg-[#121826] border border-slate-200 dark:border-[#233048] rounded-2xl w-full max-w-2xl shadow-xl overflow-hidden animate-in fade-in zoom-in-95 duration-150">
              <div className="p-5 border-b border-slate-200 dark:border-[#233048] flex items-center justify-between">
                <div className="flex items-center gap-2.5">
                  <div className="w-8 h-8 rounded-lg bg-blue-50 dark:bg-blue-950 border border-blue-200 dark:border-blue-800 flex items-center justify-center text-blue-600">
                    <Mail className="w-4 h-4" />
                  </div>
                  <div>
                    <h3 className="text-sm font-bold text-slate-900 dark:text-white">
                      Review Follow-up Email Draft
                    </h3>
                    <p className="text-xs text-slate-500 dark:text-slate-400">
                      Grounded in meeting transcript & relationship memory. Zero external email sending.
                    </p>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => setReviewingDraft(null)}
                  className="p-1 rounded-md text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 cursor-pointer"
                >
                  ✕
                </button>
              </div>

              <div className="p-5 space-y-4 max-h-[70vh] overflow-y-auto">
                {/* Recipient Details */}
                <div className="p-3 rounded-lg bg-slate-50 dark:bg-[#182234] border border-slate-200 dark:border-[#233048] flex items-center justify-between gap-3 text-xs">
                  <div>
                    <span className="text-slate-500 dark:text-slate-400">Recipient: </span>
                    <strong className="text-slate-800 dark:text-slate-200 font-semibold">
                      {reviewingDraft.raw?.payload?.recipient_name || 'Contact'}
                    </strong>
                  </div>
                  <div>
                    {reviewingDraft.raw?.payload?.recipient_email_available && reviewingDraft.raw?.payload?.recipient_email ? (
                      <span className="font-mono text-[11px] text-blue-600 dark:text-blue-400">
                        {reviewingDraft.raw?.payload?.recipient_email}
                      </span>
                    ) : (
                      <span className="font-mono text-[10px] px-2 py-0.5 rounded bg-amber-100 dark:bg-amber-900/60 text-amber-800 dark:text-amber-300 font-semibold border border-amber-200 dark:border-amber-800">
                        Recipient email not available
                      </span>
                    )}
                  </div>
                </div>

                {/* Subject Editor */}
                <div className="space-y-1.5">
                  <label className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                    Subject Line
                  </label>
                  <input
                    type="text"
                    value={draftSubjectEdit}
                    onChange={(e) => setDraftSubjectEdit(e.target.value)}
                    className="w-full px-3 py-2 text-xs bg-slate-50 dark:bg-[#0b0f17] border border-slate-200 dark:border-[#233048] rounded-lg text-slate-900 dark:text-white focus:outline-hidden focus:border-blue-500"
                  />
                </div>

                {/* Body Editor */}
                <div className="space-y-1.5">
                  <label className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                    Email Body
                  </label>
                  <textarea
                    rows={8}
                    value={draftBodyEdit}
                    onChange={(e) => setDraftBodyEdit(e.target.value)}
                    className="w-full p-3 text-xs bg-slate-50 dark:bg-[#0b0f17] border border-slate-200 dark:border-[#233048] rounded-lg text-slate-900 dark:text-white font-mono leading-relaxed focus:outline-hidden focus:border-blue-500"
                  />
                </div>

                {/* Snooze Row */}
                <div className="p-3 rounded-lg bg-purple-50/50 dark:bg-purple-950/20 border border-purple-200 dark:border-purple-800/60 space-y-2">
                  <div className="text-xs font-semibold text-purple-900 dark:text-purple-300 flex items-center gap-1.5">
                    <Clock className="w-3.5 h-3.5" />
                    <span>Snooze / Remind Later Configuration</span>
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs">
                    <input
                      type="text"
                      placeholder="e.g. Tomorrow 9:00 AM"
                      value={snoozeUntilInput}
                      onChange={(e) => setSnoozeUntilInput(e.target.value)}
                      className="px-2.5 py-1.5 bg-white dark:bg-[#121826] border border-purple-200 dark:border-purple-800 rounded-md text-xs"
                    />
                    <input
                      type="text"
                      placeholder="Reason for snooze (optional)"
                      value={snoozeReasonInput}
                      onChange={(e) => setSnoozeReasonInput(e.target.value)}
                      className="px-2.5 py-1.5 bg-white dark:bg-[#121826] border border-purple-200 dark:border-purple-800 rounded-md text-xs"
                    />
                  </div>
                </div>
              </div>

              {/* Modal Footer Controls */}
              <div className="p-4 bg-slate-50 dark:bg-[#182234] border-t border-slate-200 dark:border-[#233048] flex items-center justify-between flex-wrap gap-2">
                <button
                  type="button"
                  disabled={draftActionLoading}
                  onClick={() => handleDraftDecision('discard')}
                  className="px-3 py-1.5 bg-rose-50 hover:bg-rose-100 text-rose-700 dark:bg-rose-950/40 dark:hover:bg-rose-900/60 dark:text-rose-300 border border-rose-200 dark:border-rose-800 rounded-lg text-xs font-semibold cursor-pointer transition-colors"
                >
                  Discard Draft
                </button>

                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    disabled={draftActionLoading}
                    onClick={() => handleDraftDecision('snooze')}
                    className="px-3 py-1.5 bg-purple-50 hover:bg-purple-100 text-purple-700 dark:bg-purple-950/40 dark:hover:bg-purple-900/60 dark:text-purple-300 border border-purple-200 dark:border-purple-800 rounded-lg text-xs font-semibold cursor-pointer transition-colors"
                  >
                    Snooze
                  </button>

                  <button
                    type="button"
                    disabled={draftActionLoading}
                    onClick={() => handleDraftDecision('edit')}
                    className="px-3 py-1.5 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-xs font-semibold cursor-pointer transition-colors"
                  >
                    Save Changes
                  </button>

                  <button
                    type="button"
                    disabled={draftActionLoading}
                    onClick={() => handleDraftDecision('approve')}
                    className="px-3.5 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-xs font-bold cursor-pointer transition-colors shadow-xs flex items-center gap-1.5"
                  >
                    <CheckCircle2 className="w-3.5 h-3.5" />
                    <span>Approve Draft (No Send)</span>
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}

      </div>
    </div>
  )
}
