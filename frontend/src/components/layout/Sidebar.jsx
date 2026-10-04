import React from 'react'
import { NavLink, Link } from 'react-router-dom'
import { Zap } from 'lucide-react'
import { cn } from '../ui'

function NavItem({ to, Icon, label, badgeCount, end, onClick }) {
  return (
    <NavLink
      to={to}
      end={end}
      onClick={onClick}
      className={({ isActive }) => cn(
        'group flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-all duration-200',
        isActive
          ? 'bg-[rgba(var(--c-primary),0.08)] text-[rgb(var(--c-primary))]'
          : 'text-[rgb(var(--text-secondary))] hover:bg-[rgb(var(--bg-hover))] hover:text-[rgb(var(--text-primary))]',
      )}
    >
      <Icon className={cn(
        'w-4 h-4 flex-shrink-0 transition-colors',
        'group-hover:text-[rgb(var(--c-primary))]'
      )} />
      <span className="flex-1 truncate">{label}</span>
      {badgeCount > 0 && (
        <span className="min-w-[20px] h-5 flex items-center justify-center px-1.5 bg-[rgb(var(--c-danger))] text-white text-[10px] rounded-full font-bold">
          {badgeCount > 99 ? '99+' : badgeCount}
        </span>
      )}
    </NavLink>
  )
}

function NavSection({ title, items, getBadge, onNavClick }) {
  if (!items || items.length === 0) return null;
  
  return (
    <div className="mb-6">
      <h3 className="px-3 text-[10px] font-semibold text-[rgb(var(--text-muted))] uppercase tracking-wider mb-2">
        {title}
      </h3>
      <div className="space-y-0.5">
        {items.map((item) => (
          <NavItem
            key={item.to}
            {...item}
            badgeCount={item.badge ? getBadge(item.badge) : 0}
            onClick={onNavClick}
            end={item.to === '/admin' || item.to === '/dashboard'}
          />
        ))}
      </div>
    </div>
  )
}

export function Sidebar({ isAdmin, getBadge, className = "", onNavClick, navConfig }) {
  const { adminNav, operationsNav, configurationNav, settingsNav } = navConfig;

  return (
    <div className={cn("w-64 bg-[rgb(var(--bg-surface))] border-r border-[rgb(var(--border))] flex flex-col h-full", className)}>
      <div className="h-16 flex items-center px-6 border-b border-[rgb(var(--border-subtle))] flex-shrink-0">
        <Link to={isAdmin ? '/admin' : '/dashboard'} className="flex items-center gap-2.5 group">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-[rgb(var(--c-primary))] to-[rgb(var(--c-accent))] flex items-center justify-center shadow-sm group-hover:shadow-[0_0_12px_rgba(var(--c-primary),0.4)] transition-all">
            <Zap className="w-4.5 h-4.5 text-white" />
          </div>
          <span className="text-[17px] font-bold tracking-tight text-[rgb(var(--text-primary))]">
            SMBFlow
          </span>
        </Link>
      </div>

      <div className="flex-1 overflow-y-auto p-4 scrollbar-none">
        {isAdmin && <NavSection title="Admin" items={adminNav} getBadge={getBadge} onNavClick={onNavClick} />}
        <NavSection title="Operations" items={operationsNav} getBadge={getBadge} onNavClick={onNavClick} />
        <NavSection title="Configuration" items={configurationNav} getBadge={getBadge} onNavClick={onNavClick} />
        <NavSection title="Settings" items={settingsNav} getBadge={getBadge} onNavClick={onNavClick} />
      </div>
    </div>
  )
}
