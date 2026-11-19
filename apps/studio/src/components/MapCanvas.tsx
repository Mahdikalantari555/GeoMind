import { useEffect, useRef, useState } from "react";
import * as maplibregl from "maplibre-gl";
import type { Map as MLMap, StyleSpecification } from "maplibre-gl";
import type { Feature, FeatureCollection, Polygon } from "geojson";
import { useStore, type Basemap } from "@/lib/store";
import { basinGeoJSON, parcelsGeoJSON, KARKHEH_CENTER } from "@/lib/sample";
import { isDemo } from "@/lib/api";
import type { MapLayer, ROI } from "@/lib/types";

export type DrawMode = "bbox" | "polygon" | null;

const RASTER_EXTENT: [[number, number], [number, number], [number, number], [number, number]] = [
  [47.82, 32.72],
  [48.4, 32.72],
  [48.4, 32.12],
  [47.82, 32.12],
];

const BASEMAPS: Record<Basemap, { tiles: string[]; attribution: string; maxzoom: number }> = {
  satellite: {
    tiles: ["https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"],
    attribution: "Esri, Maxar, Earthstar Geographics",
    maxzoom: 18,
  },
  topo: { tiles: ["https://a.tile.opentopomap.org/{z}/{x}/{y}.png", "https://b.tile.opentopomap.org/{z}/{x}/{y}.png"], attribution: "© OpenTopoMap (CC-BY-SA)", maxzoom: 16 },
  gray: { tiles: ["https://basemaps.cartocdn.com/light_nolabels/{z}/{x}/{y}.png"], attribution: "© CARTO © OpenStreetMap", maxzoom: 19 },
};

// --- synthetic raster generation (offline sample data) ---
function noise2(x: number, y: number, seed: number) {
  const s = Math.sin(x * 12.9898 + y * 78.233 + seed * 37.719) * 43758.5453;
  return s - Math.floor(s);
}
function smoothNoise(x: number, y: number, seed: number) {
  const xi = Math.floor(x), yi = Math.floor(y);
  const fx = x - xi, fy = y - yi;
  const sx = fx * fx * (3 - 2 * fx), sy = fy * fy * (3 - 2 * fy);
  const a = noise2(xi, yi, seed), b = noise2(xi + 1, yi, seed), c = noise2(xi, yi + 1, seed), d = noise2(xi + 1, yi + 1, seed);
  return a + (b - a) * sx + (c - a) * sy + (a - b - c + d) * sx * sy;
}
function fbm(x: number, y: number, seed: number) {
  let v = 0, amp = 0.5, f = 1;
  for (let i = 0; i < 5; i++) {
    v += amp * smoothNoise(x * f, y * f, seed + i);
    amp *= 0.5;
    f *= 2;
  }
  return v;
}
function lerpColor(stops: [number, number, number][], t: number): [number, number, number] {
  const n = stops.length - 1;
  const i = Math.min(n - 1, Math.max(0, Math.floor(t * n)));
  const f = t * n - i;
  return [0, 1, 2].map((k) => stops[i][k] + (stops[i + 1][k] - stops[i][k]) * f) as [number, number, number];
}
function makeRaster(kind: "ndvi" | "eta" | "hillshade" | "truecolor", seed: number): HTMLCanvasElement {
  const W = 512, H = 512;
  const c = document.createElement("canvas");
  c.width = W;
  c.height = H;
  const ctx = c.getContext("2d")!;
  const img = ctx.createImageData(W, H);
  const ramps: Record<string, [number, number, number][]> = {
    ndvi: [[161, 98, 7], [217, 194, 122], [127, 176, 105], [27, 94, 32]],
    eta: [[253, 230, 138], [96, 165, 250], [29, 78, 216], [30, 27, 75]],
    hillshade: [[40, 40, 40], [240, 240, 240]],
    truecolor: [[96, 84, 62], [140, 124, 90], [112, 128, 84], [60, 92, 60]],
  };
  for (let y = 0; y < H; y++) {
    for (let x = 0; x < W; x++) {
      const u = x / W, v = y / H;
      let t = fbm(u * 6, v * 6, seed);
      // river corridor: lower NDVI/higher ETa along a sinuous band
      const river = Math.exp(-Math.pow((u - 0.45 - 0.12 * Math.sin(v * 6)) * 9, 2));
      if (kind === "ndvi") t = Math.min(1, t * 0.9 + river * 0.35 + (v > 0.55 && u > 0.3 ? 0.18 : 0));
      if (kind === "eta") t = Math.min(1, t * 0.8 + river * 0.5);
      if (kind === "hillshade") {
        const dx = fbm((u + 0.004) * 6, v * 6, seed) - fbm((u - 0.004) * 6, v * 6, seed);
        t = Math.min(1, Math.max(0, 0.5 + dx * 12));
      }
      const [r, g, b] = lerpColor(ramps[kind], Math.max(0, Math.min(0.999, t)));
      const i = (y * W + x) * 4;
      img.data[i] = r;
      img.data[i + 1] = g;
      img.data[i + 2] = b;
      img.data[i + 3] = 255;
    }
  }
  ctx.putImageData(img, 0, 0);
  return c;
}

