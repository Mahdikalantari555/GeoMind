import type { AgentTool, Collection, IndexManifest, Playbook, Scene, QAResult, Passage } from "./types";
import { generateScenes, samplePassages } from "./sample";

export const API_BASE: string | undefined = (import.meta.env.VITE_GEOMIND_API as string | undefined)?.replace(/\/$/, "");

/** Demo data is opt-in only (VITE_GEOMIND_DEMO=1) — never a silent fallback. */
export const DEMO_MODE: boolean = (import.meta.env.VITE_GEOMIND_DEMO as string | undefined) === "1";

export const gatewayConfigured = Boolean(API_BASE);

let gatewayUp = false;
export const isGatewayUp = () => gatewayUp;
export const isDemo = () => DEMO_MODE;

export async function probeGateway(): Promise<boolean> {
  if (!API_BASE) return (gatewayUp = false);
  try {
    const ctrl = new AbortController();
    const t = setTimeout(() => ctrl.abort(), 2500);
    const r = await fetch(`${API_BASE}/api/v1/health`, { signal: ctrl.signal });
    clearTimeout(t);
    gatewayUp = r.ok;
  } catch {
    gatewayUp = false;
  }
  return gatewayUp;
}

function requireGateway(op: string): void {
  if (!gatewayUp) {
    throw new Error(
      `${op}: gateway offline — start the gateway (uvicorn geofront_api.main:app --port 8000) or set VITE_GEOMIND_DEMO=1 for the demo workspace`,
    );
  }
}

async function get<T>(path: string): Promise<T> {
  requireGateway(`GET ${path}`);
  const r = await fetch(`${API_BASE}/api/v1${path}`);
  if (!r.ok) {
    let detail = `${r.status} ${r.statusText}`;
    try {
      const envelope = (await r.json()) as { error?: { message?: string } };
      if (envelope.error?.message) detail = envelope.error.message;
    } catch {
      /* keep status-line detail */
    }
    throw new Error(`GET ${path} → ${detail}`);
  }
  return r.json();
}

async function post<T>(path: string, body: unknown): Promise<T> {
  requireGateway(`POST ${path}`);
  const r = await fetch(`${API_BASE}/api/v1${path}`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) {
    let detail = `${r.status} ${r.statusText}`;
    try {
      const envelope = (await r.json()) as { error?: { message?: string } };
      if (envelope.error?.message) detail = envelope.error.message;
    } catch {
      /* keep status-line detail */
    }
    throw new Error(`POST ${path} → ${detail}`);
  }
  return r.json();
}

export const sleep = (ms: number) => new Promise((res) => setTimeout(res, ms));

// ---------- Geometry / sensor helpers ----------

/** Convert a lon/lat ring to a GeoJSON Polygon geometry (null-safe). */
export function ringToPolygon(roi: [number, number][] | null): { type: "Polygon"; coordinates: [number, number][][] } | null {
  if (!roi || roi.length < 3) return null;
  const first = roi[0];
  const last = roi[roi.length - 1];
  const ring = first[0] === last[0] && first[1] === last[1] ? roi : [...roi, first];
  return { type: "Polygon", coordinates: [ring] };
}

/** Map the UI's display sensor names to the gateway's sensor keys. */
export function sensorKey(display: string): "landsat" | "sentinel" {
  return /sentinel|s2/i.test(display) ? "sentinel" : "landsat";
}

const WORLD_POLYGON = {
  type: "Polygon" as const,
  coordinates: [[[-180, -85], [180, -85], [180, 85], [-180, 85], [-180, -85]]],
};

function thumbSeed(id: string): number {
  let h = 0;
  for (let i = 0; i < id.length; i++) h = (h * 31 + id.charCodeAt(i)) % 9973;
  return h;
}

// ---------- Data engine (change: add-scene-data-gateway) ----------

interface SceneRefDto {
  scene_id: string;
  datetime: string;
  cloud_cover: number;
  platform: string | null;
  bbox: number[];
}

