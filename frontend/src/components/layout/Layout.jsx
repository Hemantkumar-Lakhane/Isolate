// frontend/src/components/layout/Layout.jsx
import React, { useState, useEffect, useCallback, useRef } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import {
  LayoutDashboard, Settings2, Brain, DollarSign, Wrench,
  GitBranch, Bell, Shield, Users, Globe,
  LogOut, User, HelpCircle, Activity, ChevronDown, Zap
} from 'lucide-react'

import { useAuth }       from '../../contexts/AuthContext'
import { useWebSocket }  from '../../contexts/WSContext'
import { useTheme }      from '../../contexts/ThemeContext'
import { useBadgeStore, useUIStore } from '../../utils/appStore'
import { LiveDot, Breadcrumbs, cn } from '../ui'
import { Sidebar }       from './Sidebar'
import { PageHeader, ThemeToggle } from './PageHeader'

// ── Nav Definitions ────────────────────────────────────────────────────────────

const OPERATIONS_NAV = [
  { to: '/dashboard',         Icon: LayoutDashboard, label: 'Home' },
  { to: '/escalations',       Icon: Bell,            label: 'Action Center', badge: 'esc' },
  { to: '/workflows',         Icon: GitBranch,       label: 'Workflows' },
]

const CONFIGURATION_NAV = [
  { to: '/workflow-library', Icon: Settings2,       label: 'Workflow Library' },
]

const SETTINGS_NAV = [
  { to: '/config',            Icon: Settings2,       label: 'General' },
  { to: '/tools',             Icon: Wrench,          label: 'Integrations' },
  { to: '/budget',            Icon: DollarSign,      label: 'Budget & Billing' },
  { to: '/evidence',          Icon: Shield,          label: 'Evidence' },
]

const ADMIN_NAV = [
  { to: '/admin',        Icon: Globe,         label: 'Tenants' },
  { to: '/admin/users',  Icon: Users,         label: 'Users' },
  { to: '/admin/health', Icon: Activity,      label: 'Health' },
  { to: '/admin/fleet',  Icon: DollarSign,    label: 'Fleet Cost' },
]

const NAV_CONFIG = {
  adminNav: ADMIN_NAV,
  operationsNav: OPERATIONS_NAV,
  configurationNav: CONFIGURATION_NAV,
  settingsNav: SETTINGS_NAV,
}

// ── Shared Components ────────────────────────────────────────────────────────

function WSStatus({ status }) {
  return (
    <div className={cn(
      'flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-medium border transition-all',
      status === 'connected'
        ? 'bg-success/10 border-success/20 text-success'
        : status === 'error'
        ? 'bg-danger/10 border-danger/20 text-danger'
        : 'bg-[rgb(var(--bg-hover))] border-[rgb(var(--border))] text-[rgb(var(--text-muted))]',
    )}>
      <LiveDot
        color={status === 'connected' ? 'green' : status === 'error' ? 'red' : 'gray'}
        pulse={status === 'connected'}
        size="xs"
      />
      <span className="hidden sm:inline">WS {status}</span>
    </div>
  )
}

function UserMenu({ user, isAdmin, onLogout }) {
  const [open, setOpen] = useState(false)
  const ref = useRef(null)

  useEffect(() => {
    const h = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false) }
    document.addEventListener('mousedown', h)
    return () => document.removeEventListener('mousedown', h)
  }, [])

  const initials = (user?.full_name || user?.email || 'U')
    .split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase()

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen(p => !p)}
        className="flex items-center gap-2 p-1 pr-2 rounded-lg border border-transparent hover:bg-[rgb(var(--bg-hover))] transition-all"
      >
        <div className="w-7 h-7 rounded-md bg-gradient-to-tr from-[rgb(var(--c-primary))] to-[rgb(var(--c-accent))] flex items-center justify-center text-[10px] font-bold text-white shadow-sm">
          {initials}
        </div>
        <ChevronDown className={cn('w-3.5 h-3.5 text-[rgb(var(--text-muted))] transition-transform', open && 'rotate-180')} />
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: -4 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: -4 }}
            transition={{ duration: 0.15 }}
            className="absolute right-0 top-full mt-2 w-56 bg-[rgb(var(--bg-surface))] rounded-xl shadow-lg border border-[rgb(var(--border))] overflow-hidden z-50"
          >
            <div className="px-4 py-3 border-b border-[rgb(var(--border-subtle))] bg-[rgb(var(--bg-base))]">
              <p className="text-sm font-semibold text-[rgb(var(--text-primary))] truncate">{user?.full_name || 'User'}</p>
              <p className="text-xs text-[rgb(var(--text-muted))] truncate mt-0.5">{user?.email}</p>
              {isAdmin && (
                <span className="inline-flex items-center gap-1 mt-2 px-2 py-0.5 bg-[rgba(var(--c-primary),0.1)] text-[rgb(var(--c-primary))] text-[10px] font-semibold rounded-full border border-[rgba(var(--c-primary),0.2)]">
                  <Zap className="w-2.5 h-2.5" /> Administrator
                </span>
              )}
            </div>
            <div className="py-1">
              {[
                { icon: User,     label: 'Profile',   action: () => {} },
                { icon: HelpCircle, label: 'Help & Documentation', action: () => {} },
              ].map(({ icon: Icon, label, action }) => (
                <button
                  key={label}
                  onClick={() => { action(); setOpen(false) }}
                  className="w-full flex items-center gap-2.5 px-4 py-2 text-sm text-[rgb(var(--text-secondary))] hover:text-[rgb(var(--text-primary))] hover:bg-[rgb(var(--bg-hover))] transition-colors text-left"
                >
                  <Icon className="w-4 h-4" />{label}
                </button>
              ))}
            </div>
            <div className="py-1 border-t border-[rgb(var(--border-subtle))]">
              <button
                onClick={() => { onLogout(); setOpen(false) }}
                className="w-full flex items-center gap-2.5 px-4 py-2 text-sm text-[rgb(var(--c-danger))] hover:bg-[rgba(var(--c-danger),0.1)] transition-colors"
              >
                <LogOut className="w-4 h-4" />Sign Out
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

