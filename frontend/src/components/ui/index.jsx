// frontend/src/components/ui/index.jsx
import { useState, useEffect, useRef, forwardRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Loader2, CheckCircle2, AlertTriangle, XCircle, Info,
  X, ChevronDown, Eye, EyeOff, Copy, Check,
  Circle, Minus, TrendingUp, TrendingDown,
} from 'lucide-react'
import { clsx } from 'clsx'
import { STATUS_COLORS } from '../../utils/helpers'

// ── Utility ───────────────────────────────────────────────────────────────────
export function cn(...inputs) { return clsx(inputs) }

// ── Spinner ───────────────────────────────────────────────────────────────────
const SPINNER_SIZES = { xs: 'w-3 h-3', sm: 'w-4 h-4', md: 'w-5 h-5', lg: 'w-8 h-8', xl: 'w-12 h-12' }

export function Spinner({ size = 'md', className = '', color = 'text-primary-500' }) {
  return (
    <Loader2
      className={cn('animate-spin', SPINNER_SIZES[size], color, className)}
      strokeWidth={2.5}
    />
  )
}

// ── Button ────────────────────────────────────────────────────────────────────
const BTN_BASE = 'inline-flex items-center justify-center gap-2 rounded-xl font-semibold transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-500 focus-visible:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed select-none'

const BTN_VARIANTS = {
  primary:  'bg-primary-500 hover:bg-primary-600 text-white shadow-md hover:shadow-glow-primary active:scale-[0.97]',
  secondary:'bg-surface text-content border border-[rgb(var(--border))] hover:bg-[rgb(var(--bg-hover))] active:scale-[0.97]',
  success:  'bg-success/90 hover:bg-success text-gray-900 shadow-md hover:shadow-glow-success active:scale-[0.97]',
  danger:   'bg-danger/10 hover:bg-danger/20 text-danger border border-danger/30 active:scale-[0.97]',
  warning:  'bg-warning/10 hover:bg-warning/20 text-warning border border-warning/30 active:scale-[0.97]',
  ghost:    'bg-transparent hover:bg-[rgb(var(--bg-hover))] text-[rgb(var(--text-secondary))] hover:text-[rgb(var(--text-primary))] active:scale-[0.97]',
  outline:  'bg-transparent border border-[rgb(var(--border))] hover:border-primary-500/60 text-[rgb(var(--text-secondary))] hover:text-primary-500 active:scale-[0.97]',
  gradient: 'bg-gradient-primary text-white shadow-md hover:shadow-glow-primary active:scale-[0.97]',
}

const BTN_SIZES = {
  xs: 'px-2.5 py-1 text-xs gap-1',
  sm: 'px-3 py-1.5 text-sm',
  md: 'px-4 py-2 text-sm',
  lg: 'px-5 py-2.5 text-base',
  xl: 'px-7 py-3.5 text-base',
}

export const Button = forwardRef(function Button({
  children, variant = 'primary', size = 'md', loading = false,
  className = '', icon, iconRight, ...props
}, ref) {
  return (
    <button
      ref={ref}
      {...props}
      disabled={props.disabled || loading}
      className={cn(BTN_BASE, BTN_VARIANTS[variant], BTN_SIZES[size], className)}
    >
      {loading ? <Spinner size="sm" color="currentColor" /> : icon}
      {children}
      {!loading && iconRight}
    </button>
  )
})

// ── Card ──────────────────────────────────────────────────────────────────────
export function Card({
  children, className = '', title, subtitle, action, noPad = false,
  glass = false, glow = false, hover = false,
}) {
  return (
    <div className={cn(
      'rounded-2xl border transition-all duration-200',
      glass
        ? 'glass'
        : 'bg-[rgb(var(--bg-card))] border-[rgb(var(--border))]',
      glow && 'shadow-glow',
      hover && 'hover:border-primary-500/40 hover:shadow-md cursor-pointer',
      className,
    )}>
      {(title || action) && (
        <div className={cn(
          'flex items-center justify-between border-b border-[rgb(var(--border))]',
          noPad ? 'px-5 py-4' : 'px-5 py-4 mb-0',
        )}>
          <div>
            {title && <h3 className="text-sm font-semibold text-[rgb(var(--text-primary))]">{title}</h3>}
            {subtitle && <p className="text-xs text-[rgb(var(--text-muted))] mt-0.5">{subtitle}</p>}
          </div>
          {action}
        </div>
      )}
      <div className={noPad ? '' : 'p-5'}>{children}</div>
    </div>
  )
}

