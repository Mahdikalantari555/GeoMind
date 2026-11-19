import { useState } from "react";
import { AlertTriangle, Check, Cpu, History, Pencil, RotateCcw, X, Zap } from "lucide-react";
import { useStore } from "@/lib/store";
import { isColdStart, predictionAbstained, readinessByKey, samplesToGraduation } from "@/lib/api";
import { Badge, Button, Card, inputCls, Mono, PageHeader, Progress } from "@/components/ui";
import { cn } from "@/utils/cn";

const CROPS = ["wheat", "sugarcane", "maize", "fallow", "orchard"];

export function TrainingView() {
  const s = useStore();
  const [editing, setEditing] = useState<string | null>(null);
  const [val, setVal] = useState("");
  const [note, setNote] = useState("");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const pending = s.review.filter((r) => r.status === "pending");
  const labelled = s.review.filter((r) => r.status === "accepted" || r.status === "corrected");
  const active = s.versions.find((v) => v.active);
  const liveJob = s.online ? s.jobs.find(j => j.kind === "train") : undefined;
  const ts = s.trainingState;
  const cold = isColdStart(labelled.length);
  const toGraduation = samplesToGraduation(labelled.length);
  const readiness = readinessByKey(s.review);
  const threshold = s.settings.classifierThreshold;

  const toggleSelect = (id: string) =>
    setSelected((cur) => {
      const next = new Set(cur);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

  const bulk = (status: "accepted" | "rejected") => {
    for (const id of selected) s.reviewAction(id, status, undefined, note || undefined);
    setSelected(new Set());
    setNote("");
  };

  return (
    <div className="scroll-thin h-full overflow-y-auto p-5">
      <PageHeader
        title={s.t("nav_training")}
        subtitle="geolearn · Correct → Learn · CPU-frugal online partial_fit, seconds not hours"
        actions={
          <>
            <Badge tone="neutral">
              <Cpu className="h-3 w-3" /> CPU · 4 threads
            </Badge>
            {labelled.length === 0 ? <Button onClick={() => document.getElementById("review-queue")?.scrollIntoView()}>0 eligible · Review feedback</Button> : <Button variant="primary" onClick={() => s.trainNow()} disabled={ts?.running || liveJob?.status === "running" || liveJob?.status === "queued"}>
              <Zap className="h-3.5 w-3.5" /> {ts?.running ? s.t("training") : `${s.t("trainNow")} (${s.fmt.num(labelled.length)})`}
            </Button>}
          </>
        }
      />
      <label>Classifier confidence: {threshold.toFixed(2)} <input type="range" min="0" max="1" step="0.01" value={threshold} onChange={e => s.updateSettings({classifierThreshold:+e.target.value})} /></label>
      {cold && (
        <div className="mb-4 flex items-start gap-2.5 rounded-lg border border-warn/40 bg-warn-50 p-3 text-[12.5px] text-warn">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
          <div>
            <span className="font-semibold">{s.t("coldStart")}.</span>{" "}
            {s.fmt.num(toGraduation)} {s.t("samplesToGraduation")} — predictions below the confidence threshold render as explicit abstentions.
          </div>
        </div>
      )}
      <div className="grid gap-4 xl:grid-cols-[1fr_380px]">
        <Card
          title={
            <span className="flex items-center gap-2">
              <span id="review-queue">{s.t("reviewQueue")}</span> <Badge tone="warn">{s.fmt.num(pending.length)} {s.t("pending")}</Badge>
            </span>
          }
          actions={
            pending.length > 0 ? (
              <div className="flex items-center gap-1.5">
                <button
                  className="text-[11px] text-muted underline hover:text-ink"
                  onClick={() => setSelected(new Set(pending.map((r) => r.id)))}
                >
                  {s.t("selectAll")}
                </button>
                <input
                  value={note}
                  onChange={(e) => setNote(e.target.value)}
                  placeholder={s.t("reviewNote")}
                  className={cn(inputCls, "h-7 w-44 text-[12px]")}
                />
                <Button size="sm" className="text-ok" disabled={selected.size === 0} onClick={() => bulk("accepted")}>
                  <Check className="h-3.5 w-3.5" /> {s.t("bulkAccept")} ({s.fmt.num(selected.size)})
                </Button>
                <Button size="sm" className="text-bad" disabled={selected.size === 0} onClick={() => bulk("rejected")}>
                  <X className="h-3.5 w-3.5" /> {s.t("bulkReject")}
                </Button>
              </div>
            ) : undefined
          }
        >
          <ul className="divide-y divide-line">
            {s.review.map((r) => (
              <li key={r.id} className={cn("flex flex-wrap items-center gap-3 px-3 py-2.5", r.status !== "pending" && "bg-canvas/50")}>
                {r.status === "pending" && (
                  <input type="checkbox" checked={selected.has(r.id)} onChange={() => toggleSelect(r.id)} aria-label={`${s.t("selected")} ${r.id}`} />
                )}
                <Badge tone={r.kind === "qa" ? "info" : "brand"}>{r.kind === "qa" ? "QA" : "CLS"}</Badge>
                <div className="min-w-0 flex-1">
                  <div className="truncate text-[12.5px] font-medium">{r.subject}</div>
                  <div className="mt-0.5 flex flex-wrap items-center gap-2 text-[11.5px] text-muted">
                    <span>→</span>
                    <Mono className={cn(r.status === "corrected" && "line-through")}>{r.prediction}</Mono>
                    {r.correction && <Mono className="text-ok">{r.correction}</Mono>}
                    <span className="ms-1">· {r.confidence === null ? "—" : s.fmt.pct(r.confidence * 100)}</span>
                    {r.confidence !== null && predictionAbstained(r.confidence, threshold) && (
                      <Badge tone="warn">{s.t("predictionAbstention")}</Badge>
                    )}
                    {r.provenance?.assetId && (
                      <span className="text-[10.5px] text-muted">
                        {s.t("provenanceChain")}: <Mono>{r.provenance.assetId}</Mono>
                      </span>
                    )}
                  </div>
                </div>
                {r.status === "pending" ? (
                  editing === r.id ? (
                    <div className="flex items-center gap-1.5">
                      {r.kind === "classification" ? (
                        <select value={val} onChange={(e) => setVal(e.target.value)} className={cn(inputCls, "h-7 w-32 text-[12px]")}>
                          <option value="">—</option>
                          {CROPS.map((c) => (
                            <option key={c}>{c}</option>
                          ))}
                        </select>
                      ) : (
                        <input value={val} onChange={(e) => setVal(e.target.value)} className={cn(inputCls, "h-7 w-56 text-[12px]")} placeholder="corrected answer" />
                      )}
                      <Button size="sm" variant="primary" disabled={!val} onClick={() => { s.reviewAction(r.id, "corrected", val, note || undefined); setEditing(null); }}>
                        <Check className="h-3.5 w-3.5" />
                      </Button>
                      <Button size="sm" variant="ghost" onClick={() => setEditing(null)}>
                        <X className="h-3.5 w-3.5" />
                      </Button>
                    </div>
                  ) : (
                    <div className="flex items-center gap-1.5">
                      <Button size="sm" className="text-ok" onClick={() => s.reviewAction(r.id, "accepted", undefined, note || undefined)}>
                        <Check className="h-3.5 w-3.5" /> {s.t("accept")}
                      </Button>
                      <Button size="sm" className="text-bad" onClick={() => s.reviewAction(r.id, "rejected", undefined, note || undefined)}>
                        <X className="h-3.5 w-3.5" /> {s.t("reject")}
                      </Button>
                      <Button size="sm" onClick={() => { setEditing(r.id); setVal(""); }}>
                        <Pencil className="h-3.5 w-3.5" /> {s.t("correct")}
                      </Button>
                    </div>
                  )
                ) : (
                  <Badge tone={r.status === "accepted" ? "ok" : r.status === "rejected" ? "bad" : "info"}>{r.status}</Badge>
                )}
              </li>
            ))}
          </ul>
        </Card>

        <div className="space-y-4">
          <Card title={s.t("readiness")}>
            <ul className="divide-y divide-line">
              {readiness.map((row) => (
                <li key={row.key} className="flex items-center gap-2 px-3 py-2 text-[12px]">
                  <Mono className="font-medium text-ink">{row.key}</Mono>
                  <span className="ms-auto text-muted">
                    {s.fmt.num(row.labelled)} {s.t("samples")} · {s.fmt.num(row.pending)} {s.t("pending")}
                  </span>
                  {row.labelled >= 30 ? (
                    <Badge tone="ok">{s.t("trainLink")}</Badge>
                  ) : (
                    <Badge tone="warn">{s.fmt.num(samplesToGraduation(row.labelled))} {s.t("samplesToGraduation")}</Badge>
                  )}
                </li>
              ))}
            </ul>
          </Card>

          <Card title="partial_fit">
            <div className="p-3">
              {s.online ? <div role="status">{liveJob ? <>{liveJob.title} · {liveJob.status} · {liveJob.progress}%<Progress value={liveJob.progress}/>{liveJob.logs.at(-1)}</> : "No training job yet"}</div> : ts ? (
                <>
                  <div className="flex items-center justify-between text-[12px]">
                    <span className="text-muted">batch</span>
                    <Mono>{s.fmt.num(ts.batch)} / 6</Mono>
                  </div>
                  <Progress value={(ts.batch / 6) * 100} className="mt-1.5" tone={ts.running ? "brand" : "ok"} />
                  <div className="mt-3 grid grid-cols-3 gap-2 text-center">
                    <div className="rounded-md bg-canvas p-2">
                      <div className="text-[10px] uppercase text-muted">loss</div>
                      <Mono className="text-[13px] font-medium">{ts.loss.toFixed(3)}</Mono>
                    </div>
                    <div className="rounded-md bg-canvas p-2">
                      <div className="text-[10px] uppercase text-muted">{s.t("valAcc")}</div>
                      <Mono className="text-[13px] font-medium">{s.fmt.pct(ts.acc * 100, 1)}</Mono>
                    </div>
                    <div className="rounded-md bg-canvas p-2">
                      <div className="text-[10px] uppercase text-muted">{s.t("delta")}</div>
                      <Mono className={cn("text-[13px] font-medium", "text-ok")}>+{((ts.acc - (s.versions[1]?.valAcc ?? s.versions[0]?.valAcc ?? ts.acc)) * 100).toFixed(1)}%</Mono>
                    </div>
                  </div>
                  <div className="mt-2 h-10 rounded-md bg-ink p-1.5 font-mono text-[10px] leading-tight text-emerald-300" dir="ltr">
                    {ts.running ? `[geolearn] SGDClassifier.partial_fit(batch=${ts.batch}, classes=5) loss=${ts.loss.toFixed(3)}` : `[geolearn] checkpoint saved → ${active?.version}`}
                  </div>
                </>
              ) : (
                <p className="text-[12px] text-muted">Label items in the review queue, then run <Mono>POST /api/v1/models/train</Mono>. Expected wall time ≈ 1–3 s on CPU.</p>
              )}
            </div>
          </Card>

          <Card
            title={
              <span className="flex items-center gap-2">
                <History className="h-3.5 w-3.5" /> {s.t("versions")}
              </span>
            }
          >
            <ul className="divide-y divide-line">
              {s.versions.map((v) => (
                <li key={v.id} className={cn("px-3 py-2.5", v.active && "bg-brand-50/50")}>
                  <div className="flex items-center gap-2">
                    <Mono className="font-medium text-ink">{v.version}</Mono>
                    {v.active && <Badge tone="brand">{s.t("active")}</Badge>}
                    <span className="ms-auto text-[11px] text-muted">{s.fmt.date(v.createdAt, { month: "short", day: "2-digit", hour: "2-digit", minute: "2-digit" })}</span>
                  </div>
                  <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11.5px] text-muted">
                    <span>
                      {s.t("valAcc")} <Mono className="text-ink">{v.versionNumber ? "—" : s.fmt.pct(v.valAcc * 100, 1)}</Mono>
                    </span>
                    <Mono className={v.delta >= 0 ? "text-ok" : "text-bad"}>
                      {v.versionNumber ? "—" : `${v.delta >= 0 ? "+" : ""}${v.delta.toFixed(1)}%`}
                    </Mono>
                    <span>
                      {s.t("trainTime")} <Mono className="text-ink">{v.versionNumber ? "—" : `${v.trainSeconds}s`}</Mono>
                    </span>
                    <span>
                      n=<Mono className="text-ink">{v.samples}</Mono>
                    </span>
                    {!v.active && (
                      <Button size="sm" variant="ghost" className="ms-auto h-6 px-1.5" onClick={() => s.rollback(v.id)}>
                        <RotateCcw className="h-3 w-3" /> {s.t("rollback")}
                      </Button>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          </Card>
        </div>
      </div>
    </div>
  );
}
