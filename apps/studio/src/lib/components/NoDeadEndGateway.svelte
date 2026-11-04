<script lang="ts">
	import { studioState } from '$lib/stores/studio.svelte';
	import { Button } from '$lib/components/ui/button';

	let retrying = $state(false);

	async function handleRetry() {
		retrying = true;
		await studioState.checkHealth();
		retrying = false;
	}
</script>

<div class="flex h-screen w-screen flex-col items-center justify-center bg-background p-6 text-foreground">
	<div class="w-full max-w-md rounded-lg border border-destructive/40 bg-card p-6 shadow-2xl">
		<div class="mb-4 flex items-center space-x-3">
			<div class="flex h-10 w-10 items-center justify-center rounded-full bg-destructive/10 text-destructive">
				<svg class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
					<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
				</svg>
			</div>
			<div>
				<h2 class="text-lg font-semibold tracking-tight">Gateway Unreachable</h2>
				<p class="text-xs text-muted-foreground">Cannot establish connection to FastAPI service</p>
			</div>
		</div>

		<div class="mb-6 rounded bg-background/50 p-3 font-num text-xs text-muted-foreground border border-border">
			{studioState.connectionError || 'Failed to reach /api/v1/health'}
		</div>

		<div class="flex flex-col space-y-2">
			<Button variant="default" onclick={handleRetry} disabled={retrying} class="w-full">
				{retrying ? 'Connecting...' : 'Retry Connection'}
			</Button>
			<p class="text-center text-[11px] text-muted-foreground">
				Make sure <code class="font-num text-foreground">uvicorn geofront_api.main:app</code> is running on port 8000.
			</p>
		</div>
	</div>
</div>
