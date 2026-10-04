import React from 'react'
import { Link } from 'react-router-dom'

export function Breadcrumbs({ crumbs, isAdmin }) {
  return (
    <div className="hidden sm:flex items-center gap-2 text-sm">
      {crumbs.length === 0 ? (
        <span className="font-semibold text-[rgb(var(--text-primary))]">Overview</span>
      ) : (
        <>
          <Link to={isAdmin ? '/admin' : '/dashboard'} className="text-[rgb(var(--text-muted))] hover:text-[rgb(var(--text-primary))] transition-colors">
            Home
          </Link>
          {crumbs.map((c, i) => (
            <span key={c.path} className="flex items-center gap-2">
              <span className="text-[rgb(var(--border))]">/</span>
              {i < crumbs.length - 1 ? (
                <Link to={c.path} className="text-[rgb(var(--text-muted))] hover:text-[rgb(var(--text-primary))] transition-colors">
                  {c.label}
                </Link>
              ) : (
                <span className="font-semibold text-[rgb(var(--text-primary))]">{c.label}</span>
              )}
            </span>
          ))}
        </>
      )}
    </div>
  )
}
