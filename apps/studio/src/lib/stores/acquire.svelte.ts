export interface SceneSearchResult {
	id: string;
	collection: 'landsat-c2-l2' | 'sentinel-2-l2a';
	datetime: string;
	cloud_cover: number;
	thumbnail_url?: string;
	already_owned: boolean;
}

export interface DownloadTask {
	id: string;
	scene_id: string;
	status: 'queued' | 'running' | 'done' | 'failed' | 'cancelled';
	percent: number;
	stage: string;
	detail?: string;
	error?: string;
}

class AcquireStateStore {
	sensor = $state<'landsat-c2-l2' | 'sentinel-2-l2a'>('landsat-c2-l2');
	startDate = $state<string>('2024-06-01');
	endDate = $state<string>('2024-08-31');
	maxCloudCover = $state<number>(20);

	isSearching = $state<boolean>(false);
	searchResults = $state<SceneSearchResult[]>([]);
	searchError = $state<string | null>(null);

	downloadQueue = $state<DownloadTask[]>([]);

	startSearch() {
		this.isSearching = true;
		this.searchError = null;

		// Mocked search results based on selected ROI / STAC simulation
		setTimeout(() => {
			this.isSearching = false;
			this.searchResults = [
				{
					id: 'LC09_L2SP_166038_20240715_02_T1',
					collection: this.sensor,
					datetime: '2024-07-15T07:22:15Z',
					cloud_cover: 2.4,
					already_owned: false
				},
				{
					id: 'LC08_L2SP_166038_20240723_02_T1',
					collection: this.sensor,
					datetime: '2024-07-23T07:22:30Z',
					cloud_cover: 8.1,
					already_owned: true
				},
				{
					id: 'LC09_L2SP_166038_20240731_02_T1',
					collection: this.sensor,
					datetime: '2024-07-31T07:22:12Z',
					cloud_cover: 0.8,
					already_owned: false
				}
			];
		}, 300);
	}

	queueDownload(scene: SceneSearchResult) {
		if (this.downloadQueue.some((t) => t.scene_id === scene.id)) return;

		const task: DownloadTask = {
			id: `task-${Date.now()}-${scene.id.slice(0, 6)}`,
			scene_id: scene.id,
			status: 'queued',
			percent: 0,
			stage: 'pending'
		};

		this.downloadQueue = [...this.downloadQueue, task];
		this.simulateJobProgress(task.id);
	}

	cancelDownload(taskId: string) {
		this.downloadQueue = this.downloadQueue.map((t) =>
			t.id === taskId ? { ...t, status: 'cancelled', detail: 'User cancelled' } : t
		);
	}

	retryDownload(taskId: string) {
		this.downloadQueue = this.downloadQueue.map((t) =>
			t.id === taskId ? { ...t, status: 'queued', percent: 0, stage: 'pending', error: undefined } : t
		);
		this.simulateJobProgress(taskId);
	}

	private simulateJobProgress(taskId: string) {
		let percent = 0;
		const interval = setInterval(() => {
			const task = this.downloadQueue.find((t) => t.id === taskId);
			if (!task || task.status === 'cancelled') {
				clearInterval(interval);
				return;
			}

			percent += 20;
			if (percent < 40) {
				this.updateTask(taskId, { status: 'running', percent, stage: 'fetching_bands', detail: 'Downloading spectral bands from STAC' });
			} else if (percent < 80) {
				this.updateTask(taskId, { status: 'running', percent, stage: 'ingesting', detail: 'Registering scene in workspace' });
			} else if (percent < 100) {
				this.updateTask(taskId, { status: 'running', percent, stage: 'indexing', detail: 'Generating vector and spectral indices' });
			} else {
				this.updateTask(taskId, { status: 'done', percent: 100, stage: 'done', detail: 'Scene ready on map' });
				clearInterval(interval);
			}
		}, 200);
	}

	private updateTask(taskId: string, patch: Partial<DownloadTask>) {
		this.downloadQueue = this.downloadQueue.map((t) =>
			t.id === taskId ? { ...t, ...patch } : t
		);
	}
}

export const acquireState = new AcquireStateStore();
