import type { Scene, QAResult, Passage } from "./types";
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
