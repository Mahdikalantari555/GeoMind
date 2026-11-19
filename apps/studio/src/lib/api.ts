import type { AgentTool, Collection, IndexManifest, Playbook, Scene, QAResult, Passage } from "./types";
import { generateScenes, samplePassages } from "./sample";

// Use same-origin requests by default; Vite proxies /api in development.
export const API_BASE: string =
  (import.meta.env.VITE_GEOMIND_API as string | undefined)?.replace(/\/$/, "") ?? "";

/** Demo data is opt-in only (VITE_GEOMIND_DEMO=1) — never a silent fallback. */
export const DEMO_MODE: boolean = (import.meta.env.VITE_GEOMIND_DEMO as string | undefined) === "1";

export const gatewayConfigured = true;

let gatewayUp = false;
export const isGatewayUp = () => gatewayUp;
export const isDemo = () => DEMO_MODE;

export async function probeGateway(): Promise<boolean> {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), 2500);
  try {
    const r = await fetch(`${API_BASE}/api/v1/health`, { signal: ctrl.signal });
    gatewayUp = r.ok;
  } catch {
    gatewayUp = false;
  } finally {clearTimeout(t); }
  return gatewayUp;
}

function requireGateway(op: string): void {
  if (!gatewayUp) {
    throw new Error(
      `${op}: gateway offline — start the gateway (uvicorn geofront_api.main:app --port 8000) or set VITE_GEOMIND_DEMO=1 for the demo workspace`,
    );
  }
}

