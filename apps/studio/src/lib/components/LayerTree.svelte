<script lang="ts">
	import { mapState } from '$lib/stores/map.svelte';
	import { Badge } from '$lib/components/ui/badge';
	import { Button } from '$lib/components/ui/button';

	const categories = [
		{ id: 'rois', label: 'Regions of Interest' },
		{ id: 'scenes', label: 'Raster Scenes' },
		{ id: 'products', label: 'Biophysical Products' },
		{ id: 'base', label: 'Basemap' }
	] as const;

	function formatArea(m2: number): string {
		if (m2 > 1000000) {
			return `${(m2 / 1000000).toFixed(2)} km²`;
		}
		return `${(m2 / 10000).toFixed(2)} ha`;
	}
</script>

<aside class="flex h-full w-72 flex-col border-r border-border bg-card/60 backdrop-blur">
	<div class="flex h-10 items-center justify-between border-b border-border px-3">
		<span class="text-xs font-bold uppercase tracking-wider font-num text-muted-foreground">Layer Hierarchy</span>
		<Badge variant="outline" class="font-num text-[10px]">
			{mapState.layers.filter(l => l.visible).length} visible
		</Badge>
	</div>

	<div class="flex-1 overflow-y-auto p-2 space-y-4">
		{#each categories as cat (cat.id)}
			{@const catLayers = mapState.layers.filter(l => l.category === cat.id)}
			{#if catLayers.length > 0}
				<div class="space-y-1">
					<div class="px-2 text-[11px] font-semibold tracking-wider text-muted-foreground uppercase font-num">
						{cat.label}
					</div>
					{#each catLayers as layer (layer.id)}
						<div class="flex flex-col rounded p-1.5 hover:bg-accent/30 transition-colors space-y-1">
							<div class="flex items-center justify-between text-xs">
								<label class="flex items-center space-x-2 cursor-pointer flex-1 overflow-hidden">
									<input
										type="checkbox"
										checked={layer.visible}
										onchange={() => mapState.toggleLayer(layer.id)}
										class="rounded border-border bg-background text-primary focus:ring-primary h-3.5 w-3.5"
									/>
									<span class="truncate font-medium {layer.visible ? 'text-foreground' : 'text-muted-foreground'}">
										{layer.name}
									</span>
								</label>

								{#if layer.category === 'rois'}
									{@const roi = mapState.rois.find(r => r.id === layer.id)}
									{#if roi}
										<span class="font-num text-[10px] text-primary/80 ml-2">
											{formatArea(roi.area_m2)}
										</span>
									{/if}
								{/if}
							</div>

							<!-- Opacity slider for overlays -->
							{#if layer.category !== 'base' && layer.visible}
								<div class="flex items-center space-x-2 px-2 pt-0.5">
									<span class="text-[9px] font-num text-muted-foreground">Opacity</span>
									<input
										type="range"
										min="0.1"
										max="1"
										step="0.05"
										value={layer.opacity ?? 0.7}
										oninput={(e) => mapState.setLayerOpacity(layer.id, parseFloat((e.target as HTMLInputElement).value))}
										class="h-1 flex-1 accent-primary bg-muted rounded cursor-pointer"
									/>
									<span class="text-[9px] font-num text-muted-foreground w-6 text-right">
										{Math.round((layer.opacity ?? 0.7) * 100)}%
									</span>
								</div>
							{/if}
						</div>
					{/each}
				</div>
			{/if}
		{/each}
	</div>

	{#if mapState.currentRoi}
		<div class="border-t border-border p-3 bg-background/40">
			<div class="text-[10px] font-num text-muted-foreground uppercase tracking-wider mb-1">Target ROI</div>
			<div class="flex items-center justify-between">
				<div class="truncate text-xs font-semibold text-foreground">{mapState.currentRoi.name}</div>
				<Button
					size="sm"
					variant="ghost"
					class="h-6 px-2 text-[10px] text-destructive hover:bg-destructive/10"
					onclick={() => mapState.deleteRoi(mapState.currentRoi!.id)}
				>
					Delete
				</Button>
			</div>
		</div>
	{/if}
</aside>
