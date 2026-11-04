import { useRef, useState } from "react";
import { FileText, Image as ImageIcon, Map as MapIcon, Table2, Trash2, UploadCloud, ShieldAlert } from "lucide-react";
import { useStore } from "@/lib/store";
import { Badge, Button, Card, Field, fmtBytes, inputCls, Mono, PageHeader, Progress, StatusBadge } from "@/components/ui";
import type { Asset } from "@/lib/types";
import { cn } from "@/utils/cn";

const typeIcon: Record<Asset["type"], typeof FileText> = { pdf: FileText, tif: ImageIcon, geojson: MapIcon, csv: Table2 };
const modalityTone: Record<Asset["modality"], "info" | "brand" | "warn" | "ok"> = { text: "info", vision: "brand", vector: "warn", table: "ok" };

export function ResourcesView() {
  const s = useStore();
  const [drag, setDrag] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const [del, setDel] = useState<Asset | null>(null);
  const [confirm, setConfirm] = useState("");
  const ingestJobs = s.jobs.filter((j) => j.kind === "ingest" && j.status !== "complete").slice(0, 6);

  const handleFiles = (list: FileList | null) => {
    if (!list) return;
    const files = Array.from(list).filter((f) => /\.(pdf|tiff?|geojson|csv)$/i.test(f.name));
    if (!files.length) return s.toast("Unsupported file type", "warn");
    s.ingestFiles(files.map((f) => ({ name: f.name, size: f.size })));
  };

  const addDemo = () => s.ingestFiles([{ name: "Bastiaanssen_1998_SEBAL.pdf", size: 2_410_000 }, { name: "S2B_38SNA_20240503_B08.tif", size: 182_000_000 }]);

  const totalBytes = s.assets.reduce((a, x) => a + x.sizeBytes, 0);

  return (
    <div className="scroll-thin h-full overflow-y-auto p-5">
      <PageHeader
        title={s.t("nav_resources")}
        subtitle="Ingestion manager · modality-isolated embeddings (text.* vs vision.*) · content-addressed by SHA-256"
        actions={
          <Button size="sm" onClick={addDemo}>
            + demo files
          </Button>
        }
      />
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

          <Card title={s.t("pipeline")}>
            <div className="divide-y divide-line">
              {ingestJobs.length === 0 && <p className="p-3 text-[12px] text-muted">Idle — drop files to start.</p>}
              {ingestJobs.map((j) => (
                <div key={j.id} className="p-3">
                  <div className="flex items-center justify-between gap-2">
                    <Mono className="truncate text-ink">{String(j.meta?.file ?? j.title)}</Mono>
                    <StatusBadge status={j.status} label={s.t(j.status)} />
                  </div>
                  <Progress value={j.progress} className="mt-2" tone={j.status === "failed" ? "bad" : "brand"} />
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
              <input value={confirm} onChange={(e) => setConfirm(e.target.value)} className={cn(inputCls, "mt-2 font-mono")} dir="ltr" placeholder={del.name} />
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
