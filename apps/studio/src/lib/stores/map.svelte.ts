export interface GeoJSONGeometry {
	type: 'Polygon' | 'MultiPolygon' | 'Point' | 'LineString';
	coordinates: unknown;
}

export interface ROI {
	id: string;
	name: string;
	geometry: GeoJSONGeometry;
	area_m2: number;
	created_at: string;
}

export type LayerSourceType = 'geojson' | 'raster' | 'image' | 'base';

export interface MapLayer {
	id: string;
	name: string;
	category: 'base' | 'scenes' | 'products' | 'doc_overlays' | 'rois';
	visible: boolean;
	opacity?: number;
	sourceType?: LayerSourceType;
	sourceData?: unknown; // GeoJSON object or image URL/coordinates
	metadata?: Record<string, unknown>;
}

// Simple spherical geodesic polygon area calculation in square meters
export function computePolygonAreaM2(coordinates: [number, number][][]): number {
	if (!coordinates || coordinates.length === 0) return 0;
	const ring = coordinates[0];
	if (ring.length < 3) return 0;

	const radius = 6378137; // WGS84 earth radius
	let total = 0;

	for (let i = 0; i < ring.length; i++) {
		const lower = ring[i];
		const upper = ring[(i + 1) % ring.length];
		const p1Lon = (lower[0] * Math.PI) / 180;
		const p1Lat = (lower[1] * Math.PI) / 180;
		const p2Lon = (upper[0] * Math.PI) / 180;
		const p2Lat = (upper[1] * Math.PI) / 180;
		total += (p2Lon - p1Lon) * (2 + Math.sin(p1Lat) + Math.sin(p2Lat));
	}

	return Math.abs((total * radius * radius) / 2);
}

class MapStateStore {
	rois = $state<ROI[]>([]);
	currentRoi = $state<ROI | null>(null);

	layers = $state<MapLayer[]>([
		{ id: 'dark-base', name: 'Instrument Dark Basemap', category: 'base', visible: true, sourceType: 'base' }
	]);

	// Camera fit bounds target: [[minLng, minLat], [maxLng, maxLat]]
	cameraBounds = $state<[[number, number], [number, number]] | null>(null);

	addRoi(name: string, geometry: GeoJSONGeometry): ROI {
		const area = geometry.type === 'Polygon' ? computePolygonAreaM2(geometry.coordinates as [number, number][][]) : 0;
		const roi: ROI = {
			id: `roi-${Date.now()}`,
			name,
			geometry,
			area_m2: area,
			created_at: new Date().toISOString()
		};
		this.rois = [...this.rois, roi];
		this.currentRoi = roi;

		// Add layer entry
		this.layers = [
			...this.layers,
			{
				id: roi.id,
				name: roi.name,
				category: 'rois',
				visible: true,
				opacity: 0.35,
				sourceType: 'geojson',
				sourceData: {
					type: 'Feature',
					geometry: roi.geometry,
					properties: { id: roi.id, name: roi.name }
				},
				metadata: { roiId: roi.id }
			}
		];

		// Fit bounds to ROI
		this.fitToGeometry(geometry);

		return roi;
	}

	selectRoi(roiId: string) {
		const found = this.rois.find((r) => r.id === roiId);
		if (found) {
			this.currentRoi = found;
			this.fitToGeometry(found.geometry);
		}
	}

	deleteRoi(roiId: string) {
		this.rois = this.rois.filter((r) => r.id !== roiId);
		this.layers = this.layers.filter((l) => l.id !== roiId);
		if (this.currentRoi?.id === roiId) {
			this.currentRoi = this.rois[0] ?? null;
		}
	}

	toggleLayer(layerId: string) {
		this.layers = this.layers.map((l) => (l.id === layerId ? { ...l, visible: !l.visible } : l));
	}

	setLayerOpacity(layerId: string, opacity: number) {
		this.layers = this.layers.map((l) =>
			l.id === layerId ? { ...l, opacity: Math.max(0, Math.min(1, opacity)) } : l
		);
	}

	fitToGeometry(geometry: GeoJSONGeometry) {
		if (geometry.type === 'Polygon') {
			const coords = (geometry.coordinates as [number, number][][])[0];
			if (coords && coords.length > 0) {
				let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
				for (const [lng, lat] of coords) {
					if (lng < minX) minX = lng;
					if (lat < minY) minY = lat;
					if (lng > maxX) maxX = lng;
					if (lat > maxY) maxY = lat;
				}
				this.cameraBounds = [[minX, minY], [maxX, maxY]];
			}
		}
	}

	addSceneLayer(sceneId: string, name: string, sourceData?: unknown) {
		if (this.layers.some((l) => l.id === sceneId)) return;
		this.layers = [
			...this.layers,
			{
				id: sceneId,
				name,
				category: 'scenes',
				visible: true,
				opacity: 0.7,
				sourceType: 'geojson',
				sourceData,
				metadata: { sceneId }
			}
		];
	}
}

export const mapState = new MapStateStore();
