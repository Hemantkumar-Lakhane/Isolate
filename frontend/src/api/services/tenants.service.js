// frontend/src/api/services/tenants.service.js
// ─────────────────────────────────────────────────────────────────────────────
// Tenants (a.k.a. "organizations" in the new UI), users, config and budget.
// Verified endpoints (api/main.py):
//   GET  /tenants                 GET /tenants/{id}
//   GET  /tenants/{id}/config-schema
//   PUT  /tenants/{id}/config     (body shape is caller-owned — ConfigStudio
//                                  sends { config }, ModelSettings sends overrides)
//   GET  /tenants/{id}/budget     PUT /tenants/{id}/budget
//   GET  /users   POST /users     PATCH /users/{id}/deactivate
// ─────────────────────────────────────────────────────────────────────────────

export function createTenantsService(api) {
  return {
    list: () => api.get('/tenants'),
    get: (id) => api.get(`/tenants/${id}`),
    getConfigSchema: (id) => api.get(`/tenants/${id}/config-schema`),
    // body is passed through verbatim so each caller controls its own payload shape.
    updateConfig: (id, body) => api.put(`/tenants/${id}/config`, body),
    getBudget: (id) => api.get(`/tenants/${id}/budget`),
    updateBudget: (id, settings) => api.put(`/tenants/${id}/budget`, settings),

    // ── Users ──────────────────────────────────────────────────────────────────
    listUsers: () => api.get('/users'),
    createUser: (payload) => api.post('/users', payload),
    deactivateUser: (id) => api.patch(`/users/${id}/deactivate`, {}),
  }
}
