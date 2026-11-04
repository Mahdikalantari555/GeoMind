import { useState } from "react";
import { AlertTriangle, ExternalLink, FileText, Loader2, Search, Sparkles, X } from "lucide-react";
import { useStore } from "@/lib/store";
import { groundedAsk } from "@/lib/api";
import type { Passage, QAResult } from "@/lib/types";
import { Badge, Button, Card, Mono, PageHeader } from "@/components/ui";
import { cn } from "@/utils/cn";

const SUGGESTED = ["How does METRIC estimate evapotranspiration?", "Mean annual ETa of sugarcane in lower Karkheh?", "Kc values for sugarcane mid-season?", "What is the soil salinity trend in Khuzestan since 2010?"];

export function Gauge({ value, threshold, label }: { value: number; threshold: number; label: string }) {
  const s = useStore();
  const pct = Math.round(value * 100);
  const ok = value >= threshold;
  return (
    <div className="min-w-32">
      <div className="mb-1 flex items-center justify-between text-[10.5px] uppercase tracking-wide text-muted">
        <span>{label}</span>
        <Mono className={cn("font-medium", ok ? "text-ok" : "text-bad")}>{s.fmt.pct(pct)}</Mono>
      </div>
      <div className="relative h-2 rounded-full bg-line" dir="ltr">
        <div className={cn("h-full rounded-full", ok ? "bg-ok" : "bg-bad")} style={{ width: `${pct}%` }} />
        <div className="absolute -top-0.5 h-3 w-0.5 bg-ink/60" style={{ left: `${threshold * 100}%` }} title={`threshold ${threshold}`} />
      </div>
    </div>
  );
}

export function CitationChip({ n, onClick }: { n: number; onClick: () => void }) {
  return (
    <button onClick={onClick} className="mx-0.5 inline-flex h-4.5 min-w-4.5 items-center justify-center rounded bg-brand-50 px-1 font-mono text-[10px] font-semibold text-brand-700 hover:bg-brand-100 align-text-top">
      [{n}]
    </button>
  );
}

export function renderWithChips(text: string, onChip: (i: number) => void) {
  const parts = text.split(/(\[\d+\])/g);
  return parts.map((p, i) => {
    const m = p.match(/^\[(\d+)\]$/);
    return m ? <CitationChip key={i} n={+m[1]} onClick={() => onChip(+m[1] - 1)} /> : <span key={i}>{p}</span>;
  });
}

export function ProvenanceDrawer({ passage, index, onClose }: { passage: Passage; index: number; onClose: () => void }) {
  const s = useStore();
  return (
    <aside className="flex w-80 shrink-0 flex-col border-s border-line bg-surface">
      <header className="flex items-center justify-between border-b border-line px-3 py-2">
        <div className="flex items-center gap-2 text-[12.5px] font-semibold">
          <CitationChip n={index + 1} onClick={() => {}} /> {s.t("provenance")}
        </div>
        <button onClick={onClose} className="text-muted hover:text-ink">
          <X className="h-4 w-4" />
        </button>
      </header>
      <div className="scroll-thin flex-1 space-y-3 overflow-y-auto p-3 text-[12.5px]">
        <div className="flex items-start gap-2">
          <FileText className="mt-0.5 h-4 w-4 text-muted" />
          <Mono className="break-all font-medium text-ink">{passage.assetName}</Mono>
        </div>
        <blockquote className="rounded-md border-s-2 border-brand bg-brand-50/60 p-2.5 leading-relaxed">“{passage.text}”</blockquote>
        <dl className="grid grid-cols-[88px_1fr] gap-y-1.5 text-[11.5px]">
          <dt className="text-muted">Score</dt>
          <dd>
            <Mono>{passage.score.toFixed(2)}</Mono>
          </dd>
          {passage.page !== undefined && (
            <>
              <dt className="text-muted">{s.t("page")}</dt>
              <dd>
                <Mono>{passage.page}</Mono>
              </dd>
            </>
          )}
          {passage.bbox && (
            <>
              <dt className="text-muted">{s.t("bbox")}</dt>
              <dd>
                <Mono>[{passage.bbox.join(", ")}] pt</Mono>
              </dd>
            </>
          )}
          {passage.rasterCoord && (
            <>
              <dt className="text-muted">Raster</dt>
              <dd>
                <Mono>
                  {passage.rasterCoord[1].toFixed(4)}°N {passage.rasterCoord[0].toFixed(4)}°E
                </Mono>
              </dd>
            </>
          )}
          <dt className="text-muted">{s.t("asset")} ID</dt>
          <dd>
            <Mono className="break-all text-muted">{(s.assets.find((a) => a.id === passage.assetId)?.sha256 ?? "").slice(0, 32)}…</Mono>
          </dd>
          <dt className="text-muted">Segment</dt>
          <dd>
            <Mono>{passage.id}</Mono>
          </dd>
        </dl>
        {passage.rasterCoord && (
          <Button
            size="sm"
            className="w-full"
            onClick={() => {
              s.setView("map");
              s.requestFly(passage.rasterCoord!);
            }}
          >
            <ExternalLink className="h-3.5 w-3.5" /> Locate on map
          </Button>
        )}
      </div>
    </aside>
  );
}