const rasterKind = (l: MapLayer): "ndvi" | "eta" | "hillshade" | "truecolor" =>
  l.id.includes("ndvi") || l.name.toLowerCase().includes("ndvi") ? "ndvi" : l.id.includes("eta") || l.name.includes("ETa") ? "eta" : l.id.includes("hillshade") ? "hillshade" : "truecolor";

function roiFeature(r: ROI, active: boolean): Feature<Polygon> {
  return { type: "Feature", properties: { id: r.id, name: r.name, active }, geometry: { type: "Polygon", coordinates: [r.coords] } };
}

function buildStyle(b: Basemap): StyleSpecification {
  return {
    version: 8,
    glyphs: "https://demotiles.maplibre.org/font/{fontstack}/{range}.pbf",
    sources: { base: { type: "raster", tiles: BASEMAPS[b].tiles, tileSize: 256, attribution: BASEMAPS[b].attribution, maxzoom: BASEMAPS[b].maxzoom } },
    layers: [
      { id: "bg", type: "background", paint: { "background-color": b === "satellite" ? "#1b2a26" : "#e9ece9" } },
      { id: "base", type: "raster", source: "base", paint: { "raster-saturation": b === "gray" ? -1 : 0 } },
    ],
  };
}

interface Props {
  drawMode: DrawMode;
  draft: [number, number][];
  setDraft: (pts: [number, number][]) => void;
  onFinish: () => void;
  onCursor?: (lngLat: [number, number] | null) => void;
}

