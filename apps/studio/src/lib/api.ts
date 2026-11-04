import type { Scene, QAResult, Passage } from "./types";
import { generateScenes, samplePassages } from "./sample";

export const API_BASE: string | undefined = (import.meta.env.VITE_GEOMIND_API as string | undefined)?.replace(/\/$/, "");

export const gatewayConfigured = Boolean(API_BASE);

let gatewayUp = false;
export const isGatewayUp = () => gatewayUp;

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

async function post<T>(path: string, body: unknown): Promise<T> {
  const r = await fetch(`${API_BASE}/api/v1${path}`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
  return r.json();
}

export const sleep = (ms: number) => new Promise((res) => setTimeout(res, ms));

// ---------- Data engine ----------
export async function searchScenes(params: { roi: [number, number][] | null; sensor: string; from: string; to: string; maxCloud: number }): Promise<Scene[]> {
  if (gatewayUp) {
    const r = await post<{ scenes: Scene[] }>("/data/search", params);
    return r.scenes;
  }
  await sleep(650);
  return generateScenes(params.sensor, params.from, params.to, params.maxCloud);
}

export async function requestDownload(sceneId: string, roi: [number, number][] | null): Promise<{ job_id: string }> {
  if (gatewayUp) return post<{ job_id: string }>("/data/download", { scene_id: sceneId, roi });
  await sleep(200);
  return { job_id: `job-${Math.random().toString(16).slice(2, 6)}` };
}

export async function requestTrain(samples: number): Promise<{ job_id: string }> {
  if (gatewayUp) return post<{ job_id: string }>("/models/train", { strategy: "partial_fit", samples });
  await sleep(120);
  return { job_id: `job-${Math.random().toString(16).slice(2, 6)}` };
}

/** Subscribe to SSE `job.progress` events from the gateway. Returns an unsubscribe fn. */
export function subscribeJob(jobId: string, onEvent: (e: { progress: number; step?: string; status?: string; log?: string }) => void): () => void {
  if (!gatewayUp || !API_BASE) return () => {};
  const es = new EventSource(`${API_BASE}/api/v1/jobs/${jobId}/events`);
  es.addEventListener("job.progress", (ev) => {
    try {
      onEvent(JSON.parse((ev as MessageEvent).data));
    } catch {
      /* ignore */
    }
  });
  es.onerror = () => es.close();
  return () => es.close();
}

// ---------- Knowledge ----------
const tokenize = (s: string) =>
  s
    .toLowerCase()
    .split(/[^a-z0-9\u0600-\u06FF]+/)
    .filter((w) => w.length > 2);

export async function groundedAsk(question: string, mode: QAResult["mode"], threshold: number): Promise<QAResult> {
  if (gatewayUp) return post<QAResult>("/knowledge/ask", { question, mode, threshold });
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
    caveats: ["Figures are reported as published; no re-computation was performed.", "Raster citations refer to tile-level aggregates, not individual pixels."],
  };
}

export function hybridSearch(query: string): Passage[] {
  const qt = tokenize(query);
  return samplePassages
    .map((p) => {
      const pt = new Set(tokenize(p.text + " " + p.assetName));
      const overlap = qt.filter((w) => pt.has(w)).length;
      return { ...p, score: +Math.min(0.99, p.score * (0.3 + overlap / Math.max(1, qt.length))).toFixed(2) };
    })
    .sort((a, b) => b.score - a.score);
}
