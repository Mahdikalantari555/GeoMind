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
  reconnecting?: boolean;
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
  roiId?: string;
  id: string;
  group: "scenes" | "indices" | "vectors" | "rois";
  name: string;
  visible: boolean;
  opacity: number;
  legend?: { label: string; stops: { color: string; value: string }[] };
  kind: "raster" | "vector" | "roi";
  color?: string;
  geojson?: GeoJSON.GeoJSON;
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
  synthetic?: boolean;
}

export interface Asset {
  id: string;
  name: string;
  type: "pdf" | "tif" | "geojson" | "csv" | "txt";
  sha256: string;
  segments: number | null;
  sizeBytes: number;
  modality: "text" | "vision" | "vector" | "table";
  addedAt: number;
  live?: boolean;
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
  /** (crop, region) training key when known (gateway candidates). */
  key?: string;
  /** Provenance chain: answer → citation → segment → asset. */
  provenance?: { answerId?: string; citationId?: string; segmentId?: string; assetId?: string };
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
  /** Gateway identity for rollback (geolearn key + version number). */
  key?: [string, string];
  versionNumber?: number;
  sha256?: string;
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
  /** Citation numbers stripped because no matching source exists. */
  invalidCitations?: number[];
  /** True when the gateway reports no LLM key (retrieval-only mode). */
  degraded?: boolean;
}

export interface Collection {
  id: string;
  name: string;
  description?: string;
  archived?: boolean;
  assetCount?: number;
}

export interface IndexManifest {
  spaceId: string;
  exists: boolean;
  totalVectors?: number;
  totalSegments?: number;
  modalities?: string[];
}

export interface AgentTool {
  name: string;
  description: string;
  timeoutS?: number;
  cacheable?: boolean;
}

export interface Playbook {
  name: string;
  version?: string;
  triggers?: string[];
  steps?: { tool: string; args: Record<string, unknown> }[];
  valid?: boolean;
  problems?: string[];
}

export interface Settings {
  dataRoot: string;
  cogRoot: string;
  indexRoot: string;
  llmUrl: string;
  llmModel: string;
  apiKeyFromEnv: boolean;
  density: "compact" | "comfortable";
  classifierThreshold: number;
  groundingThreshold: number;
}
