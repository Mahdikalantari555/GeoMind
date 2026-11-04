<script lang="ts">
	import { onMount } from 'svelte';
	import * as maplibregl from 'maplibre-gl';
	import type { MapMouseEvent } from 'maplibre-gl';
	import 'maplibre-gl/dist/maplibre-gl.css';
	import maplibreWorkerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?url';
	import { mapState, type GeoJSONGeometry } from '$lib/stores/map.svelte';
	import { Button } from '$lib/components/ui/button';
	import LayerTree from '$lib/components/LayerTree.svelte';

	// Configure MapLibre Web Worker for Vite/SvelteKit
	maplibregl.config.WORKER_URL = maplibreWorkerUrl;

	let mapContainer: HTMLDivElement;
	let map: maplibregl.Map | null = null;
	let isMapReady = $state(false);
	let isDrawing = $state(false);
	let drawnPoints = $state<[number, number][]>([]);

	// Dark-first offline fallback style definition
	const offlineStyle: maplibregl.StyleSpecification = {
		version: 8,
		sources: {
			'carto-dark': {
				type: 'raster',
				tiles: [
					'https://a.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png',
					'https://b.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png',
					'https://c.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png'
				],
				tileSize: 256,
				attribution: '&copy; CARTO'
			}
		},
		layers: [
			{
				id: 'background',
				type: 'background',
				paint: {
					'background-color': '#0b0f19'
				}
			},
			{
				id: 'carto-layer',
				type: 'raster',
				source: 'carto-dark',
				minzoom: 0,
				maxzoom: 19,
				paint: {
					'raster-opacity': 0.75
				}
			}
		]
	};

	onMount(() => {
		map = new maplibregl.Map({
			container: mapContainer,
			style: offlineStyle,
			center: [48.68, 31.32],
			zoom: 10
		});

		(window as unknown as { __map: maplibregl.Map }).__map = map;

		map.addControl(new maplibregl.NavigationControl(), 'top-right');

		map.on('click', (e: MapMouseEvent) => {
			if (!isDrawing) return;
			drawnPoints = [...drawnPoints, [e.lngLat.lng, e.lngLat.lat]];
			updateDrawPreview();
		});

		map.on('style.load', () => {
			isMapReady = true;
			initDrawLayers();
			syncAllLayers();
			if (mapState.cameraBounds) {
				map?.fitBounds(mapState.cameraBounds, { padding: 60, maxZoom: 14 });
			}
		});

		return () => {
			map?.remove();
		};
	});

	function initDrawLayers() {
		if (!map || !isMapReady) return;
		if (map.getSource('draw-preview-source')) return;

		map.addSource('draw-preview-source', {
			type: 'geojson',
			data: { type: 'FeatureCollection', features: [] }
		});

		// In-progress polygon fill
		map.addLayer({
			id: 'draw-preview-fill',
			type: 'fill',
			source: 'draw-preview-source',
			filter: ['==', '$type', 'Polygon'],
			paint: {
				'fill-color': '#2dd4bf',
				'fill-opacity': 0.25
			}
		});

		// In-progress lines
		map.addLayer({
			id: 'draw-preview-lines',
			type: 'line',
			source: 'draw-preview-source',
			filter: ['in', '$type', 'LineString', 'Polygon'],
			paint: {
				'line-color': '#2dd4bf',
				'line-width': 2.5,
				'line-dasharray': [2, 1]
			}
		});

		// In-progress point vertices
		map.addLayer({
			id: 'draw-preview-points',
			type: 'circle',
			source: 'draw-preview-source',
			filter: ['==', '$type', 'Point'],
			paint: {
				'circle-radius': 6,
				'circle-color': '#2dd4bf',
				'circle-stroke-color': '#ffffff',
				'circle-stroke-width': 2
			}
		});
	}

	function updateDrawPreview() {
		if (!map || !isMapReady) return;
		initDrawLayers();

		const source = map.getSource('draw-preview-source') as maplibregl.GeoJSONSource | undefined;
		if (!source) return;

		type DrawFeature =
			| { type: 'Feature'; geometry: { type: 'Point'; coordinates: [number, number] }; properties: { index: number } }
			| { type: 'Feature'; geometry: { type: 'LineString'; coordinates: [number, number][] }; properties: Record<string, never> }
			| { type: 'Feature'; geometry: { type: 'Polygon'; coordinates: [number, number][][] }; properties: Record<string, never> };

		const features: DrawFeature[] = [];

		// Add point features for every vertex
		for (let i = 0; i < drawnPoints.length; i++) {
			features.push({
				type: 'Feature',
				geometry: {
					type: 'Point',
					coordinates: drawnPoints[i]
				},
				properties: { index: i }
			});
		}

		// Line connecting vertices
		if (drawnPoints.length > 1) {
			features.push({
				type: 'Feature',
				geometry: {
					type: 'LineString',
					coordinates: drawnPoints
				},
				properties: {}
			});
		}

		// Polygon preview if 3 or more points
		if (drawnPoints.length >= 3) {
			features.push({
				type: 'Feature',
				geometry: {
					type: 'Polygon',
					coordinates: [[...drawnPoints, drawnPoints[0]]]
				},
				properties: {}
			});
		}

		source.setData({
			type: 'FeatureCollection',
			features: features as unknown as Array<Record<string, unknown>>
		} as maplibregl.GeoJSONSourceSpecification['data']);
	}

	function startDrawing() {
		isDrawing = true;
		drawnPoints = [];
		if (map) map.getCanvas().style.cursor = 'crosshair';
		updateDrawPreview();
	}

	function completeDrawing() {
		if (drawnPoints.length < 3) {
			alert('Polygon requires at least 3 points.');
			return;
		}
		const ring = [...drawnPoints, drawnPoints[0]];
		const geom: GeoJSONGeometry = {
			type: 'Polygon',
			coordinates: [ring]
		};

		const name = prompt('Name this Region of Interest:', `ROI-${mapState.rois.length + 1}`) || `ROI-${mapState.rois.length + 1}`;
		mapState.addRoi(name, geom);

		isDrawing = false;
		drawnPoints = [];
		if (map) map.getCanvas().style.cursor = '';
		updateDrawPreview();
		syncAllLayers();
	}

	function cancelDrawing() {
		isDrawing = false;
		drawnPoints = [];
		if (map) map.getCanvas().style.cursor = '';
		updateDrawPreview();
	}

	function syncAllLayers() {
		if (!map || !isMapReady) return;

		for (const layer of mapState.layers) {
			if (layer.category === 'base') continue;

			const sourceId = `src-${layer.id}`;
			const fillLayerId = `layer-${layer.id}-fill`;
			const lineLayerId = `layer-${layer.id}-line`;

			if (layer.sourceType === 'geojson' && layer.sourceData) {
				const existingSource = map.getSource(sourceId) as maplibregl.GeoJSONSource | undefined;
				if (!existingSource) {
					map.addSource(sourceId, {
						type: 'geojson',
						data: layer.sourceData as maplibregl.GeoJSONSourceSpecification['data']
					});

					const color =
						layer.category === 'rois'
							? '#2dd4bf'
							: layer.category === 'scenes'
								? '#f59e0b'
								: '#38bdf8';

					map.addLayer({
						id: fillLayerId,
						type: 'fill',
						source: sourceId,
						paint: {
							'fill-color': color,
							'fill-opacity': layer.opacity ?? 0.4
						}
					});

					map.addLayer({
						id: lineLayerId,
						type: 'line',
						source: sourceId,
						paint: {
							'line-color': color,
							'line-width': layer.category === 'rois' ? 2.5 : 2
						}
					});
				} else {
					existingSource.setData(layer.sourceData as maplibregl.GeoJSONSourceSpecification['data']);
				}

				// Update visibility & opacity
				const visibility = layer.visible ? 'visible' : 'none';
				if (map.getLayer(fillLayerId)) {
					map.setLayoutProperty(fillLayerId, 'visibility', visibility);
					map.setPaintProperty(fillLayerId, 'fill-opacity', (layer.opacity ?? 0.4));
				}
				if (map.getLayer(lineLayerId)) {
					map.setLayoutProperty(lineLayerId, 'visibility', visibility);
				}
			}
		}

		// Clean up removed layers
		const activeIds = new Set(mapState.layers.map((l) => l.id));
		const currentStyle = map.getStyle();
		if (currentStyle && currentStyle.layers) {
			for (const l of currentStyle.layers) {
				if (l.id.startsWith('layer-') && (l.id.endsWith('-fill') || l.id.endsWith('-line'))) {
					const layerId = l.id.replace(/^layer-/, '').replace(/-(fill|line)$/, '');
					if (!activeIds.has(layerId)) {
						if (map.getLayer(l.id)) map.removeLayer(l.id);
					}
				}
			}
		}
	}

	$effect(() => {
		// Track layers mutation & properties
		const layers = mapState.layers;
		const _deps = layers.map((l) => `${l.id}:${l.visible}:${l.opacity}`);
		if (map && isMapReady && _deps.length > 0) {
			syncAllLayers();
		}
	});

	$effect(() => {
		if (mapState.cameraBounds && map && isMapReady) {
			map.fitBounds(mapState.cameraBounds, { padding: 60, maxZoom: 14 });
		}
	});
</script>

<div class="relative flex h-full w-full overflow-hidden">
	<!-- Sidebar Layer Tree -->
	<LayerTree />

	<!-- Map Viewport -->
	<div class="relative flex-1">
		<div bind:this={mapContainer} class="h-full w-full bg-background"></div>

		<!-- ROI Draw Toolbar Overlay -->
		<div class="absolute top-4 left-4 z-10 flex items-center space-x-2 rounded-lg border border-border/80 bg-card/90 p-1.5 shadow-lg backdrop-blur">
			{#if !isDrawing}
				<Button size="sm" variant="default" class="h-7 text-xs font-medium" onclick={startDrawing}>
					<svg class="mr-1.5 h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
					</svg>
					Draw Polygon ROI
				</Button>
			{:else}
				<span class="px-2 font-num text-xs text-primary font-medium">Click map to add vertices ({drawnPoints.length})</span>
				<Button size="sm" variant="default" class="h-7 text-xs" onclick={completeDrawing} disabled={drawnPoints.length < 3}>
					Complete ({drawnPoints.length} pts)
				</Button>
				<Button size="sm" variant="outline" class="h-7 text-xs" onclick={cancelDrawing}>
					Cancel
				</Button>
			{/if}
		</div>
	</div>
</div>
