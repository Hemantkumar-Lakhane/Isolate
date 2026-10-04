// frontend/src/api/services/dashboard.service.js
// ─────────────────────────────────────────────────────────────────────────────
// Owner dashboard service.
// Verified endpoint: GET /dashboard/{tenant_id}
// (returns the tenant KPI + recent-activity payload consumed by Dashboard.jsx).
// ─────────────────────────────────────────────────────────────────────────────

export function createDashboardService(api) {
  return {
    get: (tenantId) => api.get(`/dashboard/${tenantId}`),
  }
}
