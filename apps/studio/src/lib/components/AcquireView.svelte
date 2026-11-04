<script lang="ts">
	import { acquireState } from '$lib/stores/acquire.svelte';
	import { mapState } from '$lib/stores/map.svelte';
	import { studioState } from '$lib/stores/studio.svelte';
	import { Card } from '$lib/components/ui/card';
	import { Badge } from '$lib/components/ui/badge';
	import { Progress } from '$lib/components/ui/progress';
	import EmptyState from '$lib/components/EmptyState.svelte';

	let fileInput = $state<HTMLInputElement | null>(null);

	function handleFileSelect(e: Event) {
		const target = e.target as HTMLInputElement;
		if (target.files && target.files.length > 0) {
			for (let i = 0; i < target.files.length; i++) {
				acquireState.ingestFile(target.files[i]);
			}
		}
	}
</script>

<div class="h-full overflow-y-auto p-6 space-y-6">
	<!-- Page Header -->
	<div class="flex items-center justify-between border-b border-border pb-4">
		<div>
			<h2 class="text-xl font-bold tracking-tight">Acquire & Ingest Data</h2>
			<p class="text-xs text-muted-foreground">Ingest local satellite rasters, vector parcels, or documents into active research workspace</p>
		</div>

		{#if mapState.currentRoi}
			<Badge variant="outline" class="font-num text-xs px-3 py-1">
				Active ROI: <span class="text-primary font-bold ml-1">{mapState.currentRoi.name}</span>
			</Badge>
		{/if}
	</div>

	{#if !studioState.workspace.isOpen}
		<EmptyState
			title="No Active Workspace Open"
			description="Before ingesting remote sensing data, open or create a research workspace."
			actionLabel="Go to Map Canvas"
			onaction={() => (studioState.activeTab = 'map')}
		/>
	{:else}
		<div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
			<!-- Ingest Files Section -->
			<div class="lg:col-span-2 space-y-6">
				<!-- Local File Upload Card -->
				<Card class="border-border/60 bg-card/60 p-6">
					<div class="space-y-4">
						<div class="flex items-center justify-between">
							<h3 class="text-sm font-semibold text-foreground uppercase tracking-wider font-num">Direct File Ingestion</h3>
							<span class="text-xs text-muted-foreground font-num">GeoTIFF, GeoJSON, GPKG, PDF</span>
						</div>

						<p class="text-xs text-muted-foreground leading-relaxed">
							Upload local remote sensing scenes (Landsat/Sentinel-2 GeoTIFFs), parcel boundary GeoJSONs, or telemetry PDFs directly to the local memory engine.
						</p>

						<input
							type="file"
							bind:this={fileInput}
							onchange={handleFileSelect}
							multiple
							accept=".tif,.tiff,.geojson,.gpkg,.pdf,.csv,.md,.txt"
							class="hidden"
						/>

						<div
							class="flex flex-col items-center justify-center border-2 border-dashed border-border/80 rounded-lg p-8 text-center bg-background/50 hover:bg-background/80 transition-colors cursor-pointer"
							onclick={() => fileInput?.click()}
							onkeydown={(e) => e.key === 'Enter' && fileInput?.click()}
							role="button"
							tabindex="0"
						>
							<svg class="h-8 w-8 text-muted-foreground mb-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
								<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
							</svg>
							<div class="text-xs font-semibold text-foreground">Click to select files from disk</div>
							<p class="text-[11px] text-muted-foreground mt-1">Files are ingested into your local SQLite workspace database without cloud transfer.</p>
						</div>

						{#if acquireState.error}
							<div class="rounded border border-destructive/50 bg-destructive/10 p-2 text-xs text-destructive">
								{acquireState.error}
							</div>
						{/if}
					</div>
				</Card>

				<!-- STAC Notice Card -->
				<Card class="border-border/60 bg-card/40 p-4">
					<div class="flex items-start space-x-3">
						<div class="rounded-full bg-primary/10 p-2 text-primary mt-0.5">
							<svg class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
								<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
							</svg>
						</div>
						<div class="space-y-1">
							<div class="text-xs font-semibold text-foreground">Remote STAC Catalog Integration</div>
							<p class="text-[11px] text-muted-foreground leading-relaxed">
								Live automated scene downloading connects directly to Microsoft Planetary Computer or USGS EarthExplorer STAC APIs. When configuring STAC endpoints in settings, credentials authenticate against the data provider.
							</p>
						</div>
					</div>
				</Card>
			</div>

			<!-- Real Pipeline Job Queue -->
			<div class="space-y-4">
				<div class="flex items-center justify-between">
					<h3 class="text-sm font-semibold text-foreground uppercase tracking-wider font-num">Active Ingest Jobs</h3>
					<Badge variant="outline" class="font-num text-[10px]">
						{acquireState.tasks.length} jobs
					</Badge>
				</div>

				{#if acquireState.tasks.length === 0}
					<div class="rounded-lg border border-border/40 p-6 text-center text-xs text-muted-foreground">
						No active ingest jobs. Select a file to start processing.
					</div>
				{/if}

				<div class="space-y-3">
					{#each acquireState.tasks as task (task.id)}
						<Card class="border-border/60 bg-card p-3 space-y-2">
							<div class="flex items-center justify-between">
								<span class="font-num text-xs font-semibold truncate max-w-[180px]">{task.fileName}</span>
								<Badge
									variant={task.status === 'completed' ? 'default' : task.status === 'failed' || task.status === 'error' ? 'destructive' : 'secondary'}
									class="text-[9px] uppercase font-num"
								>
									{task.status}
								</Badge>
							</div>

							{#if task.status === 'running'}
								<Progress value={task.percent} class="h-1.5" />
							{/if}

							<div class="flex items-center justify-between text-[10px] font-num text-muted-foreground">
								<span>Stage: {task.stage ?? 'processing'}</span>
								<span>{task.percent}%</span>
							</div>

							{#if task.detail}
								<p class="text-[10px] text-muted-foreground truncate">{task.detail}</p>
							{/if}

							{#if task.error}
								<p class="text-[10px] text-destructive truncate">{task.error}</p>
							{/if}
						</Card>
					{/each}
				</div>
			</div>
		</div>
	{/if}
</div>