export function KnowledgeView() {
  const s = useStore();
  const [q, setQ] = useState("");
  const [mode, setMode] = useState<QAResult["mode"]>("hybrid");
  const [loading, setLoading] = useState(false);
  const [res, setRes] = useState<QAResult | null>(null);
  const [open, setOpen] = useState<number | null>(null);
  const threshold = s.settings.groundingThreshold;

  const ask = async (question = q) => {
    if (!question.trim()) return;
    setQ(question);
    setLoading(true);
    setOpen(null);
    try {
      setRes(await groundedAsk(question, mode, threshold));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex h-full min-h-0">
      <div className="scroll-thin min-w-0 flex-1 overflow-y-auto p-5">
        <PageHeader title={s.t("nav_knowledge")} subtitle={`Grounded QA · every claim cites a segment or abstains · threshold ${threshold}`} />
        <div className="rounded-lg border border-line bg-surface p-2 shadow-sm">
          <div className="flex items-center gap-2">
            <Search className="ms-1 h-4 w-4 text-muted" />
            <input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && ask()}
              placeholder={s.t("ask")}
              className="h-9 flex-1 bg-transparent text-[14px] outline-none"
            />
            <Button variant="primary" onClick={() => ask()} disabled={loading}>
              {loading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Sparkles className="h-3.5 w-3.5" />} Ask
            </Button>
          </div>
          <div className="mt-1.5 flex items-center gap-1 border-t border-line pt-1.5">
            {(["hybrid", "semantic", "keyword"] as const).map((m) => (
              <button key={m} onClick={() => setMode(m)} className={cn("rounded px-2 py-0.5 text-[11.5px] font-medium", mode === m ? "bg-brand-50 text-brand-700" : "text-muted hover:bg-canvas")}>
                {s.t(m)}
                {m === "hybrid" && <span className="ms-1 font-mono text-[9.5px] text-muted">dense+BM25</span>}
              </button>
            ))}
          </div>
        </div>
        <div className="mt-2 flex flex-wrap gap-1.5">
          {SUGGESTED.map((x) => (
            <button key={x} onClick={() => ask(x)} className="rounded-full border border-line bg-surface px-2.5 py-1 text-[11.5px] text-muted hover:border-brand hover:text-brand-700">
              {x}
            </button>
          ))}
        </div>

        {res && (
          <div className="mt-5 space-y-4">
            {res.abstained ? (
              <Card className="border-warn/40">
                <div className="flex gap-3 p-4">
                  <div className="grid h-9 w-9 shrink-0 place-items-center rounded-md bg-warn-50 text-warn">
                    <AlertTriangle className="h-5 w-5" />
                  </div>
                  <div className="flex-1">
                    <h3 className="font-semibold text-warn">{s.t("abstain")}</h3>
                    <p className="mt-1 text-[12.5px] text-muted">{s.t("abstainBody")}</p>
                    <div className="mt-3 flex flex-wrap gap-6">
                      <Gauge value={res.topScore} threshold={threshold} label={s.t("grounding")} />
                      <div className="text-[11.5px] text-muted">
                        top score <Mono className="text-bad">{res.topScore.toFixed(2)}</Mono> &lt; threshold <Mono>{threshold}</Mono>
                      </div>
                    </div>
                  </div>
                </div>
              </Card>
            ) : (
              <Card title={s.t("answer")} actions={<Badge tone="ok">{res.mode}</Badge>}>
                <div className="p-4">
                  <p className="text-[14px] leading-relaxed">{renderWithChips(res.answer ?? "", setOpen)}</p>
                  <div className="mt-4 flex flex-wrap gap-6">
                    <Gauge value={res.confidence} threshold={threshold} label={s.t("confidence")} />
                    <Gauge value={res.topScore} threshold={threshold} label={s.t("grounding")} />
                  </div>
                  {res.caveats.length > 0 && (
                    <div className="mt-4 rounded-md bg-canvas p-2.5 text-[11.5px] text-muted">
                      <div className="mb-1 font-medium uppercase tracking-wide">{s.t("caveats")}</div>
                      <ul className="list-disc space-y-0.5 ps-4">
                        {res.caveats.map((c) => (
                          <li key={c}>{c}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              </Card>
            )}

            <Card title={res.abstained ? s.t("closest") : s.t("sources")}>
              <ul className="divide-y divide-line">
                {res.citations.map((c, i) => (
                  <li key={c.id}>
                    <button onClick={() => setOpen(i)} className={cn("flex w-full gap-3 p-3 text-start hover:bg-canvas/60", open === i && "bg-brand-50/50")}>
                      <CitationChip n={i + 1} onClick={() => setOpen(i)} />
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2">
                          <Mono className="truncate font-medium text-ink">{c.assetName}</Mono>
                          {c.page !== undefined && <Badge tone="neutral">p.{c.page}</Badge>}
                          {c.rasterCoord && <Badge tone="brand">raster</Badge>}
                        </div>
                        <p className="mt-0.5 line-clamp-2 text-[12px] text-muted">{c.text}</p>
                      </div>
                      <Mono className={cn("shrink-0", c.score >= threshold ? "text-ok" : "text-bad")}>{c.score.toFixed(2)}</Mono>
                    </button>
                  </li>
                ))}
              </ul>
            </Card>
          </div>
        )}
      </div>
      {res && open !== null && res.citations[open] && <ProvenanceDrawer passage={res.citations[open]} index={open} onClose={() => setOpen(null)} />}
    </div>
  );
}