export async function searchScenes(params: { roi: [number, number][] | null; sensor: string; from: string; to: string; maxCloud: number }): Promise<Scene[]> {
  if (gatewayUp) {
    const body = {
      roi: ringToPolygon(params.roi) ?? WORLD_POLYGON,
      sensor: sensorKey(params.sensor),
      date_from: params.from,
      date_to: params.to,
      max_cloud: params.maxCloud,
    };
    const r = await post<{ scenes: SceneRefDto[] }>("/data/search", body);
    return r.scenes.map((s) => ({
      id: s.scene_id,
      sensor: s.platform ?? sensorKey(params.sensor),
      acquired: s.datetime.slice(0, 10),
      cloud: s.cloud_cover,
      sunElev: 0,
      path: "",
      row: "",
      thumbSeed: thumbSeed(s.scene_id),
    }));
  }
  if (DEMO_MODE) {
    await sleep(650);
    return generateScenes(params.sensor, params.from, params.to, params.maxCloud);
  }
  requireGateway("scene search");
  return [];
}

export interface DownloadOpts {
  sensor: string;
  from: string;
  to: string;
}

export async function requestDownload(sceneId: string, roi: [number, number][] | null, opts: DownloadOpts): Promise<{ job_id: string }> {
  if (gatewayUp) {
    const body = {
      scene_id: sceneId,
      roi: ringToPolygon(roi) ?? WORLD_POLYGON,
      sensor: sensorKey(opts.sensor),
      date_from: opts.from,
      date_to: opts.to,
    };
    const r = await post<{ job_id: string }>("/data/download", body);
    return r;
  }
  if (DEMO_MODE) {
    await sleep(200);
    return { job_id: `job-${Math.random().toString(16).slice(2, 6)}` };
  }
  requireGateway("scene download");
  return { job_id: "" };
}

export async function requestTrain(batchSize = 10): Promise<{ job_id: string }> {
  if (gatewayUp) return post<{ job_id: string }>("/models/train", { batch_size: batchSize });
  if (DEMO_MODE) {
    await sleep(120);
    return { job_id: `job-${Math.random().toString(16).slice(2, 6)}` };
  }
  requireGateway("model training");
  return { job_id: "" };
}

/** Public tiles URL for a workspace-relative band file (gateway route). */
export function tileUrlFor(relPath: string, bands = "1"): string | undefined {
  if (!API_BASE) return undefined;
  return `${API_BASE}/api/v1/data/tiles/{z}/{x}/{y}.png?path=${encodeURIComponent(relPath)}&bands=${encodeURIComponent(bands)}`;
}

/** Subscribe to gateway `job.progress` SSE events for one job. */
export function subscribeJob(jobId: string, onEvent: (e: { progress: number; step?: string; status?: string; log?: string; result?: Record<string, unknown> }) => void): () => void {
  if (!gatewayUp || !API_BASE) return () => {};
  const es = new EventSource(`${API_BASE}/api/v1/events`);
  es.addEventListener("job.progress", (ev) => {
    try {
      const payload = JSON.parse((ev as MessageEvent).data) as {
        id?: string;
        percent?: number | null;
        progress?: number;
        stage?: string | null;
        status?: string;
        detail?: string | null;
        result?: Record<string, unknown>;
      };
      if (payload.id !== jobId) return;
      const progress = payload.percent ?? Math.round((payload.progress ?? 0) * 100);
      const status = payload.status === "completed" ? "complete" : payload.status;
      onEvent({
        progress,
        step: payload.stage ?? undefined,
        status,
        log: payload.detail ?? undefined,
        result: payload.result,
      });
    } catch {
      /* ignore malformed events */
    }
  });
  es.onerror = () => es.close();
  return () => es.close();
}

// ---------- Knowledge (search + grounded QA) ----------

interface HitDto {
  id: string;
  score: number;
  text: string;
  locator: Record<string, unknown>;
  metadata: Record<string, unknown>;
}

function hitToPassage(hit: HitDto): Passage {
  const loc = hit.locator ?? {};
  return {
    id: hit.id,
    assetId: String(loc["asset_id"] ?? ""),
    assetName: String(loc["title"] ?? loc["source"] ?? loc["asset_id"] ?? "segment"),
    page: typeof loc["page"] === "number" ? (loc["page"] as number) : undefined,
    text: hit.text,
    score: +Number(hit.score).toFixed(2),
  };
}

