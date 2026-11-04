import { useEffect, useMemo, useState } from "react";
import { Bot, ChevronDown, ChevronRight, Crosshair, Eye, EyeOff, Layers, MapPin, Pentagon, Send, Square, Trash2, X } from "lucide-react";
import { useStore, ringArea, type Basemap } from "@/lib/store";
import { MapCanvas, bboxRing, type DrawMode } from "@/components/MapCanvas";
import { Button, Badge, Field, inputCls, Mono } from "@/components/ui";
import { cn } from "@/utils/cn";
import type { MapLayer } from "@/lib/types";

const GROUPS: { id: MapLayer["group"]; key: "scenes" | "indices" | "vectors" | "rois" }[] = [
  { id: "scenes", key: "scenes" },
  { id: "indices", key: "indices" },
  { id: "vectors", key: "vectors" },
  { id: "rois", key: "rois" },
];

export function MapView() {
  const s = useStore();
  const [drawMode, setDrawMode] = useState<DrawMode>(null);
  const [draft, setDraft] = useState<[number, number][]>([]);
  const [finished, setFinished] = useState<[number, number][] | null>(null);
  const [name, setName] = useState("");
  const [cursor, setCursor] = useState<[number, number] | null>(null);
  const [open, setOpen] = useState<Record<string, boolean>>({ scenes: true, indices: true, vectors: true, rois: true });
  const roiLayer = s.layers.find((l) => l.group === "rois");
  const roisVisible = roiLayer?.visible ?? true;

  const ring = finished ?? (drawMode === "bbox" && draft.length === 2 ? bboxRing(draft[0], draft[1]) : drawMode === "polygon" && draft.length >= 3 ? [...draft, draft[0]] : null);
  const stats = useMemo(() => (ring ? ringArea(ring) : null), [ring]);

  const finish = () => {
    if (drawMode === "bbox" && draft.length === 2) setFinished(bboxRing(draft[0], draft[1]));
    else if (drawMode === "polygon" && draft.length >= 3) setFinished([...draft, draft[0]]);
    else return;
    setName(`${s.workspace.split("-")[0]}-roi-${s.rois.length + 1}`);
  };
  useEffect(() => {
    if (drawMode === "bbox" && draft.length === 2 && !finished) finish();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [drawMode, draft, finished]);
  const reset = () => {
    setDrawMode(null);
    setDraft([]);
    setFinished(null);
  };
  const saveRoi = (then?: "acquire" | "agent") => {
    if (!finished || !stats) return;
    const roi = s.addRoi({ name: name || "untitled-roi", kind: drawMode === "bbox" ? "bbox" : "polygon", coords: finished, areaHa: stats.areaHa, centroid: stats.centroid });
    reset();
    if (then === "acquire") s.setView("acquire");
    if (then === "agent") {
      s.setRailOpen(true);
      s.setAgentDraft(`Summarize vegetation condition and water use for ROI "${roi.name}" (${stats.areaHa.toFixed(0)} ha).`);
    }
  };

  return (
    <div className="flex h-full min-h-0">
      {/* Layer tree */}
      <aside className="flex w-72 shrink-0 flex-col border-e border-line bg-surface">
        <div className="flex items-center justify-between border-b border-line px-3 py-2">
          <div className="flex items-center gap-1.5 text-[12px] font-semibold uppercase tracking-wide text-muted">
            <Layers className="h-3.5 w-3.5" /> {s.t("layers")}
          </div>
          <select value={s.basemap} onChange={(e) => s.setBasemap(e.target.value as Basemap)} className="h-6 rounded border border-line bg-canvas px-1 text-[11px]">
            <option value="satellite">{s.t("satellite")}</option>
            <option value="topo">{s.t("topo")}</option>
            <option value="gray">{s.t("gray")}</option>
          </select>
        </div>
        <div className="scroll-thin min-h-0 flex-1 overflow-y-auto">
          {GROUPS.map((g) => {
            const items = g.id === "rois" ? [] : s.layers.filter((l) => l.group === g.id);
            return (
              <div key={g.id} className="border-b border-line">
                <button onClick={() => setOpen((o) => ({ ...o, [g.id]: !o[g.id] }))} className="flex w-full items-center gap-1 px-2 py-1.5 text-[12.5px] font-medium hover:bg-canvas">
                  {open[g.id] ? <ChevronDown className="h-3.5 w-3.5 text-muted" /> : <ChevronRight className="h-3.5 w-3.5 text-muted rtl:rotate-180" />}
                  {s.t(g.key)}
                  <span className="ms-auto text-[11px] text-muted">{s.fmt.num(g.id === "rois" ? s.rois.length : items.length)}</span>
                </button>
                {open[g.id] && g.id !== "rois" && (
                  <ul className="pb-1">
                    {items.map((l) => (
                      <li key={l.id} className="px-2 py-1">
                        <div className="flex items-center gap-1.5">
                          <button onClick={() => s.updateLayer(l.id, { visible: !l.visible })} className="text-muted hover:text-ink">
                            {l.visible ? <Eye className="h-3.5 w-3.5 text-brand" /> : <EyeOff className="h-3.5 w-3.5" />}
                          </button>
                          {l.color && <span className="h-2.5 w-2.5 rounded-sm" style={{ background: l.color }} />}
                          <span className={cn("flex-1 truncate text-[12px]", !l.visible && "text-muted")} title={l.name}>
                            {l.name}
                          </span>
                          <Mono className="text-[10px] text-muted">{Math.round(l.opacity * 100)}%</Mono>
                        </div>
                        {l.visible && (
                          <div className="ms-5 mt-1 flex items-center gap-2">
                            <input type="range" min={0} max={1} step={0.01} value={l.opacity} onChange={(e) => s.updateLayer(l.id, { opacity: +e.target.value })} className="h-1 flex-1" dir="ltr" />
                          </div>
                        )}
                        {l.visible && l.legend && (
                          <div className="ms-5 mt-1.5">
                            <div className="h-2 rounded-sm" style={{ background: `linear-gradient(to right, ${l.legend.stops.map((st) => st.color).join(",")})` }} dir="ltr" />
                            <div className="mt-0.5 flex justify-between font-mono text-[9.5px] text-muted" dir="ltr">
                              {l.legend.stops.map((st) => (
                                <span key={st.value}>{st.value}</span>
                              ))}
                            </div>
                          </div>
                        )}
                      </li>
                    ))}
                  </ul>
                )}
                {open[g.id] && g.id === "rois" && (
                  <ul className="pb-1">
                    <li className="flex items-center gap-1.5 px-2 py-1 text-[11px] text-muted">
                      <button
                        onClick={() => roiLayer && s.updateLayer(roiLayer.id, { visible: !roisVisible })}
                        className="hover:text-ink"
                      >
                        {roisVisible ? <Eye className="h-3.5 w-3.5 text-brand" /> : <EyeOff className="h-3.5 w-3.5" />}
                      </button>
                      {s.t("epsg")}
                    </li>
                    {s.rois.map((r) => (
                      <li key={r.id} className={cn("group flex items-center gap-1.5 px-2 py-1 text-[12px]", r.id === s.activeRoiId && "bg-brand-50")}>
                        <button
                          onClick={() => {
                            s.setActiveRoi(r.id);
                            s.requestFly(r.centroid);
                          }}
                          className="flex flex-1 items-center gap-1.5 truncate text-start"
                        >
                          <Crosshair className={cn("h-3.5 w-3.5", r.id === s.activeRoiId ? "text-warn" : "text-muted")} />
                          <span className="truncate font-mono text-[11.5px]">{r.name}</span>
                        </button>
                        <span className="text-[10.5px] text-muted">{s.fmt.num(r.areaHa, { maximumFractionDigits: 0 })} ha</span>
                        <button onClick={() => s.removeRoi(r.id)} className="invisible text-muted hover:text-bad group-hover:visible">
                          <Trash2 className="h-3 w-3" />
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            );
          })}
        </div>

        {/* Draw ROI tool */}
        <div className="border-t border-line bg-canvas/60 p-3">
          <div className="mb-2 flex items-center gap-1.5 text-[12px] font-semibold uppercase tracking-wide text-muted">
            <Pentagon className="h-3.5 w-3.5" /> {s.t("drawRoi")}
          </div>
          {!finished ? (
            <>
              <div className="grid grid-cols-2 gap-1.5">
                <Button size="sm" variant={drawMode === "bbox" ? "primary" : "secondary"} onClick={() => { setDrawMode("bbox"); setDraft([]); }}>
                  <Square className="h-3.5 w-3.5" /> {s.t("drawBox")}
                </Button>
                <Button size="sm" variant={drawMode === "polygon" ? "primary" : "secondary"} onClick={() => { setDrawMode("polygon"); setDraft([]); }}>
                  <Pentagon className="h-3.5 w-3.5" /> {s.t("drawPolygon")}
                </Button>
              </div>
              {drawMode && (
                <div className="mt-2 flex items-center gap-1.5">
                  <span className="flex-1 text-[11px] text-muted">
                    {drawMode === "bbox" ? "Click two corners" : `${draft.length} pts · dbl-click to close`}
                  </span>
                  {drawMode === "polygon" && (
                    <Button size="sm" variant="primary" disabled={draft.length < 3} onClick={finish}>
                      {s.t("finish")}
                    </Button>
                  )}
                  <Button size="sm" variant="ghost" onClick={reset}>
                    <X className="h-3.5 w-3.5" />
                  </Button>
                </div>
              )}
            </>
          ) : (
            <div className="space-y-2">
              <Field label={s.t("roiName")}>
                <input value={name} onChange={(e) => setName(e.target.value)} className={cn(inputCls, "font-mono")} dir="ltr" />
              </Field>
              <div className="grid grid-cols-2 gap-2 text-[11px]">
                <div>
                  <div className="text-muted">{s.t("area")}</div>
                  <div className="font-mono">{s.fmt.num(stats!.areaHa, { maximumFractionDigits: 1 })} ha</div>
                  <div className="font-mono text-muted">{s.fmt.num(stats!.areaHa / 100, { maximumFractionDigits: 2 })} km²</div>
                </div>
                <div>
                  <div className="text-muted">{s.t("centroid")}</div>
                  <Mono>{stats!.centroid[1].toFixed(4)}, {stats!.centroid[0].toFixed(4)}</Mono>
                  <div className="font-mono text-[10px] text-muted">{s.t("epsg")}</div>
                </div>
              </div>
              <Button variant="primary" className="w-full" onClick={() => saveRoi()}>
                <MapPin className="h-3.5 w-3.5" /> {s.t("saveRoi")}
              </Button>
              <div className="grid grid-cols-2 gap-1.5">
                <Button size="sm" onClick={() => saveRoi("acquire")}>
                  <Send className="h-3.5 w-3.5" /> {s.t("sendToAcquire")}
                </Button>
                <Button size="sm" onClick={() => saveRoi("agent")}>
                  <Bot className="h-3.5 w-3.5" /> {s.t("agent")}
                </Button>
              </div>
              <Button size="sm" variant="ghost" className="w-full" onClick={reset}>
                {s.t("cancel")}
              </Button>
            </div>
          )}
        </div>
      </aside>

      {/* Canvas */}
      <div className="relative min-w-0 flex-1">
        <MapCanvas drawMode={drawMode} draft={draft} setDraft={setDraft} onFinish={finish} onCursor={setCursor} />
        {/* Active ROI chip */}
        {s.activeRoi && (
          <div className="absolute start-3 top-3 flex items-center gap-2 rounded-md border border-line bg-surface/95 px-2.5 py-1.5 shadow-sm backdrop-blur">
            <Crosshair className="h-3.5 w-3.5 text-warn" />
            <span className="text-[11px] text-muted">{s.t("activeRoi")}</span>
            <Mono className="font-medium">{s.activeRoi.name}</Mono>
            <Badge tone="neutral">{s.fmt.num(s.activeRoi.areaHa, { maximumFractionDigits: 0 })} ha</Badge>
            <Button size="sm" variant="ghost" onClick={() => s.setView("acquire")} title={s.t("sendToAcquire")}>
              <Send className="h-3.5 w-3.5" />
            </Button>
            <Button
              size="sm"
              variant="ghost"
              title={s.t("askAgent")}
              onClick={() => {
                s.setRailOpen(true);
                s.setAgentDraft(`What does the literature say about water use in ROI "${s.activeRoi!.name}"?`);
              }}
            >
              <Bot className="h-3.5 w-3.5" />
            </Button>
          </div>
        )}
        {/* Coordinate readout (always LTR) */}
        <div className="absolute bottom-3 start-3 rounded border border-line bg-surface/95 px-2 py-1 font-mono text-[10.5px] text-muted" dir="ltr">
          {cursor ? `${cursor[1].toFixed(5)}°N  ${cursor[0].toFixed(5)}°E` : "—"} · EPSG:4326
        </div>
      </div>
    </div>
  );
}
