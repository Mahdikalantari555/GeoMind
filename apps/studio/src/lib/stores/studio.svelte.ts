import { api, type Health, ApiError } from '$lib/api/client';

export type WorkspaceState = {
	isOpen: boolean;
	path: string | null;
	name: string | null;
};

export type LLMState = {
	provider: string;
	keyConfigured: boolean;
	baseUrl: string | null;
};

class StudioStateStore {
	connected = $state<boolean>(false);
	isConnecting = $state<boolean>(true);
	connectionError = $state<string | null>(null);

	workspace = $state<WorkspaceState>({
		isOpen: false,
		path: null,
		name: null
	});

	llm = $state<LLMState>({
		provider: 'unknown',
		keyConfigured: false,
		baseUrl: null
	});

	version = $state<string>('');

	// Active tab / route
	activeTab = $state<'map' | 'acquire' | 'health'>('map');

	// Command palette visibility
	commandPaletteOpen = $state<boolean>(false);

	async checkHealth(): Promise<boolean> {
		this.isConnecting = true;
		try {
			const res: Health = await api.health();
			this.connected = true;
			this.connectionError = null;
			this.version = res.version;
			this.workspace = {
				isOpen: res.workspace.status === 'open',
				path: res.workspace.path ?? null,
				name: res.workspace.name ?? null
			};
			this.llm = {
				provider: res.llm.provider,
				keyConfigured: res.llm.key_configured,
				baseUrl: res.llm.base_url ?? null
			};
			return true;
		} catch (err) {
			this.connected = false;
			if (err instanceof ApiError) {
				this.connectionError = `${err.code}: ${err.message}`;
			} else if (err instanceof Error) {
				this.connectionError = err.message;
			} else {
				this.connectionError = 'Gateway unreachable';
			}
			return false;
		} finally {
			this.isConnecting = false;
		}
	}
}

export const studioState = new StudioStateStore();