const tokenize = (s: string) =>
  s
    .toLowerCase()
    .split(/[^a-z0-9\u0600-\u06FF]+/)
    .filter((w) => w.length > 2);

export async function groundedAsk(question: string, mode: QAResult["mode"], threshold: number): Promise<QAResult> {
  if (gatewayUp) {
    const r = await post<{
      text: string;
      abstained: boolean;
      abstention_reason: string | null;
      sources: HitDto[];
      citations: { segment_id: string }[];
    }>("/ask", { question, mode: "grounded_qa" });
    const passages = (r.sources ?? []).map(hitToPassage);
    const topScore = passages[0]?.score ?? 0;
    return {
      question,
      mode,
      abstained: r.abstained,
      answer: r.text,
      confidence: +Math.min(0.99, topScore * 0.95).toFixed(2),
      topScore,
      citations: passages.slice(0, 3),
      caveats: r.abstention_reason ? [r.abstention_reason] : [],
    };
  }
  if (DEMO_MODE) {
    await sleep(900);
    const qt = tokenize(question);
    const scored: Passage[] = samplePassages
      .map((p) => {
        const pt = new Set(tokenize(p.text + " " + p.assetName));
        const overlap = qt.filter((w) => pt.has(w)).length;
        const lexical = qt.length ? overlap / Math.sqrt(qt.length) : 0;
        const dense = p.score * Math.min(1, 0.35 + lexical);
        const score = mode === "keyword" ? Math.min(0.99, lexical * 0.9) : mode === "semantic" ? dense : Math.min(0.99, dense * 0.6 + lexical * 0.5);
        return { ...p, score: +score.toFixed(2) };
      })
      .sort((a, b) => b.score - a.score);
    const top = scored[0]?.score ?? 0;
    if (top < threshold) {
      return { question, mode, abstained: true, confidence: top, topScore: top, citations: scored.slice(0, 3), caveats: ["No passage exceeds grounding threshold."] };
    }
    const cites = scored.filter((p) => p.score >= threshold * 0.8).slice(0, 3);
    const answer = cites.map((c, i) => `${c.text.split(/(?<=[.;])\s/)[0]} [${i + 1}]`).join(" ");
    return {
      question,
      mode,
      abstained: false,
      answer,
      confidence: +(top * 0.95).toFixed(2),
      topScore: top,
      citations: cites,
      caveats: ["Demo mode — figures come from the bundled sample workspace, not a live index."],
    };
  }
  // Designed abstention state — never a crash (platform invariant).
  return { question, mode, abstained: true, confidence: 0, topScore: 0, citations: [], caveats: ["Gateway offline — start the gateway and retry."] };
}

/** Hybrid search over the active workspace index (async — real gateway call). */
export async function hybridSearch(query: string): Promise<Passage[]> {
  if (gatewayUp) {
    try {
      const r = await post<{ hits: HitDto[] }>("/search", { query, mode: "hybrid", top_n: 8, top_k: 40 });
      return (r.hits ?? []).map(hitToPassage);
    } catch (err) {
      console.warn("hybridSearch failed:", err);
      return [];
    }
  }
  if (DEMO_MODE) {
    const qt = tokenize(query);
    return samplePassages
      .map((p) => {
        const pt = new Set(tokenize(p.text + " " + p.assetName));
        const overlap = qt.filter((w) => pt.has(w)).length;
        return { ...p, score: +Math.min(0.99, p.score * (0.3 + overlap / Math.max(1, qt.length))).toFixed(2) };
      })
      .sort((a, b) => b.score - a.score);
  }
  console.warn("hybridSearch: gateway offline — returning no results");
  return [];
}

// ---------- Collections / index / assets (live ingest) ----------

interface CollectionDto {
  id: string;
  name: string;
  description?: string | null;
  archived?: boolean;
}

export async function listCollections(): Promise<Collection[]> {
  const rows = await get<CollectionDto[]>("/collections");
  return rows.map((c) => ({ id: c.id, name: c.name, description: c.description ?? undefined, archived: c.archived }));
}

