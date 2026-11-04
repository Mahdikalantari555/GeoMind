<script lang="ts">
	import { studioState } from '$lib/stores/studio.svelte';
	import { Button } from '$lib/components/ui/button';
	import { Badge } from '$lib/components/ui/badge';

	function openCommand() {
		studioState.commandPaletteOpen = true;
	}
</script>

<header class="flex h-12 w-full items-center justify-between border-b border-border bg-card px-4">
	<div class="flex items-center space-x-4">
		<div class="flex items-center space-x-2">
			<div class="h-3 w-3 rounded-full bg-primary animate-pulse"></div>
			<span class="text-sm font-bold tracking-tight text-foreground uppercase tracking-widest font-num">GeoMind Studio</span>
		</div>

		<div class="h-4 w-px bg-border"></div>

		<!-- Nav Tabs -->
		<nav class="flex items-center space-x-1">
			<button
				class="rounded px-2.5 py-1 text-xs font-medium transition-colors {studioState.activeTab === 'map' ? 'bg-accent text-accent-foreground font-semibold' : 'text-muted-foreground hover:bg-accent/40'}"
				onclick={() => (studioState.activeTab = 'map')}
			>
				Map & ROI
			</button>
			<button
				class="rounded px-2.5 py-1 text-xs font-medium transition-colors {studioState.activeTab === 'acquire' ? 'bg-accent text-accent-foreground font-semibold' : 'text-muted-foreground hover:bg-accent/40'}"
				onclick={() => (studioState.activeTab = 'acquire')}
			>
				Acquire
			</button>
			<button
				class="rounded px-2.5 py-1 text-xs font-medium transition-colors {studioState.activeTab === 'health' ? 'bg-accent text-accent-foreground font-semibold' : 'text-muted-foreground hover:bg-accent/40'}"
				onclick={() => (studioState.activeTab = 'health')}
			>
				Health
			</button>
		</nav>
	</div>

	<div class="flex items-center space-x-3">
		<!-- Ctrl+K shortcut bar -->
		<Button variant="outline" size="sm" class="h-7 px-2 font-num text-xs text-muted-foreground border-border/80" onclick={openCommand}>
			<span>Search & Actions...</span>
			<kbd class="ml-2 rounded border border-border bg-background px-1 text-[10px]">⌘K</kbd>
		</Button>

		<!-- Workspace / Status indicators -->
		<div class="flex items-center space-x-2">
			<Badge variant={studioState.workspace.isOpen ? 'default' : 'secondary'} class="text-[10px] font-num">
				{studioState.workspace.isOpen ? (studioState.workspace.name ?? 'Workspace') : 'No Workspace'}
			</Badge>

			<Badge variant={studioState.llm.keyConfigured ? 'default' : 'outline'} class="text-[10px] font-num">
				{studioState.llm.keyConfigured ? studioState.llm.provider : 'Retrieval-Only'}
			</Badge>
		</div>
	</div>
</header>
