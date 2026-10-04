// frontend/src/api/services/admin.service.js
// ─────────────────────────────────────────────────────────────────────────────
// Platform-admin (super_admin) service.
// Verified endpoints (api/main.py):
//   GET  /admin/god-view                    (fleet-wide state snapshot)
//   GET  /analytics/admin/fleet             (fleet cost analytics)
//   GET  /analytics/{tenant_id}             (per-tenant analytics)
//   POST /admin/auto-eval/run
//   POST /admin/auto-eval/suggestions/{id}/apply | /dismiss
// NOTE: Provider/model management, platform-settings, and a full audit-log API
// do NOT exist yet (integration plan §13). No placeholder methods are added for
// them — screens that need them must show honest "not configured" states.
// ─────────────────────────────────────────────────────────────────────────────

export function createAdminService(api) {
  return {
    getGodView: () => api.get('/admin/god-view'),
    getFleetAnalytics: () => api.get('/analytics/admin/fleet'),
    getTenantAnalytics: (tenantId) => api.get(`/analytics/${tenantId}`),

    // ── Prompt auto-evaluation ─────────────────────────────────────────────────
    runAutoEval: (payload) => api.post('/admin/auto-eval/run', payload),
    applyAutoEvalSuggestion: (id, payload) =>
      api.post(`/admin/auto-eval/suggestions/${id}/apply`, payload),
    dismissAutoEvalSuggestion: (id) =>
      api.post(`/admin/auto-eval/suggestions/${id}/dismiss`, {}),
  }
}
