// frontend/src/components/workflow/CostRibbon.jsx
import { motion } from 'framer-motion'
import { DollarSign, ArrowDownToLine, ArrowUpFromLine, TrendingUp } from 'lucide-react'
import { fmtCost, fmtTokens } from '../../utils/helpers'
import { cn } from '../ui'

export default function CostRibbon({ liveStats = {}, isRunning = false, activeCost = 0, activeTokensOut = 0 }) {
  const { cost_usd = 0, tokens_in = 0, tokens_out = 0 } = liveStats
  const displayCost      = cost_usd + activeCost
  const displayTokensOut = tokens_out + activeTokensOut
  const hasLiveEstimate  = isRunning && activeCost > 0

  const STATS = [
    {
      icon:  DollarSign,
      label: 'Total Cost',
      value: fmtCost(displayCost),
      color: 'text-warning',
      bg:    'bg-warning/8 border-warning/20',
      live:  hasLiveEstimate,
    },
    {
      icon:  ArrowDownToLine,
      label: 'Tokens In',
      value: fmtTokens(tokens_in),
      color: 'text-success',
      bg:    'bg-success/8 border-success/20',
      live:  false,
    },
    {
      icon:  ArrowUpFromLine,
      label: 'Tokens Out',
      value: fmtTokens(displayTokensOut),
      color: 'text-accent',
      bg:    'bg-accent/8 border-accent/20',
      live:  isRunning && activeTokensOut > 0,
    },
  ]

  return (
    <div className="grid grid-cols-3 gap-3">
      {STATS.map(({ icon: Icon, label, value, color, bg, live }) => (
        <div
          key={label}
          className={cn('relative border rounded-2xl p-4 text-center overflow-hidden', bg)}
        >
          {live && (
            <div className="absolute inset-0 rounded-2xl pointer-events-none">
              <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/3 to-transparent animate-shimmer" />
            </div>
          )}

          <div className="relative">
            <div className="flex items-center justify-center gap-1.5 mb-1">
              <Icon className={cn('w-3.5 h-3.5', color)} />
              <p className="text-[11px] font-medium text-[rgb(var(--text-muted))] uppercase tracking-wider">{label}</p>
              {live && (
                <span className="flex items-center gap-0.5 px-1.5 py-0.5 bg-primary-500/10 text-primary-400 text-[9px] rounded-full border border-primary-500/20">
                  <span className="w-1 h-1 rounded-full bg-primary-400 animate-pulse" />
                  live
                </span>
              )}
            </div>

            <motion.p
              key={value}
              initial={{ scale: 0.95, opacity: 0.7 }}
              animate={{ scale: 1, opacity: 1 }}
              className={cn('text-2xl font-bold font-mono', color, live && 'animate-pulse')}
            >
              {value}
            </motion.p>
          </div>
        </div>
      ))}
    </div>
  )
}