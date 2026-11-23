import type { FeatureCollection } from "geojson";
import type { Asset, MapLayer, ModelVersion, Passage, ReviewItem, ROI, Scene, Job } from "./types";

export const KARKHEH_CENTER: [number, number] = [48.05, 32.35];

export const sampleROIs: ROI[] = [
  {
    id: "roi-1",
    name: "karkheh-block-3",
    kind: "polygon",
    coords: [
      [48.02, 32.44],
      [48.14, 32.46],
      [48.19, 32.38],
      [48.11, 32.3],
      [48.0, 32.33],
      [48.02, 32.44],
    ],
    areaHa: 18640,
    centroid: [48.092, 32.382],
    createdAt: Date.now() - 86400000 * 3,
  },
  {
    id: "roi-2",
    name: "dam-reservoir-north",
    kind: "bbox",
    coords: [
      [48.08, 32.52],
      [48.2, 32.52],
      [48.2, 32.62],
      [48.08, 32.62],
      [48.08, 32.52],
    ],
    areaHa: 12480,
    centroid: [48.14, 32.57],
    createdAt: Date.now() - 86400000 * 9,
  },
];

export const parcelsGeoJSON: FeatureCollection = {
  type: "FeatureCollection",
  features: Array.from({ length: 28 }, (_, i) => {
    const col = i % 7;
    const row = Math.floor(i / 7);
    const x0 = 47.98 + col * 0.034;
    const y0 = 32.25 + row * 0.03;
    const crop = ["wheat", "sugarcane", "maize", "fallow"][(i * 7) % 4];
    return {
      type: "Feature" as const,
      properties: { id: `P-${100 + i}`, crop, ndvi: +(0.2 + ((i * 37) % 60) / 100).toFixed(2) },
      geometry: {
        type: "Polygon" as const,
        coordinates: [
          [
            [x0, y0],
            [x0 + 0.03, y0 + 0.004],
            [x0 + 0.031, y0 + 0.027],
            [x0 + 0.002, y0 + 0.025],
            [x0, y0],
          ],
        ],
      },
    };
  }),
};

export const basinGeoJSON: FeatureCollection = {
  type: "FeatureCollection",
  features: [
    {
      type: "Feature",
      properties: { name: "Karkheh Basin (lower)" },
      geometry: {
        type: "Polygon",
        coordinates: [
          [
            [47.6, 32.9],
            [48.1, 33.05],
            [48.55, 32.8],
            [48.6, 32.3],
            [48.3, 31.85],
            [47.8, 31.75],
            [47.5, 32.2],
            [47.6, 32.9],
          ],
        ],
      },
    },
    {
      type: "Feature",
      properties: { name: "Dez interbasin" },
      geometry: {
        type: "Polygon",
        coordinates: [
          [
            [48.55, 32.8],
            [48.9, 32.95],
            [49.1, 32.5],
            [48.85, 32.1],
            [48.6, 32.3],
            [48.55, 32.8],
          ],
        ],
      },
    },
  ],
};

export const sampleLayers: MapLayer[] = [
  { id: "scene-l9-0412", group: "scenes", name: "LC09_165038_20240412 True Color", visible: true, opacity: 0.85, kind: "raster" },
  { id: "scene-s2-0503", group: "scenes", name: "S2B_38SNA_20240503 True Color", visible: false, opacity: 0.85, kind: "raster" },
  {
    id: "idx-ndvi",
    group: "indices",
    name: "NDVI · 2024-04-12",
    visible: true,
    opacity: 0.7,
    kind: "raster",
    legend: {
      label: "NDVI",
      stops: [
        { color: "#a16207", value: "-0.1" },
        { color: "#d9c27a", value: "0.2" },
        { color: "#7fb069", value: "0.5" },
        { color: "#1b5e20", value: "0.8" },
      ],
    },
  },
  {
    id: "idx-eta",
    group: "indices",
    name: "METRIC ETa · Apr 2024",
    visible: false,
    opacity: 0.7,
    kind: "raster",
    legend: {
      label: "ETa mm/day",
      stops: [
        { color: "#fde68a", value: "0" },
        { color: "#60a5fa", value: "3" },
        { color: "#1d4ed8", value: "6" },
        { color: "#1e1b4b", value: "9" },
      ],
    },
  },
  {
    id: "idx-hillshade",
    group: "indices",
    name: "Hillshade (SRTM 30 m)",
    visible: false,
    opacity: 0.5,
    kind: "raster",
  },
  { id: "vec-parcels", group: "vectors", name: "Agricultural parcels", visible: true, opacity: 0.9, kind: "vector", color: "#1e6b62" },
  { id: "vec-basins", group: "vectors", name: "Water basins", visible: true, opacity: 0.8, kind: "vector", color: "#2c6399" },
  { id: "roi-layer", group: "rois", name: "User ROIs", visible: true, opacity: 1, kind: "roi", color: "#f59e0b" },
];

