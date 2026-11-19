import { useEffect, useRef, useState } from "react";
import { AlertTriangle, Bot, CheckCircle2, ChevronDown, Loader2, Play, Save, Send, Sparkles, Wrench, XCircle, User } from "lucide-react";
import { useStore, uid, ringArea } from "@/lib/store";
import { hybridSearch, listPlaybooks, runPlaybook, savePlaybook, sleep, streamAgentChat, stripInvalidCitations } from "@/lib/api";
import { playbooks } from "@/lib/sample";
import type { ChatMessage, Playbook, ToolCall } from "@/lib/types";
import { Badge, Mono } from "./ui";
import { cn } from "@/utils/cn";
import { ProvenanceDrawer, renderWithChips } from "@/views/KnowledgeView";

export function AgentRail() {
  const s = useStore();
  const [busy, setBusy] = useState(false);
  const [prov, setProv] = useState<{ msg: ChatMessage; i: number } | null>(null);
  const [pbOpen, setPbOpen] = useState(true);
  const [livePlaybooks, setLivePlaybooks] = useState<Playbook[]>([]);
  const endRef = useRef<HTMLDivElement>(null);
  const draft = s.agentDraft;

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [s.messages, busy]);

  useEffect(() => {
    if (!s.online) return;
    void listPlaybooks()
      .then(setLivePlaybooks)
      .catch(() => setLivePlaybooks([]));
  }, [s.online]);

  /** Live gateway chat: POST /agent/chat SSE, token-by-token render. */
  const sendLive = async (text: string) => {
    const agentId = uid("m");
    s.setMessages((ms) => [...ms, { id: agentId, role: "user", text }, { id: agentId, role: "agent", text: "", streaming: true, tools: [] }]);
    let acc = "";
    const tools: ToolCall[] = [];
    try {
      await streamAgentChat(text, (e) => {
        if (e.event === "message" && e.text) {
          acc += e.text;
          const { text: cleaned, invalid } = stripInvalidCitations(acc, 99);
          update(agentId, { text: cleaned, streaming: true, invalidCitations: invalid.length ? invalid : undefined });
        } else if (e.event === "tool_start" && e.tool) {
          const tc: ToolCall = { id: uid("tc"), name: e.tool, args: "", status: "running" };
          tools.push(tc);
          update(agentId, { tools: [...tools] });
        } else if (e.event === "tool_end" && e.tool) {
          const tc = tools.find((t) => t.name === e.tool && t.status === "running");
          if (tc) {
            tc.status = e.status === "ok" ? "complete" : "failed";
            update(agentId, { tools: [...tools] });
          }
        } else if (e.event === "error" && e.message) {
          update(agentId, { text: acc || e.message, streaming: false, caveats: [e.message] });
        }
      });
      update(agentId, { streaming: false });
    } catch (err) {
      update(agentId, { text: String(err instanceof Error ? err.message : err), streaming: false });
    }
  };

  const replayPlaybook = async (pb: Playbook) => {
    if (busy) return;
    setBusy(true);
    const agentId = uid("m");
    const label = `Replay ${pb.name}`;
    s.setMessages((ms) => [...ms, { id: agentId, role: "user", text: label }, { id: agentId, role: "agent", text: "", streaming: true, tools: [] }]);
    try {
      const result = await runPlaybook(pb.name);
      update(agentId, {
        streaming: false,
        text: `Playbook ${pb.name} completed.`,
        table: { headers: ["Result"], rows: [[JSON.stringify(result).slice(0, 120)]] },
      });
    } catch (err) {
      update(agentId, { streaming: false, text: String(err instanceof Error ? err.message : err) });
    } finally {
      setBusy(false);
    }
  };

  const saveAsPlaybook = async (msg: ChatMessage) => {
    const name = `saved-${Date.now().toString(36).slice(-4)}`;
    const content = `---\nname: ${name}\n---\n\n# ${name}\n\n${msg.text}\n`;
    try {
      await savePlaybook(name, content);
      s.toast(`${s.t("savePlaybook")}: ${name}`, "ok");
    } catch (err) {
      s.toast(String(err instanceof Error ? err.message : err), "bad");
    }
  };

  const update = (id: string, patch: Partial<ChatMessage> | ((m: ChatMessage) => Partial<ChatMessage>)) =>
    s.setMessages((ms) => ms.map((m) => (m.id === id ? { ...m, ...(typeof patch === "function" ? patch(m) : patch) } : m)));

  const runTool = async (msgId: string, name: string, args: string, work: () => Promise<string> | string, ms = 500) => {
    const tc: ToolCall = { id: uid("tc"), name, args, status: "running" };
    update(msgId, (m) => ({ tools: [...(m.tools ?? []), tc] }));
    const t0 = performance.now();
    await sleep(ms + Math.random() * 300);
    try {
      const result = await work();
      update(msgId, (m) => ({ tools: m.tools!.map((t) => (t.id === tc.id ? { ...t, status: "complete", durationMs: Math.round(performance.now() - t0), result } : t)) }));
      return result;
    } catch (e) {
      update(msgId, (m) => ({ tools: m.tools!.map((t) => (t.id === tc.id ? { ...t, status: "failed", durationMs: Math.round(performance.now() - t0), result: String(e) } : t)) }));
      throw e;
    }
  };

  const stream = async (msgId: string, text: string) => {
    const words = text.split(" ");
    let acc = "";
    for (const w of words) {
      acc += (acc ? " " : "") + w;
      update(msgId, { text: acc, streaming: true });
      await sleep(18 + Math.random() * 30);
    }
    update(msgId, { streaming: false });
  };

  const send = async (text: string, playbook?: (typeof playbooks)[number]) => {
    if (!text.trim() || busy) return;
    s.setAgentDraft("");
    setBusy(true);
    if (s.online && !playbook) {
      try {
        await sendLive(text);
      } finally {
        setBusy(false);
      }
      return;
    }
    const userMsg: ChatMessage = { id: uid("m"), role: "user", text };
    const agentId = uid("m");
    s.setMessages((ms) => [...ms, userMsg, { id: agentId, role: "agent", text: "", streaming: true, tools: [] }]);
    const roi = s.activeRoi;
    const lower = text.toLowerCase();
    try {
      if (playbook) {
        update(agentId, { plan: playbook.tools.map((t) => `${t} → ${t.includes("search") ? "retrieve context" : t.includes("compute") || t.includes("balance") || t.includes("detect") ? "run numeric step" : "resolve inputs"}`) });
        const roiName = roi?.name ?? "karkheh-block-3";
        for (const t of playbook.tools) {
          if (t === "roi_resolve") await runTool(agentId, t, `{name:"${roiName}"}`, () => `${roiName} · ${roi ? s.fmt.num(roi.areaHa, { maximumFractionDigits: 0 }) : "18,640"} ha`);
          else if (t === "scene_search") await runTool(agentId, t, `{sensor:"L9", cloud<20}`, () => "7 scenes · 2024-03-01…2024-06-30", 700);
          else if (t === "metric_compute" || t === "index_compute:ndvi" || t === "water_balance" || t === "anomaly_detect") {
            await runTool(agentId, t, `{roi:"${roiName}"}`, () => {
              s.startJob({ id: uid("job"), kind: "metric", title: `${t} · ${roiName}`, steps: [{ label: "Load", done: false }, { label: "Calibrate", done: false }, { label: "Compute", done: false }, { label: "Write COG", done: false }], logs: ["[agent] queued by playbook"] }, { stepMs: 600 });
              return "job queued · 202";
            }, 600);
          } else if (t === "zonal_stats" || t === "table_query") await runTool(agentId, t, "{stat:'mean'}", () => "mean ETa 5.8 mm/d · σ 1.1", 500);
          else if (t === "hybrid_search") await runTool(agentId, t, `{q:"${text.slice(0, 32)}"}`, () => "3 passages ≥ 0.62", 450);
          else if (t === "roi_create") await runTool(agentId, t, "{from:'anomaly-mask'}", () => {
              const coords: [number, number][] = [[48.03, 32.28], [48.07, 32.29], [48.075, 32.255], [48.035, 32.25], [48.03, 32.28]];
              const { areaHa, centroid } = ringArea(coords);
              s.addRoi({ name: `anomaly-${Date.now().toString(36).slice(-3)}`, kind: "polygon", coords, areaHa, centroid });
              return "ROI created";
            });
        }
        const cites = (await hybridSearch(text)).slice(0, 2);
        const body =
          playbook.id === "eta"
            ? `Seasonal METRIC ETa for ${roiName} is being computed as an energy-balance residual with CIMEC anchor pixels [1]. Preliminary zonal mean is 5.8 mm/day; published basin figures put irrigated ETa near 1,180 mm/yr [2]. Final rasters will register in the layer tree when the job completes.`
            : playbook.id === "ndvi"
              ? `NDVI anomaly detection over ${roiName} flagged one cluster of parcels ~0.18 below the seasonal median; a new ROI was created around it for follow-up. Tile-level NDVI statistics come from the ingested raster segment [1].`
              : `Water balance for the lower Karkheh: inflow ≈ 5.8 BCM/yr with a declining trend of −62 MCM/yr, 71% of releases going to irrigation [1]. ETa demand is being recomputed; closure error will be reported with the job result.`;
        update(agentId, { citations: cites, caveats: ["Numbers from running jobs are provisional until the job reaches `complete`.", "Playbook ran only against the active workspace; no external data was fetched."], table: { headers: ["Step", "Result"], rows: playbook.tools.map((t) => [t, "ok"]) } });
        await stream(agentId, body);
      } else if (/(create|draw|make).*roi|roi.*(around|at)/.test(lower)) {
        update(agentId, { plan: ["Parse geometry from request", "roi_create via gateway", "Confirm & set active"] });
        const c = roi?.centroid ?? [48.09, 32.38];
        const d = 0.03;
        const coords: [number, number][] = [[c[0] - d, c[1] - d], [c[0] + d, c[1] - d], [c[0] + d, c[1] + d], [c[0] - d, c[1] + d], [c[0] - d, c[1] - d]];
        const { areaHa, centroid } = ringArea(coords);
        await runTool(agentId, "roi_create", `{bbox:[${coords[0].map((x) => x.toFixed(3))},${coords[2].map((x) => x.toFixed(3))}]}`, () => {
          s.addRoi({ name: `agent-roi-${s.rois.length + 1}`, kind: "bbox", coords, areaHa, centroid });
          return `created · ${s.fmt.num(areaHa, { maximumFractionDigits: 0 })} ha`;
        });
        await stream(agentId, `Created a ${s.fmt.num(areaHa, { maximumFractionDigits: 0 })} ha bounding-box ROI centred at ${centroid[1].toFixed(4)}°N ${centroid[0].toFixed(4)}°E and set it active. You can send it to Acquire or ask me to compute NDVI over it.`);
      } else if (/train|partial_fit|retrain/.test(lower)) {
        update(agentId, { plan: ["Collect labelled feedback", "partial_fit (CPU)", "Report checkpoint"] });
        const n = s.review.filter((r) => r.status !== "pending").length;
        if (n === 0) {
          await runTool(agentId, "feedback_count", "{}", () => "0 labelled samples");
          await stream(agentId, "There are no labelled samples in the review queue yet — accept, reject or correct a few predictions in the Training Lab and I will run `partial_fit` right away.");
        } else {
          await runTool(agentId, "partial_fit", `{samples:${n}}`, async () => {
            await s.trainNow();
            return "checkpoint saved";
          }, 200);
          await stream(agentId, `Ran an online partial_fit on ${n} labelled samples. A new checkpoint is now active; see Training Lab → Model versions for the accuracy delta and one-click rollback.`);
        }
      } else {
        update(agentId, { plan: ["hybrid_search over literature + rasters", "Check grounding threshold", "Synthesize with citations or abstain"] });
        const res = await runTool(agentId, "hybrid_search", `{q:"${text.slice(0, 40)}", k:5}`, async () => {
          const r = await hybridSearch(text);
          return `${r.filter((p) => p.score >= s.settings.groundingThreshold).length} passages ≥ ${s.settings.groundingThreshold}`;
        }, 650);
        const passages = await hybridSearch(text);
        const good = passages.filter((p) => p.score >= s.settings.groundingThreshold).slice(0, 3);
        if (roi) await runTool(agentId, "roi_context", `{roi:"${roi.name}"}`, () => `${s.fmt.num(roi.areaHa, { maximumFractionDigits: 0 })} ha · ${roi.kind}`, 250);
        if (good.length === 0) {
          update(agentId, { citations: passages.slice(0, 2), caveats: ["Abstained: no retrieved segment met the grounding threshold.", "Closest passages are listed for manual inspection."] });
          await stream(agentId, `I can't answer that from the indexed corpus — top retrieval score ${passages[0]?.score.toFixed(2) ?? "0.00"} is below the ${s.settings.groundingThreshold} grounding threshold, so I'm abstaining rather than guessing. Ingest a relevant document in Resources and ask again.`);
          void res;
        } else {
          update(agentId, { citations: good, caveats: ["Figures quoted as published — not re-derived from rasters.", roi ? `Context scoped to ROI ${roi.name}.` : "No ROI active; answer is basin-wide."] });
          const body = good.map((g, i) => `${g.text.split(/(?<=[.;])\s/)[0]} [${i + 1}]`).join(" ");
          await stream(agentId, body);
        }
      }
    } catch {
      update(agentId, { text: "Tool execution failed — see Operations for logs.", streaming: false });
    } finally {
      setBusy(false);
    }
  };

  return (
    <aside className="flex h-full w-[400px] shrink-0 border-s border-line bg-surface">
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center gap-2 border-b border-line px-3 py-2">
          <div className="grid h-6 w-6 place-items-center rounded bg-brand text-white">
            <Bot className="h-3.5 w-3.5" />
          </div>
          <div className="text-[12.5px] font-semibold">GeoAgent</div>
          <Badge tone={s.online ? "ok" : "warn"} className="ms-1">
            <span className={cn("h-1.5 w-1.5 rounded-full", s.online ? "bg-ok" : "bg-warn")} /> {s.online ? s.t("liveStream") : s.t("local")}
          </Badge>
          <Mono className="ms-auto truncate text-muted">{s.settings.llmModel}</Mono>
        </header>

        {!s.online && (
          <div className="flex items-center gap-1.5 border-b border-line bg-warn-50 px-3 py-1.5 text-[11px] text-warn">
            <AlertTriangle className="h-3.5 w-3.5 shrink-0" /> {s.t("agentOffline")}
          </div>
        )}
        {s.online && s.llmReady === false && (
          <div className="flex items-center gap-1.5 border-b border-line bg-warn-50 px-3 py-1.5 text-[11px] text-warn">
            <AlertTriangle className="h-3.5 w-3.5 shrink-0" /> {s.t("retrievalOnly")}
          </div>
        )}

        <div className="border-b border-line">
          <button onClick={() => setPbOpen((o) => !o)} className="flex w-full items-center gap-1.5 px-3 py-1.5 text-[11px] font-medium uppercase tracking-wide text-muted hover:bg-canvas">
            <Play className="h-3 w-3" /> {s.t("playbooks")} <ChevronDown className={cn("ms-auto h-3.5 w-3.5 transition-transform", !pbOpen && "-rotate-90 rtl:rotate-90")} />
          </button>
          {pbOpen && (
            <div className="flex flex-col gap-1 px-2 pb-2">
              {playbooks.map((p) => (
                <button key={p.id} disabled={busy} onClick={() => send(s.t(p.key), p)} className="flex items-center gap-2 rounded-md border border-line px-2 py-1.5 text-start text-[12px] hover:border-brand hover:bg-brand-50/40 disabled:opacity-50">
                  <Sparkles className="h-3.5 w-3.5 text-brand" />
                  <span className="flex-1">{s.t(p.key)}</span>
                  <Mono className="text-[9.5px] text-muted">{p.tools.length} tools</Mono>
                </button>
              ))}
              {livePlaybooks.map((pb) => (
                <button key={pb.name} disabled={busy} onClick={() => void replayPlaybook(pb)} className="flex items-center gap-2 rounded-md border border-dashed border-line px-2 py-1.5 text-start text-[12px] hover:border-brand hover:bg-brand-50/40 disabled:opacity-50">
                  <Play className="h-3.5 w-3.5 text-brand" />
                  <span className="flex-1 truncate">{pb.name}</span>
                  <span className="text-[10px] text-muted">{s.t("replay")}</span>
                </button>
              ))}
            </div>
          )}
        </div>

        <div className="scroll-thin min-h-0 flex-1 space-y-3 overflow-y-auto p-3">
          {s.messages.length === 0 && (
            <div className="rounded-lg border border-dashed border-line p-4 text-center text-[12px] text-muted">
              <Bot className="mx-auto mb-1.5 h-6 w-6 text-line" />
              {s.t("tagline")}
              <div className="mt-2 flex flex-wrap justify-center gap-1">
                {["How does METRIC estimate ET?", "Create an ROI around the active block", "Train on my corrections"].map((x) => (
                  <button key={x} onClick={() => send(x)} className="rounded-full border border-line px-2 py-0.5 text-[11px] hover:border-brand hover:text-brand-700">
                    {x}
                  </button>
                ))}
              </div>
            </div>
          )}
          {s.messages.map((m) => (
            <MessageBubble key={m.id} m={m} onChip={(i) => setProv({ msg: m, i })} onSave={() => void saveAsPlaybook(m)} />
          ))}
          <div ref={endRef} />
        </div>

        <form
          onSubmit={(e) => {
            e.preventDefault();
            send(draft);
          }}
          className="border-t border-line p-2"
        >
          <div className="flex items-end gap-1.5 rounded-lg border border-line bg-canvas p-1.5 focus-within:border-brand">
            <textarea
              value={draft}
              onChange={(e) => s.setAgentDraft(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  send(draft);
                }
              }}
              rows={2}
              placeholder={s.t("typeMessage")}
              className="max-h-32 flex-1 resize-none bg-transparent px-1 text-[13px] outline-none"
            />
            <button type="submit" disabled={busy || !draft.trim()} className="grid h-7 w-7 place-items-center rounded-md bg-brand text-white disabled:opacity-40">
              {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Send className="h-3.5 w-3.5 rtl:-scale-x-100" />}
            </button>
          </div>
          {s.activeRoi && (
            <div className="mt-1 px-1 text-[10.5px] text-muted">
              context: <Mono>{s.activeRoi.name}</Mono> · {s.t("privacy")}
            </div>
          )}
        </form>
      </div>
      {prov && prov.msg.citations?.[prov.i] && <ProvenanceDrawer passage={prov.msg.citations[prov.i]} index={prov.i} onClose={() => setProv(null)} />}
    </aside>
  );
}

