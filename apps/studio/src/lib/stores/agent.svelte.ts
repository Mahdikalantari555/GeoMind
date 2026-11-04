import { mapState } from '$lib/stores/map.svelte';
import { studioState } from '$lib/stores/studio.svelte';
import { SAMPLE_WORKSPACE } from '$lib/data/sampleWorkspace';

export interface ChatMessage {
	id: string;
	role: 'user' | 'assistant';
	content: string;
	timestamp: string;
	citations?: {
		id: string;
		source: string;
		sourceId?: string;
		page?: number;
		snippet: string;
	}[];
	metrics?: {
		latencyMs: number;
		mode: 'retrieval' | 'generative';
	};
}

class AgentStateStore {
	isOpen = $state<boolean>(true);
	isThinking = $state<boolean>(false);
	messages = $state<ChatMessage[]>([]);

	// Predefined quick prompt chips
	promptChips = [
		'What is the peak daily ETa in Sector A?',
		'Summarize sugar-cane parcels at risk',
		'Cite findings from Karun irrigation study'
	];

	toggleOpen() {
		this.isOpen = !this.isOpen;
	}

	async sendMessage(query: string) {
		if (!query.trim()) return;

		const userMsg: ChatMessage = {
			id: `msg-${Date.now()}-user`,
			role: 'user',
			content: query,
			timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
		};

		this.messages = [...this.messages, userMsg];
		this.isThinking = true;

		// Simulate research retrieval loop
		setTimeout(() => {
			this.isThinking = false;
			const sampleQ = SAMPLE_WORKSPACE.guidedQuestions[0];
			const isMatch = query.toLowerCase().includes('eta') || query.toLowerCase().includes('sector a');

			const assistantMsg: ChatMessage = {
				id: `msg-${Date.now()}-assistant`,
				role: 'assistant',
				content: isMatch
					? sampleQ.answer
					: `Retrieved relevant spatial documents and telemetry for "${query}". Surface canopy indices indicate nominal transpiration across Karun Sector A parcels with active irrigation schedules.`,
				timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
				citations: sampleQ.citations,
				metrics: {
					latencyMs: 380,
					mode: studioState.llm.keyConfigured ? 'generative' : 'retrieval'
				}
			};

			this.messages = [...this.messages, assistantMsg];
		}, 600);
	}

	locateCitation(citation: NonNullable<ChatMessage['citations']>[number]) {
		if (citation.sourceId) {
			const layer = mapState.layers.find((l) => l.id === citation.sourceId);
			if (layer) {
				// Ensure layer is visible
				if (!layer.visible) {
					mapState.toggleLayer(layer.id);
				}
				// Trigger camera fit
				mapState.cameraBounds = [
					[48.62, 31.30],
					[48.72, 31.38]
				];
			}
		}
	}
}

export const agentState = new AgentStateStore();
