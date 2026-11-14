export type View = "map" | "acquire" | "resources" | "knowledge" | "training" | "ops" | "settings";

export type JobStatus = "queued" | "running" | "complete" | "failed" | "cancelled";

export interface JobStep {
  label: string;
  done: boolean;
}

export interface Job {
  id: string;
  kind: "download" | "ingest" | "train" | "metric" | "playbook";
  title: string;
  status: JobStatus;
  progress: number; // 0-100
  steps: JobStep[];
  createdAt: number;
  updatedAt: number;
  logs: string[];
  meta?: Record<string, unknown>;
  result?: Record<string, unknown> | null;
}

export interface ROI {
  id: string;
  name: string;
  kind: "bbox" | "polygon";
  coords: [number, number][]; // ring, lon/lat
  areaHa: number;
  centroid: [number, number];
  createdAt: number;
}

export interface MapLayer {
  id: string;
  group: "scenes" | "indices" | "vectors" | "rois";
  name: string;
  visible: boolean;
  opacity: number;
  legend?: { label: string; stops: { color: string; value: string }[] };
  kind: "raster" | "vector" | "roi";
  color?: string;
  tileUrl?: string; // gateway tiles route — real layers (no synthetic canvas)
}

export interface Scene {
  id: string;
  sensor: string;
  acquired: string;
  cloud: number;
  sunElev: number;
  path: string;
  row: string;
  thumbSeed: number;
}

export interface Asset {
  id: string;
  name: string;
  type: "pdf" | "tif" | "geojson" | "csv";
  sha256: string;
  segments: number;
  sizeBytes: number;
  modality: "text" | "vision" | "vector" | "table";
  addedAt: number;
}

export interface Passage {
  id: string;
  assetId: string;
  assetName: string;
  page?: number;
  bbox?: [number, number, number, number];
  rasterCoord?: [number, number];
  text: string;
  score: number;
}

export interface QAResult {
  question: string;
  mode: "hybrid" | "semantic" | "keyword";
  abstained: boolean;
  answer?: string;
  confidence: number;
  topScore: number;
  citations: Passage[];
  caveats: string[];
}

export interface ReviewItem {
  id: string;
  kind: "qa" | "classification";
  subject: string;
  prediction: string;
  confidence: number;
  status: "pending" | "accepted" | "rejected" | "corrected";
  correction?: string;
}

export interface ModelVersion {
  id: string;
  version: string;
  createdAt: number;
  valAcc: number;
  delta: number;
  trainSeconds: number;
  samples: number;
  algorithm: string;
  active: boolean;
}

export interface ToolCall {
  id: string;
  name: string;
  args: string;
  status: "running" | "complete" | "failed";
  durationMs?: number;
  result?: string;
}

export interface ChatMessage {
  id: string;
  role: "user" | "agent";
  text: string;
  streaming?: boolean;
  plan?: string[];
  tools?: ToolCall[];
  citations?: Passage[];
  caveats?: string[];
  table?: { headers: string[]; rows: string[][] };
}

export interface Settings {
  dataRoot: string;
  cogRoot: string;
  indexRoot: string;
  llmUrl: string;
  llmModel: string;
  apiKeyFromEnv: boolean;
  density: "compact" | "comfortable";
  groundingThreshold: number;
}
