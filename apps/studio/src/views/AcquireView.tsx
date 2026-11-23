import { useEffect, useRef, useState } from "react";
import { Cloud, Crosshair, Download, Loader2, Satellite, Search, Sun } from "lucide-react";
import { useStore, uid } from "@/lib/store";
import { compositeTileUrlFor, previewUrlFor, requestDownload, searchScenes, tileUrlFor } from "@/lib/api";
import type { Scene } from "@/lib/types";
import { Badge, Button, Card, Field, inputCls, Mono, PageHeader, Progress, StatusBadge } from "@/components/ui";
import { cn } from "@/utils/cn";

// Stable ids (translated labels via i18n). Landsat 8 and 9 share one
// Collection 2 L2 option — the backend already unified them.
const SENSORS = [
  { id: "landsat", labelKey: "sensorLandsat" },
  { id: "sentinel", labelKey: "sensorSentinel" },
] as const;

function Thumb({ seed, cloud }: { seed: number; cloud: number }) {
  // deterministic pseudo "quicklook" built from CSS gradients
  const h1 = (seed * 47) % 40 + 70;
  const h2 = (seed * 31) % 30 + 30;
  return (
    <div
      className="relative h-24 w-full overflow-hidden rounded-md border border-line"
      style={{
        background: `radial-gradient(circle at ${(seed * 13) % 100}% ${(seed * 29) % 100}%, hsl(${h1} 35% 40%), transparent 60%), radial-gradient(circle at ${(seed * 71) % 100}% ${(seed * 17) % 100}%, hsl(${h2} 40% 55%), transparent 55%), linear-gradient(135deg, #6b5d45, #8a7a5a 50%, #5a6b4a)`,
      }}
    >
      {Array.from({ length: Math.round(cloud / 12) }).map((_, i) => (
        <span
          key={i}
          className="absolute rounded-full bg-white/80 blur-[3px]"
          style={{ width: 18 + ((seed + i) * 7) % 20, height: 10 + ((seed + i) * 5) % 10, left: `${((seed + 1) * (i + 3) * 17) % 90}%`, top: `${((seed + 2) * (i + 1) * 23) % 80}%` }}
        />
      ))}
    </div>
  );
}

export function ScenePreview({ sc }: { sc: Scene }) {
  const s = useStore();
  const [failed, setFailed] = useState(false);
  const url = previewUrlFor(sc.id, sc.previewUrl ?? "");
  if (sc.synthetic || !url || failed) {
    return (
      <figure>
        <Thumb seed={sc.thumbSeed} cloud={sc.cloud} />
        <figcaption className="text-[10.5px] text-muted">
          {sc.synthetic ? s.t("simulatedPreview") : s.t("previewUnavailable")}
        </figcaption>
      </figure>
    );
  }
  return (
    <figure>
      <img
        src={url}
        alt={`Quicklook for ${sc.id}`}
        onError={() => setFailed(true)}
        className="h-24 w-full rounded-md border border-line object-cover"
      />
    </figure>
  );
}

/** Build the tile URL for an RGB channel selection over a band-file map. */
export function buildTileUrl(
  bandFiles: Record<string, string>,
  choice?: string[],
): string | undefined {
  if (choice && choice.length === 3 && choice.every((n) => bandFiles[n])) {
    return compositeTileUrlFor(choice.map((n) => bandFiles[n]));
  }
  const first = Object.values(bandFiles)[0];
  return first ? tileUrlFor(first) : undefined;
}

const BAND_PRESETS = {
  natural: { bands: ["red", "green", "blue"], key: "bandPresetNatural" },
  falseColor: { bands: ["nir08", "red", "green"], key: "bandPresetFalseColor" },
  swir: { bands: ["swir16", "nir08", "red"], key: "bandPresetSwir" },
} as const;
const CHANNEL_KEYS = { R: "bandR", G: "bandG", B: "bandB" } as const;

