<script lang="ts">
	import '../app.css';
	import { onMount } from 'svelte';
	import favicon from '$lib/assets/favicon.svg';
	import type { LayoutProps } from './$types';
	import { studioState } from '$lib/stores/studio.svelte';
	import TopBar from '$lib/components/TopBar.svelte';
	import CommandPalette from '$lib/components/CommandPalette.svelte';
	import NoDeadEndGateway from '$lib/components/NoDeadEndGateway.svelte';

	let { children }: LayoutProps = $props();

	onMount(() => {
		studioState.checkHealth();
	});
</script>

<svelte:head>
	<link rel="icon" href={favicon} />
	<title>GeoMind Studio</title>
</svelte:head>

{#if !studioState.connected && !studioState.isConnecting}
	<NoDeadEndGateway />
{:else}
	<div class="flex h-screen w-screen flex-col overflow-hidden bg-background text-foreground antialiased select-none">
		<TopBar />
		<main class="flex-1 overflow-hidden relative">
			{@render children()}
		</main>
		<CommandPalette />
	</div>
{/if}
