import React from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Sun, Moon, Menu } from 'lucide-react'
import { cn } from '../ui'

export function ThemeToggle({ isDark, toggle }) {
  return (
    <button
      onClick={toggle}
      className={cn(
        'p-2 rounded-lg border transition-all duration-200',
        'bg-[rgb(var(--bg-surface))] border-[rgb(var(--border))]',
        'text-[rgb(var(--text-secondary))] hover:text-[rgb(var(--text-primary))]',
        'hover:border-[rgb(var(--c-primary))]',
      )}
      title={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
    >
      <AnimatePresence mode="wait" initial={false}>
        <motion.div
          key={isDark ? 'moon' : 'sun'}
          initial={{ scale: 0.7, rotate: -30, opacity: 0 }}
          animate={{ scale: 1, rotate: 0, opacity: 1 }}
          exit={{ scale: 0.7, rotate: 30, opacity: 0 }}
          transition={{ duration: 0.2 }}
        >
          {isDark ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
        </motion.div>
      </AnimatePresence>
    </button>
  )
}

export function PageHeader({ children, onMobileMenuClick }) {
  return (
    <header className="h-16 flex items-center justify-between px-4 sm:px-6 bg-[rgb(var(--bg-surface))] border-b border-[rgb(var(--border-subtle))] z-10 flex-shrink-0">
      {/* Left: Breadcrumbs & Mobile Menu */}
      <div className="flex items-center gap-3">
        <button
          onClick={onMobileMenuClick}
          className="lg:hidden p-1.5 -ml-1.5 rounded-lg hover:bg-[rgb(var(--bg-hover))] text-[rgb(var(--text-muted))] transition-colors"
        >
          <Menu className="w-5 h-5" />
        </button>
        {children[0]}
      </div>

      {/* Right: Actions & User */}
      <div className="flex items-center gap-3 sm:gap-4">
        {children[1]}
      </div>
    </header>
  )
}
