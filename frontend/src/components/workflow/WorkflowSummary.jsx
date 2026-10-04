// frontend/src/components/workflow/WorkflowSummary.jsx
// =====================================================
// Comprehensive workflow analysis panel.
// ENHANCEMENTS:
//  - Full situation analysis with detailed urgency breakdown
//  - Per-agent evidence with tool call details
//  - Verification prosecutor findings expanded view
//  - Actions taken with full details
//  - Learning & memory summary
//  - Consensus agent results display
//  - "Evidence" section linking raw EPI data

import { useMemo, useState } from 'react'
import { Card } from '../ui'
import { fmtCost, fmtTokens, AGENT_ICONS, AGENT_LABELS } from '../../utils/helpers'
import TrendIndicator from './TrendIndicator'

// ── Collapsible section ───────────────────────────────────────────────────────
function Section({ title, defaultOpen = true, children, badge }) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <div className="border border-gray-800 rounded-xl overflow-hidden">
      <button
        onClick={() => setOpen(p => !p)}
        className="w-full flex items-center justify-between px-4 py-3 bg-gray-800/50 hover:bg-gray-800/70 transition-colors text-left"
      >
        <span className="text-sm font-semibold text-white">{title}</span>
        <div className="flex items-center gap-2">
          {badge && <span className="text-xs text-gray-400">{badge}</span>}
          <span className="text-gray-500 text-xs">{open ? '▲' : '▼'}</span>
        </div>
      </button>
      {open && <div className="p-4">{children}</div>}
    </div>
  )
}

