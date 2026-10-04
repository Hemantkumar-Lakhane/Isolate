// frontend/src/api/services/evidence.service.js
// ─────────────────────────────────────────────────────────────────────────────
// Evidence artifacts.
// Verified endpoints (api/main.py):
//   GET /evidence                              (list artifacts)
//   GET /evidence/{filename}/content           (artifact contents)
// ─────────────────────────────────────────────────────────────────────────────

export function createEvidenceService(api) {
  return {
    list: () => api.get('/evidence'),
    getContent: (filename) =>
      api.get(`/evidence/${encodeURIComponent(filename)}/content`),
  }
}
