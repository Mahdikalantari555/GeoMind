import { request } from './client'

export const environmentApi = {
  setOverrides: (env: Record<string, string>) =>
    request<{ applied: Record<string, string | null>; ignored: string[] }>('/environment/overrides', {
      method: 'POST',
      body: JSON.stringify({ env }),
    }),
  getOverrides: () => request<Record<string, string | null>>('/environment/overrides'),
}
