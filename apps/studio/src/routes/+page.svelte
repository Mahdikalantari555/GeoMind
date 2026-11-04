<script lang="ts">
	import { studioState } from '$lib/stores/studio.svelte';
	import { agentState } from '$lib/stores/agent.svelte';
	import MapView from '$lib/components/MapView.svelte';
	import AcquireView from '$lib/components/AcquireView.svelte';
	import HealthView from '$lib/components/HealthView.svelte';
	import AgentRail from '$lib/components/AgentRail.svelte';

	function handleKeydown(e: KeyboardEvent) {
		if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'b') {
			e.preventDefault();
			agentState.toggleOpen();
		}
	}
</script>

<svelte:window onkeydown={handleKeydown} />

<div class="flex h-full w-full overflow-hidden">
	<!-- Main Center Stage -->
	<div class="flex-1 h-full overflow-hidden relative">
		{#if studioState.activeTab === 'map'}
			<MapView />
		{:else if studioState.activeTab === 'acquire'}
			<AcquireView />
		{:else if studioState.activeTab === 'health'}
			<HealthView />
		{/if}
	</div>

	<!-- Docked Right Agent Rail -->
	<AgentRail />
</div>
