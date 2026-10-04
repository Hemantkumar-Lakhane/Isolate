// frontend/src/pages/client/EmailQueuePage.jsx
// ─────────────────────────────────────────────────────────────────────────────
// KEY CHANGES vs original:
//  1. Split-pane / master-detail layout (Apple Mail / Outlook UX)
//  2. Keyboard shortcut: Cmd/Ctrl+Enter to approve and auto-advance
//  3. Keyboard shortcut: Escape to reject / close
//  4. No modal round-trips — edit & approve in-place in right panel
//  5. Status badge counts update optimistically
// ─────────────────────────────────────────────────────────────────────────────
import { useState, useEffect, useCallback, useRef } from 'react'
import { useAuth }      from '../../contexts/AuthContext'
import { useWebSocket } from '../../contexts/WSContext'
import {
  Card, Button, Alert, Spinner, EmptyState, TabGroup, Badge, cn,
} from '../../components/ui'
import { timeAgo, truncate } from '../../utils/helpers'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Mail, Check, X, ChevronRight, User, Clock, Tag,
  Keyboard, ArrowRight, AlertTriangle,
} from 'lucide-react'

const EMAIL_TYPE_COLORS = {
  critical:                'text-red-300 bg-red-900/20 border-red-700/40',
  at_risk:                 'text-yellow-300 bg-yellow-900/20 border-yellow-700/40',
  critical_price_discussion:'text-orange-300 bg-orange-900/20 border-orange-800/40',
  lease_renewal:           'text-teal-300 bg-teal-900/20 border-teal-800/40',
  default:                 'text-blue-300 bg-blue-900/20 border-blue-700/40',
}

function typeColor(t) {
  return EMAIL_TYPE_COLORS[t] || EMAIL_TYPE_COLORS.default
}

// ── Draft List Item ───────────────────────────────────────────────────────────
function DraftListItem({ item, isSelected, onClick }) {
  const isPending = item.status === 'pending'
  return (
    <button
      onClick={onClick}
      className={cn(
        'w-full text-left px-4 py-3 border-b border-[rgb(var(--border-subtle))] transition-all duration-150',
        isSelected
          ? 'bg-primary-500/8 border-l-2 border-l-primary-500'
          : 'hover:bg-[rgb(var(--bg-hover))] border-l-2 border-l-transparent',
      )}
    >
      <div className="flex items-start gap-2.5">
        {/* Unread dot */}
        <div className={cn(
          'w-2 h-2 rounded-full flex-shrink-0 mt-1.5',
          isPending ? 'bg-primary-400 animate-pulse' : 'bg-transparent',
        )} />
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between gap-1 mb-0.5">
            <p className={cn('text-xs font-semibold truncate', isSelected ? 'text-primary-300' : 'text-[rgb(var(--text-primary))]')}>
              {item.recipient_name}
            </p>
            <span className="text-[10px] text-[rgb(var(--text-muted))] flex-shrink-0">
              {timeAgo(item.created_at)}
            </span>
          </div>
          <p className="text-[11px] text-[rgb(var(--text-secondary))] truncate mb-0.5">{item.subject}</p>
          <div className="flex items-center gap-1.5">
            <span className={cn('text-[9px] px-1.5 py-0.5 rounded border font-mono', typeColor(item.email_type))}>
              {item.email_type || 'outreach'}
            </span>
            {!isPending && (
              <span className={cn(
                'text-[9px] px-1.5 py-0.5 rounded font-mono',
                item.status === 'approved' ? 'text-success bg-success/10' : 'text-danger bg-danger/10',
              )}>
                {item.status}
              </span>
            )}
          </div>
        </div>
      </div>
    </button>
  )
}