export async function getIndexManifest(): Promise<IndexManifest> {
  const r = await get<{ space_id: string; manifest: Record<string, unknown> | null; exists: boolean }>("/index/manifest");
  const m = r.manifest ?? {};
  const num = (v: unknown) => (typeof v === "number" ? v : undefined);
  return {
    spaceId: r.space_id,
    exists: r.exists,
    totalVectors: num(m["total_vectors"] ?? m["vectors"]),
    totalSegments: num(m["total_segments"] ?? m["segments"]),
    modalities: Array.isArray(m["modalities"]) ? (m["modalities"] as string[]) : undefined,
  };
}

interface AssetDto {
  id: string;
  title?: string | null;
  kind?: string;
  mime_type?: string | null;
  modality?: string | null;
  collection_id?: string;
  created_at?: string;
  sha256?: string;
  segment_count?: number;
  size_bytes?: number;
}

export async function listAssets(): Promise<import("./types").Asset[]> {
  const rows = await get<AssetDto[]>("/assets");
  return rows.map((a) => {
    const name = a.title ?? a.id;
    const ext = name.toLowerCase().split(".").pop() ?? "";
    const type = ext === "pdf" ? "pdf" : ext === "tif" || ext === "tiff" ? "tif" : ext === "geojson" || ext === "json" ? "geojson" : "csv";
    const modality = a.modality === "vision" || a.modality === "image" ? "vision" : a.modality === "vector" ? "vector" : a.modality === "table" ? "table" : "text";
    return {
      id: a.id,
      name,
      type,
      sha256: a.sha256 ?? "",
      segments: a.segment_count ?? 0,
      sizeBytes: a.size_bytes ?? 0,
      modality,
      addedAt: a.created_at ? Date.parse(a.created_at) || Date.now() : Date.now(),
    };
  });
}

/** Live ingest: multipart POST /ingest → 202 {job_id}. */
export async function ingestFile(file: File, collectionId: string): Promise<{ job_id: string }> {
  requireGateway("file ingest");
  const form = new FormData();
  form.append("file", file);
  form.append("collection_id", collectionId);
  form.append("index_after", "true");
  const r = await fetch(`${API_BASE}/api/v1/ingest`, { method: "POST", body: form });
  if (!r.ok) {
    let detail = `${r.status} ${r.statusText}`;
    try {
      const envelope = (await r.json()) as { error?: { message?: string } };
      if (envelope.error?.message) detail = envelope.error.message;
    } catch {
      /* keep status-line detail */
    }
    throw new Error(`POST /ingest → ${detail}`);
  }
  return r.json();
}

// ---------- Feedback candidates / review queue ----------

interface CandidateDto {
  id: string;
  content: string;
  memory_type?: string;
  state?: string;
  author?: string | null;
}

function candidateToReview(c: CandidateDto): import("./types").ReviewItem {
  let parsed: Record<string, unknown> = {};
  try {
    parsed = JSON.parse(c.content) as Record<string, unknown>;
  } catch {
    parsed = {};
  }
  const crop = typeof parsed["crop_type"] === "string" ? (parsed["crop_type"] as string) : undefined;
  const region = typeof parsed["region"] === "string" ? (parsed["region"] as string) : undefined;
  const label = parsed["label"];
  const prediction = crop ?? (label === 0 ? "fallow" : label === 1 ? "wheat" : String(label ?? "unknown"));
  const state = c.state ?? "pending";
  const status = state === "rejected" ? "rejected" : state === "supported" || state === "verified" ? "accepted" : "pending";
  return {
    id: c.id,
    kind: crop ? "classification" : "qa",
    subject: crop && region ? `Parcel (${crop} · ${region})` : c.id,
    prediction,
    confidence: 0,
    status,
    key: crop && region ? `${crop}__${region}` : undefined,
    provenance: typeof parsed["asset_id"] === "string" ? { assetId: parsed["asset_id"] as string } : undefined,
  };
}

export async function listCandidates(): Promise<import("./types").ReviewItem[]> {
  const rows = await get<CandidateDto[]>("/feedback/candidates");
  return rows.map(candidateToReview);
}

export async function reviewCandidate(id: string, newState: "supported" | "verified" | "rejected", note?: string): Promise<void> {
  await post(`/feedback/candidates/${encodeURIComponent(id)}/review`, { new_state: newState, reviewer_id: "studio", note });
}

