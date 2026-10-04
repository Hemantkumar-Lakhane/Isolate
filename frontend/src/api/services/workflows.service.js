// frontend/src/api/services/workflows.service.js
// ─────────────────────────────────────────────────────────────────────────────
// Workflow runtime + DAG-definition service.
// Verified endpoints (api/main.py):
//   POST   /workflows/trigger
//   GET    /workflows/{run_id}/status
//   POST   /workflows/{run_id}/pause | /stop | /resume | /fork
//   GET    /config/workflows                 (list of DAG definitions)
//   GET    /config/dag/{name}
//   POST   /config/dag                        (create)
//   PUT    /config/dag/{name}                 (update)
//   DELETE /config/dag/{name}
// Note: the backend keys runs by run_id, not by a "workflow id" — the caller
// must pass the run_id it received from /workflows/trigger.
// ─────────────────────────────────────────────────────────────────────────────

export function createWorkflowsService(api) {
  return {
    // ── Runtime ──────────────────────────────────────────────────────────────
    trigger: (payload) => api.post('/workflows/trigger', payload),
    getStatus: (runId) => api.get(`/workflows/${runId}/status`),
    pause: (runId) => api.post(`/workflows/${runId}/pause`, {}),
    stop: (runId) => api.post(`/workflows/${runId}/stop`, {}),
    resume: (runId) => api.post(`/workflows/${runId}/resume`, {}),
    fork: (runId, body) => api.post(`/workflows/${runId}/fork`, body),

    // ── DAG definitions (a.k.a. the workflow catalog) ──────────────────────────
    listDefinitions: () => api.get('/config/workflows'),
    getDag: (name) => api.get(`/config/dag/${name}`),
    createDag: (name, dag) => api.post('/config/dag', { name, dag }),
    updateDag: (name, dag) => api.put(`/config/dag/${name}`, { name, dag }),
    deleteDag: (name) => api.delete(`/config/dag/${name}`),
  }
}
