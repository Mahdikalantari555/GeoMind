import { useEffect, useRef, useState } from "react";
import { Ban, HardDrive, HeartPulse, RotateCw, Terminal } from "lucide-react";
import { useStore } from "@/lib/store";
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

  const health = [
    { name: "geofront_api", ok: s.online, detail: s.online ? "/api/v1/health 200" : "Offline" },
    { name: "LLM gateway", ok: false, detail: "Inference not tested" },
    { name: "Embedding (text.bge-m3)", ok:false, detail:"Not measured" },
    { name: "Embedding (vision.clip-rs)", ok:false, detail:"Not measured" },
    { name: "Worker pool", ok:false, detail:"Not measured" },
  ];

  return (
    <div className="scroll-thin h-full overflow-y-auto p-5">
      <PageHeader title={s.t("nav_ops")} subtitle="Job queue · diagnostics · health · streaming logs" />
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
                  <th className="px-3 py-2 text-start font-medium">Job</th>
                  <th className="px-3 py-2 text-start font-medium">{s.t("status")}</th>
                  <th className="w-40 px-3 py-2 text-start font-medium">Progress</th>
                  <th className="px-3 py-2 text-start font-medium">Updated</th>
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
                  <span className={cn("h-2 w-2 rounded-full", h.ok ? "bg-ok" : "bg-warn")} />
                  <span className="font-medium">{h.name}</span>
                  <Mono className="ms-auto truncate text-muted">{h.detail}</Mono>
                </li>
              ))}
            </ul>
          </Card>
          <Card
            title={
              <span className="flex items-center gap-2">
                <HardDrive className="h-3.5 w-3.5" /> {s.t("storage")}
              </span>
            }
          >
            <p className="p-3">Storage usage not measured</p>
          </Card>
        </div>
      </div>
    </div>
  );
}
