// frontend/src/components/shell/AppShell.jsx
// ─────────────────────────────────────────────────────────────────────────────
// Approved Figma app shell (Sidebar + TopHeader + content), ported to this repo.
//
// Differences from the Figma original (intentional):
//   • Wraps `children` (react-router-dom v6 <Wrap> pattern) instead of <Outlet>.
//   • Reuses the PROVEN badge-polling + WebSocket wiring from the legacy Layout,
//     so the Action Center badge stays live. No second WS client is created.
//   • isAdmin comes from the backend role via useAuth(), not the URL.
//
// This is the presentation frame only. Individual pages are migrated later
// (Phase 3+); until then existing pages render inside this shell unchanged.
// ─────────────────────────────────────────────────────────────────────────────
import { useEffect, useCallback } from 'react'
import { useAuth } from '../../contexts/AuthContext'
import { useWebSocket } from '../../contexts/WSContext'
import { useBadgeStore } from '../../utils/appStore'
import { Sidebar } from './Sidebar'
import { TopHeader } from './TopHeader'

export function AppShell({ children }) {
  const { user, isAdmin, api } = useAuth()
  const { subscribe } = useWebSocket()

  const {
    escalations, a2a, emails, patterns,
    setEscalations, setA2A, setEmails, setPatterns,
    incEscalations, decEscalations, incA2A, decA2A,
  } = useBadgeStore()

  const getBadge = useCallback(
    (key) => {
      if (key === 'actions') return escalations + a2a
      if (key === 'email') return emails
      if (key === 'pattern') return patterns
      return 0
    },
    [escalations, a2a, emails, patterns]
  )

  // Poll the real pending queues — identical endpoints to the legacy Layout.
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
      subscribe('escalation_created', () => { incEscalations(); loadCounts() }),
      subscribe('escalation_resolved', () => { decEscalations(); loadCounts() }),
      subscribe('a2a_permission_requested', () => { incA2A(); loadCounts() }),
      subscribe('a2a_decided', () => { decA2A(); loadCounts() }),
      subscribe('workflow_completed', loadCounts),
      subscribe('workflow_failed', loadCounts),
    ]
    return () => unsubs.forEach(fn => fn())
  }, [loadCounts, subscribe, incEscalations, decEscalations, incA2A, decA2A])

  return (
    <div className="flex h-screen bg-slate-50 dark:bg-[#0b0f17] text-slate-900 dark:text-slate-100 overflow-hidden transition-colors">
      <Sidebar isAdmin={isAdmin} getBadge={getBadge} />
      <div className="flex flex-col flex-1 min-w-0">
        <TopHeader />
        <main className="flex-1 overflow-y-auto bg-slate-50 dark:bg-[#0b0f17] bg-dot-pattern transition-colors">{children}</main>
      </div>
    </div>
  )
}
