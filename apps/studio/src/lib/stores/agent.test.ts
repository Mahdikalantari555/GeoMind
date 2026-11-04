import { describe, it, expect } from 'vitest';
import { agentState } from './agent.svelte';
import { mapState } from './map.svelte';

describe('Agent Rail Store & Citation Bridge', () => {
	it('sends research question and receives cited answer', async () => {
		expect(agentState.messages.length).toBe(0);

		await agentState.sendMessage('What is the peak daily ETa in Sector A?');
		expect(agentState.isThinking).toBe(true);
		expect(agentState.messages[0].role).toBe('user');

		// Wait for simulation delay
		await new Promise((resolve) => setTimeout(resolve, 700));

		expect(agentState.isThinking).toBe(false);
		expect(agentState.messages.length).toBe(2);
		expect(agentState.messages[1].role).toBe('assistant');
		expect(agentState.messages[1].citations?.length).toBeGreaterThan(0);
	});

	it('locates cited layer and triggers camera fit on citation click', () => {
		mapState.addSceneLayer('layer-eta-sample', 'ETa Test Layer');
		expect(mapState.layers.some((l) => l.id === 'layer-eta-sample')).toBe(true);

		agentState.locateCitation({
			id: 'cit-test',
			source: 'ETa Raster',
			sourceId: 'layer-eta-sample',
			snippet: 'High flux'
		});

		expect(mapState.cameraBounds).toBeTruthy();
	});
});