async function readJson<T>(response: Response, operation: string): Promise<T> {
  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`;
    try {
      const envelope = (await response.json()) as { error?: { message?: string } };
      if (envelope.error?.message) detail = envelope.error.message;
    } catch {
      /* keep status-line detail */
    }
    throw new Error(`${operation} → ${detail}`);
  }
  return response.json();
}

async function post<T>(path: string, body: unknown): Promise<T> {
  requireGateway(`POST ${path}`);
  const response = await fetch(`${API_BASE}/api/v1${path}`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
  return readJson<T>(response, `POST ${path}`);
}

async function get<T>(path: string, signal?: AbortSignal): Promise<T> {
  requireGateway(`GET ${path}`);
  const response = await fetch(`${API_BASE}/api/v1${path}`, { signal });
  return readJson<T>(response, `GET ${path}`);
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

function sceneGeometry(roi: [number,number][] | null){
  if(roi === null) return WORLD_POLYGON;
  const polygon=ringToPolygon(roi);
  if(!polygon || roi.some(([x,y])=>!Number.isFinite(x)||!Number.isFinite(y)||Math.abs(x)>180||Math.abs(y)>90)) throw Error('Invalid ROI');
  return polygon;
}
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
      roi: sceneGeometry(params.roi),
      sensor: sensorKey(params.sensor),
      date_from: params.from,
      date_to: params.to,
      max_cloud: params.maxCloud,
    };
    const r = await post<{ scenes: SceneRefDto[] }>("/data/search", body);
    return r.scenes.map((s) => ({
      id: s.scene_id,
      sensor: s.platform ?? sensorKey(params.sensor),
      acquired: s.datetime,
      cloud: s.cloud_cover,
      sunElev: null,
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
      roi: sceneGeometry(roi),
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
  if (!gatewayUp) return undefined;
  return `${API_BASE}/api/v1/data/tiles/{z}/{x}/{y}.png?path=${encodeURIComponent(relPath)}&bands=${encodeURIComponent(bands)}`;
}

// ---------- Resources and jobs ----------

export interface UploadCollection {
  id: string;
  name: string;
  archived: boolean;
}

export async function listUploadCollections(signal?: AbortSignal): Promise<UploadCollection[]> {
  const collections = await get<UploadCollection[]>("/collections", signal);
  return collections.filter((collection) => !collection.archived);
}

export async function ingestFile(file: File, collectionId: string): Promise<{ job_id: string }> {
  requireGateway("file ingest");
  if (!collectionId) throw new Error("Select an upload collection first.");
  const form = new FormData();
  form.append("file", file);
  form.append("collection_id", collectionId);
  form.append("index_after", "true");
  const response = await fetch(`${API_BASE}/api/v1/ingest`, { method: "POST", body: form });
  return readJson(response, "POST /ingest");
}

export function inspectAsset(assetId: string): Promise<{
  asset: { title: string | null; created_at: string };
  revision: { hash: string; size_bytes: number } | null;
  segments: unknown[];
}> {
  return get(`/assets/${encodeURIComponent(assetId)}`);
}

export async function ingestedRasterTileUrl(hash: string): Promise<string | undefined> {
  if (!/^[a-f0-9]{64}$/.test(hash)) return undefined;
  const { settings } = await get<{ settings: { objects_dir: string } | null }>("/workspace");
  if (!settings) return undefined;
  // Workspace object paths in the gateway's documented SHA-256 layout.
  return tileUrlFor(`${settings.objects_dir}/sha256/${hash.slice(0, 2)}/${hash.slice(2, 4)}/${hash}`);
}

interface JobPayload {
  id: string;
  percent?: number | null;
  progress?: number;
  stage?: string | null;
  status?: string;
  detail?: string | null;
  error?: string | null;
  result?: Record<string, unknown>;
}

interface JobEvent {
  progress: number;
  step?: string;
  status?: string;
  log?: string;
  result?: Record<string, unknown>;
}

export const isTerminalJob = (status?: string) =>
  status === "complete" || status === "error" || status === "failed" || status === "cancelled";

/** Subscribe to job progress; the returned function also stops a subscription early. */
export function subscribeJob(jobId: string, onEvent: (e: JobEvent) => void): () => void {
  if (!gatewayUp) return () => {};
  let es: EventSource | undefined;
  let retry: ReturnType<typeof setTimeout> | undefined;
  let closed = false;
  let seen = 0;
  let snapshot: AbortController | undefined;
  const unsubscribe = () => {
    if (closed) return;
    closed = true;
    snapshot?.abort();
    clearTimeout(retry);
    es?.close();
  };
  const deliver = (payload: JobPayload, snapshotVersion?: number) => {
    if (closed || payload.id !== jobId) return;
    const status = payload.status === "completed" ? "complete" : payload.status;
    const terminal = isTerminalJob(status);
    if (snapshotVersion !== undefined && snapshotVersion !== seen && !terminal) return;
    seen++;
    if (terminal) unsubscribe();
    onEvent({
      progress: payload.percent ?? Math.round((payload.progress ?? 0) * 100),
      step: payload.stage ?? undefined,
      status,
      log: payload.error ?? payload.detail ?? undefined,
      result: payload.result,
    });
  };
  const connect = () => {
    if (closed) return;
    const stream = new EventSource(`${API_BASE}/api/v1/events`);
    es = stream;
    stream.addEventListener("job.progress", (ev) => {
      let payload: JobPayload;
      try {
        payload = JSON.parse((ev as MessageEvent).data) as JobPayload;
      } catch {
        return; // malformed event
      }
      if (payload) deliver(payload);
    });
    stream.onopen = () => {
      if (closed || es !== stream) return;
      // A fast job can finish between the POST and the SSE handshake. The
      // snapshot also picks up events missed during an automatic reconnect.
      snapshot?.abort();
      const ctrl = new AbortController();
      snapshot = ctrl;
      const version = seen;
      const path = `/jobs/${encodeURIComponent(jobId)}`;
      void fetch(`${API_BASE}/api/v1${path}`, { signal: ctrl.signal })
        .then(async (response) => {
          if (response.status === 404) {
            return { id: jobId, status: "error", error: "Job no longer exists on the gateway." };
          }
          return readJson<JobPayload>(response, `GET ${path}`);
        })
        .then((payload) => { if (!ctrl.signal.aborted) deliver(payload, version); })
        .catch(() => { /* the stream remains the primary source of progress */ });
    };
    stream.onerror = () => {
      if (closed || es !== stream) return;
      snapshot?.abort();
      onEvent({ progress: 0, status: "reconnecting" });
      // Transient disconnects use native retry. A failed HTTP handshake (for
      // example the proxy returning 502 while the gateway restarts) can make
      // EventSource CLOSED, which requires a fresh connection.
      if (!closed && stream.readyState === EventSource.CLOSED) retry = setTimeout(connect, 2000);
    };
  };
  connect();
  return unsubscribe;
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

export async function groundedAsk(question: string, mode: QAResult["mode"], threshold: number, options:SearchOptions={}): Promise<QAResult> {
  if (gatewayUp) {
    const r = await post<{
      text: string;
      abstained: boolean;
      abstention_reason: string | null;
      sources: HitDto[];
      citations: { segment_id: string }[];
    }>("/ask", { question, mode: "grounded_qa", min_score:threshold, ...searchFilters(options) });
    const passages = (r.sources ?? []).map(hitToPassage);
    const ids = new Set((r.citations ?? []).map(c=>c.segment_id));
    const cited = passages.filter(hit=>ids.has(hit.id));
    const answer = r.text.replace(/\[(\d+)\]/g, (_,n) => {const item=passages[Number(n)-1]; const index=cited.indexOf(item);return index<0?'':`[${index+1}]`;});
    const topScore = passages[0]?.score ?? 0;
    return {
      question,
      mode,
      abstained: r.abstained,
      answer,
      confidence:null,
      topScore,
      citations: r.abstained ? passages : cited,
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
type SearchOptions = {mode?: QAResult['mode']; collection?: string; from?:string; to?:string; bbox?:string};
function searchFilters({collection,from,to,bbox}:SearchOptions){
  const bounds=bbox?.trim()?bbox.split(',').map(x=>x.trim() ? Number(x) : NaN):null;
  if(bounds && (bounds.length!==4 || bounds.some(x=>!Number.isFinite(x)) || bounds[0]>=bounds[2] || bounds[1]>=bounds[3] || bounds[0]<-180 || bounds[2]>180 || bounds[1]<-90 || bounds[3]>90)) throw Error('Invalid bounding box');
  if(from && to && from>to) throw Error('Invalid date range');
  return {collections:collection?[collection]:undefined, spatial:bounds?{bbox:bounds}:undefined, temporal:from||to?{from:from||undefined,to:to?`${to}T23:59:59.999Z`:undefined}:undefined};
}
export async function hybridSearch(query: string, options:SearchOptions={}): Promise<Passage[]> {
  if (gatewayUp) {
    try {
      const r = await post<{ hits: HitDto[] }>("/search", { query, ...searchFilters(options), mode:options.mode === "keyword" ? "sparse" : options.mode === "semantic" ? "dense" : "hybrid", top_n: 8, top_k: 40 });
      return (r.hits ?? []).map(hitToPassage);
    } catch (err) {
      throw err;
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
    const type = ext === "pdf" ? "pdf" : ext === "tif" || ext === "tiff" ? "tif" : ext === "geojson" || ext === "json" ? "geojson" : ext === "txt" ? "txt" : "csv";
    const modality = a.modality === "vision" || a.modality === "image" ? "vision" : a.modality === "vector" ? "vector" : a.modality === "table" ? "table" : "text";
    return {
      id: a.id,
      live: true,
      name,
      type,
      sha256: a.sha256 ?? "",
      segments: a.segment_count ?? 0,
      sizeBytes: a.size_bytes ?? 0,
      modality,
      addedAt: a.created_at ? Date.parse(a.created_at) : NaN,
    };
  });
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
    confidence: typeof parsed.confidence === "number" && parsed.confidence >= 0 && parsed.confidence <= 1 ? parsed.confidence : null,
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
  active?: boolean;
  timestamp: string;
  n_samples: number;
  sha256: string;
}

export async function listModelVersions(): Promise<import("./types").ModelVersion[]> {
  const r = await get<{ versions: VersionDto[] }>("/models/versions");
  return r.versions.map((v, i) => ({
    id: `gw-${v.key.join("-")}-v${v.version}-${i}`,
    version: `${v.key.join("-")}@v${v.version}`,
    createdAt: Date.parse(v.timestamp),
    valAcc: 0,
    delta: 0,
    trainSeconds: 0,
    samples: v.n_samples,
    algorithm: "geolearn online classifier",
    active: v.active === true,
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
  final?: boolean;
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
  try { for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer = (buffer + decoder.decode(value, { stream: true })).replace(/\r\n/g, "\n");
    const frames = buffer.split("\n\n");
    buffer = frames.pop() ?? "";
    for (const frame of frames) {
      const lines = frame.split("\n");
      let event = "message";
      let data = "";
      for (const line of lines) {
        if (line.startsWith("event:")) event = line.slice(6).trim();
        else if (line.startsWith("data:")) data += line.slice(5).trimStart() + "\n";
      }
      if (!data) continue;
      let payload: Record<string, unknown>;
      try { payload=JSON.parse(data); } catch { continue; }
      if (!payload || typeof payload !== "object") continue;
        onEvent({
          event, final: payload.final === true,
          text: typeof payload["text"] === "string" ? (payload["text"] as string) : undefined,
          tool: typeof payload["tool"] === "string" ? (payload["tool"] as string) : undefined,
          status: typeof payload["status"] === "string" ? (payload["status"] as string) : undefined,
          code: typeof payload["code"] === "string" ? (payload["code"] as string) : undefined,
          message: typeof payload["message"] === "string" ? (payload["message"] as string) : undefined,
          conversationId: typeof payload["conversation_id"] === "string" ? (payload["conversation_id"] as string) : undefined,
        });
    }
  } } finally { await reader.cancel(); reader.releaseLock(); }
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
    else if (item.status === "accepted" || item.status === "corrected") row.labelled += 1;
    map.set(key, row);
  }
  return [...map.entries()].map(([key, v]) => ({ key, ...v })).sort((a, b) => b.labelled - a.labelled);
}

/** True when a prediction must render as an explicit abstention. */
export function predictionAbstained(confidence: number, threshold: number): boolean {
  return confidence < threshold;
}
