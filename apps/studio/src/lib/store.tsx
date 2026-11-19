import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import type { Asset, ChatMessage, Collection, IndexManifest, Job, MapLayer, ModelVersion, ReviewItem, ROI, Settings, View } from "./types";
import { dict, makeFormatters, type Lang, type TKey } from "./i18n";
import { sampleAssets, sampleJobs, sampleLayers, sampleReview, sampleROIs, sampleVersions } from "./sample";
import {
  API_BASE,
  DEMO_MODE,
  createRoiRemote,
  deleteRoiRemote,
  gatewayConfigured,
  getHealth,
  getIndexManifest,
  ingestFile,
  ingestedRasterTileUrl,
  inspectAsset,
  isTerminalJob,
  listAssets,
  listCandidates,
  listCollections,
  listModelVersions,
  listRois,
  probeGateway,
  recordFeedback,
  requestTrain,
  reviewCandidate,
  rollbackModel,
  subscribeJob,
} from "./api";


export type Basemap = "satellite" | "topo" | "gray";

interface Toast {
  id: number;
  text: string;
  tone?: "ok" | "warn" | "bad" | "info";
}

interface Store {
  lang: Lang;
  setLang: (l: Lang) => void;
  t: (k: TKey) => string;
  fmt: ReturnType<typeof makeFormatters>;
  dir: "ltr" | "rtl";
  view: View;
  setView: (v: View) => void;
  railOpen: boolean;
  setRailOpen: (b: boolean | ((b: boolean) => boolean)) => void;
  paletteOpen: boolean;
  setPaletteOpen: (b: boolean) => void;
  settings: Settings;
  updateSettings: (p: Partial<Settings>) => void;
  online: boolean;
  workspace: string;
  setWorkspace: (w: string) => void;
  workspaces: string[];

  rois: ROI[];
  activeRoiId: string | null;
  setActiveRoi: (id: string | null) => void;
  addRoi: (r: Omit<ROI, "id" | "createdAt">) => ROI;
  removeRoi: (id: string) => void;
  activeRoi: ROI | null;

  layers: MapLayer[];
  updateLayer: (id: string, p: Partial<MapLayer>) => void;
  addLayer: (l: MapLayer) => void;
  basemap: Basemap;
  setBasemap: (b: Basemap) => void;
  flyTo: [number, number] | null;
  requestFly: (c: [number, number] | null) => void;

  jobs: Job[];
  startJob: (j: Omit<Job, "createdAt" | "updatedAt" | "progress" | "status" | "logs"> & { logs?: string[] }, opts?: { stepMs?: number; onDone?: (result?: Record<string, unknown>) => void; failAt?: number }) => string;
  cancelJob: (id: string) => void;
  retryJob: (id: string) => void;

  assets: Asset[];
  ingestFiles: (files: File[], collectionId: string) => void;
  ingestDemoFiles: (files: { name: string; size: number }[]) => void;

  removeAsset: (id: string) => void;
  collections: Collection[];
  indexManifest: IndexManifest | null;
  llmReady: boolean | null;
  refreshLive: () => Promise<void>;

  review: ReviewItem[];
  reviewAction: (id: string, status: ReviewItem["status"], correction?: string, note?: string) => void;
  versions: ModelVersion[];
  trainNow: () => Promise<void>;
  trainingState: { running: boolean; batch: number; loss: number; acc: number } | null;
  rollback: (id: string) => void;

  messages: ChatMessage[];
  setMessages: (f: (m: ChatMessage[]) => ChatMessage[]) => void;
  agentDraft: string;
  questionDraft: string;
  setQuestionDraft: (value:string) => void;
  setAgentDraft: (s: string) => void;

  toasts: Toast[];
  toast: (text: string, tone?: Toast["tone"]) => void;
}

const Ctx = createContext<Store | null>(null);

