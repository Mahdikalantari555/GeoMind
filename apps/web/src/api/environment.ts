import { ApiError, type ApiErrorBody } from './client'

const BASE = '/api/v1'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(`${BASE}${path}`, {
    headers: init?.body ? { 'Content-Type': 'application/json' } : undefined,
    ...init,
  })
  if (!resp.ok) {
    let parsed: unknown = null
    try {
      parsed = await resp.json()
    } catch {
      /* non-JSON error body */
    }
    const err = (parsed as ApiErrorBody | null)?.error
    throw new ApiError(err ?? { code: 'http_error', message: resp.statusText }, resp.status)
  }
  return (await resp.json()) as T
}

export const environmentApi = {
  setOverrides: (env: Record<string, string>) =>
    request<{ applied: Record<string, string | null>; ignored: string[] }>('/environment/overrides', {
      method: 'POST',
      body: JSON.stringify({ env }),
    }),
  getOverrides: () => request<Record<string, string | null>>('/environment/overrides'),
}
