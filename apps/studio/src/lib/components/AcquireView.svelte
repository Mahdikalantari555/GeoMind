<script lang="ts">
	import { acquireState } from '$lib/stores/acquire.svelte';
	import { mapState } from '$lib/stores/map.svelte';
	import { studioState } from '$lib/stores/studio.svelte';
	import { Button } from '$lib/components/ui/button';
	import { Card, CardContent } from '$lib/components/ui/card';
	import { Badge } from '$lib/components/ui/badge';
	import { Progress } from '$lib/components/ui/progress';
	import EmptyState from '$lib/components/EmptyState.svelte';

	function handleSearch() {
		acquireState.startSearch();
	}
</script>

<div class="h-full overflow-y-auto p-6 space-y-6">
	<!-- Page Header -->
	<div class="flex items-center justify-between border-b border-border pb-4">
		<div>
			<h2 class="text-xl font-bold tracking-tight">Acquire Satellite Imagery</h2>
			<p class="text-xs text-muted-foreground">Search and download Landsat 8/9 & Sentinel-2 scenes for selected ROI</p>
		</div>

		{#if mapState.currentRoi}
			<Badge variant="outline" class="font-num text-xs px-3 py-1">
				Active ROI: <span class="text-primary font-bold ml-1">{mapState.currentRoi.name}</span>
			</Badge>
		{/if}
	</div>

	{#if !mapState.currentRoi}
		<EmptyState
			title="No Active Region of Interest (ROI)"
			description="Before searching for satellite scenes, select or draw an ROI polygon on the map."
			actionLabel="Go to Map Canvas"
			onaction={() => (studioState.activeTab = 'map')}
		/>
	{:else}
		<!-- Search Filter Bar -->
		<Card class="border-border/60 bg-card/60 p-4">
			<div class="grid grid-cols-1 md:grid-cols-4 gap-4 items-end">
				<div>
					<label for="sensor-select" class="block text-xs font-semibold text-muted-foreground font-num uppercase mb-1">Satellite Constellation</label>
					<select
						id="sensor-select"
						bind:value={acquireState.sensor}
						class="w-full rounded border border-border bg-background px-3 py-1.5 text-xs text-foreground font-medium focus:ring-1 focus:ring-primary"
					>
						<option value="landsat-c2-l2">Landsat 8/9 Collection 2 Level 2</option>
						<option value="sentinel-2-l2a">Sentinel-2 MSI Level 2A</option>
					</select>
				</div>

				<div>
					<label for="start-date" class="block text-xs font-semibold text-muted-foreground font-num uppercase mb-1">Start Date</label>
					<input
						id="start-date"
						type="date"
						bind:value={acquireState.startDate}
						class="w-full rounded border border-border bg-background px-3 py-1.5 text-xs text-foreground font-num focus:ring-1 focus:ring-primary"
					/>
				</div>

				<div>
					<label for="end-date" class="block text-xs font-semibold text-muted-foreground font-num uppercase mb-1">End Date</label>
					<input
						id="end-date"
						type="date"
						bind:value={acquireState.endDate}
						class="w-full rounded border border-border bg-background px-3 py-1.5 text-xs text-foreground font-num focus:ring-1 focus:ring-primary"
					/>
				</div>

				<div>
					<Button
						variant="default"
						class="w-full text-xs font-semibold"
						onclick={handleSearch}
						disabled={acquireState.isSearching}
					>
						{acquireState.isSearching ? 'Querying STAC...' : 'Search Catalog'}
					</Button>
				</div>
			</div>
		</Card>

		<!-- Results & Download Queue Grid -->
		<div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
			<!-- Available Scenes List -->
			<div class="lg:col-span-2 space-y-4">
				<div class="flex items-center justify-between">
					<h3 class="text-sm font-semibold text-foreground uppercase tracking-wider font-num">Available STAC Scenes</h3>
					<span class="text-xs font-num text-muted-foreground">{acquireState.searchResults.length} matching scenes</span>
				</div>

				{#if acquireState.searchResults.length === 0 && !acquireState.isSearching}
					<div class="rounded-lg border border-border/40 p-8 text-center text-xs text-muted-foreground">
						No queries executed yet. Adjust date filters and click "Search Catalog".
					</div>
				{/if}

				<div class="space-y-3">
					{#each acquireState.searchResults as scene (scene.id)}
						<Card class="border-border/60 bg-card/40 hover:bg-card/70 transition-colors">
							<CardContent class="p-4 flex items-center justify-between">
								<div class="space-y-1 overflow-hidden pr-4">
									<div class="flex items-center space-x-2">
										<span class="font-num text-xs font-bold text-foreground truncate">{scene.id}</span>
										{#if scene.already_owned}
											<Badge variant="secondary" class="text-[9px] uppercase font-num">Indexed</Badge>
										{/if}
									</div>
									<div class="flex items-center space-x-4 text-[11px] font-num text-muted-foreground">
										<span>Date: {scene.datetime.split('T')[0]}</span>
										<span>Cloud Cover: {scene.cloud_cover}%</span>
									</div>
								</div>

								<Button
									size="sm"
									variant={scene.already_owned ? 'outline' : 'default'}
									class="text-xs"
									onclick={() => acquireState.queueDownload(scene)}
									disabled={acquireState.downloadQueue.some(t => t.scene_id === scene.id && t.status !== 'failed')}
								>
									{scene.already_owned ? 'Re-Download' : 'Download'}
								</Button>
							</CardContent>
						</Card>
					{/each}
				</div>
			</div>

			<!-- Live Download & Auto-Ingest Queue -->
			<div class="space-y-4">
				<div class="flex items-center justify-between">
					<h3 class="text-sm font-semibold text-foreground uppercase tracking-wider font-num">Ingestion Pipeline Queue</h3>
					<Badge variant="outline" class="font-num text-[10px]">
						{acquireState.downloadQueue.length} jobs
					</Badge>
				</div>

				{#if acquireState.downloadQueue.length === 0}
					<div class="rounded-lg border border-border/40 p-6 text-center text-xs text-muted-foreground">
						Queue is idle. Trigger a download to watch live stage progress.
					</div>
				{/if}

				<div class="space-y-3">
					{#each acquireState.downloadQueue as task (task.id)}
						<Card class="border-border/60 bg-card p-3 space-y-2">
							<div class="flex items-center justify-between">
								<span class="font-num text-xs font-semibold truncate max-w-[180px]">{task.scene_id}</span>
								<Badge
									variant={task.status === 'done' ? 'default' : task.status === 'failed' ? 'destructive' : 'secondary'}
									class="text-[9px] uppercase font-num"
								>
									{task.status}
								</Badge>
							</div>

							<Progress value={task.percent} class="h-1.5" />

							<div class="flex items-center justify-between text-[10px] font-num text-muted-foreground">
								<span>Stage: {task.stage}</span>
								<span>{task.percent}%</span>
							</div>

							{#if task.detail}
								<p class="text-[10px] text-muted-foreground truncate">{task.detail}</p>
							{/if}

							<div class="flex justify-end pt-1">
								{#if task.status === 'running' || task.status === 'queued'}
									<Button
										size="sm"
										variant="ghost"
										class="h-5 px-2 text-[10px] text-destructive hover:bg-destructive/10"
										onclick={() => acquireState.cancelDownload(task.id)}
									>
										Cancel
									</Button>
								{:else if task.status === 'failed' || task.status === 'cancelled'}
									<Button
										size="sm"
										variant="outline"
										class="h-5 px-2 text-[10px]"
										onclick={() => acquireState.retryDownload(task.id)}
									>
										Retry
									</Button>
								{/if}
							</div>
						</Card>
					{/each}
				</div>
			</div>
		</div>
	{/if}
</div>
