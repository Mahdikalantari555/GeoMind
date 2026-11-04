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
	layers: {
		id: string;
		name: string;
		category: 'scenes' | 'products';
		sourceType: 'geojson';
		sourceData: unknown;
		opacity: number;
	}[];
	assets: SampleAsset[];
	guidedQuestions: {
		question: string;
		answer: string;
		citations: {
			id: string;
			source: string;
			sourceId?: string;
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
	zoom: 11,
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
	layers: [
		{
			id: 'layer-eta-sample',
			name: 'Landsat 9 METRIC ETa (July 15, 2024)',
			category: 'scenes',
			sourceType: 'geojson',
			opacity: 0.65,
			sourceData: {
				type: 'FeatureCollection',
				features: [
					{
						type: 'Feature',
						properties: { name: 'ETa High Flux Zone', eta_mm_day: 8.4 },
						geometry: {
							type: 'Polygon',
							coordinates: [
								[
									[48.63, 31.31],
									[48.71, 31.31],
									[48.71, 31.37],
									[48.63, 31.37],
									[48.63, 31.31]
								]
							]
						}
					}
				]
			}
		},
		{
			id: 'layer-farms-sample',
			name: 'Sugar-cane Field Parcels',
			category: 'products',
			sourceType: 'geojson',
			opacity: 0.85,
			sourceData: {
				type: 'FeatureCollection',
				features: [
					{
						type: 'Feature',
						properties: { parcel_id: 'P-101', crop: 'Sugar-cane', status: 'Irrigated' },
						geometry: {
							type: 'Polygon',
							coordinates: [
								[
									[48.64, 31.32],
									[48.67, 31.32],
									[48.67, 31.35],
									[48.64, 31.35],
									[48.64, 31.32]
								]
							]
						}
					},
					{
						type: 'Feature',
						properties: { parcel_id: 'P-102', crop: 'Sugar-cane', status: 'Irrigated' },
						geometry: {
							type: 'Polygon',
							coordinates: [
								[
									[48.68, 31.32],
									[48.70, 31.32],
									[48.70, 31.36],
									[48.68, 31.36],
									[48.68, 31.32]
								]
							]
						}
					}
				]
			}
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
					sourceId: 'layer-eta-sample',
					snippet: 'Pixel grid raster mean value: 8.41 mm/day (24h flux sum).'
				},
				{
					id: 'cit-2',
					source: 'khuzestan_sugar_farms.geojson',
					sourceId: 'layer-farms-sample',
					snippet: 'Parcels P-101 and P-102: Active sugarcane canopy transpiration.'
				},
				{
					id: 'cit-3',
					source: 'Karun_Basin_ETa_Irrigation_Study_2024.pdf',
					page: 14,
					snippet: 'Section 4.2: Peak summer ET rates consistently ranged between 8.2 and 8.6 mm/day across irrigated Khuzestan sugarcane canopies.'
				}
			]
		}
	]
};
