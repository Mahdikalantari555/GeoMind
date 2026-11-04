<script lang="ts">
	import { studioState } from '$lib/stores/studio.svelte';
	import { Dialog, DialogContent, DialogHeader, DialogTitle } from '$lib/components/ui/dialog';
	import { Input } from '$lib/components/ui/input';

	let query = $state('');

	const items = [
		{ label: 'Map View & Layers', action: () => { studioState.activeTab = 'map'; studioState.commandPaletteOpen = false; } },
		{ label: 'Acquire Satellite Scenes', action: () => { studioState.activeTab = 'acquire'; studioState.commandPaletteOpen = false; } },
		{ label: 'System Health & Telemetry', action: () => { studioState.activeTab = 'health'; studioState.commandPaletteOpen = false; } }
	];

	let filtered = $derived(
		items.filter(i => i.label.toLowerCase().includes(query.toLowerCase()))
	);

	function onKeydown(e: KeyboardEvent) {
		if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
			e.preventDefault();
			studioState.commandPaletteOpen = !studioState.commandPaletteOpen;
		}
	}
</script>

<svelte:window onkeydown={onKeydown} />

<Dialog bind:open={studioState.commandPaletteOpen}>
	<DialogContent class="max-w-lg border-border bg-card p-0 shadow-2xl">
		<DialogHeader class="p-4 pb-2">
			<DialogTitle class="text-xs uppercase tracking-wider text-muted-foreground font-num">Command Palette</DialogTitle>
		</DialogHeader>
		<div class="px-4 pb-2">
			<Input
				bind:value={query}
				placeholder="Type a command or navigate... (Ctrl+K)"
				class="h-9 font-num text-sm bg-background border-border"
			/>
		</div>
		<div class="max-h-60 overflow-y-auto px-2 pb-3 pt-1 space-y-1">
			{#each filtered as item (item.label)}
				<button
					class="w-full text-left px-3 py-2 rounded text-xs hover:bg-accent/50 hover:text-accent-foreground font-medium transition-colors flex items-center justify-between"
					onclick={item.action}
				>
					<span>{item.label}</span>
					<span class="text-[10px] text-muted-foreground font-num">Navigate</span>
				</button>
			{/each}
			{#if filtered.length === 0}
				<p class="p-3 text-center text-xs text-muted-foreground">No matching commands.</p>
			{/if}
		</div>
	</DialogContent>
</Dialog>
