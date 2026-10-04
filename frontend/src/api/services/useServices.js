// frontend/src/api/services/useServices.js
// ─────────────────────────────────────────────────────────────────────────────
// Convenience hook: returns the fully-built service layer for the current auth
// session. The services are memoized in AuthContext against the bound client
// (which itself only changes when the token changes), so this is stable across
// renders and safe to use in effect dependency arrays.
// ─────────────────────────────────────────────────────────────────────────────

import { useAuth } from '../../contexts/AuthContext'

export function useServices() {
  const { services } = useAuth()
  return services
}
