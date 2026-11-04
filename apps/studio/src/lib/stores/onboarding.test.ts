import { describe, it, expect } from 'vitest';
import { onboardingState } from './onboarding.svelte';
import { studioState } from './studio.svelte';
import { mapState } from './map.svelte';

describe('Onboarding State Store', () => {
	it('seeds sample workspace with ROIs, layers, and transition state', async () => {
		expect(onboardingState.isSampleActive).toBe(false);
		expect(onboardingState.currentStep).toBe('welcome');

		await onboardingState.seedSampleWorkspace();

		expect(onboardingState.isSampleActive).toBe(true);
		expect(onboardingState.currentStep).toBe('guided_question');
		expect(studioState.workspace.isOpen).toBe(true);
		expect(mapState.rois.length).toBeGreaterThan(0);
		expect(mapState.layers.some((l) => l.name.includes('ETa'))).toBe(true);
	});

	it('handles guided question and defers LLM configuration after answer', async () => {
		onboardingState.askGuidedQuestion();
		expect(onboardingState.isAnswering).toBe(true);

		// Wait for mock answer delay
		await new Promise((resolve) => setTimeout(resolve, 700));

		expect(onboardingState.isAnswering).toBe(false);
		expect(onboardingState.currentAnswer).toBeTruthy();
		expect(onboardingState.citations.length).toBeGreaterThanOrEqual(2);
		expect(onboardingState.currentStep).toBe('completed');
		expect(onboardingState.showLlmDeferredBanner).toBe(true);

		onboardingState.dismissLlmBanner();
		expect(onboardingState.showLlmDeferredBanner).toBe(false);
	});
});
