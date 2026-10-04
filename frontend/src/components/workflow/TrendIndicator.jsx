// frontend/src/components/workflow/TrendIndicator.jsx
// ======================================================
// Displays the MemoryAgent's delta_analysis as a compact
// "Run Trend" badge or a full card depending on the `compact` prop.

const TREND_CONFIG = {
  improving: {
    icon: '↑',
    color: 'text-green-400',
    bg: 'bg-green-900/20 border-green-700/40',
    label: 'Improving',
  },
  degrading: {
    icon: '↓',
    color: 'text-danger',
    bg: 'bg-red-900/20 border-red-700/40',
    label: 'Degrading',
  },
  stable: {
    icon: '→',
    color: 'text-accent',
    bg: 'bg-blue-900/20 border-blue-700/40',
    label: 'Stable',
  },
  insufficient_data: {
    icon: '?',
    color: 'text-gray-500',
    bg: 'bg-gray-800/40 border-gray-700/40',
    label: 'Insufficient Data',
  },
}

const HISTORY_CONFIG = {
  better:     { icon: '▲', color: 'text-green-400', label: 'Better than last run' },
  worse:      { icon: '▼', color: 'text-danger',   label: 'Worse than last run'  },
  similar:    { icon: '≈', color: 'text-accent',  label: 'Similar to last run'  },
  no_history: { icon: '◌', color: 'text-gray-500',  label: 'First run'            },
}

export default function TrendIndicator({ deltaAnalysis, compact = false }) {
  if (!deltaAnalysis) return null

  const trend      = deltaAnalysis.trend      || 'insufficient_data'
  const vsHistory  = deltaAnalysis.vs_history || 'no_history'
  const summary    = deltaAnalysis.summary    || ''
  const newSignals = Array.isArray(deltaAnalysis.new_signals) ? deltaAnalysis.new_signals : []

  const trendCfg = TREND_CONFIG[trend]   || TREND_CONFIG.insufficient_data
  const histCfg  = HISTORY_CONFIG[vsHistory] || HISTORY_CONFIG.no_history

  // ── Compact badge (used in WorkflowDetail header) ──────────────────────────
  if (compact) {
    return (
      <div
        title={summary || 'Run trend from MemoryAgent delta analysis'}
        className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg border text-xs font-medium cursor-default
          ${trendCfg.bg}`}
      >
        <span className={`text-sm leading-none ${trendCfg.color}`}>{trendCfg.icon}</span>
        <span className={trendCfg.color}>Trend: {trendCfg.label}</span>
        <span className="text-gray-600 mx-0.5">·</span>
        <span className={histCfg.color}>{histCfg.icon}</span>
        <span className={`${histCfg.color}`}>{histCfg.label}</span>
      </div>
    )
  }

  // ── Full card (can be used in a detail panel) ──────────────────────────────
  return (
    <div className={`rounded-xl border p-4 ${trendCfg.bg}`}>
      <div className="flex items-start gap-3">
        {/* Big trend arrow */}
        <span className={`text-3xl flex-shrink-0 mt-0.5 ${trendCfg.color}`}>
          {trendCfg.icon}
        </span>

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap mb-1">
            <span className={`text-sm font-bold ${trendCfg.color}`}>
              Run Trend: {trendCfg.label}
            </span>
            <span className={`text-xs px-2 py-0.5 rounded-full border
              ${histCfg.color} bg-black/20 border-current/30`}>
              {histCfg.icon} vs history: {histCfg.label}
            </span>
          </div>

          {summary && (
            <p className="text-xs text-gray-300 leading-relaxed mb-2">{summary}</p>
          )}

          {newSignals.length > 0 && (
            <div>
              <div className="text-[10px] text-yellow-400 font-semibold uppercase tracking-wide mb-1">
                🆕 New signals this run
              </div>
              <ul className="space-y-0.5">
                {newSignals.slice(0, 4).map((signal, i) => (
                  <li
                    key={i}
                    className="text-xs text-yellow-300 bg-yellow-900/20 border border-yellow-800/30 rounded px-2 py-0.5 truncate"
                    title={signal}
                  >
                    {signal}
                  </li>
                ))}
                {newSignals.length > 4 && (
                  <li className="text-[10px] text-gray-500">
                    +{newSignals.length - 4} more new signals
                  </li>
                )}
              </ul>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}