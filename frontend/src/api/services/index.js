// frontend/src/api/services/index.js
// ─────────────────────────────────────────────────────────────────────────────
// Central service-layer aggregator.
//
// Every domain service is built on top of the PROVEN bound client
// (createApiClient in ../client.js), so all of them inherit:
//   • Authorization: Bearer <token> injection
//   • FastAPI 422 validation-error flattening
//   • VITE_API_BASE base-URL resolution
//   • null-on-204 handling
//
// Usage (inside a component): const services = useServices()
// Usage (from AuthContext):   const services = createServices(api)
//
// This layer intentionally exposes ONLY endpoints verified against api/main.py
// or the backend audit. It invents nothing.
// ─────────────────────────────────────────────────────────────────────────────

import { createAuthService } from './auth.service'
import { createDashboardService } from './dashboard.service'
import { createWorkflowsService } from './workflows.service'
import { createOperationsService } from './operations.service'
import { createTenantsService } from './tenants.service'
import { createAIEngineService } from './aiEngine.service'
import { createIntegrationsService } from './integrations.service'
import { createEvidenceService } from './evidence.service'
import { createAdminService } from './admin.service'

/**
 * Build the full service layer from a bound API client.
 * @param {ReturnType<import('../client').createApiClient>} api
 */
export function createServices(api) {
  return {
    auth: createAuthService(api),
    dashboard: createDashboardService(api),
    workflows: createWorkflowsService(api),
    operations: createOperationsService(api),
    tenants: createTenantsService(api),
    aiEngine: createAIEngineService(api),
    integrations: createIntegrationsService(api),
    evidence: createEvidenceService(api),
    admin: createAdminService(api),
  }
}
