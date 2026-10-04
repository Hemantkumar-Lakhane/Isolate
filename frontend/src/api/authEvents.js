// frontend/src/api/authEvents.js
// ─────────────────────────────────────────────────────────────────────────────
// Tiny module-level event bus that lets the transport layer (api/client.js)
// signal an authenticated-session expiry (a 401 returned while a bearer token
// was attached) to React (AuthContext) WITHOUT a circular import or a new
// dependency. AuthContext subscribes; client.js emits.
//
// Only authenticated 401s are emitted — the login / forgot-password /
// reset-password calls run through an unauthenticated client (no token), so
// their 401s never reach here and are handled inline as normal errors.
// ─────────────────────────────────────────────────────────────────────────────

const listeners = new Set()

/** Subscribe to session-expired events. Returns an unsubscribe function. */
export function onSessionExpired(handler) {
  listeners.add(handler)
  return () => listeners.delete(handler)
}

/** Emit a session-expired event to all subscribers. */
export function emitSessionExpired() {
  listeners.forEach((fn) => {
    try { fn() } catch (_) { /* a listener error must not break others */ }
  })
}
