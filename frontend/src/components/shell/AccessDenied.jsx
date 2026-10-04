// frontend/src/components/shell/AccessDenied.jsx
// ─────────────────────────────────────────────────────────────────────────────
// Professional "permission denied" state for authenticated-but-unauthorized
// situations (e.g. a tenant_user reaching an admin-only area). This does NOT
// change any guard semantics — the existing adminOnly guard in App.jsx still
// governs access. This component is the explicit, readable surface for a 403
// where we'd otherwise show nothing useful.
// ─────────────────────────────────────────────────────────────────────────────
import { useNavigate } from 'react-router-dom'
import { ShieldAlert } from 'lucide-react'
import { useAuth } from '../../contexts/AuthContext'

export default function AccessDenied() {
  const navigate = useNavigate()
  const { isAdmin } = useAuth()
  const home = isAdmin ? '/admin' : '/dashboard'

  return (
    <div className="min-h-[60vh] flex items-center justify-center p-6">
      <div className="max-w-sm text-center">
        <div className="w-12 h-12 rounded-2xl bg-amber-100 flex items-center justify-center mx-auto mb-4">
          <ShieldAlert size={22} className="text-amber-600" />
        </div>
        <h1 className="text-lg font-semibold text-slate-900 mb-1.5">Access denied</h1>
        <p className="text-sm text-slate-500 mb-6 leading-relaxed">
          You do not have permission to access this area.
        </p>
        <button
          onClick={() => navigate(home, { replace: true })}
          className="inline-flex items-center justify-center px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 transition-colors"
        >
          Return to workspace
        </button>
      </div>
    </div>
  )
}