// ── Draft Editor Panel ────────────────────────────────────────────────────────
function DraftEditor({ item, api, onDone, onClose, totalPending }) {
  const [subject,    setSubject]    = useState(item?.subject || '')
  const [body,       setBody]       = useState(item?.body    || '')
  const [decidedBy,  setDecidedBy]  = useState('')
  const [rejReason,  setRejReason]  = useState('')
  const [showReject, setShowReject] = useState(false)
  const [loading,    setLoading]    = useState(null) // 'approve' | 'reject' | 'save'
  const [error,      setError]      = useState('')
  const [saved,      setSaved]      = useState(false)
  const nameRef = useRef(null)

  // Reset state when item changes
  useEffect(() => {
    setSubject(item?.subject || '')
    setBody(item?.body || '')
    setError('')
    setShowReject(false)
    setSaved(false)
    // Auto-focus name field after a short delay
    setTimeout(() => nameRef.current?.focus(), 100)
  }, [item?.id])

  // Keyboard shortcut: Cmd/Ctrl+Enter → approve
  useEffect(() => {
    const handler = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
        e.preventDefault()
        if (decidedBy.trim() && !loading) handleApprove()
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [decidedBy, loading, subject, body])

  if (!item) return null

  const isDirty = subject !== item.subject || body !== item.body

  const saveEdits = async () => {
    if (!isDirty) return
    setLoading('save'); setError('')
    try {
      await api.put(`/email-queue/${item.id}`, { subject, body })
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
    } catch (e) { setError(e.message) }
    finally { setLoading(null) }
  }

  const handleApprove = async () => {
    if (!decidedBy.trim()) { setError('Enter your name to approve'); nameRef.current?.focus(); return }
    if (isDirty) await saveEdits()
    setLoading('approve'); setError('')
    try {
      await api.post(`/email-queue/${item.id}/approve`, { decided_by: decidedBy })
      onDone('approved')
    } catch (e) { setError(e.message) }
    finally { setLoading(null) }
  }

  const handleReject = async () => {
    if (!decidedBy.trim()) { setError('Enter your name to reject'); nameRef.current?.focus(); return }
    setLoading('reject'); setError('')
    try {
      await api.post(`/email-queue/${item.id}/reject`, { decided_by: decidedBy, rejection_reason: rejReason })
      onDone('rejected')
    } catch (e) { setError(e.message) }
    finally { setLoading(null) }
  }

  const isPending = item.status === 'pending'
  const fieldCls = 'w-full bg-[rgb(var(--bg-input))] border border-[rgb(var(--border))] rounded-xl px-3 py-2 text-[rgb(var(--text-primary))] text-sm focus:outline-none focus:ring-2 focus:ring-primary-500/30 focus:border-primary-500/50 transition-all'

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-start justify-between px-5 py-4 border-b border-[rgb(var(--border))] bg-[rgb(var(--bg-elevated))]/60">
        <div className="flex items-start gap-3 min-w-0">
          <div className="w-9 h-9 rounded-xl bg-primary-500/15 flex items-center justify-center flex-shrink-0 mt-0.5">
            <Mail className="w-4 h-4 text-primary-400" />
          </div>
          <div className="min-w-0">
            <p className="text-sm font-bold text-[rgb(var(--text-primary))] truncate">{item.recipient_name}</p>
            <p className="text-xs text-[rgb(var(--text-muted))] truncate">{item.recipient_email}</p>
            <div className="flex items-center gap-2 mt-1 flex-wrap">
              <span className={cn('text-[10px] px-1.5 py-0.5 rounded border font-mono', typeColor(item.email_type))}>
                {item.email_type || 'outreach'}
              </span>
              {item.workflow_name && (
                <span className="text-[10px] text-[rgb(var(--text-muted))]">{item.workflow_name}</span>
              )}
              <span className="text-[10px] text-[rgb(var(--text-muted))] flex items-center gap-1">
                <Clock className="w-2.5 h-2.5" /> {timeAgo(item.created_at)}
              </span>
            </div>
          </div>
        </div>
        {/* Keyboard shortcut hint */}
        {isPending && (
          <div className="flex items-center gap-1 px-2 py-1 rounded-lg bg-[rgb(var(--bg-hover))] border border-[rgb(var(--border))] text-[10px] text-[rgb(var(--text-muted))] flex-shrink-0 ml-3">
            <Keyboard className="w-3 h-3" />
            <span>⌘↵ approve</span>
          </div>
        )}
      </div>

      {/* Scrollable editor content */}
      <div className="flex-1 overflow-y-auto px-5 py-4 space-y-4">
        {/* Sender info */}
        {item.csm_name && (
          <div className="flex items-center gap-2 text-xs text-[rgb(var(--text-muted))]">
            <User className="w-3.5 h-3.5" />
            <span>From: <span className="text-[rgb(var(--text-secondary))]">{item.csm_name}</span></span>
          </div>
        )}

        {/* Subject */}
        <div>
          <label className="block text-xs font-medium text-[rgb(var(--text-secondary))] mb-1.5">Subject</label>
          <input
            value={subject}
            onChange={e => setSubject(e.target.value)}
            readOnly={!isPending}
            className={cn(fieldCls, !isPending && 'opacity-70 cursor-default')}
          />
        </div>

        {/* Body */}
        <div>
          <label className="block text-xs font-medium text-[rgb(var(--text-secondary))] mb-1.5">
            Email Body
            {isPending && <span className="text-[rgb(var(--text-muted))] ml-2 font-normal">(edit before approving)</span>}
          </label>
          <textarea
            value={body}
            onChange={e => setBody(e.target.value)}
            readOnly={!isPending}
            rows={11}
            className={cn(fieldCls, 'resize-none font-mono leading-relaxed text-xs', !isPending && 'opacity-70 cursor-default')}
          />
        </div>

        {/* Inline save */}
        {isDirty && isPending && (
          <div className="flex items-center gap-2">
            <Button size="sm" variant="ghost" loading={loading === 'save'} onClick={saveEdits}>
              Save edits
            </Button>
            {saved && <span className="text-xs text-success flex items-center gap-1"><Check className="w-3 h-3" />Saved</span>}
          </div>
        )}

        {/* Rejection reason */}
        {showReject && isPending && (
          <motion.div
            initial={{ opacity: 0, y: -6 }}
            animate={{ opacity: 1, y: 0 }}
          >
            <label className="block text-xs font-medium text-[rgb(var(--text-secondary))] mb-1.5">
              Rejection reason <span className="text-[rgb(var(--text-muted))] font-normal">(optional)</span>
            </label>
            <textarea
              value={rejReason}
              onChange={e => setRejReason(e.target.value)}
              rows={2}
              className={cn(fieldCls, 'resize-none')}
              placeholder="e.g. Tone too aggressive, rewrite needed"
              autoFocus
            />
          </motion.div>
        )}

        {/* Review info for non-pending */}
        {!isPending && item.reviewed_by && (
          <div className={cn(
            'flex items-start gap-2 p-3 rounded-xl text-xs border',
            item.status === 'approved'
              ? 'bg-success/8 border-success/25 text-success'
              : 'bg-danger/8 border-danger/25 text-danger',
          )}>
            {item.status === 'approved' ? <Check className="w-3.5 h-3.5 flex-shrink-0 mt-0.5" /> : <X className="w-3.5 h-3.5 flex-shrink-0 mt-0.5" />}
            <div>
              <span className="font-semibold">{item.status === 'approved' ? 'Approved' : 'Rejected'}</span>
              {' '}by {item.reviewed_by}
              {item.rejection_reason && (
                <p className="mt-0.5 text-[rgb(var(--text-muted))]">{item.rejection_reason}</p>
              )}
            </div>
          </div>
        )}

        {error && (
          <div className="flex items-center gap-2 p-3 bg-danger/8 border border-danger/25 rounded-xl text-xs text-danger">
            <AlertTriangle className="w-3.5 h-3.5 flex-shrink-0" />
            {error}
          </div>
        )}
      </div>

      {/* Action footer — sticky at bottom */}
      {isPending && (
        <div className="flex-shrink-0 px-5 py-4 border-t border-[rgb(var(--border))] bg-[rgb(var(--bg-elevated))]/60 space-y-3">
          <div>
            <label className="block text-xs font-medium text-[rgb(var(--text-secondary))] mb-1.5">
              Your name <span className="text-danger">*</span>
            </label>
            <input
              ref={nameRef}
              value={decidedBy}
              onChange={e => setDecidedBy(e.target.value)}
              className={fieldCls}
              placeholder="Jane Smith"
            />
          </div>
          <div className="flex gap-2">
            <Button
              variant="success"
              loading={loading === 'approve'}
              onClick={handleApprove}
              disabled={!decidedBy.trim() || !!loading}
              className="flex-1"
              icon={<Check className="w-4 h-4" />}
            >
              Approve
            </Button>
            {!showReject ? (
              <Button
                variant="danger"
                onClick={() => setShowReject(true)}
                disabled={!!loading}
                className="flex-1"
                icon={<X className="w-4 h-4" />}
              >
                Reject
              </Button>
            ) : (
              <Button
                variant="danger"
                loading={loading === 'reject'}
                onClick={handleReject}
                disabled={!decidedBy.trim() || !!loading}
                className="flex-1"
                icon={<X className="w-4 h-4" />}
              >
                Confirm Reject
              </Button>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

// ── Main EmailQueuePage ───────────────────────────────────────────────────────
export default function EmailQueuePage() {
  const { user, api }  = useAuth()
  const { subscribe }  = useWebSocket()
  const tenantId       = user?.tenant_id

  const [tab,         setTab]       = useState('pending')
  const [items,       setItems]     = useState([])
  const [loading,     setLoading]   = useState(true)
  const [error,       setError]     = useState('')
  const [activeId,    setActiveId]  = useState(null)

  const load = useCallback(async () => {
    if (!tenantId) { setLoading(false); return }
    try {
      const data = await api.get(`/tenants/${tenantId}/email-queue?status=${tab}`)
      const arr  = Array.isArray(data) ? data : []
      setItems(arr)
      // Auto-select first pending item on load
      if (arr.length > 0 && !activeId) setActiveId(arr[0].id)
      setError('')
    } catch (err) { setError(err.message) }
    finally { setLoading(false) }
  }, [api, tenantId, tab])

  useEffect(() => {
    setActiveId(null) // reset selection on tab change
    load()
  }, [tab])

  useEffect(() => {
    const unsub = subscribe('email_draft_approved', load)
    return unsub
  }, [subscribe, load])

  // When an action completes, advance to next item
  const handleDone = useCallback((action) => {
    setItems(prev => {
      const idx  = prev.findIndex(i => i.id === activeId)
      const next = prev[idx + 1] || prev[idx - 1] || null
      // Remove the actioned item from list
      const remaining = prev.filter(i => i.id !== activeId)
      setActiveId(next ? next.id : remaining[0]?.id || null)
      return remaining
    })
    // Reload in background for fresh data
    setTimeout(load, 600)
  }, [activeId, load])

  const activeItem = items.find(i => i.id === activeId) || null

  const counts = {
    pending:  items.filter(i => i.status === 'pending').length,
    approved: items.filter(i => i.status === 'approved').length,
    rejected: items.filter(i => i.status === 'rejected').length,
  }

  if (!tenantId) return (
    <div className="flex items-center justify-center h-64 text-[rgb(var(--text-muted))] text-sm">
      No tenant assigned.
    </div>
  )

  if (loading) return (
    <div className="flex items-center justify-center h-64"><Spinner size="lg" /></div>
  )

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-xl font-bold text-[rgb(var(--text-primary))]">Email Queue</h1>
          <p className="text-xs text-[rgb(var(--text-muted))] mt-0.5">
            Review AI-generated drafts · approve to send · keyboard shortcuts available
          </p>
        </div>
        <Button size="sm" variant="secondary" onClick={load}>Refresh</Button>
      </div>

      {error && (
        <div className="flex items-center gap-2 p-3 bg-danger/8 border border-danger/25 rounded-xl text-xs text-danger">
          <AlertTriangle className="w-3.5 h-3.5" />{error}
        </div>
      )}

      {/* Tabs */}
      <TabGroup
        tabs={[
          { value: 'pending',  label: 'Pending',  badge: counts.pending  },
          { value: 'approved', label: 'Approved', badge: 0               },
          { value: 'rejected', label: 'Rejected', badge: 0               },
          { value: 'all',      label: 'All',       badge: 0               },
        ]}
        value={tab}
        onChange={setTab}
      />

      {/* Split-pane layout */}
      <div
        className="surface-card rounded-2xl border border-[rgb(var(--border))] overflow-hidden"
        style={{ height: 'calc(100vh - 260px)', minHeight: 480 }}
      >
        {items.length === 0 ? (
          <div className="h-full flex items-center justify-center">
            <EmptyState
              icon={Mail}
              title={tab === 'pending' ? 'No drafts waiting' : `No ${tab} drafts`}
              description={
                tab === 'pending'
                  ? 'Email drafts from your workflows will appear here for approval'
                  : `Drafts you've ${tab} will show here`
              }
            />
          </div>
        ) : (
          <div className="flex h-full">
            {/* ── LEFT: Scrollable list ─────────────────────────────────── */}
            <div className="w-72 flex-shrink-0 border-r border-[rgb(var(--border))] flex flex-col overflow-hidden">
              <div className="px-4 py-2.5 border-b border-[rgb(var(--border))] flex items-center justify-between bg-[rgb(var(--bg-elevated))]/50">
                <span className="text-xs font-semibold text-[rgb(var(--text-secondary))]">
                  {items.length} draft{items.length !== 1 ? 's' : ''}
                </span>
                {tab === 'pending' && items.length > 0 && (
                  <span className="text-[10px] text-[rgb(var(--text-muted))]">
                    {counts.pending} pending
                  </span>
                )}
              </div>
              <div className="flex-1 overflow-y-auto">
                {items.map(item => (
                  <DraftListItem
                    key={item.id}
                    item={item}
                    isSelected={item.id === activeId}
                    onClick={() => setActiveId(item.id)}
                  />
                ))}
              </div>
            </div>

            {/* ── RIGHT: Editor / detail ───────────────────────────────── */}
            <div className="flex-1 min-w-0 overflow-hidden">
              <AnimatePresence mode="wait">
                {activeItem ? (
                  <motion.div
                    key={activeItem.id}
                    initial={{ opacity: 0, x: 10 }}
                    animate={{ opacity: 1, x: 0 }}
                    exit={{ opacity: 0, x: -10 }}
                    transition={{ duration: 0.18, ease: 'easeOut' }}
                    className="h-full"
                  >
                    <DraftEditor
                      item={activeItem}
                      api={api}
                      onDone={handleDone}
                      onClose={() => setActiveId(null)}
                      totalPending={counts.pending}
                    />
                  </motion.div>
                ) : (
                  <motion.div
                    key="empty"
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    className="h-full flex items-center justify-center"
                  >
                    <div className="text-center">
                      <div className="w-12 h-12 rounded-2xl bg-[rgb(var(--bg-hover))] flex items-center justify-center mx-auto mb-3">
                        <Mail className="w-6 h-6 text-[rgb(var(--text-muted))]" />
                      </div>
                      <p className="text-sm text-[rgb(var(--text-muted))]">Select a draft to review</p>
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}