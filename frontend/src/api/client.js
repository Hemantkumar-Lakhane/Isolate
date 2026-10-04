// frontend/src/api/client.js

import { emitSessionExpired } from './authEvents'

export const API_BASE = import.meta.env.VITE_API_BASE || 'http://127.0.0.1:8000/api/v1'
export const WS_BASE  = import.meta.env.VITE_WS_BASE  || 'ws://127.0.0.1:8000/ws'

/**
 * Core fetch wrapper.
 * - Injects Authorization header when token is provided
 * - Throws Error with server's `detail` message on failure
 * - Returns null on 204 No Content
 */
export async function apiCall(path, options = {}, token = null) {
  const isFormData = typeof FormData !== 'undefined' && options.body instanceof FormData
  const headers = isFormData ? {} : { 'Content-Type': 'application/json' }
  if (token) headers['Authorization'] = `Bearer ${token}`
  if (options.headers) {
    Object.assign(headers, options.headers)
  }

  // Normalize path to prevent double /api/v1 prefixes
  let cleanPath = path || ''
  if (cleanPath.startsWith('/api/v1/')) {
    cleanPath = cleanPath.slice(7)
  } else if (cleanPath.startsWith('api/v1/')) {
    cleanPath = cleanPath.slice(6)
  } else if (cleanPath === '/api/v1' || cleanPath === 'api/v1') {
    cleanPath = ''
  }
  if (!cleanPath.startsWith('/')) {
    cleanPath = `/${cleanPath}`
  }

  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), options.timeout || 60000)
  const signal = options.signal || controller.signal

  let res
  try {
    res = await fetch(`${API_BASE}${cleanPath}`, { ...options, headers, signal })
  } catch (networkErr) {
    if (networkErr.name === 'AbortError') {
      throw new Error(`Request timed out after ${((options.timeout || 60000) / 1000).toFixed(0)}s. Please retry.`)
    }
    throw new Error(`Network error: cannot reach API. Is the server running?`)
  } finally {
    clearTimeout(timeoutId)
  }

  if (!res.ok) {
    // Authenticated session expiry: a 401 returned while a bearer token was
    // attached means the token is no longer valid. Signal AuthContext to clear
    // auth (which also tears down the authenticated WebSocket) and redirect.
    // Unauthenticated calls (login/forgot/reset use token === null) are exempt,
    // so their 401s are handled inline as ordinary errors.
    if (res.status === 401 && token) {
      emitSessionExpired()
    }

    let detail = `${res.status} ${res.statusText}`
    try {
      const contentType = res.headers.get('content-type') || ''
      if (contentType.includes('application/json')) {
        const body = await res.json()
        // Handle FastAPI 422 Validation Error arrays
        if (Array.isArray(body.detail)) {
          detail = body.detail.map(err => {
            const field = err.loc ? err.loc.slice(-1).join('.') : 'field'
            return `[${field}]: ${err.msg}`
          }).join(' | ')
        } else {
          detail = body.detail || body.message || detail
        }
      } else {
        const text = await res.text()
        // Only include text if it looks like a real message, not raw HTML
        if (text && !text.trimStart().startsWith('<')) {
          detail = text.slice(0, 200) || detail
        }
      }
    } catch (_) {}
    const err = new Error(detail)
    err.status = res.status
    throw err
  }

  if (res.status === 204) return null
  return res.json()
}

/**
 * Create a bound API client that auto-injects auth headers.
 *
 * Usage:
 *   const api = createApiClient(token)
 *   const user = await api.get('/auth/me')
 *   await api.post('/workflows/trigger', { ... })
 */
export function createApiClient(token) {
  const call = (path, opts) => apiCall(path, opts, token)

  return {
    get: (path, params) => {
      let finalPath = path
      const queryObj = (params && typeof params === 'object' && params.params) ? params.params : params
      if (queryObj && typeof queryObj === 'object') {
        const q = new URLSearchParams()
        Object.entries(queryObj).forEach(([k, v]) => {
          if (v !== undefined && v !== null) q.append(k, v)
        })
        const qs = q.toString()
        if (qs) finalPath += (finalPath.includes('?') ? '&' : '?') + qs
      }
      return call(finalPath, { method: 'GET' })
    },
    post: (path, data) => {
      const isFormData = typeof FormData !== 'undefined' && data instanceof FormData
      return call(path, {
        method: 'POST',
        body: isFormData ? data : JSON.stringify(data),
      })
    },
    upload: (path, formData) => call(path, { method: 'POST', body: formData }),
    put: (path, data) => {
      const isFormData = typeof FormData !== 'undefined' && data instanceof FormData
      return call(path, {
        method: 'PUT',
        body: isFormData ? data : JSON.stringify(data),
      })
    },
    patch:  (path, data)  => call(path, { method: 'PATCH',  body: JSON.stringify(data) }),
    delete: (path)        => call(path, { method: 'DELETE' }),
  }
}