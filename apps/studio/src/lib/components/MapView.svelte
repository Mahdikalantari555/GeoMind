<script lang="ts">
	import { onMount } from 'svelte';
	import * as maplibregl from 'maplibre-gl';
	import type { MapMouseEvent } from 'maplibre-gl';
	import 'maplibre-gl/dist/maplibre-gl.css';
	import { mapState, type GeoJSONGeometry } from '$lib/stores/map.svelte';
	import { Button } from '$lib/components/ui/button';
	import LayerTree from '$lib/components/LayerTree.svelte';

	let mapContainer: HTMLDivElement;
	let map: maplibregl.Map | null = null;
	let isDrawing = $state(false);
	let drawnPoints = $state<[number, number][]>([]);

	// Dark-first offline fallback style definition
	const offlineStyle: maplibregl.StyleSpecification = {
		version: 8,
		sources: {
			'osm-tiles': {
				type: 'raster',
				tiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'],
				tileSize: 256,
				attribution: '&copy; OpenStreetMap Contributors'
			}
		},
		layers: [
			{
				id: 'osm-layer',
				type: 'raster',
				source: 'osm-tiles',
				minzoom: 0,
				maxzoom: 19,
				paint: {
					'raster-opacity': 0.7,
					'raster-saturation': -0.8,
					'raster-contrast': 0.2
				}
			}
		]
	};

	onMount(() => {
		map = new maplibregl.Map({
			container: mapContainer,
			style: offlineStyle,
			center: [48.68, 31.32], // Khuzestan agricultural region default
			zoom: 9
		});

		map.addControl(new maplibregl.NavigationControl(), 'top-right');

		map.on('click', (e: MapMouseEvent) => {
			if (!isDrawing) return;
			drawnPoints = [...drawnPoints, [e.lngLat.lng, e.lngLat.lat]];
			updateDrawPreview();
		});

		map.on('load', () => {
			// Add ROI source and layer
			map?.addSource('rois-source', {
				type: 'geojson',
				data: {
					type: 'FeatureCollection',
					features: []
				}
			});

			map?.addLayer({
				id: 'rois-fill',
				type: 'fill',
				source: 'rois-source',
				paint: {
					'fill-color': '#2dd4bf',
					'fill-opacity': 0.2
				}
			});

			map?.addLayer({
				id: 'rois-line',
				type: 'line',
				source: 'rois-source',
				paint: {
					'line-color': '#2dd4bf',
					'line-width': 2
				}
			});

			syncRoisToMap();
		});

		return () => {
			map?.remove();
		};
	});

	function updateDrawPreview() {
		if (!map || drawnPoints.length === 0) return;
		// Update preview layer if needed
	}

	function startDrawing() {
		isDrawing = true;
		drawnPoints = [];
	}

	function completeDrawing() {
		if (drawnPoints.length < 3) {
			alert('Polygon requires at least 3 points.');
			return;
		}
		// Close polygon ring
		const ring = [...drawnPoints, drawnPoints[0]];
		const geom: GeoJSONGeometry = {
			type: 'Polygon',
			coordinates: [ring]
		};

		const name = prompt('Name this Region of Interest:', `ROI-${mapState.rois.length + 1}`) || `ROI-${mapState.rois.length + 1}`;
		mapState.addRoi(name, geom);

		isDrawing = false;
		drawnPoints = [];
		syncRoisToMap();
	}

	function cancelDrawing() {
		isDrawing = false;
		drawnPoints = [];
	}

	function syncRoisToMap() {
		if (!map || !map.getSource('rois-source')) return;
		const features = mapState.rois.map((roi) => ({
			type: 'Feature' as const,
			geometry: roi.geometry,
			properties: {
				id: roi.id,
				name: roi.name
			}
		}));

		(map.getSource('rois-source') as maplibregl.GeoJSONSource).setData({
			type: 'FeatureCollection',
			features
		});
	}

	$effect(() => {
		// Sync whenever ROIs change
		if (mapState.rois) {
			syncRoisToMap();
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
					Complete
				</Button>
				<Button size="sm" variant="outline" class="h-7 text-xs" onclick={cancelDrawing}>
					Cancel
				</Button>
			{/if}
		</div>
	</div>
</div>
