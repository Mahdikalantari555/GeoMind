<script lang="ts">
	import '../app.css';
	import { onMount } from 'svelte';
	import favicon from '$lib/assets/favicon.svg';
	import type { LayoutProps } from './$types';
	import { studioState } from '$lib/stores/studio.svelte';
	import { onboardingState } from '$lib/stores/onboarding.svelte';
	import TopBar from '$lib/components/TopBar.svelte';
	import CommandPalette from '$lib/components/CommandPalette.svelte';
	import NoDeadEndGateway from '$lib/components/NoDeadEndGateway.svelte';
	import OnboardingModal from '$lib/components/OnboardingModal.svelte';
	import GuidedQuestionRail from '$lib/components/GuidedQuestionRail.svelte';

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

			<!-- First-launch onboarding modal -->
			{#if !studioState.workspace.isOpen && onboardingState.currentStep === 'welcome'}
				<OnboardingModal />
			{/if}

			<!-- Guided Question research rail -->
			{#if onboardingState.isSampleActive}
				<GuidedQuestionRail />
			{/if}
		</main>
		<CommandPalette />
	</div>
{/if}