export function generateScenes(sensor: string, from: string, to: string, maxCloud: number): Scene[] {
  const start = new Date(from).getTime();
  const end = new Date(to).getTime();
  const isSentinel = /^(s2|sentinel)/i.test(sensor);
  const interval = isSentinel ? 5 : 16;
  const out: Scene[] = [];
  let t = start;
  let i = 0;
  while (t <= end && out.length < 40) {
    const cloud = Math.round(((i * 53 + 17) % 97) * 0.9);
    if (cloud <= maxCloud) {
      const d = new Date(t);
      const stamp = d.toISOString().slice(0, 10).replace(/-/g, "");
      out.push({
        id: isSentinel ? `S2B_MSIL2A_${stamp}T071619_N0510_R006_T38SNA` : `LC0${8 + (i % 2)}_L2SP_165038_${stamp}`,
        sensor,
        acquired: new Date(t + 7 * 3600e3 + 16 * 60e3).toISOString(),
        cloud,
        sunElev: +(42 + 25 * Math.sin(((d.getMonth() + 1) / 12) * Math.PI)).toFixed(1),
        path: "165",
        row: "038",
        synthetic: true,
        thumbSeed: i,
      });
    }
    t += interval * 86400e3;
    i++;
  }
  return out;
}

export const sampleAssets: Asset[] = [
  { id: "a1", name: "Allen_2007_METRIC_model.pdf", type: "pdf", sha256: "9f2c3a8e1d4b7c6a5e0f1b2d3c4a5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d", segments: 412, sizeBytes: 3_245_112, modality: "text", addedAt: Date.now() - 86400e3 * 12 },
  { id: "a2", name: "Karkheh_water_balance_2019.pdf", type: "pdf", sha256: "4b1e7a9c2d8f0e3a6b5c4d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a", segments: 238, sizeBytes: 1_988_430, modality: "text", addedAt: Date.now() - 86400e3 * 10 },
  { id: "a3", name: "FAO56_crop_coefficients.pdf", type: "pdf", sha256: "c7d9e1f3a5b7c9d1e3f5a7b9c1d3e5f7a9b1c3d5e7f9a1b3c5d7e9f1a3b5c7d9", segments: 611, sizeBytes: 5_112_880, modality: "text", addedAt: Date.now() - 86400e3 * 20 },
  { id: "a4", name: "LC09_165038_20240412_NDVI.tif", type: "tif", sha256: "e2f4a6b8c0d2e4f6a8b0c2d4e6f8a0b2c4d6e8f0a2b4c6d8e0f2a4b6c8d0e2f4", segments: 1024, sizeBytes: 148_229_000, modality: "vision", addedAt: Date.now() - 86400e3 * 4 },
  { id: "a5", name: "karkheh_parcels_2024.geojson", type: "geojson", sha256: "1a3b5c7d9e1f3a5b7c9d1e3f5a7b9c1d3e5f7a9b1c3d5e7f9a1b3c5d7e9f1a3b", segments: 28, sizeBytes: 84_220, modality: "vector", addedAt: Date.now() - 86400e3 * 4 },
  { id: "a6", name: "station_discharge_pay_pol.csv", type: "csv", sha256: "8d0e2f4a6b8c0d2e4f6a8b0c2d4e6f8a0b2c4d6e8f0a2b4c6d8e0f2a4b6c8d0e", segments: 365, sizeBytes: 22_118, modality: "table", addedAt: Date.now() - 86400e3 * 2 },
];

export const samplePassages: Passage[] = [
  {
    id: "p1",
    assetId: "a1",
    assetName: "Allen_2007_METRIC_model.pdf",
    page: 4,
    bbox: [72, 318, 528, 412],
    score: 0.91,
    text: "METRIC computes ET as a residual of the surface energy balance, ET = Rn − G − H, where sensible heat flux H is calibrated internally using hot and cold anchor pixels selected within the image (CIMEC).",
  },
  {
    id: "p2",
    assetId: "a2",
    assetName: "Karkheh_water_balance_2019.pdf",
    page: 11,
    bbox: [64, 120, 540, 260],
    score: 0.87,
    text: "Mean annual actual evapotranspiration across irrigated lands of the lower Karkheh was estimated at 1,180 mm, with sugarcane fields exceeding 1,900 mm and wheat–fallow rotations near 620 mm.",
  },
  {
    id: "p3",
    assetId: "a3",
    assetName: "FAO56_crop_coefficients.pdf",
    page: 110,
    bbox: [80, 402, 510, 470],
    score: 0.78,
    text: "Single crop coefficient Kc for sugarcane: initial 0.40, mid-season 1.25, end-season 0.75 for virgin cane; ratoon values are typically reduced by 5–10%.",
  },
  {
    id: "p4",
    assetId: "a4",
    assetName: "LC09_165038_20240412_NDVI.tif",
    rasterCoord: [48.092, 32.382],
    score: 0.74,
    text: "Raster segment tile z12/2593/1663 — mean NDVI 0.63, std 0.11 over 1,024 valid pixels; flagged as vegetated cropland class.",
  },
  {
    id: "p5",
    assetId: "a2",
    assetName: "Karkheh_water_balance_2019.pdf",
    page: 14,
    bbox: [64, 300, 540, 380],
    score: 0.69,
    text: "Inflow to the Karkheh reservoir averaged 5.8 BCM/yr (1998–2017) with a declining trend of −62 MCM/yr; releases for irrigation accounted for 71% of outflow.",
  },
  {
    id: "p6",
    assetId: "a6",
    assetName: "station_discharge_pay_pol.csv",
    page: undefined,
    score: 0.58,
    text: "Rows 212–243 (Aug 2023): daily discharge at Pay-e-Pol station ranged 38.2–61.7 m³/s; monthly mean 47.9 m³/s.",
  },
];

