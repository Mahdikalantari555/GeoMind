import type { Scene, QAResult, Passage } from "./types";
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
