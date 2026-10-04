// frontend/src/components/shell/NotificationBell.jsx
import { useState, useEffect, useRef, useCallback } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import {
  Bell, Check, X, ShieldAlert, Sparkles, Layers, Building2,
  ExternalLink, CheckCircle2, Clock, Inbox, ChevronRight, User
} from 'lucide-react'
import { useAuth } from '../../contexts/AuthContext'
import { useWebSocket } from '../../contexts/WSContext'

export function NotificationBell() {
  const { api, user, isAdmin } = useAuth()
  const { subscribe } = useWebSocket()
  const navigate = useNavigate()

  const [isOpen, setIsOpen] = useState(false)
  const [notifications, setNotifications] = useState([])
  const [activeTab, setActiveTab] = useState('all') // 'all' | 'requests' | 'workflows' | 'whats_new'
  const [loading, setLoading] = useState(false)
  const [actionLoading, setActionLoading] = useState({})
  const dropdownRef = useRef(null)

  // Fetch notifications from backend
  const fetchNotifications = useCallback(async () => {
    try {
      const res = await api.get('/notifications')
      if (Array.isArray(res)) {
        // Merge with local storage read states
        const readIds = new Set(JSON.parse(localStorage.getItem('smbflow_read_notifs') || '[]'))
        setNotifications(res.map(n => ({
          ...n,
          read: n.read || readIds.has(n.id)
        })))
      }
    } catch (err) {
      console.error('Failed to fetch notifications:', err)
    }
  }, [api])

  useEffect(() => {
    fetchNotifications()
  }, [fetchNotifications])

  // Close dropdown on click outside
  useEffect(() => {
    function handleClickOutside(event) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setIsOpen(false)
      }
    }
    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside)
    }
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [isOpen])

  // Real-time WebSocket listener
  useEffect(() => {
    const unsubscribeReq = subscribe('workflow.access_requested', (event) => {
      const newNotif = {
        id: event.id || String(Date.now()),
        type: 'access_request',
        title: 'New Workflow Access Request',
        message: `${event.user_email} (${event.org_name}) requested access to ${event.workflow_name}`,
        timestamp: event.timestamp || new Date().toISOString(),
        read: false,
        actionable: isAdmin,
        meta: {
          approval_id: event.id,
          workflow_key: event.workflow_key,
          workflow_name: event.workflow_name,
          org_id: event.org_id,
          org_name: event.org_name,
          user_email: event.user_email,
        }
      }
      setNotifications(prev => [newNotif, ...prev.filter(n => n.id !== newNotif.id)])
    })

    const unsubscribeApprove = subscribe('workflow.access_approved', (event) => {
      const newNotif = {
        id: `approved_${event.approval_id || Date.now()}`,
        type: 'workflow_assigned',
        title: 'Access Approved',
        message: `Access to '${event.workflow_name}' has been approved by ${event.approved_by || 'Admin'}.`,
        timestamp: event.timestamp || new Date().toISOString(),
        read: false,
        actionable: false,
        meta: {
          workflow_key: event.workflow_key,
          workflow_name: event.workflow_name,
          url: `/workflows/${event.workflow_key}`
        }
      }
      setNotifications(prev => [newNotif, ...prev])
      fetchNotifications()
    })

    return () => {
      unsubscribeReq()
      unsubscribeApprove()
    }
  }, [subscribe, isAdmin, fetchNotifications])

  const unreadCount = notifications.filter(n => !n.read).length

  function markAllAsRead() {
    const allIds = notifications.map(n => n.id)
    localStorage.setItem('smbflow_read_notifs', JSON.stringify(allIds))
    setNotifications(prev => prev.map(n => ({ ...n, read: true })))
  }

  function markAsRead(id) {
    const readIds = new Set(JSON.parse(localStorage.getItem('smbflow_read_notifs') || '[]'))
    readIds.add(id)
    localStorage.setItem('smbflow_read_notifs', JSON.stringify([...readIds]))
    setNotifications(prev => prev.map(n => n.id === id ? { ...n, read: true } : n))
  }

  async function handleApprove(approvalId, meta) {
    setActionLoading(prev => ({ ...prev, [approvalId]: 'approving' }))
    try {
      await api.post(`/notifications/requests/${approvalId}/approve`, {})
      markAsRead(approvalId)
      setNotifications(prev => prev.map(n => {
        if (n.id === approvalId || n.meta?.approval_id === approvalId) {
          return {
            ...n,
            actionable: false,
            read: true,
            meta: { ...n.meta, status: 'approved' },
            message: `✓ Approved access to ${meta.workflow_name || 'workflow'}`
          }
        }
        return n
      }))
    } catch (err) {
      alert(err?.response?.data?.detail || err.message || 'Failed to approve request')
    } finally {
      setActionLoading(prev => ({ ...prev, [approvalId]: null }))
    }
  }

  async function handleReject(approvalId) {
    setActionLoading(prev => ({ ...prev, [approvalId]: 'rejecting' }))
    try {
      await api.post(`/notifications/requests/${approvalId}/reject`, {})
      markAsRead(approvalId)
      setNotifications(prev => prev.map(n => {
        if (n.id === approvalId || n.meta?.approval_id === approvalId) {
          return {
            ...n,
            actionable: false,
            read: true,
            meta: { ...n.meta, status: 'rejected' },
            message: `✗ Access request rejected`
          }
        }
        return n
      }))
    } catch (err) {
      alert(err?.response?.data?.detail || err.message || 'Failed to reject request')
    } finally {
      setActionLoading(prev => ({ ...prev, [approvalId]: null }))
    }
  }

  const filteredNotifications = notifications.filter(n => {
    if (activeTab === 'all') return true
    if (activeTab === 'requests') return n.type === 'access_request'
    if (activeTab === 'workflows') return n.type === 'workflow_assigned'
    if (activeTab === 'whats_new') return n.type === 'whats_new' || n.type === 'system'
    return true
  })

  function formatTime(iso) {
    if (!iso) return 'Just now'
    try {
      const d = new Date(iso)
      const diff = Math.floor((Date.now() - d.getTime()) / 1000)
      if (diff < 60) return 'Just now'
      if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
      if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`
      return d.toLocaleDateString()
    } catch (_) {
      return 'Recently'
    }
  }

  return (
    <div className="relative" ref={dropdownRef}>
      {/* Bell Trigger Button */}
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="relative w-8 h-8 rounded-full border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 hover:bg-slate-100 dark:hover:bg-slate-700 flex items-center justify-center text-slate-600 dark:text-slate-300 transition-colors cursor-pointer"
        title="Notifications & Access Requests"
      >
        <Bell className="w-4 h-4" />
        {unreadCount > 0 && (
          <span className="absolute -top-1 -right-1 flex h-4 min-w-[16px] items-center justify-center rounded-full bg-blue-600 px-1 text-[9px] font-bold text-white ring-2 ring-white dark:ring-[#0b0f17] animate-pulse">
            {unreadCount > 9 ? '9+' : unreadCount}
          </span>
        )}
      </button>

      {/* Dropdown Menu */}
      {isOpen && (
        <div className="absolute right-0 mt-2 w-80 sm:w-96 rounded-2xl bg-white dark:bg-[#121826] border border-slate-200 dark:border-[#233048] shadow-2xl z-50 overflow-hidden animate-in fade-in slide-in-from-top-2 duration-150">
          {/* Header */}
          <div className="p-3.5 border-b border-slate-100 dark:border-[#1e2a3f] flex items-center justify-between bg-slate-50/70 dark:bg-[#162030]/60">
            <div className="flex items-center gap-2">
              <span className="text-xs font-bold text-slate-900 dark:text-white">Notifications</span>
              {unreadCount > 0 && (
                <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-blue-500/10 text-blue-600 dark:text-blue-400 border border-blue-500/20">
                  {unreadCount} unread
                </span>
              )}
            </div>
            {unreadCount > 0 && (
              <button
                type="button"
                onClick={markAllAsRead}
                className="text-[11px] font-medium text-blue-600 dark:text-blue-400 hover:underline cursor-pointer"
              >
                Mark all read
              </button>
            )}
          </div>

          {/* Filter Tabs */}
          <div className="flex items-center gap-1 px-3 py-2 border-b border-slate-100 dark:border-[#1e2a3f] bg-white dark:bg-[#121826] overflow-x-auto text-[11px]">
            {[
              { id: 'all', label: 'All' },
              { id: 'requests', label: 'Requests' },
              { id: 'workflows', label: 'Workflows' },
              { id: 'whats_new', label: "What's New" },
            ].map(tab => (
              <button
                key={tab.id}
                type="button"
                onClick={() => setActiveTab(tab.id)}
                className={`px-2.5 py-1 rounded-lg font-semibold transition-all cursor-pointer shrink-0 ${
                  activeTab === tab.id
                    ? 'bg-blue-50 dark:bg-blue-950/50 text-blue-600 dark:text-blue-400 border border-blue-200 dark:border-blue-900/50'
                    : 'text-slate-500 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white'
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>

          {/* Notification List */}
          <div className="max-h-[380px] overflow-y-auto divide-y divide-slate-100 dark:divide-[#1e2a3f]">
            {filteredNotifications.length === 0 ? (
              <div className="py-10 px-4 text-center">
                <Inbox className="w-8 h-8 text-slate-300 dark:text-slate-600 mx-auto mb-2" />
                <p className="text-xs font-semibold text-slate-700 dark:text-slate-300">No notifications</p>
                <p className="text-[11px] text-slate-400 dark:text-slate-500 mt-0.5">You're all caught up with requests & updates.</p>
              </div>
            ) : (
              filteredNotifications.map(notif => {
                const isRequest = notif.type === 'access_request'
                const isAssigned = notif.type === 'workflow_assigned'
                const isWhatsNew = notif.type === 'whats_new'

                return (
                  <div
                    key={notif.id}
                    onClick={() => markAsRead(notif.id)}
                    className={`p-3.5 transition-colors hover:bg-slate-50/80 dark:hover:bg-[#162030]/60 ${
                      !notif.read ? 'bg-blue-50/30 dark:bg-blue-950/20' : ''
                    }`}
                  >
                    <div className="flex items-start gap-2.5">
                      {/* Icon */}
                      <div className={`w-7 h-7 rounded-lg flex items-center justify-center shrink-0 mt-0.5 ${
                        isRequest
                          ? 'bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20'
                          : isAssigned
                          ? 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20'
                          : 'bg-indigo-500/10 text-indigo-600 dark:text-indigo-400 border border-indigo-500/20'
                      }`}>
                        {isRequest ? <ShieldAlert size={14} /> : isAssigned ? <Layers size={14} /> : <Sparkles size={14} />}
                      </div>

                      <div className="min-w-0 flex-1">
                        <div className="flex items-center justify-between gap-1">
                          <p className="text-xs font-bold text-slate-900 dark:text-white truncate">{notif.title}</p>
                          <span className="text-[10px] text-slate-400 shrink-0 font-mono">{formatTime(notif.timestamp)}</span>
                        </div>
                        <p className="text-xs text-slate-600 dark:text-slate-300 mt-1 leading-normal">{notif.message}</p>

                        {/* Extra metadata tags */}
                        {isRequest && notif.meta && (
                          <div className="mt-2 p-2 rounded-lg bg-slate-50 dark:bg-[#0b0f17] border border-slate-200/80 dark:border-[#1e2a3f] text-[11px] space-y-1">
                            <div className="flex items-center gap-1.5 text-slate-600 dark:text-slate-400">
                              <Building2 size={12} className="text-blue-500" />
                              <span className="font-semibold text-slate-800 dark:text-slate-200">{notif.meta.org_name}</span>
                            </div>
                            <div className="flex items-center gap-1.5 text-slate-500 dark:text-slate-400">
                              <User size={12} />
                              <span className="truncate">{notif.meta.user_email}</span>
                            </div>
                            {notif.meta.reason && (
                              <p className="italic text-slate-500 dark:text-slate-400 text-[10px] pt-1 border-t border-slate-100 dark:border-[#1a2336]">
                                "{notif.meta.reason}"
                              </p>
                            )}
                          </div>
                        )}

                        {/* 1-Click Action Buttons for Admins */}
                        {notif.actionable && isRequest && (
                          <div className="flex items-center gap-2 mt-2.5">
                            <button
                              type="button"
                              disabled={actionLoading[notif.meta?.approval_id]}
                              onClick={(e) => {
                                e.stopPropagation()
                                handleApprove(notif.meta?.approval_id || notif.id, notif.meta)
                              }}
                              className="px-2.5 py-1 rounded-lg bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 text-white text-[11px] font-semibold transition-all cursor-pointer flex items-center gap-1 shadow-2xs"
                            >
                              <Check size={12} />
                              <span>{actionLoading[notif.meta?.approval_id] === 'approving' ? 'Approving...' : 'Approve & Assign'}</span>
                            </button>
                            <button
                              type="button"
                              disabled={actionLoading[notif.meta?.approval_id]}
                              onClick={(e) => {
                                e.stopPropagation()
                                handleReject(notif.meta?.approval_id || notif.id)
                              }}
                              className="px-2 py-1 rounded-lg bg-slate-100 hover:bg-slate-200 dark:bg-[#1e293b] dark:hover:bg-[#283548] text-slate-600 dark:text-slate-300 text-[11px] font-semibold transition-all cursor-pointer"
                            >
                              Reject
                            </button>
                          </div>
                        )}

                        {/* Link for What's New or Assigned Workflows */}
                        {notif.meta?.url && (
                          <div className="mt-2">
                            <Link
                              to={notif.meta.url}
                              onClick={() => setIsOpen(false)}
                              className="inline-flex items-center gap-1 text-[11px] font-semibold text-blue-600 dark:text-blue-400 hover:underline"
                            >
                              <span>Explore Workflow</span>
                              <ExternalLink size={10} />
                            </Link>
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
          {isAdmin && (
            <div className="p-2.5 border-t border-slate-100 dark:border-[#1e2a3f] bg-slate-50 dark:bg-[#0b0f17] text-center">
              <Link
                to="/admin/workflows/assignments"
                onClick={() => setIsOpen(false)}
                className="text-[11px] font-semibold text-blue-600 dark:text-blue-400 hover:underline flex items-center justify-center gap-1"
              >
                <span>Manage Workflow Assignments</span>
                <ChevronRight size={12} />
              </Link>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
