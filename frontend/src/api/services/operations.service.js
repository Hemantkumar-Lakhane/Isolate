// frontend/src/api/services/operations.service.js
// ─────────────────────────────────────────────────────────────────────────────
// "Action Center" domain — the human-in-the-loop queues.
// Verified endpoints (api/main.py):
//   GET  /escalations?status=...            POST /escalations/{id}/decide
//   GET  /a2a/requests                      POST /a2a/{id}/decide
//   GET  /tenants/{tid}/email-queue?status=...
//   PUT  /email-queue/{id}                  POST /email-queue/{id}/approve | /reject
//   GET  /tenants/{tid}/patterns?status=...
//   POST /tenants/{tid}/patterns/{key}/promote | /demote
// ─────────────────────────────────────────────────────────────────────────────

export function createOperationsService(api) {
  return {
    // ── Escalations ────────────────────────────────────────────────────────────
    listEscalations: (status) =>
      api.get(`/escalations${status ? `?status=${status}` : ''}`),
    decideEscalation: (id, body) => api.post(`/escalations/${id}/decide`, body),

    // ── Agent-to-agent permission requests ─────────────────────────────────────
    listA2ARequests: () => api.get('/a2a/requests'),
    decideA2A: (id, body) => api.post(`/a2a/${id}/decide`, body),

    // ── Email draft queue (tenant-scoped) ──────────────────────────────────────
    listEmailQueue: (tenantId, status) =>
      api.get(`/tenants/${tenantId}/email-queue${status ? `?status=${status}` : ''}`),
    updateEmail: (id, body) => api.put(`/email-queue/${id}`, body),
    approveEmail: (id, body) => api.post(`/email-queue/${id}/approve`, body),
    rejectEmail: (id, body) => api.post(`/email-queue/${id}/reject`, body),

    // ── Learned patterns (tenant-scoped) ───────────────────────────────────────
    listPatterns: (tenantId, status) =>
      api.get(`/tenants/${tenantId}/patterns${status ? `?status=${status}` : ''}`),
    promotePattern: (tenantId, key) =>
      api.post(`/tenants/${tenantId}/patterns/${encodeURIComponent(key)}/promote`),
    demotePattern: (tenantId, key) =>
      api.post(`/tenants/${tenantId}/patterns/${encodeURIComponent(key)}/demote`),
  }
}