export async function recordFeedback(targetType: "answer" | "retrieval_run" | "segment" | "citation", targetId: string, label: string, payload: Record<string, unknown> = {}): Promise<void> {
  await post("/feedback", { target_type: targetType, target_id: targetId, label, actor: "studio", payload, metadata: {} });
}

// ---------- Model versions / rollback ----------

interface VersionDto {
  key: string[];
  version: number;
  timestamp: string;
  n_samples: number;
  sha256: string;
}

export async function listModelVersions(): Promise<import("./types").ModelVersion[]> {
  const r = await get<{ versions: VersionDto[] }>("/models/versions");
  return r.versions.map((v, i) => ({
    id: `gw-${v.key.join("-")}-v${v.version}-${i}`,
    version: `${v.key.join("-")}@v${v.version}`,
    createdAt: Date.parse(v.timestamp) || Date.now(),
    valAcc: 0,
    delta: 0,
    trainSeconds: 0,
    samples: v.n_samples,
    algorithm: "geolearn online classifier",
    active: i === 0,
    key: [v.key[0] ?? "", v.key[1] ?? ""],
    versionNumber: v.version,
    sha256: v.sha256,
  }));
}

export async function rollbackModel(key: [string, string], version: number): Promise<void> {
  await post("/models/rollback", { key, version });
}

// ---------- ROIs (gateway store, shared with roi_create tool) ----------

interface RoiDto {
  id: string;
  name: string;
  kind: "bbox" | "polygon";
  coords: [number, number][];
  areaHa: number;
  centroid: [number, number];
  createdAt: number;
}

export async function listRois(): Promise<import("./types").ROI[]> {
  const r = await get<{ rois: RoiDto[] }>("/rois");
  return r.rois.map((x) => ({ id: x.id, name: x.name, kind: x.kind, coords: x.coords, areaHa: x.areaHa, centroid: x.centroid, createdAt: x.createdAt }));
}

export async function createRoiRemote(roi: { name: string; kind: "bbox" | "polygon"; coords: [number, number][] }): Promise<import("./types").ROI> {
  const r = await post<RoiDto>("/rois", roi);
  return { id: r.id, name: r.name, kind: r.kind, coords: r.coords, areaHa: r.areaHa, centroid: r.centroid, createdAt: r.createdAt };
}

export async function deleteRoiRemote(id: string): Promise<void> {
  requireGateway("DELETE /rois");
  const r = await fetch(`${API_BASE}/api/v1/rois/${encodeURIComponent(id)}`, { method: "DELETE" });
  if (!r.ok) throw new Error(`DELETE /rois/${id} → ${r.status} ${r.statusText}`);
}

// ---------- Health / agent ----------

export async function getHealth(): Promise<{ llmKeyConfigured: boolean; workspaceOpen: boolean }> {
  const r = await get<{ llm?: { key_configured?: boolean }; workspace?: { status?: string } }>("/health");
  return { llmKeyConfigured: r.llm?.key_configured ?? false, workspaceOpen: r.workspace?.status === "open" };
}

export interface AgentStreamEvent {
  event: string;
  text?: string;
  tool?: string;
  status?: string;
  code?: string;
  message?: string;
  conversationId?: string;
}