// ── StatCard ──────────────────────────────────────────────────────────────────
export function StatCard({ icon: Icon, label, value, color = '', sub, trend, className = '' }) {
  return (
    <Card className={className} hover>
      <div className="flex items-start justify-between">
        <div>
          <p className="text-xs font-medium text-[rgb(var(--text-muted))] mb-1 uppercase tracking-wider">{label}</p>
          <p className={cn('text-2xl font-bold mt-1', color || 'text-[rgb(var(--text-primary))]')}>{value}</p>
          {sub && <p className="text-xs text-[rgb(var(--text-muted))] mt-0.5">{sub}</p>}
        </div>
        {Icon && (
          <div className={cn('p-2.5 rounded-xl opacity-80', color ? color.replace('text-','bg-').replace('400','400/15').replace('300','300/15') : 'bg-primary-500/10')}>
            {typeof Icon === 'string' ? <span className="text-xl flex items-center justify-center">{Icon}</span> : <Icon className={cn('w-5 h-5', color || 'text-primary-500')} strokeWidth={2} />}
          </div>
        )}
      </div>
      {trend !== undefined && (
        <div className="flex items-center gap-1 mt-3 text-xs">
          {trend > 0
            ? <TrendingUp className="w-3.5 h-3.5 text-success" />
            : trend < 0
            ? <TrendingDown className="w-3.5 h-3.5 text-danger" />
            : <Minus className="w-3.5 h-3.5 text-[rgb(var(--text-muted))]" />}
          <span className={trend > 0 ? 'text-success' : trend < 0 ? 'text-danger' : 'text-[rgb(var(--text-muted))]'}>
            {trend > 0 ? '+' : ''}{trend}%
          </span>
        </div>
      )}
    </Card>
  )
}

// ── Badge ─────────────────────────────────────────────────────────────────────
const BADGE_MAP = {
  running:          'bg-success/15 text-success border border-success/30',
  completed:        'bg-emerald-500/15 text-emerald-400 border border-emerald-500/30',
  'workflowstatus.completed': 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/30',
  failed:           'bg-danger/15 text-danger border border-danger/30',
  stopped:          'bg-danger/15 text-danger border border-danger/30',
  escalated:        'bg-warning/15 text-warning border border-warning/30',
  paused:           'bg-warning/15 text-warning border border-warning/30',
  pending:          'bg-[rgb(var(--text-muted))]/10 text-[rgb(var(--text-muted))] border border-[rgb(var(--border))]',
  success:          'bg-emerald-500/15 text-emerald-400 border border-emerald-500/30',
  skipped:          'bg-[rgb(var(--text-muted))]/10 text-[rgb(var(--text-muted))] border border-[rgb(var(--border))]',
  pending_a2a:      'bg-primary-500/15 text-primary-400 border border-primary-500/30',
}

const BADGE_DOTS = {
  running:   'bg-success', completed: 'bg-emerald-400', failed: 'bg-danger',
  stopped:   'bg-danger',  escalated: 'bg-warning',     paused: 'bg-warning',
  pending:   'bg-[rgb(var(--text-muted))]', success: 'bg-emerald-400',
  skipped:   'bg-[rgb(var(--text-muted))]',
}

export function Badge({ status, className = '', dot = true }) {
  const s = (status || 'pending').toLowerCase()
  const cls = BADGE_MAP[s] || BADGE_MAP.pending
  const dotCls = BADGE_DOTS[s] || 'bg-[rgb(var(--text-muted))]'
  return (
    <span className={cn('inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-semibold uppercase tracking-wide whitespace-nowrap', cls, className)}>
      {dot && <span className={cn('w-1.5 h-1.5 rounded-full flex-shrink-0', dotCls, s === 'running' && 'animate-pulse')} />}
      {s.replace(/_/g, ' ')}
    </span>
  )
}

