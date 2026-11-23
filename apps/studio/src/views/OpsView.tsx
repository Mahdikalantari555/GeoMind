import { useEffect, useRef, useState } from "react";
import { Ban, HardDrive, HeartPulse, RotateCw, Terminal } from "lucide-react";
import { useStore } from "@/lib/store";
import { getDoctor, getWorkspaceStats, type DoctorSnapshot, type WorkspaceStats } from "@/lib/api";
import { Button, Card, Mono, PageHeader, Progress, StatusBadge, Badge } from "@/components/ui";
import { cn } from "@/utils/cn";
import type { JobStatus } from "@/lib/types";

const FILTERS: (JobStatus | "all")[] = ["all", "running", "queued", "complete", "failed", "cancelled"];

export function OpsView() {
  const s = useStore();
  const [filter, setFilter] = useState<(typeof FILTERS)[number]>("all");
  const [sel, setSel] = useState<string | null>(null);
  const logRef = useRef<HTMLDivElement>(null);
  const jobs = s.jobs.filter((j) => filter === "all" || j.status === filter);
  const selected = jobs.find((j) => j.id === sel) ?? jobs[0];
  const allLogs = selected ? selected.logs : [];
  useEffect(() => {
    logRef.current?.scrollTo({ top: logRef.current.scrollHeight });
  }, [allLogs.length]);

  // Measured diagnostics from the gateway — never fabricate ok:false rows
  // (audit F-100). Unknown values are reported as "not instrumented".
  const [doctor, setDoctor] = useState<DoctorSnapshot | null>(null);
  const [stats, setStats] = useState<WorkspaceStats | null>(null);
  const [diagLoading, setDiagLoading] = useState(false);
  useEffect(() => {
    if (!s.online) { setDoctor(null); setStats(null); return; }
    const ctrl = new AbortController();
    setDiagLoading(true);
    void Promise.all([getDoctor(ctrl.signal), getWorkspaceStats(ctrl.signal)])
      .then(([d, st]) => { setDoctor(d); setStats(st); })
      .catch(() => { /* keep explicit not-instrumented state */ })
      .finally(() => { if (!ctrl.signal.aborted) setDiagLoading(false); });
    return () => ctrl.abort();
  }, [s.online]);

  const tri = (value: boolean | string | null | undefined) =>
    value === undefined ? null : value === true ? true : value === false ? false : null;
  const statusText = (value: boolean | null) =>
    value === null ? s.t("healthNotInstrumented") : value ? s.t("healthOk") : s.t("healthDegraded");

  const health: { name: string; ok: boolean | null; detail: string }[] = [
    {
      name: s.t("healthGateway"),
      ok: s.online,
      detail: s.online ? s.t("healthOk") : s.t("offline"),
    },
    {
      name: s.t("healthLlm"),
      ok: tri(doctor?.checks.llm),
      detail: doctor?.details.find((d) => d.startsWith("llm=")) ?? s.t("healthNotInstrumented"),
    },
    {
      name: s.t("healthTextEmbedding"),
      ok: tri(doctor?.checks.embedding),
      detail: doctor?.details.find((d) => d.startsWith("backend=")) ?? s.t("healthNotInstrumented"),
    },
    { name: s.t("healthVision"), ok: tri(doctor?.checks.vision), detail: statusText(tri(doctor?.checks.vision)) },
    { name: s.t("healthSqliteVec"), ok: tri(doctor?.checks.sqlite_vec), detail: statusText(tri(doctor?.checks.sqlite_vec)) },
    // The gateway exposes no worker-pool probe; say so instead of faking a row.
    { name: s.t("healthWorkerPool"), ok: null, detail: s.t("healthNotInstrumented") },
  ];

  const humanBytes = (n: number) =>
    n >= 1024 ** 3 ? `${(n / 1024 ** 3).toFixed(2)} GB`
    : n >= 1024 ** 2 ? `${(n / 1024 ** 2).toFixed(1)} MB`
    : n >= 1024 ? `${(n / 1024).toFixed(1)} KB`
    : `${n} B`;

  return (
    <div className="scroll-thin h-full overflow-y-auto p-5">
      <PageHeader title={s.t("nav_ops")} subtitle={s.t("opsSubtitle")} />
      <div className="grid gap-4 xl:grid-cols-[1fr_360px]">
        <div className="space-y-4">
          <Card
            title={s.t("jobQueue")}
            actions={
              <div className="flex gap-0.5">
                {FILTERS.map((f) => (
                  <button key={f} onClick={() => setFilter(f)} className={cn("rounded px-1.5 py-0.5 text-[11px]", filter === f ? "bg-brand-50 text-brand-700" : "text-muted hover:bg-canvas")}>
                    {f === "all" ? "all" : s.t(f)}
                  </button>
                ))}
              </div>
            }
          >
            <table className="w-full text-[12px]">
              <thead className="bg-canvas text-[10.5px] uppercase tracking-wide text-muted">
                <tr>
                  <th className="px-3 py-2 text-start font-medium">{s.t("job")}</th>
                  <th className="px-3 py-2 text-start font-medium">{s.t("status")}</th>
                  <th className="w-40 px-3 py-2 text-start font-medium">{s.t("progress")}</th>
                  <th className="px-3 py-2 text-start font-medium">{s.t("updated")}</th>
                  <th className="px-3 py-2" />
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {jobs.map((j) => (
                  <tr key={j.id} onClick={() => setSel(j.id)} className={cn("cursor-pointer hover:bg-canvas/60", selected?.id === j.id && "bg-brand-50/40")}>
                    <td className="px-3 py-2">
                      <div className="truncate font-medium">{j.title}</div>
                      <div className="flex items-center gap-1.5">
                        <Mono className="text-muted">{j.id}</Mono>
                        <Badge tone="neutral">{j.kind}</Badge>
                      </div>
                    </td>
                    <td className="px-3 py-2">
                      <StatusBadge status={j.status} label={s.t(j.status)} />
                    </td>
                    <td className="px-3 py-2">
                      <div className="flex items-center gap-2">
                        <Progress value={j.progress} tone={j.status === "failed" ? "bad" : j.status === "complete" ? "ok" : "brand"} />
                        <Mono className="w-8 text-end text-muted">{s.fmt.num(j.progress)}%</Mono>
                      </div>
                    </td>
                    <td className="px-3 py-2 text-muted">{s.fmt.time(j.updatedAt)} {j.reconnecting && <span role="status">· Reconnecting</span>}</td>
                    <td className="px-3 py-2 text-end">
                      {!s.online && !j.meta?.serverJob && !j.meta?.liveUpload && (j.status === "running" || j.status === "queued") && (
                        <Button size="sm" variant="ghost" onClick={(e) => { e.stopPropagation(); s.cancelJob(j.id); }}>
                          <Ban className="h-3.5 w-3.5" /> {s.t("cancel")}
                        </Button>
                      )}
                      {!s.online && !j.meta?.serverJob && !j.meta?.liveUpload && (j.status === "failed" || j.status === "cancelled") && (
                        <Button size="sm" variant="ghost" onClick={(e) => { e.stopPropagation(); s.retryJob(j.id); }}>
                          <RotateCw className="h-3.5 w-3.5" /> {s.t("retry")}
                        </Button>
                      )}
                    </td>
                  </tr>
                ))}
                {jobs.length === 0 && (
                  <tr>
                    <td colSpan={5} className="p-6 text-center text-muted">
                      {s.t("noResults")}
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </Card>

          <Card
            title={
              <span className="flex items-center gap-2">
                <Terminal className="h-3.5 w-3.5" /> {s.t("logs")} {selected && <Mono className="text-muted">{selected.id}</Mono>}
              </span>
            }
          >
            <div ref={logRef} className="scroll-thin h-56 overflow-y-auto bg-ink p-3 font-mono text-[11px] leading-relaxed text-emerald-200" dir="ltr">
              {allLogs.map((l, i) => (
                <div key={i} className={cn(l.includes("fail") && "text-red-300", l.includes("complete") && "text-emerald-400")}>
                  <span className="text-emerald-600/80">{String(i + 1).padStart(3, "0")} </span>
                  {l}
                </div>
              ))}
              {selected?.status === "running" && <span className="pulse-dot inline-block h-3 w-1.5 bg-emerald-300 align-middle" />}
            </div>
          </Card>
        </div>

        <div className="space-y-4">
          <Card
            title={
              <span className="flex items-center gap-2">
                <HeartPulse className="h-3.5 w-3.5" /> {s.t("health")}
              </span>
            }
          >
            <ul className="divide-y divide-line">
              {health.map((h) => (
                <li key={h.name} className="flex items-center gap-2 px-3 py-2 text-[12px]">
                  <span
                    className={cn(
                      "h-2 w-2 rounded-full",
                      h.ok === true ? "bg-ok" : h.ok === false ? "bg-bad" : "bg-muted",
                    )}
                  />
                  <span className="font-medium">{h.name}</span>
                  <Mono className="ms-auto truncate text-muted">{h.detail}</Mono>
                </li>
              ))}
              {diagLoading && <li className="px-3 py-1.5 text-[10.5px] text-muted" role="status">…</li>}
            </ul>
          </Card>
          <Card
            title={
              <span className="flex items-center gap-2">
                <HardDrive className="h-3.5 w-3.5" /> {s.t("storage")}
              </span>
            }
          >
            {stats ? (
              <div className="space-y-2 p-3 text-[12px]">
                <div className="flex justify-between"><span className="text-muted">{s.t("storage")}</span><Mono>{humanBytes(stats.storageBytes)}</Mono></div>
                <div className="flex justify-between"><span className="text-muted">{s.t("assets")}</span><Mono>{s.fmt.num(stats.assets)}</Mono></div>
                <div className="flex justify-between"><span className="text-muted">{s.t("segments")}</span><Mono>{s.fmt.num(stats.segments)}</Mono></div>
                <div className="flex justify-between"><span className="text-muted">{s.t("dbBytes")}</span><Mono>{humanBytes(stats.dbBytes)}</Mono></div>
                <p className="pt-1 text-[10.5px] text-muted">{s.t("healthStorageDetail")}</p>
              </div>
            ) : (
              <p className="p-3 text-muted">{s.online ? s.t("healthNotInstrumented") : s.t("offline")}</p>
            )}
          </Card>
        </div>
      </div>
    </div>
  );
}
