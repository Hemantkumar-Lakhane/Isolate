// frontend/src/components/shell/NotificationCenter.jsx
// ─────────────────────────────────────────────────────────────────────────────
// SMBFlow — Global & Personal Notification Center
// Features:
//   • Unified Bell Icon in TopHeader with real-time unread count badge
//   • Dual Scope Filter: 'Personal' (Tasks, Approvals, Runs) vs 'Global' (System, What's New)
//   • Real-time WebSocket refresh + automatic badge sync
//   • 1-Click Actions: Approve/Reject access requests, jump to workflow run, open review
//   • Dark & Light mode compliant enterprise design
// ─────────────────────────────────────────────────────────────────────────────

import React, { useState, useEffect, useRef, useMemo, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Bell, Check, CheckCheck, X, ExternalLink, ShieldCheck,
  AlertTriangle, Rocket, Sparkles, Info, Layers, UserCheck,
  ChevronRight, ArrowRight, Loader2, RefreshCw
} from 'lucide-react'
import { useAuth } from '../../contexts/AuthContext'
import { useWebSocket } from '../../contexts/WSContext'

export function NotificationCenter() {
  const navigate = useNavigate()
  const { api, isAdmin } = useAuth()
  const { subscribe } = useWebSocket()

  const [isOpen, setIsOpen] = useState(false)
  const [activeTab, setActiveTab] = useState('all') // 'all' | 'personal' | 'global'
  const [notifications, setNotifications] = useState([])
  const [loading, setLoading] = useState(false)
  const [actionLoadingId, setActionLoadingId] = useState(null)
  const [localReadIds, setLocalReadIds] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem('smbflow_read_notifications') || '[]')
    } catch (_) {
      return []
    }
  })

  const popoverRef = useRef(null)
  const buttonRef = useRef(null)

  // Fetch notifications from backend
  const fetchNotifications = useCallback(async () => {
    try {
      setLoading(true)
      const data = await api.get('/notifications')
      if (Array.isArray(data)) {
        setNotifications(data)
      }
    } catch (err) {
      console.warn('Failed to load notifications:', err)
    } finally {
      setLoading(false)
    }
  }, [api])

  useEffect(() => {
    fetchNotifications()

    // Real-time WebSocket event listeners
    const unsubs = [
      subscribe('workflow.access_requested', fetchNotifications),
      subscribe('workflow.access_approved', fetchNotifications),
      subscribe('escalation_created', fetchNotifications),
      subscribe('escalation_resolved', fetchNotifications),
      subscribe('workflow_completed', fetchNotifications),
      subscribe('notification_created', fetchNotifications),
    ]

    // Background interval poll every 40 seconds
    const interval = setInterval(fetchNotifications, 40000)

    return () => {
      unsubs.forEach(fn => fn && fn())
      clearInterval(interval)
    }
  }, [fetchNotifications, subscribe])

  // Click outside to close dropdown
  useEffect(() => {
    function handleClickOutside(event) {
      if (
        popoverRef.current &&
        !popoverRef.current.contains(event.target) &&
        buttonRef.current &&
        !buttonRef.current.contains(event.target)
      ) {
        setIsOpen(false)
      }
    }

    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside)
    }
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [isOpen])

  // Mark single notification as read
  const markAsRead = useCallback(async (id) => {
    setLocalReadIds(prev => {
      const next = Array.from(new Set([...prev, id]))
      try {
        localStorage.setItem('smbflow_read_notifications', JSON.stringify(next))
      } catch (_) {}
      return next
    })
    try {
      await api.post(`/notifications/${id}/read`)
    } catch (_) {}
  }, [api])

  // Mark all as read
  const markAllAsRead = useCallback(async () => {
    const allIds = notifications.map(n => n.id)
    setLocalReadIds(prev => {
      const next = Array.from(new Set([...prev, ...allIds]))
      try {
        localStorage.setItem('smbflow_read_notifications', JSON.stringify(next))
      } catch (_) {}
      return next
    })
    try {
      await api.post('/notifications/mark-all-read')
    } catch (_) {}
  }, [notifications, api])

  // Handle Admin 1-Click Approve / Reject
  const handleDecideAccess = async (approvalId, decision) => {
    if (!approvalId) return
    setActionLoadingId(approvalId)
    try {
      await api.post(`/notifications/requests/${approvalId}/${decision}`)
      markAsRead(approvalId)
      await fetchNotifications()
    } catch (err) {
      console.error(`Failed to ${decision} request:`, err)
    } finally {
      setActionLoadingId(null)
    }
  }

  // Handle clicking a notification item
  const handleItemClick = (notif) => {
    markAsRead(notif.id)
    if (notif.meta?.url) {
      setIsOpen(false)
      navigate(notif.meta.url)
    } else if (notif.type === 'escalation') {
      setIsOpen(false)
      navigate('/escalations')
    } else if (notif.type === 'access_request' && isAdmin) {
      setIsOpen(false)
      navigate('/admin/workflows/assignments')
    }
  }

  // Compute unread count
  const unreadCount = useMemo(() => {
    return notifications.filter(n => !n.read && !localReadIds.includes(n.id)).length
  }, [notifications, localReadIds])

  // Filtered notifications based on active tab
  const filteredNotifications = useMemo(() => {
    let list = notifications
    if (activeTab === 'personal') {
      list = list.filter(n => n.scope === 'personal')
    } else if (activeTab === 'global') {
      list = list.filter(n => n.scope === 'global')
    }
    return list
  }, [notifications, activeTab])

  // Format relative timestamp
  function formatRelativeTime(isoStr) {
    if (!isoStr) return 'Recently'
    try {
      const diffSec = Math.floor((new Date() - new Date(isoStr)) / 1000)
      if (diffSec < 60) return 'Just now'
      if (diffSec < 3600) return `${Math.floor(diffSec / 60)}m ago`
      if (diffSec < 86400) return `${Math.floor(diffSec / 3600)}h ago`
      return `${Math.floor(diffSec / 86400)}d ago`
    } catch (_) {
      return 'Recently'
    }
  }

  // Icon helper
  function getNotificationIcon(type, scope) {
    if (type === 'access_request') return <UserCheck className="w-4 h-4 text-blue-500" />
    if (type === 'escalation') return <AlertTriangle className="w-4 h-4 text-amber-500" />
    if (type === 'workflow_assigned') return <ShieldCheck className="w-4 h-4 text-emerald-500" />
    if (type === 'workflow_completed') return <Rocket className="w-4 h-4 text-purple-500" />
    if (type === 'whats_new') return <Sparkles className="w-4 h-4 text-indigo-500" />
    if (scope === 'global') return <Info className="w-4 h-4 text-sky-500" />
    return <Bell className="w-4 h-4 text-slate-400" />
  }

  return (
    <div className="relative">
      {/* ── Bell Icon Button ──────────────────────────────────────────────── */}
      <button
        ref={buttonRef}
        type="button"
        onClick={() => setIsOpen(prev => !prev)}
        className={`relative w-8 h-8 rounded-full border transition-all flex items-center justify-center cursor-pointer ${
          isOpen
            ? 'bg-blue-50 dark:bg-blue-950/60 border-blue-500 text-blue-600 dark:text-blue-400 shadow-xs'
            : 'border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 hover:bg-slate-100 dark:hover:bg-slate-700 text-slate-600 dark:text-slate-300'
        }`}
        title="Global & Personal Notifications"
      >
        <Bell className="w-4 h-4" />

        {/* Live Unread Badge */}
        {unreadCount > 0 && (
          <span className="absolute -top-1 -right-1 flex h-4 min-w-[16px] px-1 items-center justify-center rounded-full bg-blue-600 text-[9px] font-bold text-white shadow-xs animate-in zoom-in">
            {unreadCount > 9 ? '9+' : unreadCount}
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-blue-400 opacity-60 pointer-events-none" />
          </span>
        )}
      </button>

      {/* ── Notification Dropdown Flyout Panel ───────────────────────────── */}
      {isOpen && (
        <div
          ref={popoverRef}
          className="absolute right-0 mt-2 w-[380px] sm:w-[420px] max-w-[92vw] bg-white dark:bg-[#121826] border border-slate-200 dark:border-[#233048] rounded-2xl shadow-2xl z-50 overflow-hidden flex flex-col animate-in fade-in slide-in-from-top-2 duration-150 text-slate-800 dark:text-slate-100"
        >
          {/* Header */}
          <div className="p-3.5 border-b border-slate-200 dark:border-[#233048] flex items-center justify-between bg-slate-50/70 dark:bg-[#182234]/70 backdrop-blur-md">
            <div className="flex items-center gap-2">
              <div className="w-7 h-7 rounded-lg bg-blue-600/10 dark:bg-blue-400/10 text-blue-600 dark:text-blue-400 flex items-center justify-center">
                <Bell className="w-3.5 h-3.5" />
              </div>
              <div>
                <h3 className="text-xs font-bold text-slate-900 dark:text-white flex items-center gap-1.5">
                  <span>Notifications</span>
                  {unreadCount > 0 && (
                    <span className="px-1.5 py-0.2 bg-blue-100 dark:bg-blue-950/80 text-blue-700 dark:text-blue-300 rounded-full text-[10px] font-mono">
                      {unreadCount} new
                    </span>
                  )}
                </h3>
              </div>
            </div>

            <div className="flex items-center gap-1.5">
              {unreadCount > 0 && (
                <button
                  type="button"
                  onClick={markAllAsRead}
                  className="px-2 py-1 rounded-md text-[11px] font-medium text-slate-600 dark:text-slate-300 hover:text-blue-600 dark:hover:text-blue-400 hover:bg-slate-100 dark:hover:bg-[#233048] transition-colors flex items-center gap-1 cursor-pointer"
                  title="Mark all as read"
                >
                  <CheckCheck className="w-3 h-3" />
                  <span>Mark read</span>
                </button>
              )}
              <button
                type="button"
                onClick={fetchNotifications}
                disabled={loading}
                className="p-1.5 rounded-md text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 transition-colors cursor-pointer"
                title="Refresh"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin text-blue-500' : ''}`} />
              </button>
            </div>
          </div>

          {/* Tab Switcher: All | Personal | Global */}
          <div className="flex items-center px-3 pt-2 bg-white dark:bg-[#121826] border-b border-slate-100 dark:border-[#1a2336] gap-1">
            <button
              type="button"
              onClick={() => setActiveTab('all')}
              className={`pb-2 px-2.5 text-xs font-semibold border-b-2 transition-all cursor-pointer flex items-center gap-1.5 ${
                activeTab === 'all'
                  ? 'border-blue-600 text-blue-600 dark:text-blue-400'
                  : 'border-transparent text-slate-500 dark:text-slate-400 hover:text-slate-800 dark:hover:text-slate-200'
              }`}
            >
              <span>All</span>
              <span className="text-[10px] font-mono opacity-75">({notifications.length})</span>
            </button>

            <button
              type="button"
              onClick={() => setActiveTab('personal')}
              className={`pb-2 px-2.5 text-xs font-semibold border-b-2 transition-all cursor-pointer flex items-center gap-1.5 ${
                activeTab === 'personal'
                  ? 'border-blue-600 text-blue-600 dark:text-blue-400'
                  : 'border-transparent text-slate-500 dark:text-slate-400 hover:text-slate-800 dark:hover:text-slate-200'
              }`}
            >
              <span>Personal</span>
              <span className="text-[10px] font-mono opacity-75">
                ({notifications.filter(n => n.scope === 'personal').length})
              </span>
            </button>

            <button
              type="button"
              onClick={() => setActiveTab('global')}
              className={`pb-2 px-2.5 text-xs font-semibold border-b-2 transition-all cursor-pointer flex items-center gap-1.5 ${
                activeTab === 'global'
                  ? 'border-blue-600 text-blue-600 dark:text-blue-400'
                  : 'border-transparent text-slate-500 dark:text-slate-400 hover:text-slate-800 dark:hover:text-slate-200'
              }`}
            >
              <span>Global</span>
              <span className="text-[10px] font-mono opacity-75">
                ({notifications.filter(n => n.scope === 'global').length})
              </span>
            </button>
          </div>

          {/* Notification List Scroll Area */}
          <div className="max-h-[360px] overflow-y-auto divide-y divide-slate-100 dark:divide-[#1a2336] p-1.5 space-y-1">
            {filteredNotifications.length === 0 ? (
              <div className="py-10 px-4 text-center">
                <div className="w-10 h-10 rounded-full bg-slate-100 dark:bg-[#182234] text-slate-400 flex items-center justify-center mx-auto mb-2">
                  <Bell className="w-4 h-4" />
                </div>
                <p className="text-xs font-semibold text-slate-700 dark:text-slate-300">No notifications in this view</p>
                <p className="text-[11px] text-slate-400 mt-0.5">
                  {activeTab === 'personal'
                    ? 'No personal review tasks or pending requests.'
                    : activeTab === 'global'
                    ? 'No platform announcements at this time.'
                    : 'You are completely caught up!'}
                </p>
              </div>
            ) : (
              filteredNotifications.map((notif) => {
                const isRead = notif.read || localReadIds.includes(notif.id)
                const isPersonal = notif.scope === 'personal'
                const isActionableAdmin = notif.actionable && isAdmin

                return (
                  <div
                    key={notif.id}
                    onClick={() => handleItemClick(notif)}
                    className={`p-3 rounded-xl transition-all cursor-pointer border ${
                      !isRead
                        ? 'bg-blue-50/40 dark:bg-blue-950/20 border-blue-200/70 dark:border-blue-900/40'
                        : 'bg-white dark:bg-[#121826] border-transparent hover:bg-slate-50 dark:hover:bg-[#182234]'
                    }`}
                  >
                    <div className="flex items-start gap-2.5">
                      {/* Icon */}
                      <div className="w-7 h-7 rounded-lg bg-slate-100 dark:bg-[#182234] flex items-center justify-center shrink-0 mt-0.5">
                        {getNotificationIcon(notif.type, notif.scope)}
                      </div>

                      {/* Content */}
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center justify-between gap-1 mb-0.5">
                          <div className="flex items-center gap-1.5 min-w-0">
                            <span className={`text-[10px] font-semibold px-1.5 py-0.2 rounded-md uppercase tracking-wider ${
                              isPersonal
                                ? 'bg-purple-100 dark:bg-purple-950/60 text-purple-700 dark:text-purple-300'
                                : 'bg-sky-100 dark:bg-sky-950/60 text-sky-700 dark:text-sky-300'
                            }`}>
                              {isPersonal ? 'Personal' : 'Global'}
                            </span>
                            <span className="text-[11px] text-slate-400 font-mono">
                              {formatRelativeTime(notif.timestamp)}
                            </span>
                          </div>

                          {!isRead && (
                            <span className="w-2 h-2 rounded-full bg-blue-600 shrink-0" title="Unread" />
                          )}
                        </div>

                        <h4 className="text-xs font-bold text-slate-900 dark:text-white truncate">
                          {notif.title}
                        </h4>
                        <p className="text-[11px] text-slate-600 dark:text-slate-300 line-clamp-2 mt-0.5 leading-snug">
                          {notif.message}
                        </p>

                        {/* Admin 1-Click Action Bar for Access Requests */}
                        {isActionableAdmin && notif.meta?.approval_id && (
                          <div
                            className="mt-2 pt-2 border-t border-slate-200/70 dark:border-[#233048] flex items-center gap-2"
                            onClick={(e) => e.stopPropagation()}
                          >
                            <button
                              type="button"
                              disabled={actionLoadingId === notif.meta.approval_id}
                              onClick={() => handleDecideAccess(notif.meta.approval_id, 'approve')}
                              className="px-2.5 py-1 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-[11px] font-bold shadow-xs transition-colors flex items-center gap-1 cursor-pointer"
                            >
                              {actionLoadingId === notif.meta.approval_id ? (
                                <Loader2 className="w-3 h-3 animate-spin" />
                              ) : (
                                <Check className="w-3 h-3" />
                              )}
                              <span>Approve</span>
                            </button>

                            <button
                              type="button"
                              disabled={actionLoadingId === notif.meta.approval_id}
                              onClick={() => handleDecideAccess(notif.meta.approval_id, 'reject')}
                              className="px-2.5 py-1 bg-slate-100 dark:bg-[#182234] hover:bg-red-50 dark:hover:bg-red-950/40 text-slate-700 dark:text-slate-300 hover:text-red-600 rounded-lg text-[11px] font-medium transition-colors cursor-pointer"
                            >
                              Reject
                            </button>
                          </div>
                        )}

                        {/* Direct Action Link */}
                        {notif.meta?.url && !isActionableAdmin && (
                          <div className="mt-1.5 flex items-center gap-1 text-[11px] text-blue-600 dark:text-blue-400 font-semibold group-hover:underline">
                            <span>Open</span>
                            <ChevronRight className="w-3 h-3" />
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                )
              })
            )}
          </div>

          {/* Footer */}
          <div className="p-2.5 border-t border-slate-200 dark:border-[#233048] bg-slate-50/50 dark:bg-[#0b0f17]/50 flex items-center justify-between text-[11px] text-slate-500 dark:text-slate-400">
            <span>SMBFlow Live Notification Stream</span>
            <button
              type="button"
              onClick={() => {
                setIsOpen(false)
                navigate('/escalations')
              }}
              className="font-semibold text-blue-600 dark:text-blue-400 hover:underline flex items-center gap-0.5 cursor-pointer"
            >
              <span>Action Center</span>
              <ExternalLink className="w-3 h-3" />
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