/** Stream agent chat over POST /agent/chat (SSE via fetch — EventSource cannot POST). */
export async function streamAgentChat(
  message: string,
  onEvent: (e: AgentStreamEvent) => void,
  conversationId?: string,
): Promise<void> {
  requireGateway("agent chat");
  const r = await fetch(`${API_BASE}/api/v1/agent/chat`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ message, conversation_id: conversationId }),
  });
  if (!r.ok || !r.body) {
    let detail = `${r.status} ${r.statusText}`;
    try {
      const envelope = (await r.json()) as { error?: { message?: string } };
      if (envelope.error?.message) detail = envelope.error.message;
    } catch {
      /* keep status-line detail */
    }
    throw new Error(`POST /agent/chat → ${detail}`);
  }
  const reader = r.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const frames = buffer.split("\n\n");
    buffer = frames.pop() ?? "";
    for (const frame of frames) {
      const lines = frame.split("\n");
      let event = "message";
      let data = "";
      for (const line of lines) {
        if (line.startsWith("event:")) event = line.slice(6).trim();
        else if (line.startsWith("data:")) data += line.slice(5).trim();
      }
      if (!data) continue;
      try {
        const payload = JSON.parse(data) as Record<string, unknown>;
        onEvent({
          event,
          text: typeof payload["text"] === "string" ? (payload["text"] as string) : undefined,
          tool: typeof payload["tool"] === "string" ? (payload["tool"] as string) : undefined,
          status: typeof payload["status"] === "string" ? (payload["status"] as string) : undefined,
          code: typeof payload["code"] === "string" ? (payload["code"] as string) : undefined,
          message: typeof payload["message"] === "string" ? (payload["message"] as string) : undefined,
          conversationId: typeof payload["conversation_id"] === "string" ? (payload["conversation_id"] as string) : undefined,
        });
      } catch {
        /* ignore malformed frames */
      }
    }
  }
}

export async function listAgentTools(): Promise<AgentTool[]> {
  const r = await get<{ tools: { name: string; description: string; timeout_s?: number; cacheable?: boolean }[] }>("/agent/tools");
  return r.tools.map((t) => ({ name: t.name, description: t.description, timeoutS: t.timeout_s, cacheable: t.cacheable }));
}

export async function listPlaybooks(): Promise<Playbook[]> {
  const r = await get<{ playbooks: Playbook[] }>("/agent/playbooks");
  return r.playbooks;
}

export async function runPlaybook(name: string, params: Record<string, unknown> = {}): Promise<Record<string, unknown>> {
  return post<Record<string, unknown>>(`/agent/playbooks/${encodeURIComponent(name)}/run`, { params });
}

export async function savePlaybook(name: string, content: string): Promise<void> {
  await post("/agent/playbooks/save", { name, content });
}

// ---------- Pure helpers (unit-tested) ----------

/** Citation numbers referenced in text, e.g. [1] [2] → [1, 2]. */
export function parseCitationRefs(text: string): number[] {
  const out: number[] = [];
  for (const m of text.matchAll(/\[(\d+)\]/g)) out.push(Number(m[1]));
  return out;
}

/**
 * Strip `[n]` refs that have no matching source (1-based) and return the
 * cleaned text plus the invalid numbers. Valid refs are left untouched.
 */
export function stripInvalidCitations(text: string, validCount: number): { text: string; invalid: number[] } {
  const invalid: number[] = [];
  const cleaned = text.replace(/\[(\d+)\]/g, (match, n: string) => {
    const num = Number(n);
    if (num >= 1 && num <= validCount) return match;
    if (!invalid.includes(num)) invalid.push(num);
    return "";
  });
  return { text: cleaned.replace(/\s{2,}/g, " ").trim(), invalid };
}

/** Cold-start graduation threshold (samples) for the online classifier. */
export const GRADUATION_SAMPLES = 30;

/** Samples still needed before the classifier graduates from NN fallback. */
export function samplesToGraduation(labelled: number): number {
  return Math.max(0, GRADUATION_SAMPLES - Math.max(0, labelled));
}

/** True while the classifier is in cold-start (nearest-neighbour fallback). */
export function isColdStart(labelled: number): boolean {
  return samplesToGraduation(labelled) > 0;
}

/** Per-key readiness counts over review items (labelled vs pending). */
export function readinessByKey(items: import("./types").ReviewItem[]): { key: string; labelled: number; pending: number }[] {
  const map = new Map<string, { labelled: number; pending: number }>();
  for (const item of items) {
    const key = item.key ?? item.prediction;
    const row = map.get(key) ?? { labelled: 0, pending: 0 };
    if (item.status === "pending") row.pending += 1;
    else row.labelled += 1;
    map.set(key, row);
  }
  return [...map.entries()].map(([key, v]) => ({ key, ...v })).sort((a, b) => b.labelled - a.labelled);
}

/** True when a prediction must render as an explicit abstention. */
export function predictionAbstained(confidence: number, threshold: number): boolean {
  return confidence < threshold;
}