export function MapCanvas({ drawMode, draft, setDraft, onFinish, onCursor }: Props) {
  const s = useStore();
  const el = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MLMap | null>(null);
  const [ready, setReady] = useState(0);
  const drawRef = useRef({ drawMode, draft, setDraft, onFinish });
  drawRef.current = { drawMode, draft, setDraft, onFinish };
  const hoverRef = useRef<[number, number] | null>(null);
  const [tileErr, setTileErr] = useState(false);

  // init
  useEffect(() => {
    if (!el.current) return;
    const map = new maplibregl.Map({ container: el.current, style: buildStyle("satellite"), center: KARKHEH_CENTER, zoom: 9.6, attributionControl: { compact: true } });
    map.addControl(new maplibregl.NavigationControl({ visualizePitch: false }), "top-right");
    map.addControl(new maplibregl.ScaleControl({ unit: "metric" }), "bottom-right");
    mapRef.current = map;
    map.on("load", () => setReady((n) => n + 1));
    map.on("style.load", () => setReady((n) => n + 1));
    map.on("error", (e) => {
      if ((e as { sourceId?: string }).sourceId === "base") setTileErr(true);
    });
    map.on("mousemove", (e) => {
      const ll: [number, number] = [e.lngLat.lng, e.lngLat.lat];
      hoverRef.current = ll;
      onCursor?.(ll);
      const d = drawRef.current;
      if (d.drawMode && d.draft.length) {
        const src = map.getSource("draft") as maplibregl.GeoJSONSource | undefined;
        src?.setData(draftFC(d.drawMode, d.draft, ll));
      }
    });
    map.on("mouseout", () => onCursor?.(null));
    map.on("click", (e) => {
      const d = drawRef.current;
      if (!d.drawMode) return;
      const p: [number, number] = [e.lngLat.lng, e.lngLat.lat];
      if (d.drawMode === "bbox") {
        if (d.draft.length === 0) d.setDraft([p]);
        else d.setDraft([d.draft[0], p]);
      } else {
        d.setDraft([...d.draft, p]);
      }
    });
    map.on("dblclick", (e) => {
      const d = drawRef.current;
      if (d.drawMode === "polygon") {
        e.preventDefault();
        d.onFinish();
      }
    });
    return () => {
      map.remove();
      mapRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // basemap switch
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    map.setStyle(buildStyle(s.basemap), { diff: false });
  }, [s.basemap]);

  // (re)build overlay layers whenever style loads or layers change
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !map.isStyleLoaded()) return;
    const ensureSrc = (id: string, spec: maplibregl.SourceSpecification) => {
      if (!map.getSource(id)) map.addSource(id, spec);
    };
    // raster layers: real gateway tiles when available; synthetic canvas
    // only in the explicitly-labeled demo environment
    const rasters = s.layers.filter((l) => l.kind === "raster");
    rasters.forEach((l, i) => {
      const sid = `src-${l.id}`;
      if (l.tileUrl) {
        if (!map.getSource(sid)) {
          map.addSource(sid, { type: "raster", tiles: [l.tileUrl], tileSize: 256 } as maplibregl.RasterSourceSpecification);
        }
        if (!map.getLayer(`ly-${l.id}`)) map.addLayer({ id: `ly-${l.id}`, type: "raster", source: sid, paint: { "raster-opacity": l.opacity } });
        else map.setPaintProperty(`ly-${l.id}`, "raster-opacity", l.opacity);
        map.setLayoutProperty(`ly-${l.id}`, "visibility", l.visible ? "visible" : "none");
        return;
      }
      if (!isDemo()) return; // no fake layers outside demo mode
      const sid2 = `cv-${l.id}`;
      if (!map.getSource(sid2)) {
        const canvas = makeRaster(rasterKind(l), i + 3);
        map.addSource(sid2, { type: "canvas", canvas, coordinates: RASTER_EXTENT, animate: false } as maplibregl.CanvasSourceSpecification);
      }
      if (!map.getLayer(`ly-${l.id}`)) map.addLayer({ id: `ly-${l.id}`, type: "raster", source: sid2, paint: { "raster-opacity": l.opacity, "raster-resampling": "nearest" } });
      map.setLayoutProperty(`ly-${l.id}`, "visibility", l.visible ? "visible" : "none");
      map.setPaintProperty(`ly-${l.id}`, "raster-opacity", l.opacity);
    });
    // Real uploaded GeoJSON is independent of the bundled demo overlays.
    for (const layer of s.layers) {
      if (layer.kind !== "vector" || !layer.geojson) continue;
      const sid = `src-${layer.id}`;
      const color = layer.color ?? "#a8650b";
      const fill = `fill-${layer.id}`, line = `line-${layer.id}`, points = `points-${layer.id}`;
      ensureSrc(sid, { type: "geojson", data: layer.geojson });
      if (!map.getLayer(fill)) map.addLayer({ id: fill, type: "fill", source: sid, paint: { "fill-color": color } });
      if (!map.getLayer(line)) map.addLayer({ id: line, type: "line", source: sid, paint: { "line-color": color, "line-width": 2 } });
      if (!map.getLayer(points)) map.addLayer({ id: points, type: "circle", source: sid, paint: { "circle-color": color, "circle-radius": 4 } });
      for (const id of [fill, line, points]) map.setLayoutProperty(id, "visibility", layer.visible ? "visible" : "none");
      map.setPaintProperty(fill, "fill-opacity", layer.opacity * 0.35);
      map.setPaintProperty(line, "line-opacity", layer.opacity);
      map.setPaintProperty(points, "circle-opacity", layer.opacity);
    }
    // vectors
    ensureSrc("parcels", { type: "geojson", data: parcelsGeoJSON });
    ensureSrc("basins", { type: "geojson", data: basinGeoJSON });
    const parcels = s.layers.find((l) => l.id === "vec-parcels");
    const basins = s.layers.find((l) => l.id === "vec-basins");
    if (!map.getLayer("parcels-fill"))
      map.addLayer({ id: "parcels-fill", type: "fill", source: "parcels", paint: { "fill-color": ["match", ["get", "crop"], "wheat", "#d9c27a", "sugarcane", "#1e6b62", "maize", "#7fb069", "#b8b2a4"], "fill-opacity": 0.35 } });
    if (!map.getLayer("parcels-line")) map.addLayer({ id: "parcels-line", type: "line", source: "parcels", paint: { "line-color": parcels?.color ?? "#1e6b62", "line-width": 1.2 } });
    if (!map.getLayer("basins-line")) map.addLayer({ id: "basins-line", type: "line", source: "basins", paint: { "line-color": basins?.color ?? "#2c6399", "line-width": 2, "line-dasharray": [3, 2] } });
    ["parcels-fill", "parcels-line"].forEach((id) => {
      map.setLayoutProperty(id, "visibility", parcels?.visible ? "visible" : "none");
      map.setPaintProperty(id, id.endsWith("fill") ? "fill-opacity" : "line-opacity", (parcels?.opacity ?? 1) * (id.endsWith("fill") ? 0.35 : 1));
    });
    map.setLayoutProperty("basins-line", "visibility", basins?.visible ? "visible" : "none");
    map.setPaintProperty("basins-line", "line-opacity", basins?.opacity ?? 1);
    // ROIs
    const roiVisible = s.layers.find((l) => l.group === "rois")?.visible ?? true;
    const fc: FeatureCollection = { type: "FeatureCollection", features: s.rois.map((r) => roiFeature(r, r.id === s.activeRoiId)) };
    ensureSrc("rois", { type: "geojson", data: fc });
    (map.getSource("rois") as maplibregl.GeoJSONSource).setData(fc);
    if (!map.getLayer("rois-fill")) map.addLayer({ id: "rois-fill", type: "fill", source: "rois", paint: { "fill-color": "#f59e0b", "fill-opacity": ["case", ["get", "active"], 0.18, 0.06] } });
    if (!map.getLayer("rois-line")) map.addLayer({ id: "rois-line", type: "line", source: "rois", paint: { "line-color": ["case", ["get", "active"], "#f59e0b", "#fcd34d"], "line-width": ["case", ["get", "active"], 2.5, 1.5] } });
    if (!map.getLayer("rois-label"))
      map.addLayer({ id: "rois-label", type: "symbol", source: "rois", layout: { "text-field": ["get", "name"], "text-size": 11, "text-font": ["Noto Sans Regular"], "text-anchor": "top" }, paint: { "text-color": "#fff", "text-halo-color": "#103833", "text-halo-width": 1.2 } });
    ["rois-fill", "rois-line", "rois-label"].forEach((id) => map.setLayoutProperty(id, "visibility", roiVisible ? "visible" : "none"));
    // draft
    ensureSrc("draft", { type: "geojson", data: { type: "FeatureCollection", features: [] } });
    if (!map.getLayer("draft-fill")) map.addLayer({ id: "draft-fill", type: "fill", source: "draft", paint: { "fill-color": "#38bdf8", "fill-opacity": 0.15 } });
    if (!map.getLayer("draft-line")) map.addLayer({ id: "draft-line", type: "line", source: "draft", paint: { "line-color": "#38bdf8", "line-width": 2, "line-dasharray": [2, 1.5] } });
    if (!map.getLayer("draft-pts")) map.addLayer({ id: "draft-pts", type: "circle", source: "draft", filter: ["==", "$type", "Point"], paint: { "circle-radius": 4, "circle-color": "#fff", "circle-stroke-color": "#0284c7", "circle-stroke-width": 2 } });
  }, [ready, s.layers, s.rois, s.activeRoiId]);

  // draft updates
  useEffect(() => {
    const map = mapRef.current;
    const src = map?.getSource("draft") as maplibregl.GeoJSONSource | undefined;
    src?.setData(drawMode ? draftFC(drawMode, draft, hoverRef.current) : { type: "FeatureCollection", features: [] });
    if (map) map.getCanvas().style.cursor = drawMode ? "crosshair" : "";
    if (drawMode) map?.doubleClickZoom.disable();
    else map?.doubleClickZoom.enable();
  }, [drawMode, draft, ready]);

  // fly to
  useEffect(() => {
    if (s.flyTo && mapRef.current) {
      mapRef.current.flyTo({ center: s.flyTo, zoom: 11.2, duration: 900 });
      s.requestFly(null);
    }
  }, [s.flyTo, s]);

  return (
    <div className="map-ltr relative h-full w-full" dir="ltr">
      <div ref={el} className="h-full w-full" />
      {tileErr && (
        <div className="pointer-events-none absolute bottom-8 left-1/2 -translate-x-1/2 rounded-md bg-ink/80 px-3 py-1.5 text-[11px] text-white">
          Basemap tiles unavailable offline — showing bundled Karkheh sample layers only.
        </div>
      )}
    </div>
  );
}