export const sampleReview: ReviewItem[] = [
  { id: "r1", kind: "classification", subject: "Parcel P-104 (2024-04-12)", prediction: "sugarcane", confidence: 0.82, status: "pending" },
  { id: "r2", kind: "classification", subject: "Parcel P-111 (2024-04-12)", prediction: "wheat", confidence: 0.64, status: "pending" },
  { id: "r3", kind: "qa", subject: "What is mean ETa of sugarcane in lower Karkheh?", prediction: "≈1,900 mm/yr [Karkheh_water_balance_2019 p.11]", confidence: 0.87, status: "pending" },
  { id: "r4", kind: "classification", subject: "Parcel P-119 (2024-04-12)", prediction: "fallow", confidence: 0.58, status: "pending" },
  { id: "r5", kind: "qa", subject: "Which anchor pixels does METRIC use?", prediction: "Hot and cold pixels selected via CIMEC [Allen_2007 p.4]", confidence: 0.91, status: "pending" },
  { id: "r6", kind: "classification", subject: "Parcel P-123 (2024-04-12)", prediction: "maize", confidence: 0.71, status: "pending" },
];

export const sampleVersions: ModelVersion[] = [
  { id: "v3", version: "crop-sgd@0.3.0", createdAt: Date.now() - 86400e3 * 1, valAcc: 0.861, delta: 1.2, trainSeconds: 1.7, samples: 14, algorithm: "SGDClassifier (log-loss)", active: true },
  { id: "v2", version: "crop-sgd@0.2.0", createdAt: Date.now() - 86400e3 * 5, valAcc: 0.849, delta: 2.8, trainSeconds: 1.4, samples: 22, algorithm: "SGDClassifier (log-loss)", active: false },
  { id: "v1", version: "crop-sgd@0.1.0", createdAt: Date.now() - 86400e3 * 15, valAcc: 0.821, delta: 0, trainSeconds: 9.3, samples: 180, algorithm: "SGDClassifier (log-loss)", active: false },
];

export const sampleJobs: Job[] = [
  {
    id: "job-7f21",
    kind: "ingest",
    title: "Ingest station_discharge_pay_pol.csv",
    status: "complete",
    progress: 100,
    steps: [
      { label: "Extraction", done: true },
      { label: "Chunking", done: true },
      { label: "Embedding text.*", done: true },
      { label: "Indexing", done: true },
    ],
    createdAt: Date.now() - 3600e3 * 5,
    updatedAt: Date.now() - 3600e3 * 5 + 18e3,
    logs: ["[ingest] 365 rows parsed", "[embed] text.bge-m3 · 365 vectors", "[index] committed to lancedb/text"],
  },
  {
    id: "job-3a9c",
    kind: "download",
    title: "Download LC08_L2SP_165038_20230817",
    status: "failed",
    progress: 42,
    steps: [
      { label: "B02", done: true },
      { label: "B03", done: true },
      { label: "B04", done: false },
      { label: "B08", done: false },
      { label: "COG", done: false },
      { label: "Ingest", done: false },
    ],
    createdAt: Date.now() - 86400e3,
    updatedAt: Date.now() - 86400e3 + 60e3,
    logs: ["[fetch] B02 ok (71 MB)", "[fetch] B03 ok (69 MB)", "[fetch] B04 … HTTP 503 from upstream STAC", "[job] failed: upstream unavailable"],
  },
];

export const playbooks = [
  { id: "eta", key: "pb_eta" as const, tools: ["roi_resolve", "scene_search", "metric_compute", "zonal_stats", "hybrid_search"] },
  { id: "ndvi", key: "pb_ndvi" as const, tools: ["roi_resolve", "scene_search", "index_compute:ndvi", "anomaly_detect", "roi_create"] },
  { id: "balance", key: "pb_balance" as const, tools: ["hybrid_search", "table_query", "metric_compute", "water_balance"] },
];
