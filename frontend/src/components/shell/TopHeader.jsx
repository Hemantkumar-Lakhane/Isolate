// frontend/src/components/shell/TopHeader.jsx
// ─────────────────────────────────────────────────────────────────────────────
// Approved Figma top header, ported:
//   • breadcrumbs from the current path (react-router-dom v6 useLocation/Link)
//   • real user initials from useAuth() (no hardcoded "SA")
//   • live WebSocket connection status from the EXISTING WSContext
// ─────────────────────────────────────────────────────────────────────────────
import { Link, useLocation } from 'react-router-dom'
import { ChevronRight, Sun, Moon } from 'lucide-react'
import { useAuth } from '../../contexts/AuthContext'
import { useWebSocket } from '../../contexts/WSContext'
import { useTheme } from '../../contexts/ThemeContext'

const routeLabels = {
  dashboard:           'Dashboard',
  copilot:             'AI Assistant',
  escalations:         'Action Center',
  workflows:           'Workflows',
  'workflow-library':  'Workflow Library',
  builder:             'Workflow Builder',
  evidence:            'Evidence',
  'ai-engine':         'AI Services',
  integrations:        'Integrations',
  settings:            'Settings',
  general:             'Profile',
  config:              'Profile',
  models:              'Model Catalog',
  budget:              'Budget & Billing',
  tools:               'Integrations',
  prompts:             'Prompts',
  'email-queue':       'Email Queue',
  patterns:            'Patterns',
  admin:               'Platform Overview',
  users:               'Users',
  fleet:               'Fleet Cost',
  health:              'System Health',
  organizations:       'Organizations',
  runs:                'Workflow Runs',
  reviews:             'Review Queue',
  'ai-services':       'AI Services',
  providers:           'Provider Connections',
  routing:             'Routing & Assignments',
  usage:               'Usage & Cost',
  audit:               'Audit Log',
}

function WSDot({ status }) {
  const color =
    status === 'connected' ? 'bg-green-500' : status === 'error' ? 'bg-red-500' : 'bg-slate-300'
  return (
    <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800/80">
      <span className={`w-1.5 h-1.5 rounded-full ${color} ${status === 'connected' ? 'animate-pulse' : ''}`} />
      <span className="text-[11px] font-medium text-slate-500 dark:text-slate-400 capitalize hidden sm:inline">{status}</span>
    </div>
  )
}

export function TopHeader() {
  const location = useLocation()
  const { user, isAdmin } = useAuth()
  const { status } = useWebSocket()
  const { theme, toggle, isDark } = useTheme()

  const parts = location.pathname.split('/').filter(Boolean)
  const crumbs = parts.map((part, i) => ({
    label: routeLabels[part] ?? part.charAt(0).toUpperCase() + part.slice(1).replace(/-/g, ' '),
    to: '/' + parts.slice(0, i + 1).join('/'),
    isLast: i === parts.length - 1,
  }))

  const home = isAdmin ? '/admin' : '/dashboard'
  const initials = (user?.full_name || user?.email || 'U')
    .split(' ')
    .map(n => n[0])
    .join('')
    .slice(0, 2)
    .toUpperCase()

  const avatarUrl = user?.avatar_url || localStorage.getItem(`avatar_${user?.id}`) || localStorage.getItem('smbflow_avatar')

  return (
    <header className="h-14 shrink-0 flex items-center justify-between px-6 bg-white dark:bg-[#0b0f17] border-b border-slate-200 dark:border-[#233048] transition-colors">
      <nav className="flex items-center gap-1.5">
        <Link to={home} className="text-sm text-slate-500 hover:text-slate-900 dark:text-slate-400 dark:hover:text-slate-100 transition-colors">
          SMBFlow
        </Link>
        {crumbs.map(crumb => (
          <span key={crumb.to} className="flex items-center gap-1.5">
            <ChevronRight size={13} className="text-slate-300 dark:text-slate-600" />
            {crumb.isLast ? (
              <span className="text-sm font-medium text-slate-900 dark:text-slate-100">{crumb.label}</span>
            ) : (
              <Link to={crumb.to} className="text-sm text-slate-500 hover:text-slate-900 dark:text-slate-400 dark:hover:text-slate-100 transition-colors">
                {crumb.label}
              </Link>
            )}
          </span>
        ))}
      </nav>

      <div className="flex items-center gap-3">
        {/* Global Persistent Theme Toggle */}
        <button
          type="button"
          onClick={toggle}
          className="w-8 h-8 rounded-full border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 hover:bg-slate-100 dark:hover:bg-slate-700 flex items-center justify-center text-slate-600 dark:text-slate-300 transition-colors cursor-pointer"
          title={`Switch to ${isDark ? 'Light' : 'Dark'} Mode`}
        >
          {isDark ? <Sun className="w-4 h-4 text-amber-400" /> : <Moon className="w-4 h-4 text-slate-600" />}
        </button>

        <WSDot status={status} />

        {/* Clickable Profile Avatar */}
        <Link
          to="/settings/general"
          className="w-8 h-8 rounded-full bg-blue-600 hover:ring-2 hover:ring-blue-400 overflow-hidden flex items-center justify-center shadow-xs transition-all cursor-pointer"
          title={`View Profile (${user?.full_name || user?.email || 'User'})`}
        >
          {avatarUrl ? (
            <img src={avatarUrl} alt="Avatar" className="w-full h-full object-cover" />
          ) : (
            <span className="text-xs font-semibold text-white">{initials}</span>
          )}
        </Link>
      </div>
    </header>
  )
}
