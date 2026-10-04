// frontend/src/api/services/auth.service.js
// ─────────────────────────────────────────────────────────────────────────────
// Auth domain service.
// Every path below is a VERIFIED backend endpoint (api/main.py):
//   POST /auth/login   POST /auth/signup   GET /auth/me
// All calls flow through the bound client (createApiClient), so bearer-token
// injection and FastAPI-422 handling are inherited — nothing is re-implemented.
// ─────────────────────────────────────────────────────────────────────────────

/**
 * @param {ReturnType<import('../client').createApiClient>} api  bound API client
 */
export function createAuthService(api) {
  return {
    // Returns { access_token, user: { id, email, full_name, role, tenant_id, tenant_name } }
    login: (email, password) => api.post('/auth/login', { email, password }),

    // Returns the same shape as login; role is always 'tenant_user'.
    signup: (payload) => api.post('/auth/signup', payload),

    // Returns { id, email, role, tenant_id, full_name, tenant_name } for the
    // current bearer token. Use to verify a token and hydrate the canonical profile.
    me: () => api.get('/auth/me'),

    // Provision workspace details for current user
    provision: (payload) => api.post('/auth/provision', payload),

    // Password reset (verified backend endpoints — api/main.py):

    //   POST /auth/forgot-password  → always returns the same generic message.
    //     In an explicitly-enabled non-production dev env with email
    //     unconfigured, the response may also carry { dev_reset_url }.
    forgotPassword: (email) => api.post('/auth/forgot-password', { email }),

    //   POST /auth/reset-password → { message } on success; generic 400 on any
    //     invalid/expired/used token; 422 on a too-short password.
    resetPassword: (token, new_password) =>
      api.post('/auth/reset-password', { token, new_password }),
  }
}