// ── Agent row ─────────────────────────────────────────────────────────────────
function AgentRow({ run, dagNode, isAdmin, onFork }) {
  const [showDetails, setShowDetails] = useState(false)
  const Icon   = AGENT_ICONS[run.agent_type]
  const label  = AGENT_LABELS[run.agent_type] || run.agent_type || run.node_id
  const isOk   = run.status === 'success'
  const confPct = run.confidence != null ? Math.round(run.confidence * 100) : null

  return (
    <div className={`border rounded-xl overflow-hidden transition-colors group
      ${isOk ? 'border-gray-700/40 bg-gray-800/20' : 'border-red-700/30 bg-red-900/10'}`}>
      
      {/* Main row */}
      <div className="flex items-start gap-3 p-3">
        <span className="text-xl flex-shrink-0 mt-0.5"><Icon className="w-5 h-5" /></span>
        <div className="flex-1 min-w-0">
          {/* Header */}
          <div className="flex items-center gap-2 flex-wrap mb-1">
            <span className="text-white text-sm font-semibold">{label}</span>
            <code className="text-[10px] text-gray-600 font-mono bg-gray-900 px-1 rounded">{run.node_id}</code>
            <span className={`text-xs font-mono ${isOk ? 'text-green-400' : 'text-red-400'}`}>
              {isOk ? '✓' : '✗'} {run.status}
            </span>
            {confPct != null && (
              <span className={`text-xs ${confPct >= 75 ? 'text-green-400' : confPct >= 50 ? 'text-yellow-400' : 'text-red-400'}`}>
                {confPct}% conf
              </span>
            )}
            {run.model_used && (
              <span className="text-[10px] text-purple-300 font-mono bg-purple-900/20 px-1.5 rounded">
                {run.model_used.split('/').pop()}
              </span>
            )}
            {run.cost_usd > 0 && (
              <span className="text-xs text-yellow-400">{fmtCost(run.cost_usd)}</span>
            )}
            {run.duration_ms && (
              <span className="text-[10px] text-gray-600">
                {run.duration_ms < 1000 ? `${run.duration_ms}ms` : `${(run.duration_ms / 1000).toFixed(1)}s`}
              </span>
            )}
          </div>

          {/* Description */}
          {(run.node_description || dagNode?.description) && (
            <p className="text-xs text-gray-500 mb-1 leading-relaxed">
              {run.node_description || dagNode?.description}
            </p>
          )}

          {/* Tools used */}
          {((run.tools_used || dagNode?.tools || []).length > 0) && (
            <div className="flex flex-wrap items-center gap-1 mt-1">
              <span className="text-[10px] text-gray-600 mr-0.5">Tools:</span>
              {(run.tools_used || dagNode?.tools || []).map(t => (
                <span key={t} className="text-[10px] bg-blue-900/20 border border-blue-800/30 text-blue-300 rounded px-1.5 py-0.5">
                  {t}
                </span>
              ))}
            </div>
          )}

          {/* Verification judge pattern */}
          {(run._prosecutor_issues != null || run._judge_verdict) && (
            <div className="flex items-center gap-3 mt-1.5 text-xs">
              <span className="text-orange-400">
                ⚖ {run._prosecutor_issues ?? 0} fault{(run._prosecutor_issues ?? 0) !== 1 ? 's' : ''} reviewed
              </span>
              {run._judge_verdict && (
                <span className={run._judge_verdict === 'PASS' ? 'text-green-400' : 'text-red-400'}>
                  Judge: {run._judge_verdict}
                </span>
              )}
              {run._prosecutor_issues > 0 && (
                <button
                  onClick={() => setShowDetails(p => !p)}
                  className="text-[10px] text-gray-500 hover:text-gray-300 underline"
                >
                  {showDetails ? 'hide details' : 'show faults'}
                </button>
              )}
            </div>
          )}

          {/* Consensus agent specific */}
          {run.agent_type === 'consensus_agent' && run.output_data && (
            <div className="mt-1.5 space-y-1">
              {run.output_data.consensus !== undefined && (
                <div className={`text-xs font-semibold ${run.output_data.consensus ? 'text-green-400' : 'text-yellow-400'}`}>
                  {run.output_data.consensus ? '🤝 Agents Reached Consensus' : '⚔️ Agents Disagreed'}
                  {run.output_data.agreement_score != null && (
                    <span className="text-gray-400 font-normal ml-1">
                      ({(run.output_data.agreement_score * 100).toFixed(0)}% agreement)
                    </span>
                  )}
                </div>
              )}
            </div>
          )}

          {/* Memory delta */}
          {run.delta_analysis && (
            <div className="mt-1 text-xs text-gray-400">
              <span>Δ vs history: </span>
              <span className={
                run.delta_vs_history === 'better' ? 'text-green-400' :
                run.delta_vs_history === 'worse'  ? 'text-red-400'   : 'text-gray-400'
              }>
                {run.delta_vs_history || 'no_history'}
              </span>
              {run.delta_trend && (
                <span className="text-gray-600 ml-2">· trend: {run.delta_trend}</span>
              )}
            </div>
          )}

          {/* Error */}
          {run.error && (
            <p className="text-xs text-red-400 mt-1 leading-relaxed bg-red-900/10 rounded p-2 border border-red-800/30">
              ✗ {run.error.slice(0, 300)}
            </p>
          )}
        </div>

        {/* Token stats */}
        {(run.tokens_in > 0 || run.tokens_out > 0) && (
          <div className="text-right text-[10px] flex-shrink-0 space-y-0.5 mt-0.5">
            <div className="text-blue-400">{fmtTokens(run.tokens_in)} in</div>
            <div className="text-purple-400">{fmtTokens(run.tokens_out)} out</div>
          </div>
        )}
      </div>

      {/* Expanded faults detail */}
      {showDetails && run._prosecutor_faults?.length > 0 && (
        <div className="border-t border-orange-800/30 px-4 py-3 bg-orange-900/5">
          <div className="text-[10px] text-orange-400 font-semibold mb-2 uppercase tracking-wider">Prosecutor Findings</div>
          <div className="space-y-1">
            {run._prosecutor_faults.slice(0, 20).map((fault, i) => (
              <div key={i} className="text-xs text-orange-300 leading-relaxed">
                {fault}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function SituationCard({ outcome }) {
  if (!outcome?.situation_summary) return null
  const urgencyConfig = {
    critical: { cls: 'text-red-300 border-red-700/40 bg-red-900/20', icon: '🚨' },
    high:     { cls: 'text-orange-300 border-orange-700/40 bg-orange-900/20', icon: '⚠️' },
    medium:   { cls: 'text-yellow-300 border-yellow-700/40 bg-yellow-900/20', icon: '⚡' },
    low:      { cls: 'text-gray-300 border-gray-700/40 bg-gray-800/30', icon: '📋' },
  }
  const urgCfg = urgencyConfig[outcome.urgency?.toLowerCase()] || urgencyConfig.medium

  return (
    <div className="bg-gray-800/40 border border-gray-700/30 rounded-xl p-4 group">
      <div className="flex items-start gap-3">
        <span className="text-2xl flex-shrink-0">{urgCfg.icon}</span>
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-2">
            <span className="text-sm font-semibold text-white">Situation Analysis</span>
            {outcome.urgency && (
              <span className={`text-[10px] px-2 py-0.5 rounded border font-mono uppercase ${urgCfg.cls}`}>
                {outcome.urgency} urgency
              </span>
            )}
            {outcome.reasoning_confidence != null && (
              <span className={`text-[10px] px-1.5 py-0.5 rounded font-mono
                ${outcome.reasoning_confidence >= 0.75 ? 'text-green-400 bg-green-900/20'
                  : 'text-yellow-400 bg-yellow-900/20'}`}>
                {Math.round(outcome.reasoning_confidence * 100)}% confidence
              </span>
            )}
          </div>
          <p className="text-sm text-gray-300 leading-relaxed">{outcome.situation_summary}</p>
        </div>
      </div>
    </div>
  )
}

function EmailSummarySection({ runs }) {
  const summary = runs.find(r => r.node_id === 'summarize_emails')?.output_data || {}
  const actions = runs.find(r => r.node_id === 'evaluate_actions')?.output_data || {}
  const drafts = runs.find(r => r.node_id === 'humanize_draft')?.output_data || {}
  const summarizerRun = runs.find(r => r.node_id === 'summarize_emails') || {}
  const hasOutput = Object.keys(summary).length > 0 || Object.keys(actions).length > 0 || Object.keys(drafts).length > 0

  if (!hasOutput) return null

  const important = summary.important_emails || []
  const actionItems = summary.action_required || actions.action_items || []
  const approvalItems = drafts.approval_items || actions.approval_items || []
  const technical = [
    ['Provider', summarizerRun.provider || 'Not reported'],
    ['Model', summarizerRun.model_used || 'Not reported'],
    ['Input tokens', summarizerRun.tokens_in ?? 'Not reported'],
    ['Output tokens', summarizerRun.tokens_out ?? 'Not reported'],
    ['Cost', summarizerRun.cost_usd ?? 'Not reported'],
    ['Latency', summarizerRun.duration_ms != null ? `${summarizerRun.duration_ms}ms` : 'Not reported'],
  ]

  return (
    <Section title="Email Summary" defaultOpen>
      {summary.summary && <div className="mb-4"><h4 className="text-xs font-semibold text-gray-400 uppercase">AI Summary</h4><p className="text-sm text-gray-200 mt-1 leading-relaxed">{summary.summary}</p></div>}
      {summary.categories && <div className="mb-4"><h4 className="text-xs font-semibold text-gray-400 uppercase">Priority Breakdown</h4><div className="flex flex-wrap gap-2 mt-2">{Object.entries(summary.categories).map(([key, value]) => <span key={key} className="text-xs border border-gray-700 rounded px-2 py-1 text-gray-300">{key}: {value}</span>)}</div></div>}
      {actionItems.length > 0 && <div className="mb-4"><h4 className="text-xs font-semibold text-gray-400 uppercase">Action Items</h4><div className="mt-2 space-y-1">{actionItems.map((item, index) => <div key={index} className="text-sm text-gray-300">{item.subject || item.action || item.title || JSON.stringify(item)}</div>)}</div></div>}
      {important.length > 0 && <div className="mb-4"><h4 className="text-xs font-semibold text-gray-400 uppercase">Important Emails / Threads</h4><div className="mt-2 space-y-2">{important.map((item, index) => <div key={index} className="border border-gray-700 rounded-lg p-2"><div className="text-sm text-gray-200">{item.subject || item.message_id || 'Referenced message'}</div>{item.reason && <div className="text-xs text-gray-400 mt-1">{item.reason}</div>}{item.message_id && <div className="text-[11px] text-gray-500 font-mono mt-1">{item.message_id}</div>}</div>)}</div></div>}
      {approvalItems.length > 0 && <div className="mb-4"><h4 className="text-xs font-semibold text-gray-400 uppercase">Draft Responses</h4><div className="mt-2 space-y-2">{approvalItems.map((item, index) => <div key={index} className="border border-gray-700 rounded-lg p-2"><div className="text-sm text-gray-200">{item.title || item.source?.subject || 'Draft response'}</div><p className="text-xs text-gray-400 mt-1">{item.proposed_action?.body || item.reason || ''}</p>{item.source?.message_id && <div className="text-[11px] text-gray-500 font-mono mt-1">Source: {item.source.message_id}</div>}</div>)}</div></div>}
      <div className="border-t border-gray-800 pt-3"><h4 className="text-xs font-semibold text-gray-500 uppercase">Technical Details</h4><div className="grid grid-cols-2 gap-2 mt-2 text-xs">{technical.map(([label, value]) => <div key={label} className="text-gray-400">{label}: <span className="text-gray-200 font-mono">{value}</span></div>)}</div></div>
    </Section>
  )
}

// ── Property Card — renders when output contains RE context ───────────────────
function PropertyCard({ outputData }) {
  if (!outputData) return null

  // Dig into nested arrays returned by Real Estate agents
  let targetData = outputData;
  if (outputData.listings?.length > 0) targetData = outputData.listings[0];
  else if (outputData.critical_listings?.length > 0) targetData = outputData.critical_listings[0];
  else if (outputData.leases?.length > 0) targetData = outputData.leases[0];
  else if (outputData.high_risk_leases?.length > 0) targetData = outputData.high_risk_leases[0];

  const address = targetData.address || targetData.property_address || targetData.listing_address
  const mlsNumber = targetData.mls_number || targetData.listing_id || targetData.lease_id
  const price = targetData.price || targetData.list_price || targetData.asking_price || targetData.monthly_rent
  const dom = targetData.days_on_market ?? targetData.dom ?? targetData.days_until_expiry
  const status = targetData.status || targetData.listing_status || targetData.status_label || targetData._risk_label

  if (!address && !mlsNumber) return null

  return (
    <div className="flex items-center gap-3 p-3 bg-teal-900/15 border border-teal-800/40 rounded-xl mb-3">
      <div className="w-10 h-10 rounded-xl bg-teal-500/15 flex items-center justify-center flex-shrink-0 text-xl">
        🏠
      </div>
      <div className="flex-1 min-w-0">
        {address && (
          <p className="text-sm font-bold text-teal-300 truncate">{address}</p>
        )}
        <div className="flex flex-wrap gap-x-4 gap-y-0.5 mt-0.5 text-[11px] text-gray-400">
          {mlsNumber && <span>MLS# <span className="text-gray-200 font-mono">{mlsNumber}</span></span>}
          {price && <span>Price: <span className="text-yellow-400 font-mono">{typeof price === 'number' ? `$${price.toLocaleString()}` : price}</span></span>}
          {dom != null && <span>DOM: <span className={dom > 60 ? 'text-red-400 font-bold' : dom > 30 ? 'text-yellow-400' : 'text-green-400'}>{dom}d</span></span>}
          {status && <span>Status: <span className="text-teal-300">{status}</span></span>}
        </div>
      </div>
    </div>
  )
}

// ── Main WorkflowSummary ──────────────────────────────────────────────────────
export default function WorkflowSummary({ workflow, dag, agents, isAdmin = false, onFork }) {
  const meta      = dag?._meta     || {}
  const dagNodes  = dag?.nodes     || []
  const agentRuns = workflow?.agent_runs || []
  const outcome   = workflow?.outcome   || {}

  // De-duplicate agent runs: keep last per node_id, merge with live agent state
const dedupedRuns = useMemo(() => {
    const map = {}
    for (const run of agentRuns) {
      if (!run?.node_id) continue
      const liveData = agents?.[run.node_id] || {}
      map[run.node_id] = {
        ...run,
        ...liveData,
        // Prefer DB values for stable display
        status:      run.status,
        confidence:  run.confidence,
        cost_usd:    run.cost_usd,
        tokens_in:   run.tokens_in,
        tokens_out:  run.tokens_out,
        model_used:  run.model_used,
        
        // BUG FIX: Look inside run.output_data for the DB fallback
        // DB stores delta_analysis / prosecutor fields directly on the agent_run_record
        // (not inside output_data). The spread ...run already picks them up but the
        // ...liveData spread can override with undefined — these explicit merges fix that.
        delta_analysis:     liveData.delta_analysis     || run.delta_analysis,
        delta_vs_history:   liveData.delta_vs_history   || run.delta_vs_history,
        delta_trend:        liveData.delta_trend         || run.delta_trend,
        _prosecutor_issues: liveData._prosecutor_issues  ?? run._prosecutor_issues,
        _judge_verdict:     liveData._judge_verdict      || run._judge_verdict,
        _prosecutor_faults: liveData._prosecutor_faults  || run._prosecutor_faults || [],
      }
    }
    // Preserve DAG order
    return dagNodes.map(n => map[n.id]).filter(Boolean)
  }, [agentRuns, agents, dagNodes])

  const reasoningRun    = dedupedRuns.find(r => r.agent_type === 'reasoning_agent' || r.agent_type === 'consensus_agent')
  const memoryRun       = dedupedRuns.find(r => r.agent_type === 'memory_agent')
  const verificationRun = dedupedRuns.find(r => r.agent_type === 'verification_agent')
  const executionRun    = dedupedRuns.find(r => r.agent_type === 'execution_agent')
  const deltaAnalysis   = memoryRun?.delta_analysis || outcome.delta_analysis

  const isEscalated = workflow?.status === 'escalated'
  const hasErrors   = dedupedRuns.some(r => r.status === 'failed' || r.error)

  const durationSec = (workflow?.started_at && workflow?.completed_at)
    ? Math.round((new Date(workflow.completed_at) - new Date(workflow.started_at)) / 1000)
    : null

  const totalCost      = workflow?.total_cost_usd || outcome.total_cost_usd || 0
  const totalTokensIn  = workflow?.total_tokens_in  || outcome.total_tokens_in  || 0
  const totalTokensOut = workflow?.total_tokens_out || outcome.total_tokens_out || 0

  if (dedupedRuns.length === 0 && !outcome.situation_summary) return null

  return (
    <div className="space-y-4">

      {/* ── Overview card ─────────────────────────────────────────────── */}
      <Card className="border-blue-800/30 bg-blue-950/20">
        <div className="flex items-start gap-4">
          <span className="text-3xl flex-shrink-0">📋</span>
          <div className="flex-1 min-w-0">
            <h3 className="text-white font-bold text-sm mb-1">Workflow Analysis Report</h3>
            {meta.description && (
              <p className="text-gray-300 text-sm mb-3 leading-relaxed">{meta.description}</p>
            )}
            {/* Metrics strip */}
            <div className="flex flex-wrap gap-x-5 gap-y-1 text-xs text-gray-400">
              <span>💰 Cost: <span className="text-yellow-400 font-mono">{fmtCost(totalCost)}</span></span>
              <span>📥 Tokens in: <span className="text-blue-400 font-mono">{fmtTokens(totalTokensIn)}</span></span>
              <span>📤 Tokens out: <span className="text-purple-400 font-mono">{fmtTokens(totalTokensOut)}</span></span>
              {durationSec != null && (
                <span>⏱ Duration: <span className="text-gray-300">{durationSec < 60 ? `${durationSec}s` : `${Math.floor(durationSec / 60)}m ${durationSec % 60}s`}</span></span>
              )}
              <span>🤖 Agents: <span className="text-gray-300">{dedupedRuns.filter(r => r.status === 'success').length}/{dagNodes.length} completed</span></span>
              {reasoningRun?.confidence != null && (
                <span>🎯 Reasoning confidence: <span className={`font-mono ${reasoningRun.confidence >= 0.75 ? 'text-green-400' : reasoningRun.confidence >= 0.5 ? 'text-yellow-400' : 'text-red-400'}`}>{Math.round(reasoningRun.confidence * 100)}%</span></span>
              )}
            </div>

            {/* Situation summary inline */}
            <SituationCard outcome={outcome} />
          </div>
        </div>
      </Card>

      {workflow?.workflow_name === 'email_summarizer' && <EmailSummarySection runs={dedupedRuns} />}

      {/* ── Agent Pipeline Breakdown ──────────────────────────────────── */}
      {dedupedRuns.length > 0 && (
        <Section title="Agent Pipeline Breakdown" badge={`${dedupedRuns.length} agents`}>
          <div className="space-y-2">
            {dedupedRuns.map((run, i) => {
                    const dagNode = dagNodes.find(n => n.id === run.node_id)
                    return (
                      <div key={run.node_id}>
                        {/* Render PropertyCard if this agent output contains RE context */}
                        <PropertyCard outputData={run.output_data || run.research} />
                        <AgentRow
                          run={run}
                          dagNode={dagNode}
                          isAdmin={isAdmin}
                          onFork={onFork}
                        />
                      </div>
                    )
                  })}
          </div>
        </Section>
      )}

      {/* ── Verification Summary ──────────────────────────────────────── */}
      {outcome.verification_summary && (
        outcome.verification_summary.approved_count > 0 ||
        outcome.verification_summary.rejected_count > 0 ||
        (outcome.verification_summary.prosecutor_issues || 0) > 0
      ) && (
        <Section title="Verification Results">
          <div className="flex flex-wrap gap-4 mb-3">
            <div className="bg-green-900/20 border border-green-700/30 rounded-lg px-4 py-3 text-center min-w-[80px]">
              <div className="text-2xl font-bold text-green-400">{outcome.verification_summary.approved_count}</div>
              <div className="text-xs text-gray-500">Approved</div>
            </div>
            <div className="bg-red-900/20 border border-red-700/30 rounded-lg px-4 py-3 text-center min-w-[80px]">
              <div className="text-2xl font-bold text-red-400">{outcome.verification_summary.rejected_count}</div>
              <div className="text-xs text-gray-500">Rejected</div>
            </div>
            <div className="bg-orange-900/20 border border-orange-700/30 rounded-lg px-4 py-3 text-center min-w-[80px]">
              <div className="text-2xl font-bold text-orange-400">{outcome.verification_summary.prosecutor_issues || 0}</div>
              <div className="text-xs text-gray-500">Faults Found</div>
            </div>
            <div className={`border rounded-lg px-4 py-3 text-center min-w-[80px] ${
              outcome.verification_summary.passed ? 'bg-green-900/20 border-green-700/30' : 'bg-red-900/20 border-red-700/30'
            }`}>
              <div className={`text-2xl font-bold ${outcome.verification_summary.passed ? 'text-green-400' : 'text-red-400'}`}>
                {outcome.verification_summary.passed ? 'PASS' : 'FAIL'}
              </div>
              <div className="text-xs text-gray-500">Judge Verdict</div>
            </div>
          </div>
          {!outcome.verification_summary.passed && (
            <div className="bg-red-900/10 border border-red-700/20 rounded-lg p-3 text-xs text-red-300">
              ℹ️ Verification failed — execution agent received fewer approved drafts. Check individual agent faults above.
            </div>
          )}
        </Section>
      )}

      {/* ── Actions Taken ─────────────────────────────────────────────── */}
      {outcome.actions_summary?.length > 0 && (
        <Section title="Actions Taken" badge={`${outcome.actions_summary.length} actions`}>
          <div className="space-y-1.5">
            {outcome.actions_summary.map((action, i) => (
              <div key={i} className="flex items-center gap-2 text-xs bg-gray-800/30 border border-gray-700/30 rounded-lg px-3 py-2">
                <span className={action.status === 'success' ? 'text-green-400' : action.status === 'failed' ? 'text-red-400' : 'text-gray-400'}>
                  {action.status === 'success' ? '✓' : action.status === 'failed' ? '✗' : '○'}
                </span>
                <span className="text-gray-300 font-mono">{action.action}</span>
                {action.account_id && (
                  <span className="text-gray-600 ml-auto truncate max-w-[120px]">{action.account_id}</span>
                )}
              </div>
            ))}
          </div>
        </Section>
      )}

      {/* ── Issues & Problems ─────────────────────────────────────────── */}
      {(hasErrors || isEscalated || workflow?.error) && (
        <Section title="Issues & Problems" defaultOpen={true}>
          <div className="space-y-2">
            {isEscalated && (outcome.reason || workflow?.outcome?.reason) && (
              <div className="bg-yellow-900/20 border border-yellow-700/30 rounded-xl p-3">
                <div className="text-xs font-semibold text-yellow-400 mb-1">⚠ Escalation Required</div>
                <p className="text-sm text-yellow-200 leading-relaxed">
                  {outcome.reason || workflow?.outcome?.reason}
                </p>
              </div>
            )}
            {dedupedRuns.filter(r => r.error || r.status === 'failed').map(run => (
              <div key={run.node_id} className="bg-red-900/10 border border-red-700/30 rounded-xl p-3">
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-sm">{(() => { const Icon = AGENT_ICONS[run.agent_type]; return <Icon className="w-4 h-4" />; })()}</span>
                  <span className="text-xs font-semibold text-red-400">
                    {AGENT_LABELS[run.agent_type] || run.node_id} failed
                  </span>
                </div>
                {run.error && (
                  <p className="text-xs text-red-300 font-mono leading-relaxed">{run.error.slice(0, 400)}</p>
                )}
              </div>
            ))}
            {workflow?.error && (
              <div className="bg-red-900/10 border border-red-700/30 rounded-xl p-3">
                <div className="text-xs font-semibold text-red-400 mb-1">Engine Error</div>
                <p className="text-xs text-red-300 font-mono">{workflow.error.slice(0, 400)}</p>
              </div>
            )}
          </div>
        </Section>
      )}

      {/* ── Learning & Pattern Updates ────────────────────────────────── */}
      {(deltaAnalysis || outcome.memory_summary) && (
        <Section title="Learning & Pattern Updates">
          {deltaAnalysis && (
            <div className="mb-3">
              <TrendIndicator deltaAnalysis={deltaAnalysis} compact={false} />
            </div>
          )}
          {outcome.memory_summary && (
            <div className="bg-blue-900/10 border border-blue-800/20 rounded-lg p-3">
              <div className="text-xs text-blue-400 font-semibold mb-1">Memory Agent Summary</div>
              <p className="text-xs text-gray-400 leading-relaxed">{outcome.memory_summary}</p>
            </div>
          )}
          <div className="mt-2 text-xs text-gray-600">
            ℹ️ New patterns are sandboxed (pending_review). An admin must promote them in the God View
            before they influence future reasoning. This prevents hallucinated lessons from reinforcing.
          </div>
        </Section>
      )}
    </div>
  )
}