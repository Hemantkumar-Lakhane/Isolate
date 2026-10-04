// frontend/src/api/services/integrations.service.js
// ─────────────────────────────────────────────────────────────────────────────
// Tool Connections: multi-tenant integration lifecycle & credential vault.
// Verified endpoints (api/routers/connections.py):
//   GET  /connections                 POST /connections            GET /connections/available
//   GET  /connections/{id}            PATCH /connections/{id}      DELETE /connections/{id}
//   POST /connections/{id}/test
// ─────────────────────────────────────────────────────────────────────────────

export function createIntegrationsService(api) {
  return {
    // ── Tool Connections API ───────────────────────────────────────────────────
    listConnections: () => api.get('/connections'),
    getAvailableConnectors: () => api.get('/connections/available'),
    getConnection: (id) => api.get(`/connections/${id}`),
    connectTool: (payload) => api.post('/connections', payload),
    updateConnection: (id, payload) => api.patch(`/connections/${id}`, payload),
    testConnection: (id) => api.post(`/connections/${id}/test`),
    deleteConnection: (id) => api.delete(`/connections/${id}`),

    // ── Legacy Aliases ─────────────────────────────────────────────────────────
    listCredentials: () => api.get('/connections'),
    createCredential: (payload) => api.post('/connections', payload),
    deleteCredential: (id) => api.delete(`/connections/${id}`),

    // ── Seed data ──────────────────────────────────────────────────────────────
    getSeedStatus: () => api.get('/seed-data/status'),
    generateSeed: (industry) =>
      api.post(`/seed-data/generate${industry ? `?industry=${industry}` : ''}`),
  }
}

