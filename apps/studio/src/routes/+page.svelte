<script lang="ts">
	import { studioState } from '$lib/stores/studio.svelte';
	import MapView from '$lib/components/MapView.svelte';
	import AcquireView from '$lib/components/AcquireView.svelte';
	import HealthView from '$lib/components/HealthView.svelte';
</script>

{#if studioState.activeTab === 'map'}
	<MapView />
{:else if studioState.activeTab === 'acquire'}
	<AcquireView />
{:else if studioState.activeTab === 'health'}
	<HealthView />
{/if}
