import { SAMPLE_WORKSPACE, type SampleWorkspaceData } from '$lib/data/sampleWorkspace';
import { studioState } from '$lib/stores/studio.svelte';
import { mapState } from '$lib/stores/map.svelte';

class OnboardingStateStore {
	isSeeding = $state<boolean>(false);
	isSampleActive = $state<boolean>(false);
	currentStep = $state<'welcome' | 'guided_question' | 'completed'>('welcome');

	// Guided Q&A state
	activeQuestion = $state<string>(SAMPLE_WORKSPACE.guidedQuestions[0].question);
	currentAnswer = $state<string | null>(null);
	citations = $state<SampleWorkspaceData['guidedQuestions'][0]['citations']>([]);
	isAnswering = $state<boolean>(false);

	// Deferred LLM banner
	showLlmDeferredBanner = $state<boolean>(false);

	async seedSampleWorkspace(): Promise<void> {
		this.isSeeding = true;
		try {
			studioState.workspace = {
				isOpen: true,
				name: SAMPLE_WORKSPACE.name,
				path: `/workspaces/${SAMPLE_WORKSPACE.id}`
			};

			// Add sample ROI
			const sampleRoi = SAMPLE_WORKSPACE.rois[0];
			mapState.addRoi(sampleRoi.name, {
				type: 'Polygon',
				coordinates: sampleRoi.coordinates
			});

			// Add rich sample layers with geometries
			for (const l of SAMPLE_WORKSPACE.layers) {
				if (!mapState.layers.some((existing) => existing.id === l.id)) {
					mapState.layers = [
						...mapState.layers,
						{
							id: l.id,
							name: l.name,
							category: l.category,
							visible: true,
							opacity: l.opacity,
							sourceType: l.sourceType,
							sourceData: l.sourceData
						}
					];
				}
			}

			// Focus camera on the area
			mapState.cameraBounds = [
				[48.61, 31.29],
				[48.73, 31.39]
			];

			this.isSampleActive = true;
			this.currentStep = 'guided_question';
		} finally {
			this.isSeeding = false;
		}
	}

	askGuidedQuestion(): void {
		this.isAnswering = true;
		setTimeout(() => {
			const guided = SAMPLE_WORKSPACE.guidedQuestions[0];
			this.currentAnswer = guided.answer;
			this.citations = guided.citations;
			this.isAnswering = false;
			this.currentStep = 'completed';

			// Show deferred LLM setup affordance only after first answer
			if (!studioState.llm.keyConfigured) {
				this.showLlmDeferredBanner = true;
			}
		}, 600);
	}

	dismissLlmBanner(): void {
		this.showLlmDeferredBanner = false;
	}
}

export const onboardingState = new OnboardingStateStore();
