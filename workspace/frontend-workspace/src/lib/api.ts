/**
 * Centralized fetch wrapper.
 * Automatically attaches X-API-Key header to every request when
 * VITE_DASHBOARD_API_KEY is set in the environment.
 *
 * Usage:
 *   import { apiFetch } from '../lib/api'
 *   const res = await apiFetch('/api/signals/123/confirm', { method: 'POST' })
 */

const API_KEY = (import.meta as any).env?.VITE_DASHBOARD_API_KEY ?? ''

export function apiFetch(input: string, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers)
  if (API_KEY) {
    headers.set('X-API-Key', API_KEY)
  }
  return fetch(input, { ...init, headers })
}
