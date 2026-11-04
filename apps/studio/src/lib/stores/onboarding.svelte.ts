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
		// Seed sample into state & map
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

			// Add sample raster and vector layers
			mapState.addSceneLayer('layer-eta-sample', 'Landsat 9 METRIC ETa (July 2024)');
			mapState.layers = [
				...mapState.layers,
				{
					id: 'layer-farms-sample',
					name: 'Sugar-cane Field Parcels',
					category: 'products',
					visible: true
				}
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
