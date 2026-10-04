// frontend/src/components/workflow/A2APermissionModal.jsx
import { Modal, Button, Alert } from '../ui';
import { fmtCost, AGENT_ICONS, AGENT_LABELS } from '../../utils/helpers';
import { useState } from 'react';
import { useAuth } from '../../contexts/AuthContext';

/**
 * A2A Permission Request Modal.
 * Shown when an agent wants to call a previous agent to refine its data.
 *
 * Props:
 *   request: { a2a_id, requesting_agent, target_agent, reason, refinement_note, estimated_cost_usd }
 *   onDecide: (a2a_id, approved) => void
 */
export default function A2APermissionModal({ request, onDecide }) {
  const { api } = useAuth();
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState('');

  if (!request) return null;

  const {
    a2a_id,
    requesting_agent,
    target_agent,
    reason,
    refinement_note,
    estimated_cost_usd,
  } = request;

  const decide = async (approved) => {
    setLoading(true);
    setError('');
    try {
      await api.post(`/a2a/${a2a_id}/decide`, { approved, reason: approved ? 'Approved by user' : 'Rejected by user' });
      onDecide(a2a_id, approved);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const ReqIcon = AGENT_ICONS[requesting_agent];
  const TgtIcon = AGENT_ICONS[target_agent];
  const reqLabel = AGENT_LABELS[requesting_agent] || requesting_agent;
  const tgtLabel = AGENT_LABELS[target_agent]     || target_agent;

  return (
    <Modal open title="🤖 Agent-to-Agent Request" width="max-w-lg">
      {/* Header chip */}
      <div className="flex items-center gap-2 mb-4">
        <span className="px-2 py-0.5 bg-blue-900/40 border border-blue-600/40 text-blue-300 text-xs rounded-full font-medium">
          Needs Your Permission
        </span>
        <span className="text-xs text-gray-500">Estimated extra cost: {fmtCost(estimated_cost_usd)}</span>
      </div>

      {/* Flow diagram */}
      <div className="flex items-center gap-3 mb-5 p-4 bg-gray-800/60 rounded-xl">
        <div className="text-center">
          <div className="text-2xl flex justify-center"><ReqIcon className="w-6 h-6" /></div>
          <div className="text-xs text-gray-400 mt-1">{reqLabel}</div>
        </div>
        <div className="flex-1 flex items-center">
          <div className="flex-1 h-px bg-blue-500/40" />
          <span className="text-blue-400 text-xs px-2">↩ requests re-run</span>
          <div className="flex-1 h-px bg-blue-500/40" />
        </div>
        <div className="text-center">
          <div className="text-2xl flex justify-center"><TgtIcon className="w-6 h-6" /></div>
          <div className="text-xs text-gray-400 mt-1">{tgtLabel}</div>
        </div>
      </div>

      {/* Reason */}
      <div className="mb-4">
        <div className="text-xs text-gray-500 mb-1 uppercase tracking-wide">Reason</div>
        <div className="text-sm text-gray-300 bg-gray-800/50 rounded-lg p-3 leading-relaxed">
          {reason}
        </div>
      </div>

      {/* Refinement note */}
      {refinement_note && (
        <div className="mb-4">
          <div className="text-xs text-gray-500 mb-1 uppercase tracking-wide">What to look for</div>
          <div className="text-xs text-blue-300 bg-blue-900/20 border border-blue-800/40
            rounded-lg p-3 font-mono leading-relaxed">
            {refinement_note}
          </div>
        </div>
      )}

      <div className="text-xs text-yellow-400/80 mb-5">
        ⚠️ This will re-run the {tgtLabel} agent and increase session cost by ~{fmtCost(estimated_cost_usd)}.
      </div>

      {error && <Alert type="error" className="mb-4">{error}</Alert>}

      <div className="flex gap-3">
        <Button
          variant="success"
          loading={loading}
          onClick={() => decide(true)}
          className="flex-1 justify-center"
        >
          ✓ Allow A2A Re-run
        </Button>
        <Button
          variant="danger"
          loading={loading}
          onClick={() => decide(false)}
          className="flex-1 justify-center"
        >
          ✗ Reject
        </Button>
      </div>
    </Modal>
  );
}