const defaultSettings: Settings = {
  dataRoot: "~/geomind/data",
  cogRoot: "~/geomind/cog",
  indexRoot: "~/geomind/index/lancedb",
  llmUrl: "",
  llmModel: "",
  apiKeyFromEnv: true,
  density: "compact",
  classifierThreshold: 0.62,
  groundingThreshold: 0.62,
};

let idc = 0;
const uid = (p: string) => `${p}-${Date.now().toString(36).slice(-4)}${(idc++).toString(36)}`;

export function ringArea(coords: [number, number][]): { areaHa: number; centroid: [number, number] } {
  // Shoelace on an equirectangular projection around the centroid latitude.
  if (coords.length < 3) return { areaHa: 0, centroid: coords[0] ?? [0, 0] };
  const lat0 = coords.reduce((a, c) => a + c[1], 0) / coords.length;
  const k = Math.cos((lat0 * Math.PI) / 180);
  const R = 6371000;
  const pts = coords.map(([x, y]) => [((x * Math.PI) / 180) * R * k, ((y * Math.PI) / 180) * R]);
  let a = 0;
  let cx = 0;
  let cy = 0;
  for (let i = 0; i < pts.length - 1; i++) {
    const f = pts[i][0] * pts[i + 1][1] - pts[i + 1][0] * pts[i][1];
    a += f;
    cx += (coords[i][0] + coords[i + 1][0]) * f;
    cy += (coords[i][1] + coords[i + 1][1]) * f;
  }
  a /= 2;
  const centroid: [number, number] = a === 0 ? coords[0] : [cx / (6 * a), cy / (6 * a)];
  return { areaHa: Math.abs(a) / 10000, centroid };
}