// ── Input ─────────────────────────────────────────────────────────────────────
export function Input({ label, hint, error, className = '', required, type = 'text', icon: Icon, ...props }) {
  const [showPw, setShowPw] = useState(false)
  const isPw = type === 'password'
  const inputType = isPw ? (showPw ? 'text' : 'password') : type

  return (
    <div className={className}>
      {label && (
        <label className="block text-xs font-medium text-[rgb(var(--text-secondary))] mb-1.5">
          {label}{required && <span className="text-danger ml-1">*</span>}
        </label>
      )}
      <div className="relative">
        {Icon && (
          <div className="absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none text-[rgb(var(--text-muted))]">
            <Icon className="w-4 h-4" />
          </div>
        )}
        <input
          {...props}
          type={inputType}
          autoComplete={props.autoComplete || (isPw ? 'current-password' : 'off')}
          className={cn(
  'input-base',
  Icon ? '!pl-10' : '',
  isPw ? '!pr-10' : '',
  error && '!border-danger !ring-0 focus:!border-danger focus:!ring-danger/20',
)}
        />
        {isPw && (
          <button
            type="button"
            onClick={() => setShowPw(p => !p)}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-[rgb(var(--text-muted))] hover:text-[rgb(var(--text-primary))] transition-colors"
          >
            {showPw ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
          </button>
        )}
      </div>
      {hint && !error && <p className="text-xs text-[rgb(var(--text-muted))] mt-1">{hint}</p>}
      {error && <p className="text-xs text-danger mt-1 flex items-center gap-1"><XCircle className="w-3.5 h-3.5" />{error}</p>}
    </div>
  )
}

// ── Textarea ──────────────────────────────────────────────────────────────────
export function Textarea({ label, hint, error, rows = 4, className = '', ...props }) {
  return (
    <div className={className}>
      {label && <label className="block text-xs font-medium text-[rgb(var(--text-secondary))] mb-1.5">{label}</label>}
      <textarea
        rows={rows}
        {...props}
        className={cn('input-base resize-none', error && '!border-danger')}
      />
      {hint && <p className="text-xs text-[rgb(var(--text-muted))] mt-1">{hint}</p>}
      {error && <p className="text-xs text-danger mt-1">{error}</p>}
    </div>
  )
}

// ── Select ────────────────────────────────────────────────────────────────────
export function Select({ label, options = [], className = '', ...props }) {
  return (
    <div className={className}>
      {label && <label className="block text-xs font-medium text-[rgb(var(--text-secondary))] mb-1.5">{label}</label>}
      <div className="relative">
        <select
          {...props}
          className="input-base appearance-none pr-9"
        >
          {options.map(opt =>
            typeof opt === 'string'
              ? <option key={opt} value={opt}>{opt}</option>
              : <option key={opt.value} value={opt.value}>{opt.label}</option>
          )}
        </select>
        <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[rgb(var(--text-muted))] pointer-events-none" />
      </div>
    </div>
  )
}

// ── Toggle ────────────────────────────────────────────────────────────────────
export function Toggle({ checked, onChange, label, description, disabled = false }) {
  return (
    <label className={cn('flex items-center justify-between gap-4', disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer')}>
      {(label || description) && (
        <div className="min-w-0">
          {label && <p className="text-sm font-medium text-[rgb(var(--text-primary))] truncate">{label}</p>}
          {description && <p className="text-xs text-[rgb(var(--text-muted))] mt-0.5 leading-relaxed">{description}</p>}
        </div>
      )}
      <div
        role="switch"
        aria-checked={checked}
        onClick={() => !disabled && onChange(!checked)}
        className={cn(
          'relative w-11 h-6 rounded-full transition-all duration-300 flex-shrink-0',
          checked ? 'bg-primary-500 shadow-md shadow-primary-500/30' : 'bg-[rgb(var(--border))]',
        )}
      >
        <div className={cn(
          'absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full shadow-sm transition-transform duration-300',
          checked ? 'translate-x-5' : 'translate-x-0',
        )} />
      </div>
    </label>
  )
}

// ── Modal ─────────────────────────────────────────────────────────────────────
export function Modal({ open, onClose, title, children, width = 'max-w-lg', subtitle }) {
  useEffect(() => {
    if (!open) return
    const h = (e) => { if (e.key === 'Escape' && onClose) onClose() }
    document.addEventListener('keydown', h)
    return () => document.removeEventListener('keydown', h)
  }, [open, onClose])

  return (
    <AnimatePresence>
      {open && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <motion.div
            key="overlay"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="absolute inset-0 bg-black/60 backdrop-blur-sm"
            onClick={onClose}
          />
          <motion.div
            key="modal"
            initial={{ opacity: 0, scale: 0.96, y: 8 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.96, y: 8 }}
            transition={{ duration: 0.2, ease: [0.34, 1.56, 0.64, 1] }}
            className={cn(
              'relative bg-[rgb(var(--bg-elevated))] border border-[rgb(var(--border))] rounded-2xl shadow-2xl w-full max-h-[90vh] flex flex-col',
              width,
            )}
          >
            {title && (
              <div className="flex items-start justify-between p-5 border-b border-[rgb(var(--border))] flex-shrink-0">
                <div>
                  <h2 className="text-base font-bold text-[rgb(var(--text-primary))]">{title}</h2>
                  {subtitle && <p className="text-xs text-[rgb(var(--text-muted))] mt-0.5">{subtitle}</p>}
                </div>
                {onClose && (
                  <button
                    onClick={onClose}
                    className="p-1 rounded-lg text-[rgb(var(--text-muted))] hover:text-[rgb(var(--text-primary))] hover:bg-[rgb(var(--bg-hover))] transition-all"
                  >
                    <X className="w-4 h-4" />
                  </button>
                )}
              </div>
            )}
            <div className="p-5 overflow-y-auto flex-1">{children}</div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  )
}

// ── Alert ─────────────────────────────────────────────────────────────────────
const ALERT_STYLES = {
  info:    { cls: 'bg-primary-500/8 border-primary-500/25 text-primary-400', Icon: Info },
  success: { cls: 'bg-success/8 border-success/25 text-success',            Icon: CheckCircle2 },
  warning: { cls: 'bg-warning/8 border-warning/25 text-warning',            Icon: AlertTriangle },
  error:   { cls: 'bg-danger/8 border-danger/25 text-danger',               Icon: XCircle },
}

export function Alert({ type = 'info', children, onClose, className = '' }) {
  const { cls, Icon } = ALERT_STYLES[type] || ALERT_STYLES.info
  return (
    <motion.div
      initial={{ opacity: 0, y: -6 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0 }}
      className={cn('flex items-start gap-3 p-3.5 border rounded-xl text-sm', cls, className)}
    >
      <Icon className="w-4 h-4 flex-shrink-0 mt-0.5" />
      <div className="flex-1 text-sm leading-relaxed">{children}</div>
      {onClose && (
        <button onClick={onClose} className="opacity-60 hover:opacity-100 transition-opacity flex-shrink-0">
          <X className="w-3.5 h-3.5" />
        </button>
      )}
    </motion.div>
  )
}

// ── EmptyState ────────────────────────────────────────────────────────────────
export function EmptyState({ icon: Icon, title, description, action }) {
  return (
    <div className="flex flex-col items-center justify-center py-14 text-center">
      {Icon && (
        <div className="w-14 h-14 rounded-2xl bg-[rgb(var(--bg-hover))] flex items-center justify-center mb-4 text-[rgb(var(--text-muted))]">
          {typeof Icon === 'string' ? <span className="text-3xl">{Icon}</span> : <Icon className="w-7 h-7" />}
        </div>
      )}
      {title && <p className="text-sm font-semibold text-[rgb(var(--text-primary))] mb-1">{title}</p>}
      {description && <p className="text-xs text-[rgb(var(--text-muted))] mb-4 max-w-xs leading-relaxed">{description}</p>}
      {action}
    </div>
  )
}

// ── CodeBlock ─────────────────────────────────────────────────────────────────
export function CodeBlock({ children, lang = 'json' }) {
  const [copied, setCopied] = useState(false)
  const copy = () => {
    navigator.clipboard?.writeText(String(children))
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }
  return (
    <div className="relative group">
      <pre className="bg-[rgb(var(--bg-base))] border border-[rgb(var(--border))] rounded-xl px-4 py-3.5 text-xs text-success font-mono overflow-x-auto whitespace-pre-wrap leading-relaxed">
        {children}
      </pre>
      <button
        onClick={copy}
        className="absolute top-2.5 right-2.5 opacity-0 group-hover:opacity-100 transition-all text-xs flex items-center gap-1.5 px-2.5 py-1 bg-[rgb(var(--bg-elevated))] border border-[rgb(var(--border))] rounded-lg text-[rgb(var(--text-secondary))] hover:text-[rgb(var(--text-primary))]"
      >
        {copied ? <><Check className="w-3 h-3" />Copied</> : <><Copy className="w-3 h-3" />Copy</>}
      </button>
    </div>
  )
}

// ── TabGroup ──────────────────────────────────────────────────────────────────
export function TabGroup({ tabs, value, onChange, className = '' }) {
  return (
    <div className={cn('flex bg-[rgb(var(--bg-base))] rounded-xl p-1 gap-1', className)}>
      {tabs.map(tab => (
        <button
          key={tab.value}
          onClick={() => onChange(tab.value)}
          className={cn(
            'flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all duration-200',
            value === tab.value
              ? 'bg-[rgb(var(--bg-card))] text-[rgb(var(--text-primary))] shadow-sm'
              : 'text-[rgb(var(--text-muted))] hover:text-[rgb(var(--text-primary))] hover:bg-[rgb(var(--bg-hover))]',
          )}
        >
          {tab.icon && <tab.icon className="w-3.5 h-3.5" />}
          {tab.label}
          {tab.badge > 0 && (
            <span className="min-w-[18px] h-[18px] flex items-center justify-center px-1 bg-danger text-white text-[10px] rounded-full font-bold leading-none">
              {tab.badge}
            </span>
          )}
        </button>
      ))}
    </div>
  )
}

// ── LiveDot ───────────────────────────────────────────────────────────────────
const DOT_COLORS = {
  green:  'bg-success',
  red:    'bg-danger',
  yellow: 'bg-warning',
  blue:   'bg-primary-400',
  gray:   'bg-[rgb(var(--text-muted))]',
}

export function LiveDot({ color = 'green', pulse = true, size = 'sm' }) {
  const sz = size === 'sm' ? 'h-2 w-2' : 'h-2.5 w-2.5'
  return (
    <span className={cn('relative flex flex-shrink-0', sz)}>
      {pulse && (
        <span className={cn('animate-ping absolute inline-flex h-full w-full rounded-full opacity-70', DOT_COLORS[color])} />
      )}
      <span className={cn('relative inline-flex rounded-full', sz, DOT_COLORS[color])} />
    </span>
  )
}

// ── Skeleton ──────────────────────────────────────────────────────────────────
export function Skeleton({ className = '', height, width }) {
  return (
    <div
      className={cn('skeleton rounded-xl', className)}
      style={{ height, width }}
    />
  )
}

// ── Tooltip-like hint ─────────────────────────────────────────────────────────
export function Chip({ children, color = 'default', className = '' }) {
  const CHIP_COLORS = {
    default: 'bg-[rgb(var(--bg-hover))] text-[rgb(var(--text-secondary))] border-[rgb(var(--border))]',
    primary: 'bg-primary-500/10 text-primary-400 border-primary-500/30',
    success: 'bg-success/10 text-success border-success/30',
    warning: 'bg-warning/10 text-warning border-warning/30',
    danger:  'bg-danger/10 text-danger border-danger/30',
  }
  return (
    <span className={cn('inline-flex items-center px-2.5 py-0.5 rounded-full text-[11px] font-medium border', CHIP_COLORS[color], className)}>
      {children}
    </span>
  )
}

// ── Section Header ────────────────────────────────────────────────────────────
export function SectionHeader({ title, description, action }) {
  return (
    <div className="flex items-start justify-between gap-4 mb-6">
      <div>
        <h1 className="text-xl font-bold text-[rgb(var(--text-primary))]">{title}</h1>
        {description && <p className="text-sm text-[rgb(var(--text-muted))] mt-1">{description}</p>}
      </div>
      {action}
    </div>
  )
}

// ── Progress Bar ──────────────────────────────────────────────────────────────
export function ProgressBar({ value = 0, max = 100, color = 'primary', label, showValue = false, className = '' }) {
  const pct = Math.min(100, Math.max(0, (value / max) * 100))
  const COLORS = {
    primary: 'from-primary-500 to-accent',
    success: 'from-success to-emerald-400',
    warning: 'from-warning to-orange-400',
    danger:  'from-danger to-red-400',
  }
  return (
    <div className={className}>
      {(label || showValue) && (
        <div className="flex justify-between text-xs text-[rgb(var(--text-secondary))] mb-1.5">
          {label && <span>{label}</span>}
          {showValue && <span className="font-mono">{pct.toFixed(0)}%</span>}
        </div>
      )}
      <div className="h-1.5 bg-[rgb(var(--bg-hover))] rounded-full overflow-hidden">
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${pct}%` }}
          transition={{ duration: 0.6, ease: 'easeOut' }}
          className={cn('h-full rounded-full bg-gradient-to-r', COLORS[color] || COLORS.primary)}
        />
      </div>
    </div>
  )
}

export * from './Breadcrumbs'
export * from './LoadingState'
export * from './ErrorState'