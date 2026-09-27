import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError, request } from './client'

describe('request client', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn())
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('omits Content-Type when body is FormData', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      headers: new Headers(),
      json: async () => ({ success: true }),
    })
    vi.stubGlobal('fetch', mockFetch)

    const formData = new FormData()
    formData.append('file', new Blob(['test']), 'test.txt')

    await request('/upload', { method: 'POST', body: formData })

    expect(mockFetch).toHaveBeenCalledTimes(1)
    const [, init] = mockFetch.mock.calls[0]
    const headers = init?.headers as Headers
    expect(headers.has('Content-Type')).toBe(false)
  })

  it('sets Content-Type to application/json when body is not FormData', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      headers: new Headers(),
      json: async () => ({ id: '123' }),
    })
    vi.stubGlobal('fetch', mockFetch)

    await request('/items', { method: 'POST', body: JSON.stringify({ name: 'test' }) })

    const [, init] = mockFetch.mock.calls[0]
    const headers = init?.headers as Headers
    expect(headers.get('Content-Type')).toBe('application/json')
  })

  it('throws ApiError with envelope details on error response', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 400,
      statusText: 'Bad Request',
      headers: new Headers({ 'X-Request-ID': 'req-999' }),
      json: async () => ({
        error: { code: 'validation_failed', message: 'Invalid payload', detail: { field: 'name' } },
      }),
    })
    vi.stubGlobal('fetch', mockFetch)

    await expect(request('/bad')).rejects.toThrow('Invalid payload')
    try {
      await request('/bad')
    } catch (e) {
      expect(e).toBeInstanceOf(ApiError)
      const err = e as ApiError
      expect(err.code).toBe('validation_failed')
      expect(err.status).toBe(400)
      expect(err.requestId).toBe('req-999')
      expect(err.detail).toEqual({ field: 'name' })
    }
  })
})
