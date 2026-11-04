import { describe, it, expect, vi, beforeEach } from 'vitest';
import { request, ApiError } from './client';

describe('API client', () => {
	beforeEach(() => {
		vi.resetAllMocks();
	});

	it('handles successful requests with JSON parsing', async () => {
		const mockData = { status: 'ok' };
		vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
			ok: true,
			json: async () => mockData,
			headers: new Headers()
		}));

		const res = await request<{ status: string }>('/health');
		expect(res).toEqual(mockData);
		expect(fetch).toHaveBeenCalledWith('/api/v1/health', expect.any(Object));
	});

	it('throws structured ApiError on non-ok responses', async () => {
		const errorBody = {
			error: {
				code: 'NOT_FOUND',
				message: 'Workspace not found'
			}
		};
		vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
			ok: false,
			status: 404,
			statusText: 'Not Found',
			json: async () => errorBody,
			headers: new Headers({ 'X-Request-ID': 'req-123' })
		}));

		await expect(request('/workspace')).rejects.toThrow('Workspace not found');
		try {
			await request('/workspace');
		} catch (err) {
			expect(err).toBeInstanceOf(ApiError);
			const apiErr = err as ApiError;
			expect(apiErr.code).toBe('NOT_FOUND');
			expect(apiErr.status).toBe(404);
			expect(apiErr.requestId).toBe('req-123');
		}
	});
});
