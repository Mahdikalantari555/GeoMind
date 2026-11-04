import { describe, it, expect, vi, beforeEach } from 'vitest';
import { studioState } from './studio.svelte';
import { api } from '../api/client';

describe('Studio State Store', () => {
	beforeEach(() => {
		vi.resetAllMocks();
	});

	it('initializes in connecting state', () => {
		expect(studioState.isConnecting).toBe(true);
		expect(studioState.connected).toBe(false);
	});

	it('updates state on successful health check', async () => {
		vi.spyOn(api, 'health').mockResolvedValue({
			status: 'ok',
			version: '0.1.0',
			workspace: { status: 'open', name: 'demo-workspace', path: '/path/demo' },
			llm: { provider: 'kilo', key_configured: true, base_url: null, key_env: 'KEY' }
		});

		const ok = await studioState.checkHealth();
		expect(ok).toBe(true);
		expect(studioState.connected).toBe(true);
		expect(studioState.workspace.isOpen).toBe(true);
		expect(studioState.workspace.name).toBe('demo-workspace');
		expect(studioState.llm.keyConfigured).toBe(true);
	});

	it('handles unreachable gateway without crashing', async () => {
		vi.spyOn(api, 'health').mockRejectedValue(new Error('Network error'));

		const ok = await studioState.checkHealth();
		expect(ok).toBe(false);
		expect(studioState.connected).toBe(false);
		expect(studioState.connectionError).toBe('Network error');
	});
});
