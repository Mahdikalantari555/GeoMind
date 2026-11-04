import { describe, it, expect } from 'vitest';
import { mapState, computePolygonAreaM2 } from './map.svelte';

describe('Map Store & Area Utilities', () => {
	it('calculates geodesic polygon area', () => {
		// ~1 degree box near equator
		const coords: [number, number][][] = [
			[
				[0, 0],
				[1, 0],
				[1, 1],
				[0, 1],
				[0, 0]
			]
		];
		const area = computePolygonAreaM2(coords);
		// 1 deg x 1 deg is roughly 12,300 km^2 = 1.23e10 m^2
		expect(area).toBeGreaterThan(1e10);
		expect(area).toBeLessThan(1.3e10);
	});

	it('manages ROI lifecycle and layer synchronization', () => {
		const roi = mapState.addRoi('Test Farm', {
			type: 'Polygon',
			coordinates: [
				[
					[48.0, 31.0],
					[48.1, 31.0],
					[48.1, 31.1],
					[48.0, 31.1],
					[48.0, 31.0]
				]
			]
		});

		expect(roi.name).toBe('Test Farm');
		expect(mapState.currentRoi?.id).toBe(roi.id);
		expect(mapState.layers.some((l) => l.id === roi.id)).toBe(true);

		// Toggle layer
		mapState.toggleLayer(roi.id);
		expect(mapState.layers.find((l) => l.id === roi.id)?.visible).toBe(false);

		// Delete ROI
		mapState.deleteRoi(roi.id);
		expect(mapState.rois.some((r) => r.id === roi.id)).toBe(false);
		expect(mapState.layers.some((l) => l.id === roi.id)).toBe(false);
	});
});
