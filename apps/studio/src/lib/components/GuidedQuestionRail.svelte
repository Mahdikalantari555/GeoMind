<script lang="ts">
	import { onboardingState } from '$lib/stores/onboarding.svelte';
	import { Button } from '$lib/components/ui/button';
	import { Card, CardHeader, CardTitle, CardContent } from '$lib/components/ui/card';
	import { Badge } from '$lib/components/ui/badge';

	function handleAsk() {
		onboardingState.askGuidedQuestion();
	}
</script>

<div class="fixed bottom-6 right-6 z-40 w-96 rounded-lg border border-primary/40 bg-card/95 shadow-2xl backdrop-blur">
	<Card class="border-0 shadow-none bg-transparent">
		<CardHeader class="p-4 pb-2 flex flex-row items-center justify-between">
			<div>
				<Badge variant="outline" class="font-num text-[9px] uppercase tracking-wider text-primary border-primary/40">
					Step 2: Guided First Question
				</Badge>
				<CardTitle class="text-sm font-bold tracking-tight mt-1">Research Assistant</CardTitle>
			</div>
			<Badge variant="secondary" class="font-num text-[9px]">Retrieval-Only</Badge>
		</CardHeader>

		<CardContent class="p-4 pt-2 space-y-3">
			<div class="rounded border border-border bg-background/60 p-2.5 text-xs text-foreground font-medium">
				"{onboardingState.activeQuestion}"
			</div>

			{#if !onboardingState.currentAnswer}
				<Button
					variant="default"
					size="sm"
					class="w-full text-xs font-semibold"
					onclick={handleAsk}
					disabled={onboardingState.isAnswering}
				>
					{onboardingState.isAnswering ? 'Searching Index & Citing...' : 'Ask Question (Zero Setup)'}
				</Button>
			{:else}
				<div class="space-y-2">
					<div class="rounded border border-primary/20 bg-primary/5 p-3 text-xs leading-relaxed text-foreground">
						{onboardingState.currentAnswer}
					</div>

					<!-- Citations list -->
					<div class="space-y-1">
						<div class="text-[10px] font-num uppercase tracking-wider text-muted-foreground font-semibold">
							Grounding Citations ({onboardingState.citations.length})
						</div>
						{#each onboardingState.citations as citation (citation.id)}
							<div class="rounded border border-border bg-background/50 p-2 text-[11px] space-y-0.5">
								<div class="flex items-center justify-between text-primary font-num font-semibold text-[10px]">
									<span>{citation.source}</span>
									{#if citation.page}<span>Page {citation.page}</span>{/if}
								</div>
								<p class="text-muted-foreground text-[10px] italic">"{citation.snippet}"</p>
							</div>
						{/each}
					</div>
				</div>
			{/if}

			<!-- Deferred LLM Configuration Affordance -->
			{#if onboardingState.showLlmDeferredBanner}
				<div class="rounded border border-accent bg-accent/20 p-2.5 text-xs space-y-2">
					<div class="flex items-center justify-between">
						<span class="font-semibold text-foreground text-[11px]">Answer Grounded! Want LLM Synthesis?</span>
						<button
							class="text-muted-foreground hover:text-foreground text-xs"
							onclick={() => onboardingState.dismissLlmBanner()}
							aria-label="Dismiss"
						>
							&times;
						</button>
					</div>
					<p class="text-[10px] text-muted-foreground">
						You reached your first cited answer using local vector search. To enable autonomous reasoning and agent synthesis, configure an LLM key.
					</p>
					<div class="flex space-x-2">
						<Button size="sm" variant="default" class="h-6 text-[10px] px-2" onclick={() => alert('Set GEOMEMORY_LLM_API_KEY to activate generative agent mode.')}>
							Configure Key
						</Button>
						<Button size="sm" variant="ghost" class="h-6 text-[10px] px-2 text-muted-foreground" onclick={() => onboardingState.dismissLlmBanner()}>
							Later
						</Button>
					</div>
				</div>
			{/if}
		</CardContent>
	</Card>
</div>
