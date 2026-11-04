<script lang="ts">
	import { Button } from '$lib/components/ui/button';
	import type { Snippet } from 'svelte';

	interface Props {
		title: string;
		description: string;
		actionLabel?: string;
		onaction?: () => void;
		secondaryLabel?: string;
		onsecondary?: () => void;
		icon?: Snippet;
	}

	let {
		title,
		description,
		actionLabel,
		onaction,
		secondaryLabel,
		onsecondary,
		icon
	}: Props = $props();
</script>

<div class="flex flex-col items-center justify-center rounded-lg border border-border/60 bg-card/40 p-8 text-center">
	{#if icon}
		<div class="mb-3 text-muted-foreground">
			{@render icon()}
		</div>
	{/if}
	<h3 class="text-sm font-medium tracking-tight text-foreground">{title}</h3>
	<p class="mt-1 max-w-sm text-xs text-muted-foreground">{description}</p>
	{#if actionLabel || secondaryLabel}
		<div class="mt-4 flex items-center space-x-2">
			{#if actionLabel && onaction}
				<Button size="sm" variant="default" onclick={onaction}>
					{actionLabel}
				</Button>
			{/if}
			{#if secondaryLabel && onsecondary}
				<Button size="sm" variant="outline" onclick={onsecondary}>
					{secondaryLabel}
				</Button>
			{/if}
		</div>
	{/if}
</div>