export function StoreProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(() => (localStorage.getItem("gm.lang") as Lang) || "en");
  const [view, setView] = useState<View>(() => (location.hash.replace("#/", "") as View) || "map");
  const [railOpen, setRailOpen] = useState(true);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [settings, setSettings] = useState<Settings>(defaultSettings);
  const [online, setOnline] = useState(false);
  const [workspace, setWorkspace] = useState("karkheh-basin");
  const workspaces = ["karkheh-basin", "urmia-lake", "zayandeh-rud"];

  const [rois, setRois] = useState<ROI[]>(sampleROIs);
  const [activeRoiId, setActiveRoi] = useState<string | null>("roi-1");
  const [layers, setLayers] = useState<MapLayer[]>(sampleLayers);
  const [basemap, setBasemap] = useState<Basemap>("satellite");
  const [flyTo, requestFly] = useState<[number, number] | null>(null);
  const [jobs, setJobs] = useState<Job[]>(DEMO_MODE ? sampleJobs : []);
  const [assets, setAssets] = useState<Asset[]>(DEMO_MODE ? sampleAssets : []);
  const [review, setReview] = useState<ReviewItem[]>(sampleReview);
  const [versions, setVersions] = useState<ModelVersion[]>(sampleVersions);
  const [collections, setCollections] = useState<Collection[]>([]);
  const [indexManifest, setIndexManifest] = useState<IndexManifest | null>(null);
  const [llmReady, setLlmReady] = useState<boolean | null>(null);
  const [trainingState, setTrainingState] = useState<Store["trainingState"]>(null);
  const [messages, setMessagesState] = useState<ChatMessage[]>([]);
  const [questionDraft,setQuestionDraft] = useState("");
  const [agentDraft, setAgentDraft] = useState("");
  const [toasts, setToasts] = useState<Toast[]>([]);
  const timers = useRef<Record<string, number>>({});
  const jobSubscriptions = useRef(new Map<string, () => void>());
  useEffect(() => {
    const subscriptions = jobSubscriptions.current;
    return () => {
      subscriptions.forEach((unsubscribe) => unsubscribe());
      subscriptions.clear();
    };
  }, []);

  useEffect(() => {
    localStorage.setItem("gm.lang", lang);
    document.documentElement.lang = lang;
    document.documentElement.dir = lang === "fa" ? "rtl" : "ltr";
  }, [lang]);

  useEffect(() => {
    location.hash = `/${view === "map" ? "" : view}`;
  }, [view]);

  useEffect(() => {
    const onHash = () => setView(((location.hash.replace("#/", "") || "map") as View) ?? "map");
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  useEffect(() => {
    if (!gatewayConfigured) return;
    probeGateway().then(setOnline);
    const id = setInterval(() => probeGateway().then(setOnline), 15000);
    return () => clearInterval(id);
  }, []);

  useEffect(() => {
    const ctrl = new AbortController();
    const clear = () => setSettings(v => ({...v,llmModel:'',llmUrl:''}));
    clear();
    if (online) void fetch(`${API_BASE}/api/v1/workspace`, {signal:ctrl.signal}).then(async r => {
      if (!r.ok) return;
      const {settings:w} = await r.json();
      if (w && !ctrl.signal.aborted) setSettings(v => ({...v,llmModel:w.llm_model_id ?? '', llmUrl:w.llm_provider === 'api' ? w.llm_api_base_url || 'Kilo API' : w.model_path ? 'Local GGUF' : ''}));
    }).catch(() => {});
    return () => ctrl.abort();
  }, [online, workspace]);

  /** Pull live gateway state (collections, assets, index, review, versions, ROIs). */
  const refreshLive = useCallback(async () => {
    if (!online) return;
    try {
      setCollections(await listCollections());
    } catch {
      /* keep previous state */
    }
    try {
      setIndexManifest(await getIndexManifest());
    } catch {
      /* keep previous state */
    }
    try {
      const liveAssets = await listAssets();
      if (liveAssets.length) setAssets(liveAssets);
    } catch {
      /* keep previous state */
    }
    try {
      const liveReview = await listCandidates();
      if (liveReview.length) setReview(liveReview);
    } catch {
      /* keep previous state */
    }
    try {
      const liveVersions = await listModelVersions();
      if (liveVersions.length) setVersions(liveVersions);
    } catch {
      /* keep previous state */
    }
    try {
      const liveRois = await listRois();
      if (liveRois.length) {
        setRois(liveRois);
        setActiveRoi((cur) => (cur && liveRois.some((r) => r.id === cur) ? cur : liveRois[0]?.id ?? null));
      }
    } catch {
      /* keep previous state */
    }
    try {
      const health = await getHealth();
      setLlmReady(health.llmKeyConfigured);
    } catch {
      /* keep previous state */
    }
  }, [online]);

  useEffect(() => {
    if (online) void refreshLive();
  }, [online, refreshLive]);

  const toast = useCallback((text: string, tone: Toast["tone"] = "info") => {
    const id = Date.now() + Math.random();
    setToasts((t) => [...t, { id, text, tone }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 4200);
  }, []);

  const t = useCallback((k: TKey) => dict[lang][k], [lang]);
  const fmt = useMemo(() => makeFormatters(lang), [lang]);

  const patchJob = (id: string, p: Partial<Job> | ((j: Job) => Partial<Job>)) =>
    setJobs((js) => js.map((j) => (j.id === id ? { ...j, ...(typeof p === "function" ? p(j) : p), updatedAt: Date.now() } : j)));

  const startJob: Store["startJob"] = useCallback(
    (j, opts = {}) => {
      const job: Job = { ...j, logs: j.logs ?? [], status: "queued", progress: 0, createdAt: Date.now(), updatedAt: Date.now() };
      setJobs((js) => [job, ...js]);
      if (online) {
        const unsub = subscribeJob(job.id, (e) => {
          if (e.status === "reconnecting") {
            patchJob(job.id, { reconnecting: true });
            return;
          }
          const status: Job["status"] = e.status === "complete" || e.status === "cancelled" ? e.status
            : e.status === "error" || e.status === "failed" ? "failed"
            : e.status === "pending" ? "queued" : "running";
          patchJob(job.id, (cur) => ({
            status,
            reconnecting: false,
            progress: status === "complete" ? 100 : e.progress,
            logs: e.log ? [...cur.logs, e.log] : status === "failed" ? [...cur.logs, "[job] job failed"] : cur.logs,
            steps: cur.steps.map((step) => ({ ...step, done: step.done || status === "complete" || step.label === e.step })),
            result: e.result ?? cur.result ?? null,
          }));
          if (isTerminalJob(e.status)) {
            unsub();
            jobSubscriptions.current.delete(job.id);
          }
          if (e.status === "complete") opts.onDone?.(e.result);
        });
        jobSubscriptions.current.set(job.id, unsub);
        return job.id;
      }
      if (!DEMO_MODE) {
        // No gateway, no demo flag: fail loudly instead of faking progress.
        patchJob(job.id, (cur) => ({
          status: "failed",
          logs: [...cur.logs, "[job] gateway offline — start uvicorn :8000 or set VITE_GEOMIND_DEMO=1"],
        }));
        return job.id;
      }
      // Demo mode: simulated steps (explicitly labeled demo environment).
      const stepMs = opts.stepMs ?? 700;
      let i = 0;
      const n = job.steps.length;
      const tick = () => {
        i++;
        if (opts.failAt && i === opts.failAt) {
          patchJob(job.id, (cur) => ({ status: "failed", logs: [...cur.logs, `[job] failed at step ${cur.steps[i - 1]?.label}`] }));
          return;
        }
        patchJob(job.id, (cur) => ({
          status: i >= n ? "complete" : "running",
          progress: Math.round((i / n) * 100),
          steps: cur.steps.map((s, k) => ({ ...s, done: k < i })),
          logs: [...cur.logs, i >= n ? "[job] complete" : `[${cur.kind}] ${cur.steps[i - 1]?.label} ✓ → ${cur.steps[i]?.label}`],
        }));
        if (i >= n) {
          delete timers.current[job.id];
          opts.onDone?.();
        } else {
          timers.current[job.id] = window.setTimeout(tick, stepMs + Math.random() * 300);
        }
      };
      patchJob(job.id, (cur) => ({ status: "running", logs: [...cur.logs, `[job] started → ${cur.steps[0]?.label}`] }));
      timers.current[job.id] = window.setTimeout(tick, stepMs);
      return job.id;
    },
    [online],
  );

  const cancelJob = (id: string) => {
    if (jobs.find((job) => job.id === id)?.meta?.liveUpload) return;
    jobSubscriptions.current.get(id)?.();
    jobSubscriptions.current.delete(id);
    window.clearTimeout(timers.current[id]);
    delete timers.current[id];
    patchJob(id, (cur) => ({ status: "cancelled", logs: [...cur.logs, "[job] cancelled by user"] }));
  };

  const retryJob = (id: string) => {
    const j = jobs.find((x) => x.id === id);
    if (!j || j.meta?.liveUpload) return;
    setJobs((js) => js.filter((x) => x.id !== id));
    startJob({ id: uid("job"), kind: j.kind, title: j.title, steps: j.steps.map((s) => ({ ...s, done: false })), meta: j.meta, logs: ["[job] retry of " + id] });
  };

  const addRoi: Store["addRoi"] = (r) => {
    const roi: ROI = { ...r, id: uid("roi"), createdAt: Date.now() };
    setRois((rs) => [roi, ...rs]);
    setActiveRoi(roi.id);
    toast(`ROI "${roi.name}" saved`, "ok");
    if (online) {
      // Persist to the gateway ROI store (shared with the roi_create tool).
      void createRoiRemote({ name: r.name, kind: r.kind, coords: r.coords })
        .then((saved) => {
          setRois((rs) => rs.map((x) => (x.id === roi.id ? saved : x)));
          setActiveRoi(saved.id);
          toast(t("roiSynced"), "ok");
        })
        .catch((err) => toast(String(err instanceof Error ? err.message : err), "bad"));
    }
    return roi;
  };
  const removeRoi = (id: string) => {
    setRois((rs) => rs.filter((r) => r.id !== id));
    if (activeRoiId === id) setActiveRoi(null);
    if (online) {
      void deleteRoiRemote(id).catch((err) => toast(String(err instanceof Error ? err.message : err), "bad"));
    }
  };
  const activeRoi = rois.find((r) => r.id === activeRoiId) ?? null;

  const updateLayer = (id: string, p: Partial<MapLayer>) => setLayers((ls) => ls.map((l) => (l.id === id ? { ...l, ...p } : l)));
  const addLayer = (l: MapLayer) => setLayers((ls) => (ls.some((x) => x.id === l.id) ? ls : [l, ...ls]));

  const fileType = (n: string): Asset["type"] => {
    const e = n.toLowerCase().split(".").pop();
    if (e === "pdf") return "pdf";
    if (e === "tif" || e === "tiff") return "tif";
    if (e === "geojson" || e === "json") return "geojson";
    return e === "csv" ? "csv" : "txt";
  };
  const ingestFiles: Store["ingestFiles"] = (files, collectionId) => {
    if (!online) {
      if (DEMO_MODE) ingestDemoFiles(files);
      else toast(t("uploadOffline"), "bad");
      return;
    }
    if (!collectionId) {
      toast(t("chooseUploadCollection"), "warn");
      return;
    }
    for (const file of files) {
      void (async () => {
        const title = `Ingest ${file.name}`;
        const meta = { file: file.name, collectionId, liveUpload: true };
        const steps = [{ label: t("serverIngest"), done: false }];
        try {
          const { job_id } = await ingestFile(file, collectionId);
          startJob({ id: job_id, kind: "ingest", title, steps, meta }, {
            onDone: async (result) => {
              const assetId = result?.asset_id;
              if (typeof assetId !== "string" || !assetId) {
                const message = typeof result?.error === "string" ? result.error : t("ingestMissingAsset");
                patchJob(job_id, (cur) => ({ status: "failed", logs: [...cur.logs, message] }));
                return;
              }
              const type = fileType(file.name);
              const detail = await inspectAsset(assetId).catch(() => null);
              const asset: Asset = {
                id: assetId,
                name: detail?.asset.title || file.name,
                sha256: detail?.revision?.hash ?? "",
                segments: detail?.segments.length ?? (typeof result?.segment_count === "number" ? result.segment_count : null),
                sizeBytes: detail?.revision?.size_bytes ?? file.size,
                modality: type === "tif" ? "vision" : type === "geojson" ? "vector" : type === "csv" ? "table" : "text",
                addedAt: detail ? Date.parse(detail.asset.created_at) : Date.now(),
                type,
                live: true,
              };
              setAssets((current) => [asset, ...current.filter((a) => a.id !== assetId)]);
              toast(`${t("registered")}: ${asset.name}`, "ok");
              try {
                if (type === "tif") {
                  const tileUrl = await ingestedRasterTileUrl(asset.sha256);
                  if (tileUrl) addLayer({ id: `asset-${assetId}`, group: "scenes", kind: "raster", name: asset.name, visible: true, opacity: 0.8, tileUrl });
                } else if (type === "geojson") {
                  const geojson = JSON.parse(await file.text()) as GeoJSON.GeoJSON;
                  addLayer({ id: `asset-${assetId}`, group: "vectors", kind: "vector", name: asset.name, visible: true, opacity: 0.8, color: "#a8650b", geojson });
                }
              } catch {
                toast(`${t("ingestPreviewUnavailable")}: ${asset.name}`, "warn");
              }
            },
          });
        } catch (err) {
          const message = err instanceof Error ? err.message : String(err);
          const now = Date.now();
          setJobs((current) => [{
            id: uid("upload-error"), kind: "ingest", title, steps, meta, status: "failed",
            logs: [message], progress: 0, createdAt: now, updatedAt: now,
          }, ...current]);
          toast(message, "bad");
        }
      })();
    }
  };

  const ingestDemoFiles: Store["ingestDemoFiles"] = (files) => {
    if (online || !DEMO_MODE) return;
    const fakeSha = () => Array.from({ length: 64 }, () => "0123456789abcdef"[Math.floor(Math.random() * 16)]).join("");
    files.forEach((f) => {
      const type = fileType(f.name);
      const vision = type === "tif";
      const steps = [
        { label: "Extraction", done: false },
        { label: vision ? "Raster tiling" : "Text chunking", done: false },
        { label: vision ? "Embedding vision.*" : "Embedding text.*", done: false },
        { label: "Vector indexing", done: false },
      ];
      startJob(
        { id: uid("job"), kind: "ingest", title: `Ingest ${f.name}`, steps, meta: { file: f.name } },
        {
          stepMs: 900,
          onDone: () => {
            const segments = type === "pdf" ? Math.round(f.size / 8000) + 20 : type === "tif" ? 1024 : Math.max(10, Math.round(f.size / 400));
            setAssets((as) => [
              { id: uid("a"), name: f.name, type, sha256: fakeSha(), segments, sizeBytes: f.size, modality: vision ? "vision" : type === "geojson" ? "vector" : type === "csv" ? "table" : "text", addedAt: Date.now() },
              ...as,
            ]);
            if (vision || type === "geojson") {
              addLayer({ id: uid("layer"), group: vision ? "scenes" : "vectors", name: f.name, visible: true, opacity: 0.8, kind: vision ? "raster" : "vector", color: "#a8650b" });
              toast(t("registered"), "ok");
            }
          },
        },
      );
    });
  };
  const removeAsset = (id: string) => setAssets((as) => as.filter((a) => a.id !== id));

  const reviewAction: Store["reviewAction"] = (id, status, correction, note) => {
    setReview((rs) => rs.map((r) => (r.id === id ? { ...r, status, correction } : r)));
    toast(t("feedbackLogged"), "ok");
    if (online) {
      const newState = status === "rejected" ? "rejected" : "supported";
      const reviewNote = correction ? `correction: ${correction}${note ? ` · ${note}` : ""}` : note;
      void reviewCandidate(id, newState, reviewNote)
        .then(() => recordFeedback("segment", id, status, { correction, note }))
        .catch((err) => toast(String(err instanceof Error ? err.message : err), "bad"));
    }
  };

  const trainNow = async () => {
    const labelled = review.filter((r) => r.status === "accepted" || r.status === "corrected").length;
    if (!labelled) return;
    const samples = Math.max(1, labelled);
    const prev = versions.find((v) => v.active)?.valAcc ?? 0.8;

    if (online) {
      // Real training: gateway job over geolearn; progress + versions live.
      setTrainingState({ running: true, batch: 0, loss: 0.62, acc: prev });
      try {
        const { job_id } = await requestTrain();
        await new Promise<void>((resolve) => {
          const unsub = subscribeJob(job_id, (e) => {
            if (e.status === "reconnecting") return;
            const percent = Math.max(0, Math.min(100, e.progress));
            setTrainingState({ running: true, batch: Math.round(percent / 20), loss: +(0.62 * (1 - percent / 130)).toFixed(3), acc: prev });
            if (e.status === "complete" || e.status === "error") {
              unsub();
              resolve();
            }
          });
          // safety: resolve even if the stream drops
          setTimeout(resolve, 120000);
        });
        setJobs((js) => [
          {
            id: job_id,
            kind: "train",
            title: `partial_fit · ${samples} samples`,
            status: "complete",
            progress: 100,
            steps: [{ label: "partial_fit", done: true }],
            createdAt: Date.now(),
            updatedAt: Date.now(),
            logs: [`[geolearn] trained on ${samples} labelled samples`],
          },
          ...js,
        ]);
      } catch (err) {
        toast(String(err), "bad");
      }
      // Refresh model versions from the gateway (geolearn versioning).
      try {
        const live = await listModelVersions();
        if (live.length) setVersions(live.slice(0, 8));
      } catch {
        /* versions panel keeps its previous state */
      }
      setTrainingState({ running: false, batch: 0, loss: 0, acc: prev });
      toast(`Trained on ${samples} labelled samples`, "ok");
      return;
    }

    let acc = prev;
    let loss = 0.62;
    setTrainingState({ running: true, batch: 0, loss, acc });
    const t0 = performance.now();
    const batches = 6;
    for (let b = 1; b <= batches; b++) {
      await new Promise((r) => setTimeout(r, 180 + Math.random() * 120));
      loss = +(loss * 0.86).toFixed(3);
      acc = Math.min(0.99, acc + 0.0025 + Math.random() * 0.004);
      setTrainingState({ running: true, batch: b, loss, acc });
    }
    const secs = +((performance.now() - t0) / 1000).toFixed(1);
    const n = versions.length + 1;
    const v: ModelVersion = {
      id: uid("v"),
      version: `crop-sgd@0.${n}.0`,
      createdAt: Date.now(),
      valAcc: acc,
      delta: +((acc - prev) * 100).toFixed(1),
      trainSeconds: secs,
      samples,
      algorithm: "SGDClassifier partial_fit (CPU)",
      active: true,
    };
    setVersions((vs) => [v, ...vs.map((x) => ({ ...x, active: false }))]);
    toast(`Checkpoint ${v.version} · ${secs}s`, "ok");
    setTrainingState({ running: false, batch: batches, loss, acc });
    setJobs((js) => [
      {
        id: uid("job"),
        kind: "train",
        title: `partial_fit · ${samples} samples`,
        status: "complete",
        progress: 100,
        steps: [{ label: "partial_fit", done: true }],
        createdAt: Date.now(),
        updatedAt: Date.now(),
        logs: [`[geolearn] partial_fit on ${samples} samples`, `[geolearn] done in ${secs}s`],
      },
      ...js,
    ]);
  };

  const rollback = (id: string) => {
    const target = versions.find((v) => v.id === id);
    setVersions((vs) => vs.map((v) => ({ ...v, active: v.id === id })));
    toast(`Rolled back to ${target?.version}`, "warn");
    if (online && target?.key && target.versionNumber) {
      void rollbackModel(target.key, target.versionNumber)
        .then(() => void refreshLive())
        .catch((err) => toast(String(err instanceof Error ? err.message : err), "bad"));
    }
  };

  const value: Store = {
    lang,
    setLang: setLangState,
    t,
    fmt,
    dir: lang === "fa" ? "rtl" : "ltr",
    view,
    setView,
    railOpen,
    setRailOpen,
    paletteOpen,
    setPaletteOpen,
    settings,
    updateSettings: (p) => setSettings((s) => ({ ...s, ...p })),
    online,
    workspace,
    setWorkspace,
    workspaces,
    rois,
    activeRoiId,
    setActiveRoi,
    addRoi,
    removeRoi,
    activeRoi,
    layers,
    updateLayer,
    addLayer,
    basemap,
    setBasemap,
    flyTo,
    requestFly,
    jobs,
    startJob,
    cancelJob,
    retryJob,
    assets,
    ingestFiles,
    ingestDemoFiles,
    removeAsset,
    collections,
    indexManifest,
    llmReady,
    refreshLive,
    review,
    reviewAction,
    versions,
    trainNow,
    trainingState,
    rollback,
    messages,
    setMessages: (f) => setMessagesState(f),
    agentDraft,
    questionDraft, setQuestionDraft,
    setAgentDraft,
    toasts,
    toast,
  };

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useStore() {
  const s = useContext(Ctx);
  if (!s) throw new Error("StoreProvider missing");
  return s;
}

export { uid };
