// frontend/src/api/services/aiEngine.service.js
// ─────────────────────────────────────────────────────────────────────────────
// AI engine: model catalog, provider health, and the prompt tree.
// Verified endpoints (api/main.py):
//   GET  /config/models                 (available models / routing catalog)
//   GET  /health                        (includes llm provider key presence)
//   GET  /config/prompt-tree
//   GET  /config/prompts/{path}         PUT /config/prompts/{path}
//   POST /config/prompts/{path}         (create)
// NOTE: this is read/config only. Provider *management* and per-agent routing
// assignment are NOT backend capabilities today (see integration plan §13) — do
// not add methods for them here until those endpoints exist.
// ─────────────────────────────────────────────────────────────────────────────

export function createAIEngineService(api) {
  return {
    listModels: () => api.get('/config/models'),
    getHealth: () => api.get('/health'),

    // ── Prompt tree ────────────────────────────────────────────────────────────
    getPromptTree: () => api.get('/config/prompt-tree'),
    getPrompt: (path) => api.get(`/config/prompts/${path}`),
    updatePrompt: (path, content) => api.put(`/config/prompts/${path}`, { content }),
    createPrompt: (path, content) => api.post(`/config/prompts/${path}`, { content }),
  }
}
