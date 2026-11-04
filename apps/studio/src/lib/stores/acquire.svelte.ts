import { api } from '$lib/api/client';

export interface IngestTask {
	id: string;
	fileName: string;
	status: 'queued' | 'running' | 'completed' | 'failed' | 'error';
	percent: number;
	stage?: string;
	detail?: string;
	error?: string;
}

class AcquireStateStore {
	sensor = $state<'landsat-c2-l2' | 'sentinel-2-l2a'>('landsat-c2-l2');
	startDate = $state<string>('2024-06-01');
	endDate = $state<string>('2024-08-31');
	maxCloudCover = $state<number>(20);

	isIngesting = $state<boolean>(false);
	tasks = $state<IngestTask[]>([]);
	error = $state<string | null>(null);

	async ingestFile(file: File) {
		this.isIngesting = true;
		this.error = null;

		try {
			const res = await api.ingest.file(file);
			const taskId = res.job_id;

			const newTask: IngestTask = {
				id: taskId,
				fileName: file.name,
				status: 'running',
				percent: 0,
				stage: 'uploading',
				detail: 'Uploaded to gateway, job started'
			};

			this.tasks = [newTask, ...this.tasks];
			this.pollJob(taskId);
		} catch (err: unknown) {
			const msg = err instanceof Error ? err.message : 'File ingestion failed';
			this.error = msg;
		} finally {
			this.isIngesting = false;
		}
	}

	private async pollJob(jobId: string) {
		const pollInterval = setInterval(async () => {
			try {
				const job = await api.jobs.get(jobId);
				if (!job) return;

				const status = (job.status as IngestTask['status']) ?? 'running';
				const percent = typeof job.percent === 'number' ? job.percent : (status === 'completed' ? 100 : 0);
				const stage = typeof job.stage === 'string' ? job.stage : status;
				const detail = typeof job.detail === 'string' ? job.detail : undefined;
				const error = typeof job.error === 'string' ? job.error : undefined;

				this.tasks = this.tasks.map((t) =>
					t.id === jobId
						? {
								...t,
								status,
								percent,
								stage,
								detail,
								error
							}
						: t
				);

				if (status === 'completed' || status === 'failed' || status === 'error') {
					clearInterval(pollInterval);
				}
			} catch {
				clearInterval(pollInterval);
			}
		}, 1000);
	}
}

export const acquireState = new AcquireStateStore();
