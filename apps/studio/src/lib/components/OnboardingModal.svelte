<script lang="ts">
	import { onboardingState } from '$lib/stores/onboarding.svelte';
	import { Button } from '$lib/components/ui/button';
	import { Card, CardHeader, CardTitle, CardContent } from '$lib/components/ui/card';
	import { Badge } from '$lib/components/ui/badge';

	let realWorkspacePath = $state('');
	let showRealWorkspaceInput = $state(false);

	async function handleSeedSample() {
		await onboardingState.seedSampleWorkspace();
	}
</script>

<div class="fixed inset-0 z-50 flex items-center justify-center bg-background/80 backdrop-blur-sm p-4">
	<Card class="w-full max-w-lg border-border/80 bg-card/95 shadow-2xl">
		<CardHeader class="pb-3 text-center">
			<div class="mx-auto mb-2 flex h-10 w-10 items-center justify-center rounded-full bg-primary/10 text-primary">
				<svg class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
					<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7" />
				</svg>
			</div>
			<CardTitle class="text-xl font-bold tracking-tight">Welcome to GeoMind Studio</CardTitle>
			<p class="text-xs text-muted-foreground mt-1">
				Data-sovereign remote sensing research platform. Reach your first cited answer in under two minutes.
			</p>
		</CardHeader>

		<CardContent class="space-y-4 pt-2">
			<!-- Primary Onboarding Path: One-click Sample Workspace -->
			<div class="rounded-lg border border-primary/40 bg-primary/5 p-4 space-y-2">
				<div class="flex items-center justify-between">
					<span class="text-xs font-semibold text-primary font-num uppercase tracking-wide">Recommended for First-Time Users</span>
					<Badge variant="default" class="text-[9px] font-num">0 Keys Required</Badge>
				</div>
				<h4 class="text-sm font-semibold text-foreground">Explore Pre-Seeded Khuzestan Ag Demo</h4>
				<p class="text-xs text-muted-foreground">
					Instant access to pre-indexed Landsat 9 ETa thermal rasters, farm parcels, and hydrologic reports.
				</p>
				<Button
					variant="default"
					class="w-full text-xs font-semibold mt-2"
					onclick={handleSeedSample}
					disabled={onboardingState.isSeeding}
				>
					{onboardingState.isSeeding ? 'Seeding Demo Assets...' : 'Try Sample Workspace'}
				</Button>
			</div>

			<!-- Secondary Path: Real Workspace -->
			<div class="border-t border-border/60 pt-3 text-center">
				{#if !showRealWorkspaceInput}
					<Button
						variant="ghost"
						size="sm"
						class="text-xs text-muted-foreground hover:text-foreground"
						onclick={() => (showRealWorkspaceInput = true)}
					>
						Or open / create an existing workspace folder &rarr;
					</Button>
				{:else}
					<div class="space-y-2 text-left">
						<label for="ws-path" class="text-xs font-medium text-muted-foreground">Workspace Directory Path</label>
						<div class="flex space-x-2">
							<input
								id="ws-path"
								type="text"
								bind:value={realWorkspacePath}
								placeholder="/path/to/research/workspace"
								class="flex-1 rounded border border-border bg-background px-3 py-1.5 text-xs font-num focus:ring-1 focus:ring-primary"
							/>
							<Button size="sm" variant="outline" class="text-xs" disabled={!realWorkspacePath}>
								Open
							</Button>
						</div>
					</div>
				{/if}
			</div>
		</CardContent>
	</Card>
</div>