export function AcquireView() {
  const s = useStore();
  const [sensor, setSensor] = useState<string>(SENSORS[0].id);
  const [from, setFrom] = useState("2024-03-01");
  const [to, setTo] = useState("2024-06-30");
  const [cloud, setCloud] = useState(30);
  const [loading, setLoading] = useState(false);
  const [scenes, setScenes] = useState<Scene[] | null>(null);
  const [roiFilter, setRoiFilter] = useState<string | null>(null);
  // Per-scene RGB band selection, persisted on the corresponding MapLayer.
  const [bandChoice, setBandChoice] = useState<Record<string, string[]>>({});
  const roi = s.activeRoi;

  const [globalSearch,setGlobalSearch] = useState(false);
  useEffect(() => setGlobalSearch(false), [roi?.id]);
  const [context,setContext] = useState<{roi:typeof roi;sensor:string;from:string;to:string} | null>(null);
  const pendingDownloads=useRef(new Set<string>());
  const invalidDates = !from || !to || from > to;
  const search = async () => {
    if (invalidDates || (!roi && !globalSearch)) return;
    setScenes(null); setContext(null);setLoading(true);
    try {
      setScenes(await searchScenes({ roi: roi?.coords ?? null, sensor, from, to, maxCloud: cloud }));
      setContext({roi,sensor,from,to});
    } catch (err) {
      s.toast(String(err instanceof Error ? err.message : err), "bad");
    } finally {
      setLoading(false);
    }
  };

  const download = async (sc: Scene) => {
    if (!context) return;
    const {roi,sensor,from,to} = context;
    // Dedup on the ROI captured with the search, not whichever ROI happens to
    // be active when the user clicks download (CORRECT-07).
    const key=JSON.stringify([sc.id,context?.roi?.id??null]);
    if(pendingDownloads.current.has(key)) return;
    pendingDownloads.current.add(key);
    let job_id: string;
    try {
      job_id = (await requestDownload(sc.id, roi?.coords ?? null, { sensor, from, to })).job_id;
    } catch (err) {
      s.toast(String(err instanceof Error ? err.message : err), "bad");
      return;
    } finally {pendingDownloads.current.delete(key);}
    const bands = /sentinel|s2/i.test(sc.sensor) ? ["B02", "B03", "B04", "B08"] : ["B2", "B3", "B4", "B5", "B10"];
    s.startJob(
      {
        id: job_id ?? uid("job"),
        kind: "download",
        title: `Download ${sc.id}`,
        steps: [...bands.map((b) => ({ label: b, done: false })), { label: "COG", done: false }, { label: "Ingest", done: false }],
        meta: { sceneId: sc.id, roiId:roi?.id??null },
        logs: [`[stac] resolved ${sc.id}`, `[clip] ROI ${roi?.name ?? "full scene"}`],
      },
      {
        stepMs: 800,
        onDone: (result) => {
          const bandFiles = (result?.band_files ?? {}) as Record<string, string>;
          const bandMap = (result?.band_map ?? {}) as Record<string, string>;
          if (!sc.synthetic && Object.keys(bandFiles).length === 0) {
            s.toast(s.t("downloadNoBand"), "warn");
            return;
          }
          const names = ["R", "G", "B"].map((ch) => bandMap[ch] ?? ch.toLowerCase());
          const choice = names.every((n) => bandFiles[n]) ? names : undefined;
          setBandChoice((prev) => ({ ...prev, [key]: choice ?? [] }));
          s.addLayer({
            id: `scene-${key}`,
            roiId: roi?.id,
            group: "scenes",
            name: `${sc.id.split("_").slice(0, 2).join("_")} band preview`,
            visible: true,
            opacity: 0.85,
            kind: "raster",
            tileUrl: buildTileUrl(bandFiles, choice),
            bandMap: choice
              ? Object.fromEntries(choice.map((n, i) => [["R", "G", "B"][i], n]))
              : undefined,
            bandPaths: bandFiles,
          });
          s.toast(`${s.t("registered")}: ${sc.id}`, "ok");
        },
      },
    );
    s.toast(`202 Accepted · job ${job_id}`, "info");
  };

  const jobFor = (sc: Scene) => s.jobs.find((j) => j.kind === "download" && j.meta?.sceneId === sc.id && (j.meta.roiId??null)===(context?.roi?.id??null) && j.status !== "cancelled");

  function changeBands(layerId: string, key: string, channel: number, bandName: string) {
    const layer = s.layers.find((l) => l.id === layerId);
    if (!layer?.bandPaths) return;
    const current = bandChoice[key] ?? ["red", "green", "blue"];
    const next = [...current];
    next[channel] = bandName;
    setBandChoice((prev) => ({ ...prev, [key]: next }));
    s.updateLayer(layerId, {
      tileUrl: buildTileUrl(layer.bandPaths, next),
      bandMap: Object.fromEntries(next.map((n, i) => [["R", "G", "B"][i], n])),
    });
  }

  const visible = scenes?.filter((sc) => !roiFilter || sc.id.includes(roiFilter)) ?? null;

  return (
    <div className="scroll-thin h-full overflow-y-auto p-5">
      <PageHeader title={s.t("nav_acquire")} subtitle="Data Engine · STAC scene search → clipped COG download → auto-register" />
      <div className="grid gap-4 lg:grid-cols-[320px_1fr]">
        <Card title={s.t("searchScenes")} className="h-fit">
          <div className="space-y-3 p-3">
            <Field label={s.t("activeRoi")}>
              {roi ? (
                <div className="flex items-center gap-2 rounded-md border border-warn/30 bg-warn-50 px-2.5 py-1.5">
                  <Crosshair className="h-3.5 w-3.5 text-warn" />
                  <Mono className="flex-1 font-medium">{roi.name}</Mono>
                  <span className="text-[11px] text-muted">{s.fmt.num(roi.areaHa, { maximumFractionDigits: 0 })} ha</span>
                </div>
              ) : (
                <div className="rounded-md border border-dashed border-line p-2.5 text-[12px] text-muted">
                  {s.t("noRoi")}{" "}
                  <button className="text-brand underline" onClick={() => s.setView("map")}>
                    {s.t("goToMap")}
                  </button>
                </div>
              )}
              {s.rois.length > 1 && (
                <select value={roi?.id ?? ""} onChange={(e) => s.setActiveRoi(e.target.value || null)} className={cn(inputCls, "mt-1.5 font-mono text-[12px]")}>
                  {s.rois.map((r) => (
                    <option key={r.id} value={r.id}>
                      {r.name}
                    </option>
                  ))}
                </select>
              )}
            </Field>
            {!roi && <label><input type="checkbox" checked={globalSearch} onChange={e => setGlobalSearch(e.target.checked)} /> {s.t("searchGlobally")}</label>}
            <Field label={s.t("sensor")}>
              <select value={sensor} onChange={(e) => setSensor(e.target.value)} className={inputCls}>
                {SENSORS.map((x) => (
                  <option key={x.id} value={x.id}>{s.t(x.labelKey)}</option>
                ))}
              </select>
            </Field>
            <Field label={s.t("dateRange")}>
              <div className="grid grid-cols-2 gap-1.5" dir="ltr">
                <input aria-label={s.lang === "fa" ? "تاریخ شروع" : "Start date"} type="date" value={from} onChange={(e) => setFrom(e.target.value)} className={cn(inputCls, "font-mono text-[12px]")} />
                <input aria-label={s.lang === "fa" ? "تاریخ پایان" : "End date"} type="date" value={to} onChange={(e) => setTo(e.target.value)} className={cn(inputCls, "font-mono text-[12px]")} />
              </div>
            </Field>
            <Button size="sm" onClick={() => { const end = new Date(); const start = new Date(end); start.setUTCDate(start.getUTCDate() - 29); setFrom(start.toISOString().slice(0,10)); setTo(end.toISOString().slice(0,10)); }}>Last 30 days</Button>
            {invalidDates && <p role="alert">Select a valid start and end date in chronological order.</p>}
            <Field label={`${s.t("cloudCover")} · ${s.fmt.pct(cloud)}`}>
              <input type="range" min={0} max={100} value={cloud} onChange={(e) => setCloud(+e.target.value)} className="w-full" dir="ltr" />
            </Field>
            <Button variant="primary" className="w-full" onClick={search} disabled={loading || invalidDates || (!roi && !globalSearch)}>
              {loading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Search className="h-3.5 w-3.5" />}
              {s.t("searchScenes")}
            </Button>
            <p className="font-mono text-[10.5px] text-muted" dir="ltr">
              POST /api/v1/data/search
            </p>
          </div>
        </Card>

        <div>
          {visible === null ? (
            <div className="grid h-64 place-items-center rounded-lg border border-dashed border-line text-muted">
              <div className="text-center">
                <Satellite className="mx-auto mb-2 h-8 w-8 text-line" />
                <p className="text-[12.5px]">Run a search to list scenes intersecting the active ROI.</p>
              </div>
            </div>
          ) : (
            <>
              <div className="mb-2 flex items-center gap-2 text-[12px] text-muted">
                <span>
                  {s.fmt.num(visible.length)} {s.t("results")}
                </span>
                <input placeholder={s.t("filterById")} value={roiFilter ?? ""} onChange={(e) => setRoiFilter(e.target.value || null)} className="ms-auto h-7 w-44 rounded-md border border-line bg-surface px-2 font-mono text-[11px]" dir="ltr" />
              </div>
              {visible.length === 0 && (scenes?.length ? <p>{s.t("noMatchingIds")} <Button onClick={() => setRoiFilter(null)}>{s.t("clearFilter")}</Button></p> : <p>{s.t("noScenesFound")}</p>)}
              <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                {visible.map((sc) => {
                  const job = jobFor(sc);
                  return (
                    <Card key={sc.id} className="overflow-hidden">
                      <div className="p-2.5">
                        <ScenePreview sc={sc} />
                        <Mono className="mt-2 block truncate text-[11px] font-medium text-ink" >
                          {sc.id}
                        </Mono>
                        <div className="mt-1.5 flex flex-wrap items-center gap-1.5 text-[11px] text-muted">
                          <Badge tone="neutral">{s.fmt.date(sc.acquired)} {s.fmt.time(sc.acquired,true)}</Badge>
                          <Badge tone={sc.cloud < 10 ? "ok" : sc.cloud < 30 ? "warn" : "bad"}>
                            <Cloud className="h-3 w-3" /> {s.fmt.pct(sc.cloud)}
                          </Badge>
                          <Badge tone="neutral">
                            <Sun className="h-3 w-3" /> {sc.sunElev === null ? "—" : `${s.fmt.num(sc.sunElev)}°`}
                          </Badge>
                        </div>
                        <div className="mt-2.5">
                          {job ? (
                            <div>
                              <div className="flex items-center justify-between">
                                <StatusBadge status={job.status} label={s.t(job.status)} />
                                <Mono className="text-muted">{s.fmt.num(job.progress)}%</Mono>
                              </div>
                              <Progress value={job.progress} className="mt-1.5" tone={job.status === "failed" ? "bad" : job.status === "complete" ? "ok" : "brand"} />
                              <div className="mt-1.5 flex flex-wrap gap-1" dir="ltr">
                                {job.steps.map((st) => (
                                  <span key={st.label} className={cn("rounded px-1 font-mono text-[9.5px]", st.done ? "bg-ok-50 text-ok" : "bg-canvas text-muted")}>
                                    {st.label}
                                  </span>
                                ))}
                              </div>
                              {job.status === "failed" && (
                                <Button size="sm" className="mt-2 w-full" disabled={!!job.meta?.serverJob && !s.online} onClick={() => s.online ? download(sc) : s.retryJob(job.id)}>
                                  {s.t("retry")}
                                </Button>
                              )}
                            </div>
                          ) : (
                            <Button size="sm" variant="primary" className="w-full" onClick={() => download(sc)}>
                              <Download className="h-3.5 w-3.5" /> {s.t("download")}
                            </Button>
                          )}
                          {(() => {
                            const key = JSON.stringify([sc.id, context?.roi?.id ?? null]);
                            const layerId = `scene-${key}`;
                            const layer = s.layers.find((l) => l.id === layerId);
                            if (!layer?.bandPaths) return null;
                            const available = Object.keys(layer.bandPaths);
                            const choice = bandChoice[key] ?? ["red", "green", "blue"];
                            return (
                              <div className="mt-3 border-t border-line pt-2">
                                <div className="flex items-center justify-between gap-1">
                                  <span className="text-[11px] text-muted">{s.t("editBands")}</span>
                                  <div className="flex gap-1">
                                    {Object.entries(BAND_PRESETS).map(([id, preset]) => (
                                      <Button
                                        key={id}
                                        size="sm"
                                        onClick={() => {
                                          const names = preset.bands.filter((n) => layer.bandPaths?.[n]);
                                          if (names.length === 3) {
                                            setBandChoice((prev) => ({ ...prev, [key]: [...names] }));
                                            s.updateLayer(layerId, {
                                              tileUrl: buildTileUrl(layer.bandPaths!, [...names]),
                                              bandMap: Object.fromEntries(names.map((n, i) => [["R", "G", "B"][i], n])),
                                            });
                                          }
                                        }}
                                      >
                                        {s.t(preset.key)}
                                      </Button>
                                    ))}
                                  </div>
                                </div>
                                <div className="mt-1.5 grid grid-cols-3 gap-1">
                                  {(["R", "G", "B"] as const).map((channel, i) => (
                                    <label key={channel} className="flex flex-col gap-0.5 text-[10.5px] text-muted">
                                      {s.t(CHANNEL_KEYS[channel])}
                                      <select
                                        aria-label={`${s.t("bandFor")} ${channel}`}
                                        className={inputCls}
                                        value={choice[i] ?? ""}
                                        onChange={(e) => changeBands(layerId, key, i, e.target.value)}
                                      >
                                        {available.map((name) => (
                                          <option key={name} value={name}>{name}</option>
                                        ))}
                                      </select>
                                    </label>
                                  ))}
                                </div>
                              </div>
                            );
                          })()}
                        </div>
                      </div>
                    </Card>
                  );
                })}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
