import { useRef, useState } from "react";
import { Database, FileText, Image as ImageIcon, Map as MapIcon, RotateCcw, Table2, Trash2, UploadCloud, ShieldAlert } from "lucide-react";
import { useStore } from "@/lib/store";
import { Badge, Button, Card, Field, fmtBytes, inputCls, Mono, PageHeader, Progress, StatusBadge } from "@/components/ui";
import type { Asset } from "@/lib/types";
import { cn } from "@/utils/cn";

const typeIcon: Record<Asset["type"], typeof FileText> = { pdf: FileText, tif: ImageIcon, geojson: MapIcon, csv: Table2 };
const modalityTone: Record<Asset["modality"], "info" | "brand" | "warn" | "ok"> = { text: "info", vision: "brand", vector: "warn", table: "ok" };

const ACCEPTED_EXT = /\.(pdf|tiff?|geojson|csv)$/i;

/** Split dropped files into accepted + rejected (per-file error reason). */
export function splitFiles(files: File[]): { accepted: File[]; rejected: { name: string; reason: string }[] } {
  const accepted: File[] = [];
  const rejected: { name: string; reason: string }[] = [];
  for (const f of files) {
    if (ACCEPTED_EXT.test(f.name)) accepted.push(f);
    else rejected.push({ name: f.name, reason: `unsupported extension — accepted: .pdf, .tif/.tiff, .geojson, .csv` });
  }
  return { accepted, rejected };
}

