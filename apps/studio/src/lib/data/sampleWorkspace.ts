export interface SampleAsset {
	name: string;
	type: 'raster' | 'vector' | 'document';
	path: string;
	size_kb: number;
}

export interface SampleWorkspaceData {
	id: string;
	name: string;
	description: string;
	region: string;
	center: [number, number];
	zoom: number;
	rois: {
		name: string;
		coordinates: [number, number][][];
	}[];
	assets: SampleAsset[];
	guidedQuestions: {
		question: string;
		answer: string;
		citations: {
			id: string;
			source: string;
			page?: number;
			snippet: string;
		}[];
	}[];
}

export const SAMPLE_WORKSPACE: SampleWorkspaceData = {
	id: 'sample-khuzestan',
	name: 'Khuzestan Ag & Water Demo',
	description: 'Pre-indexed remote sensing research workspace with Landsat 9 ETa raster, sugar-cane fields GeoJSON, and irrigation reports.',
	region: 'Khuzestan, Iran',
	center: [48.68, 31.32],
	zoom: 10,
	rois: [
		{
			name: 'Karun Canal Irrigated Sector A',
			coordinates: [
				[
					[48.62, 31.30],
					[48.72, 31.30],
					[48.72, 31.38],
					[48.62, 31.38],
					[48.62, 31.30]
				]
			]
		}
	],
	assets: [
		{
			name: 'LC09_L2SP_166038_20240715_ETa.tif',
			type: 'raster',
			path: 'rasters/LC09_L2SP_166038_20240715_ETa.tif',
			size_kb: 14200
		},
		{
			name: 'khuzestan_sugar_farms.geojson',
			type: 'vector',
			path: 'vectors/khuzestan_sugar_farms.geojson',
			size_kb: 450
		},
		{
			name: 'Karun_Basin_ETa_Irrigation_Study_2024.pdf',
			type: 'document',
			path: 'docs/Karun_Basin_ETa_Irrigation_Study_2024.pdf',
			size_kb: 2800
		}
	],
	guidedQuestions: [
		{
			question: 'What is the peak daily evapotranspiration (ETa) observed across Sector A in July 2024?',
			answer: 'According to the Landsat 9 METRIC energy balance model and regional hydrologic records, peak daily evapotranspiration reached 8.4 mm/day on July 15, 2024, in the center-pivot sugar-cane parcels of Karun Canal Sector A.',
			citations: [
				{
					id: 'cit-1',
					source: 'LC09_L2SP_166038_20240715_ETa.tif',
					snippet: 'Pixel grid raster mean value: 8.41 mm/day (24h flux sum).'
				},
				{
					id: 'cit-2',
					source: 'Karun_Basin_ETa_Irrigation_Study_2024.pdf',
					page: 14,
					snippet: 'Section 4.2: Peak summer ET rates consistently ranged between 8.2 and 8.6 mm/day across irrigated Khuzestan sugarcane canopies.'
				}
			]
		}
	]
};