function MessageBubble({ m, onChip, onSave }: { m: ChatMessage; onChip: (i: number) => void; onSave: () => void }) {
  const s = useStore();
  if (m.role === "user")
    return (
      <div className="flex justify-end gap-2">
        <div className="max-w-[85%] rounded-lg rounded-ee-sm bg-brand px-3 py-2 text-[12.5px] text-white">{m.text}</div>
        <div className="grid h-6 w-6 shrink-0 place-items-center rounded-full bg-canvas text-muted">
          <User className="h-3.5 w-3.5" />
        </div>
      </div>
    );
  return (
    <div className="space-y-2">
      {m.plan && (
        <div className="rounded-md border border-line bg-canvas/60 p-2">
          <div className="mb-1 text-[10px] font-medium uppercase tracking-wide text-muted">{s.t("plan")}</div>
          <ol className="list-decimal space-y-0.5 ps-4 text-[11.5px]">
            {m.plan.map((p) => (
              <li key={p}>{p}</li>
            ))}
          </ol>
        </div>
      )}
      {m.tools && m.tools.length > 0 && (
        <div className="space-y-1">
          {m.tools.map((t) => (
            <div key={t.id} className="flex items-center gap-2 rounded-md border border-line bg-surface px-2 py-1.5 text-[11.5px]">
              <Wrench className="h-3.5 w-3.5 text-muted" />
              <Mono className="font-medium text-ink">{t.name}</Mono>
              <Mono className="truncate text-muted">{t.args}</Mono>
              <span className="ms-auto flex items-center gap-1.5">
                {t.durationMs !== undefined && <Mono className="text-muted">{t.durationMs} ms</Mono>}
                {t.status === "running" && <Loader2 className="h-3.5 w-3.5 animate-spin text-info" />}
                {t.status === "complete" && <CheckCircle2 className="h-3.5 w-3.5 text-ok" />}
                {t.status === "failed" && <XCircle className="h-3.5 w-3.5 text-bad" />}
              </span>
              {t.result && <span className="basis-full truncate ps-5 text-[10.5px] text-muted">↳ {t.result}</span>}
            </div>
          ))}
        </div>
      )}
      {(m.text || m.streaming) && (
        <div className="rounded-lg rounded-ss-sm border border-line bg-surface px-3 py-2 text-[12.5px] leading-relaxed">
          {renderWithChips(m.text, onChip)}
          {m.streaming && <span className="pulse-dot ms-0.5 inline-block h-3.5 w-1.5 bg-brand align-middle" />}
        </div>
      )}
      {!m.streaming && m.table && (
        <table className="w-full overflow-hidden rounded-md border border-line text-[11px]">
          <thead className="bg-canvas text-muted">
            <tr>
              {m.table.headers.map((h) => (
                <th key={h} className="px-2 py-1 text-start font-medium">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {m.table.rows.map((r, i) => (
              <tr key={i} className="border-t border-line">
                {r.map((c, j) => (
                  <td key={j} className="px-2 py-1 font-mono">
                    {c}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {!m.streaming && m.citations && m.citations.length > 0 && (
        <div className="space-y-1">
          <div className="text-[10px] font-medium uppercase tracking-wide text-muted">{s.t("sources")}</div>
          {m.citations.map((c, i) => (
            <button key={c.id} onClick={() => onChip(i)} className="flex w-full items-center gap-2 rounded-md border border-line px-2 py-1 text-start text-[11px] hover:bg-canvas">
              <span className="font-mono font-semibold text-brand-700">[{i + 1}]</span>
              <Mono className="truncate">{c.assetName}</Mono>
              {c.page !== undefined && <span className="text-muted">p.{c.page}</span>}
              <Mono className={cn("ms-auto", c.score >= s.settings.groundingThreshold ? "text-ok" : "text-bad")}>{c.score.toFixed(2)}</Mono>
            </button>
          ))}
        </div>
      )}
      {!m.streaming && m.invalidCitations && m.invalidCitations.length > 0 && (
        <div className="rounded-md bg-warn-50/60 p-2 text-[11px] text-warn">
          {m.invalidCitations.length} {s.t("invalidCitations")}: <Mono>[{m.invalidCitations.join("], [")}]</Mono>
        </div>
      )}
      {!m.streaming && m.caveats && m.caveats.length > 0 && (
        <div className="rounded-md bg-warn-50/60 p-2 text-[11px] text-warn">
          <div className="mb-0.5 font-medium uppercase tracking-wide">{s.t("caveats")}</div>
          <ul className="list-disc ps-4">
            {m.caveats.map((c) => (
              <li key={c}>{c}</li>
            ))}
          </ul>
        </div>
      )}
      {!m.streaming && m.text && (
        <button onClick={onSave} className="flex items-center gap-1.5 text-[11px] text-muted hover:text-brand-700">
          <Save className="h-3 w-3" /> {s.t("savePlaybook")}
        </button>
      )}
    </div>
  );
}
