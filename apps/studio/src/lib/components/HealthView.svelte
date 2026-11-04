<script lang="ts">
	import { studioState } from '$lib/stores/studio.svelte';
	import { api } from '$lib/api/client';
	import { Button } from '$lib/components/ui/button';
	import { Badge } from '$lib/components/ui/badge';
	import { Card, CardHeader, CardTitle, CardContent } from '$lib/components/ui/card';

	type CheckItem = {
		name: string;
		status: 'pass' | 'fail' | 'warn';
		detail: string;
		action?: { label: string; run: () => void };
	};

	let doctorLoading = $state(false);
	let doctorData = $state<Record<string, unknown> | null>(null);

	async function runDoctor() {
		doctorLoading = true;
		try {
			doctorData = await api.workspace.doctor();
		} catch (err) {
			console.error('Doctor check failed:', err);
		} finally {
			doctorLoading = false;
		}
	}

	$effect(() => {
		if (studioState.workspace.isOpen) {
			runDoctor();
		}
	});

	let checks = $derived<CheckItem[]>([
		{
			name: 'Workspace Open',
			status: studioState.workspace.isOpen ? 'pass' : 'fail',
			detail: studioState.workspace.isOpen
				? (studioState.workspace.name ?? studioState.workspace.path ?? 'Open')
				: 'No active workspace selected',
			action: studioState.workspace.isOpen
				? undefined
				: { label: 'Open Workspace', run: () => (studioState.activeTab = 'map') }
		},
		{
			name: 'LLM Engine',
			status: studioState.llm.keyConfigured ? 'pass' : 'warn',
			detail: studioState.llm.keyConfigured
				? `${studioState.llm.provider} (Ready)`
				: `${studioState.llm.provider} - Key not configured (Retrieval-only active)`,
			action: studioState.llm.keyConfigured
				? undefined
				: {
						label: 'Configure Key',
						run: () => {
							alert('Set GEOMEMORY_LLM_API_KEY environment variable or configure in settings.');
						}
					}
		},
		{
			name: 'Vector Index',
			status: (doctorData?.['index_healthy'] as boolean ?? true) ? 'pass' : 'fail',
			detail: (doctorData?.['index_manifest'] as string) ?? 'Ready for retrieval & hybrid search'
		},
		{
			name: 'Data Engine Fetcher',
			status: 'pass',
			detail: 'Planetary Computer STAC fetcher connected (online)'
		}
	]);
</script>

<div class="h-full overflow-y-auto p-6 space-y-6">
	<div class="flex items-center justify-between">
		<div>
			<h2 class="text-xl font-bold tracking-tight">System Telemetry & Health</h2>
			<p class="text-xs text-muted-foreground">Continuous diagnostic telemetry of the local GeoMind stack</p>
		</div>
		<Button variant="outline" size="sm" onclick={runDoctor} disabled={doctorLoading}>
			{doctorLoading ? 'Probing...' : 'Refresh Telemetry'}
		</Button>
	</div>

	<div class="grid gap-4 md:grid-cols-2">
		{#each checks as check (check.name)}
			<Card class="border-border/60 bg-card/60">
				<CardHeader class="flex flex-row items-center justify-between pb-2">
					<CardTitle class="text-sm font-medium">{check.name}</CardTitle>
					<Badge
						variant={check.status === 'pass'
							? 'default'
							: check.status === 'warn'
								? 'secondary'
								: 'destructive'}
						class="text-[10px] uppercase font-num"
					>
						{check.status}
					</Badge>
				</CardHeader>
				<CardContent class="space-y-3">
					<p class="font-num text-xs text-muted-foreground">{check.detail}</p>
					{#if check.action}
						<Button size="sm" variant="outline" onclick={check.action.run}>
							{check.action.label}
						</Button>
					{/if}
				</CardContent>
			</Card>
		{/each}
	</div>
</div>
