import { describe, it, expect, vi } from 'vitest';
import { acquireState } from './acquire.svelte';
import { api } from '$lib/api/client';

describe('Acquire Store Ingestion', () => {
	it('starts ingestion job via gateway api and creates tracking task', async () => {
		vi.spyOn(api.ingest, 'file').mockResolvedValueOnce({ job_id: 'job-test-123' });
		vi.spyOn(api.jobs, 'get').mockResolvedValueOnce({
			id: 'job-test-123',
			status: 'running',
			percent: 50,
			stage: 'indexing'
		});

		const file = new File(['mock content'], 'test_raster.tif', { type: 'image/tiff' });
		await acquireState.ingestFile(file);

		expect(acquireState.tasks.length).toBeGreaterThan(0);
		const task = acquireState.tasks.find((t) => t.fileName === 'test_raster.tif');
		expect(task).toBeDefined();
		expect(task?.id).toBe('job-test-123');
	});
});
