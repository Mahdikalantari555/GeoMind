<script lang="ts">
	import { agentState } from '$lib/stores/agent.svelte';
	import { studioState } from '$lib/stores/studio.svelte';
	import { Button } from '$lib/components/ui/button';
	import { Badge } from '$lib/components/ui/badge';

	let inputQuery = $state('');

	function handleSend() {
		if (!inputQuery.trim() || agentState.isThinking) return;
		const text = inputQuery;
		inputQuery = '';
		agentState.sendMessage(text);
	}

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Enter' && !e.shiftKey) {
			e.preventDefault();
			handleSend();
		}
	}

	function handlePromptChip(chip: string) {
		inputQuery = chip;
		handleSend();
	}
</script>

{#if agentState.isOpen}
	<aside class="flex h-full w-96 flex-col border-l border-border bg-card/80 backdrop-blur z-20">
		<!-- Rail Header -->
		<div class="flex h-11 items-center justify-between border-b border-border px-3">
			<div class="flex items-center space-x-2">
				<div class="h-2 w-2 rounded-full bg-primary animate-pulse"></div>
				<span class="text-xs font-bold uppercase tracking-wider font-num text-foreground">Research Assistant</span>
			</div>
			<div class="flex items-center space-x-1.5">
				<Badge variant={studioState.llm.keyConfigured ? 'default' : 'secondary'} class="font-num text-[9px] uppercase">
					{studioState.llm.keyConfigured ? 'Generative' : 'Retrieval-Only'}
				</Badge>
				<Button
					size="sm"
					variant="ghost"
					class="h-6 w-6 p-0 text-muted-foreground hover:text-foreground"
					onclick={() => agentState.toggleOpen()}
					title="Collapse Agent Rail"
				>
					<svg class="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
					</svg>
				</Button>
			</div>
		</div>

		<!-- Chat Feed -->
		<div class="flex-1 overflow-y-auto p-3 space-y-3">
			{#if agentState.messages.length === 0}
				<div class="rounded-lg border border-border/50 bg-background/50 p-4 text-center space-y-2 mt-4">
					<div class="text-xs font-semibold text-foreground">Zero-Setup Research Grounding</div>
					<p class="text-[11px] text-muted-foreground leading-relaxed">
						Ask questions across loaded vector rasters, field boundaries, and telemetry reports. Grounded with citations.
					</p>
				</div>
			{/if}

			{#each agentState.messages as msg (msg.id)}
				<div class="flex flex-col space-y-1.5 {msg.role === 'user' ? 'items-end' : 'items-start'}">
					<div class="flex items-center space-x-1.5 text-[10px] font-num text-muted-foreground">
						<span>{msg.role === 'user' ? 'You' : 'GeoMind Agent'}</span>
						<span>&bull;</span>
						<span>{msg.timestamp}</span>
					</div>

					<div
						class="max-w-[90%] rounded-lg p-2.5 text-xs leading-relaxed {msg.role === 'user'
							? 'bg-primary text-primary-foreground font-medium'
							: 'border border-border/80 bg-background/70 text-foreground'}"
					>
						{msg.content}

						<!-- Citations Bridge -->
						{#if msg.citations && msg.citations.length > 0}
							<div class="mt-2.5 space-y-1.5 border-t border-border/60 pt-2">
								<div class="text-[9px] font-num uppercase tracking-wider text-muted-foreground font-bold">
									Grounding Evidence ({msg.citations.length})
								</div>
								{#each msg.citations as citation (citation.id)}
									<button
										class="w-full text-left rounded border border-border/60 bg-card/60 p-1.5 hover:border-primary/60 hover:bg-primary/5 transition-all cursor-pointer group"
										onclick={() => agentState.locateCitation(citation)}
										title="Click to locate on Map canvas"
									>
										<div class="flex items-center justify-between font-num text-[10px]">
											<span class="text-primary font-semibold truncate group-hover:underline">{citation.source}</span>
											<span class="text-[9px] text-muted-foreground">Locate &rarr;</span>
										</div>
										<p class="text-[10px] text-muted-foreground italic truncate mt-0.5">"{citation.snippet}"</p>
									</button>
								{/each}
							</div>
						{/if}
					</div>
				</div>
			{/each}

			{#if agentState.isThinking}
				<div class="flex items-center space-x-2 text-xs font-num text-muted-foreground p-2">
					<div class="h-2 w-2 rounded-full bg-primary animate-ping"></div>
					<span>Grounding sources & calculating biophysical fluxes...</span>
				</div>
			{/if}
		</div>

		<!-- Quick Prompt Chips -->
		<div class="border-t border-border/60 p-2 bg-background/40 space-y-1.5">
			<div class="flex items-center space-x-1 overflow-x-auto no-scrollbar py-0.5">
				{#each agentState.promptChips as chip (chip)}
					<button
						class="whitespace-nowrap rounded-full border border-border bg-card/80 px-2 py-0.5 text-[10px] text-muted-foreground hover:border-primary hover:text-foreground transition-colors"
						onclick={() => handlePromptChip(chip)}
					>
						{chip}
					</button>
				{/each}
			</div>

			<!-- Prompt Input Bar -->
			<div class="flex items-center space-x-1.5">
				<textarea
					bind:value={inputQuery}
					onkeydown={handleKeydown}
					rows="1"
					placeholder="Ask research query across workspace..."
					class="flex-1 resize-none rounded border border-border bg-background px-2.5 py-1.5 text-xs text-foreground placeholder:text-muted-foreground focus:ring-1 focus:ring-primary focus:outline-none"
				></textarea>
				<Button
					size="sm"
					variant="default"
					class="h-8 px-3 text-xs"
					onclick={handleSend}
					disabled={!inputQuery.trim() || agentState.isThinking}
				>
					Ask
				</Button>
			</div>
		</div>
	</aside>
{:else}
	<!-- Collapsed Rail Trigger Pill -->
	<button
		class="fixed bottom-6 right-6 z-30 flex items-center space-x-2 rounded-full border border-border/80 bg-card/90 px-3.5 py-2 text-xs font-semibold shadow-xl backdrop-blur hover:border-primary transition-all cursor-pointer"
		onclick={() => agentState.toggleOpen()}
	>
		<div class="h-2 w-2 rounded-full bg-primary animate-pulse"></div>
		<span>Research Assistant</span>
		<kbd class="rounded border border-border bg-background px-1 text-[10px] font-num text-muted-foreground">Ctrl+B</kbd>
	</button>
{/if}
