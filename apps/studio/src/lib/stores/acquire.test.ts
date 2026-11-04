import { describe, it, expect } from 'vitest';
import { acquireState, type SceneSearchResult } from './acquire.svelte';

describe('Acquire Store State Machine', () => {
	it('queues downloads and transitions progress', async () => {
		const scene: SceneSearchResult = {
			id: 'LC09_TEST_SCENE',
			collection: 'landsat-c2-l2',
			datetime: '2024-07-01T00:00:00Z',
			cloud_cover: 5.0,
			already_owned: false
		};

		acquireState.queueDownload(scene);
		expect(acquireState.downloadQueue.some((t) => t.scene_id === scene.id)).toBe(true);

		const task = acquireState.downloadQueue.find((t) => t.scene_id === scene.id);
		expect(task?.status).toBe('queued');

		acquireState.cancelDownload(task!.id);
		const cancelled = acquireState.downloadQueue.find((t) => t.id === task!.id);
		expect(cancelled?.status).toBe('cancelled');

		acquireState.retryDownload(task!.id);
		const retried = acquireState.downloadQueue.find((t) => t.id === task!.id);
		expect(retried?.status).toBe('queued');
	});
});