function draftFC(mode: DrawMode, pts: [number, number][], hover: [number, number] | null): FeatureCollection {
  const features: FeatureCollection["features"] = pts.map((p) => ({ type: "Feature", properties: {}, geometry: { type: "Point", coordinates: p } }));
  const all = hover && pts.length ? [...pts, hover] : pts;
  if (mode === "bbox" && all.length >= 2) {
    const ring = bboxRing(all[0], all[1]);
    features.push({ type: "Feature", properties: {}, geometry: { type: "Polygon", coordinates: [ring] } });
  } else if (mode === "polygon" && all.length >= 2) {
    if (all.length >= 3) features.push({ type: "Feature", properties: {}, geometry: { type: "Polygon", coordinates: [[...all, all[0]]] } });
    else features.push({ type: "Feature", properties: {}, geometry: { type: "LineString", coordinates: all } });
  }
  return { type: "FeatureCollection", features };
}

export function bboxRing(a: [number, number], b: [number, number]): [number, number][] {
  const x0 = Math.min(a[0], b[0]), x1 = Math.max(a[0], b[0]);
  const y0 = Math.min(a[1], b[1]), y1 = Math.max(a[1], b[1]);
  return [
    [x0, y0],
    [x1, y0],
    [x1, y1],
    [x0, y1],
    [x0, y0],
  ];
}