// ── Mobile Drawer ─────────────────────────────────────────────────────────────

function MobileDrawer({ open, onClose, isAdmin, getBadge }) {
  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-[rgba(0,0,0,0.4)] backdrop-blur-sm z-40 lg:hidden"
            onClick={onClose}
          />
          <motion.div
            initial={{ x: '-100%' }}
            animate={{ x: 0 }}
            exit={{ x: '-100%' }}
            transition={{ type: 'spring', damping: 26, stiffness: 300 }}
            className="fixed left-0 top-0 bottom-0 z-50 lg:hidden"
          >
            <Sidebar isAdmin={isAdmin} getBadge={getBadge} onNavClick={onClose} navConfig={NAV_CONFIG} />
          </motion.div>
        </>
      )}
    </AnimatePresence>
  )
}

// ── Main Layout ───────────────────────────────────────────────────────────────

export default function Layout({ children }) {
  const { user, isAdmin, logout, api } = useAuth()
  const { status, subscribe }          = useWebSocket()
  const { isDark, toggle: toggleTheme } = useTheme()
  const navigate                       = useNavigate()
  const location                       = useLocation()

  const { escalations, a2a, emails, patterns, setEscalations, setA2A, setEmails, setPatterns, incEscalations, decEscalations, incA2A, decA2A } = useBadgeStore()
  const { mobileMenuOpen, setMobileMenu } = useUIStore()

  const getBadge = useCallback((key) => {
    if (key === 'esc')     return escalations + a2a
    if (key === 'email')   return emails
    if (key === 'pattern') return patterns
    return 0
  }, [escalations, a2a, emails, patterns])

  const loadCounts = useCallback(async () => {
    try {
      const tid = user?.tenant_id
      const [escs, a2as, emls, pats] = await Promise.all([
        api.get('/escalations?status=pending').catch(() => []),
        api.get('/a2a/requests').catch(() => []),
        tid ? api.get(`/tenants/${tid}/email-queue?status=pending`).catch(() => []) : [],
        tid ? api.get(`/tenants/${tid}/patterns?status=pending_review`).catch(() => []) : [],
      ])
      setEscalations(Array.isArray(escs) ? escs.length : 0)
      setA2A(Array.isArray(a2as) ? a2as.length : 0)
      setEmails(Array.isArray(emls) ? emls.length : 0)
      setPatterns(Array.isArray(pats) ? pats.length : 0)
    } catch (_) {}
  }, [api, user?.tenant_id, setEscalations, setA2A, setEmails, setPatterns])

  useEffect(() => {
    loadCounts()
    const unsubs = [
      subscribe('escalation_created',       () => { incEscalations(); loadCounts() }),
      subscribe('escalation_resolved',      () => { decEscalations(); loadCounts() }),
      subscribe('a2a_permission_requested', () => { incA2A();         loadCounts() }),
      subscribe('a2a_decided',              () => { decA2A();         loadCounts() }),
      subscribe('workflow_completed',       loadCounts),
      subscribe('workflow_failed',          loadCounts),
    ]
    return () => unsubs.forEach(fn => fn())
  }, [loadCounts, subscribe, incEscalations, decEscalations, incA2A, decA2A])

  const handleLogout = () => {
    logout()
    navigate('/auth', { replace: true })
  }

  // Breadcrumb generation
  const crumbs = location.pathname.split('/').filter(Boolean).map((seg, i, arr) => ({
    label: seg.charAt(0).toUpperCase() + seg.slice(1).replace(/-/g, ' '),
    path: '/' + arr.slice(0, i + 1).join('/'),
  }))

  return (
    <div className="flex h-screen bg-[rgb(var(--bg-base))] overflow-hidden text-[rgb(var(--text-primary))] font-sans">
      
      {/* ── Desktop Sidebar ── */}
      <Sidebar className="hidden lg:flex" isAdmin={isAdmin} getBadge={getBadge} navConfig={NAV_CONFIG} />

      {/* ── Mobile Drawer ── */}
      <MobileDrawer
        open={mobileMenuOpen}
        onClose={() => setMobileMenu(false)}
        isAdmin={isAdmin}
        getBadge={getBadge}
      />

      {/* ── Main Content Area ── */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        
        {/* ── Top Header ── */}
        <PageHeader onMobileMenuClick={() => setMobileMenu(true)}>
          <Breadcrumbs crumbs={crumbs} isAdmin={isAdmin} />
          <>
            <WSStatus status={status} />
            <ThemeToggle isDark={isDark} toggle={toggleTheme} />
            <UserMenu user={user} isAdmin={isAdmin} onLogout={handleLogout} />
          </>
        </PageHeader>

        {/* ── Page Content ── */}
        <main className="flex-1 overflow-auto bg-[rgb(var(--bg-base))]">
          <div className="p-4 sm:p-6 lg:p-8 max-w-7xl mx-auto">
            <motion.div
              key={location.pathname}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.2 }}
            >
              {children}
            </motion.div>
          </div>
        </main>

      </div>
    </div>
  )
}