export function ResourcesView() {
  const s = useStore();
  const [drag, setDrag] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const [del, setDel] = useState<Asset | null>(null);
  const [confirm, setConfirm] = useState("");
  const [rejected, setRejected] = useState<{ name: string; reason: string }[]>([]);
  const ingestJobs = s.jobs.filter((j) => j.kind === "ingest" && j.status !== "complete").slice(0, 6);
  const failedJobs = s.jobs.filter((j) => j.kind === "ingest" && j.status === "failed");

  const handleFiles = (list: FileList | null) => {
    if (!list) return;
    const { accepted, rejected: bad } = splitFiles(Array.from(list));
    setRejected(bad);
    if (bad.length) s.toast(`${s.t("unsupportedType")}: ${bad.map((b) => b.name).join(", ")}`, "warn");
    if (!accepted.length) return;
    s.ingestFiles(accepted.map((f) => ({ name: f.name, size: f.size, file: f })));
  };

  const addDemo = () => s.ingestFiles([{ name: "Bastiaanssen_1998_SEBAL.pdf", size: 2_410_000 }, { name: "S2B_38SNA_20240503_B08.tif", size: 182_000_000 }]);

  const totalBytes = s.assets.reduce((a, x) => a + x.sizeBytes, 0);
  const manifest = s.indexManifest;

  return (
    <div className="scroll-thin h-full overflow-y-auto p-5">
      <PageHeader
        title={s.t("nav_resources")}
        subtitle="Ingestion manager · modality-isolated embeddings (text.* vs vision.*) · content-addressed by SHA-256"
        actions={
          <>
            {s.online && (
              <Button size="sm" onClick={() => void s.refreshLive()}>
                <RotateCcw className="h-3.5 w-3.5" /> {s.t("syncRois")}
              </Button>
            )}
            <Button size="sm" onClick={addDemo}>
              {s.t("demoFiles")}
            </Button>
          </>
        }
      />
      {s.online && (
        <div className="mb-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <Card title={s.t("collections")}>
            <div className="p-3 text-[12px]">
              {s.collections.length === 0 ? (
                <span className="text-muted">—</span>
              ) : (
                <ul className="space-y-1">
                  {s.collections.map((c) => (
                    <li key={c.id} className="flex items-center gap-2">
                      <Database className="h-3.5 w-3.5 text-muted" />
                      <Mono className="font-medium text-ink">{c.name}</Mono>
                      {c.archived && <Badge tone="neutral">archived</Badge>}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </Card>
          <Card title={s.t("indexStats")}>
            <div className="p-3 text-[12px]">
              {manifest?.exists ? (
                <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1">
                  <dt className="text-muted">{s.t("scenes")}</dt>
                  <dd><Mono>{manifest.spaceId}</Mono></dd>
                  {manifest.totalVectors !== undefined && (
                    <>
                      <dt className="text-muted">vectors</dt>
                      <dd><Mono>{s.fmt.num(manifest.totalVectors)}</Mono></dd>
                    </>
                  )}
                  {manifest.totalSegments !== undefined && (
                    <>
                      <dt className="text-muted">{s.t("segments")}</dt>
                      <dd><Mono>{s.fmt.num(manifest.totalSegments)}</Mono></dd>
                    </>
                  )}
                  {manifest.modalities && (
                    <>
                      <dt className="text-muted">modalities</dt>
                      <dd><Mono>{manifest.modalities.join(", ")}</Mono></dd>
                    </>
                  )}
                </dl>
              ) : (
                <span className="text-muted">no index built yet</span>
              )}
            </div>
          </Card>
          <Card title={s.t("collection")}>
            <div className="p-3 text-[12px] text-muted">
              <Mono className="text-[15px] font-medium text-ink">{s.fmt.num(s.assets.length)}</Mono> assets · {fmtBytes(totalBytes)}
            </div>
          </Card>
          <Card title={s.t("status")}>
            <div className="p-3 text-[12px] text-muted">
              {failedJobs.length > 0 ? (
                <span className="text-bad">{s.fmt.num(failedJobs.length)} failed — retry below</span>
              ) : (
                <span className="text-ok">all batches complete</span>
              )}
            </div>
          </Card>
        </div>
      )}
      <div className="grid gap-4 lg:grid-cols-[360px_1fr]">
        <div className="space-y-4">
          <div
            onDragOver={(e) => {
              e.preventDefault();
              setDrag(true);
            }}
            onDragLeave={() => setDrag(false)}
            onDrop={(e) => {
              e.preventDefault();
              setDrag(false);
              handleFiles(e.dataTransfer.files);
            }}
            onClick={() => inputRef.current?.click()}
            className={cn(
              "cursor-pointer rounded-lg border-2 border-dashed p-8 text-center transition-colors",
              drag ? "border-brand bg-brand-50" : "border-line bg-surface hover:border-brand/50",
            )}
          >
            <UploadCloud className={cn("mx-auto mb-2 h-8 w-8", drag ? "text-brand" : "text-muted")} />
            <p className="text-[13px] font-medium">{s.t("dropZone")}</p>
            <p className="mt-1 text-[12px] text-muted">{s.t("browse")}</p>
            <input ref={inputRef} type="file" multiple accept=".pdf,.tif,.tiff,.geojson,.csv" className="hidden" onChange={(e) => handleFiles(e.target.files)} />
          </div>

          {rejected.length > 0 && (
            <Card title={s.t("unsupportedType")}>
              <ul className="divide-y divide-line">
                {rejected.map((r) => (
                  <li key={r.name} className="p-3 text-[12px]">
                    <Mono className="font-medium text-bad">{r.name}</Mono>
                    <div className="mt-0.5 text-muted">{r.reason}</div>
                  </li>
                ))}
              </ul>
            </Card>
          )}

          <Card title={s.t("pipeline")}>
            <div className="divide-y divide-line">
              {ingestJobs.length === 0 && <p className="p-3 text-[12px] text-muted">{s.t("idleDrop")}</p>}
              {ingestJobs.map((j) => (
                <div key={j.id} className="p-3">
                  <div className="flex items-center justify-between gap-2">
                    <Mono className="truncate text-ink">{String(j.meta?.file ?? j.title)}</Mono>
                    <StatusBadge status={j.status} label={s.t(j.status)} />
                  </div>
                  {j.status === "failed" && j.logs.length > 0 && (
                    <div className="mt-1 truncate text-[11px] text-bad">{j.logs[j.logs.length - 1]}</div>
                  )}
                  <Progress value={j.progress} className="mt-2" tone={j.status === "failed" ? "bad" : "brand"} />
                  {j.status === "failed" && (
                    <Button size="sm" className="mt-2" onClick={() => s.retryJob(j.id)}>
                      <RotateCcw className="h-3.5 w-3.5" /> {s.t("retryFile")}
                    </Button>
                  )}
                  <ol className="mt-2 grid grid-cols-4 gap-1">
                    {j.steps.map((st, i) => {
                      const current = !st.done && j.steps.slice(0, i).every((x) => x.done);
                      return (
                        <li key={st.label} className={cn("rounded px-1 py-0.5 text-center font-mono text-[9.5px] leading-tight", st.done ? "bg-ok-50 text-ok" : current ? "bg-info-50 text-info" : "bg-canvas text-muted")}>
                          {st.label}
                        </li>
                      );
                    })}
                  </ol>
                </div>
              ))}
            </div>
          </Card>
        </div>

        <Card
          title={
            <span className="flex items-center gap-2">
              {s.t("collection")} <Badge tone="neutral">{s.fmt.num(s.assets.length)}</Badge>
            </span>
          }
          actions={<span className="text-[11px] text-muted">{fmtBytes(totalBytes)}</span>}
        >
          <div className="overflow-x-auto">
            <table className="w-full text-[12px]">
              <thead className="bg-canvas text-start text-[10.5px] uppercase tracking-wide text-muted">
                <tr>
                  <th className="px-3 py-2 text-start font-medium">{s.t("asset")}</th>
                  <th className="px-3 py-2 text-start font-medium">{s.t("fingerprint")}</th>
                  <th className="px-3 py-2 text-end font-medium">{s.t("segments")}</th>
                  <th className="px-3 py-2 text-end font-medium">{s.t("size")}</th>
                  <th className="px-3 py-2 text-start font-medium">{s.t("recentlyAdded")}</th>
                  <th className="px-3 py-2" />
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {s.assets.map((a) => {
                  const Icon = typeIcon[a.type];
                  return (
                    <tr key={a.id} className="hover:bg-canvas/60">
                      <td className="px-3 py-2">
                        <div className="flex items-center gap-2">
                          <Icon className="h-4 w-4 shrink-0 text-muted" />
                          <div className="min-w-0">
                            <Mono className="block truncate font-medium text-ink">{a.name}</Mono>
                            <Badge tone={modalityTone[a.modality]} className="mt-0.5">
                              {a.modality}.*
                            </Badge>
                          </div>
                        </div>
                      </td>
                      <td className="px-3 py-2">
                        <Mono className="text-muted" >{a.sha256.slice(0, 12)}…{a.sha256.slice(-6)}</Mono>
                      </td>
                      <td className="px-3 py-2 text-end tabular-nums">{s.fmt.num(a.segments)}</td>
                      <td className="px-3 py-2 text-end tabular-nums">{fmtBytes(a.sizeBytes)}</td>
                      <td className="px-3 py-2 text-muted">{s.fmt.date(a.addedAt)}</td>
                      <td className="px-3 py-2 text-end">
                        <button onClick={() => { setDel(a); setConfirm(""); }} className="text-muted hover:text-bad" title={s.t("delete")}>
                          <Trash2 className="h-3.5 w-3.5" />
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </Card>
      </div>

      {del && (
        <div className="fixed inset-0 z-50 grid place-items-center bg-ink/30" onClick={() => setDel(null)}>
          <div className="w-[420px] rounded-xl border border-line bg-surface p-4 shadow-2xl" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center gap-2 text-bad">
              <ShieldAlert className="h-5 w-5" />
              <h3 className="font-semibold">{s.t("delete")}</h3>
            </div>
            <p className="mt-2 text-[12.5px] text-muted">
              This removes <Mono className="text-ink">{del.segments}</Mono> indexed segments and any citations pointing at <Mono className="text-ink">{del.sha256.slice(0, 16)}…</Mono>. Existing answers will lose provenance.
            </p>
            <Field label={s.t("confirmDelete")}>
              <input value={confirm} onChange={(e) => setConfirm(e.target.value)} className={cn(inputCls, "mt-2 font-mono")} dir="ltr" placeholder={s.t("typeConfirm")} />
            </Field>
            <div className="mt-4 flex justify-end gap-2">
              <Button onClick={() => setDel(null)}>{s.t("cancel")}</Button>
              <Button variant="danger" disabled={confirm !== del.name} onClick={() => { s.removeAsset(del.id); setDel(null); s.toast(`Deleted ${del.name}`, "warn"); }}>
                {s.t("delete")}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
