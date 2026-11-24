import { useEffect, useRef, useState } from "react";
import { AlertTriangle, Bot, CheckCircle2, ChevronDown, Loader2, Play, Save, Send, Wrench, XCircle, User } from "lucide-react";
import { useStore, uid } from "@/lib/store";
import {
  getConversation,
  listPlaybooks,
  normalizeCitationMarkers,
  runPlaybook,
  savePlaybook,
  streamAgentChat,
  stripInvalidCitations,
  type AgentToolRun,
} from "@/lib/api";
import type { ChatMessage, Playbook, ToolCall } from "@/lib/types";
import { Badge, Mono } from "./ui";
import { cn } from "@/utils/cn";
import { ProvenanceDrawer, renderWithChips } from "@/views/KnowledgeView";

export function AgentRail() {
  const s = useStore();
  const [busy, setBusy] = useState(false);
  const [thinking, setThinking] = useState(false);
  const [prov, setProv] = useState<{ msg: ChatMessage; i: number } | null>(null);
  const [pbOpen, setPbOpen] = useState(true);
  const [livePlaybooks, setLivePlaybooks] = useState<Playbook[]>([]);
  const endRef = useRef<HTMLDivElement>(null);
  // A new send or unmount cancels the previous stream (CORRECT-04).
  const streamRef = useRef<AbortController | null>(null);
  useEffect(() => () => streamRef.current?.abort(), []);
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

  /** Live gateway chat: POST /agent/chat SSE. No scripted replies (F-095). */
  const sendLive = async (text: string) => {
    streamRef.current?.abort();
    const controller = new AbortController();
    streamRef.current = controller;
    const agentId = uid("m");
    s.setMessages((ms) => [
      ...ms,
      { id: uid("user"), role: "user", text },
      { id: agentId, role: "agent", text: "", streaming: true, tools: [] },
    ]);
    let acc = "";
    let terminal = false;
    let conversationId = s.conversationId;
    const tools: ToolCall[] = [];
    const caveats: string[] = [];
    let degraded = false;
    setThinking(true);
    try {
      await streamAgentChat(
        text,
        (e) => {
          if (e.conversationId) {
            conversationId = e.conversationId;
            s.setConversationId(e.conversationId);
          }
          if (e.event === "message" && e.text) {
            // Keep citation markers intact while streaming; the server has
            // already stripped invalid ones (CORRECT-02).
            acc = e.final ? e.text : acc + e.text;
            terminal = e.final === true;
            setThinking(false);
            update(agentId, { text: acc, streaming: !terminal });
          } else if (e.event === "tool_start" && e.tool) {
            setThinking(false);
            const tc: ToolCall = { id: e.id ?? uid("tc"), name: e.tool, args: e.args ?? "", status: "running" };
            tools.push(tc);
            update(agentId, { tools: [...tools] });
          } else if (e.event === "tool_end" && e.tool) {
            // Match by id first, then oldest running call of the same name.
            // geoagent appends " (N citations)" to ok, so prefix-match (F-095).
            const tc = (e.id ? tools.find((t) => t.id === e.id) : undefined)
              ?? tools.find((t) => t.name === e.tool && t.status === "running");
            if (tc) {
              tc.status = e.status?.startsWith("ok") ? "complete" : "failed";
              tc.result = e.status || undefined;
              update(agentId, { tools: [...tools] });
            }
          } else if (e.event === "error" && e.message) {
            terminal = true;
            degraded = e.code === "agent_not_ready" || e.code === "backend_error";
            caveats.push(e.message);
            if (degraded) caveats.push(s.t("configureLlm"));
            update(agentId, { text: acc || e.message, streaming: false, caveats: [...caveats], degraded });
          } else if (e.event === "done") {
            terminal = true;
          }
          // `thinking` / `conversation` are surfaced by the indicator above.
        },
        s.conversationId,
        controller.signal,
      );
      void terminal;
      // geoagent uses [S#]; rewrite to [n] for the chip renderer, then strip
      // anything still unresolved. The server already removed invalid keys.
      const { text: cleaned, invalid } = stripInvalidCitations(normalizeCitationMarkers(acc), null);
      update(agentId, {
        text: cleaned,
        streaming: false,
        invalidCitations: invalid.length ? invalid : undefined,
        caveats: caveats.length ? caveats : undefined,
        degraded,
      });
      // Hydrate tool cards from the persisted ToolRun audit records — the SSE
      // events carry only {id, tool, status} (spec studio-agent-rail §3.3).
      if (conversationId) {
        void getConversation(conversationId)
          .then(({ tool_runs }) => {
            const byId = new Map<string, AgentToolRun>(tool_runs.map((r) => [r.id, r]));
            const hydrated = tools.map((t) => {
              const run = byId.get(t.id);
              return run
                ? {
                    ...t,
                    args: run.args_json,
                    durationMs: run.latency_ms ?? undefined,
                    result: run.error ?? t.result,
                    status: run.status === "ok" ? ("complete" as const) : ("failed" as const),
                  }
                : t;
            });
            update(agentId, { tools: hydrated });
          })
          .catch(() => { /* cards keep their SSE data if audit is unavailable */ });
      }
    } catch (err) {
      if (controller.signal.aborted) return;
      const message = String(err instanceof Error ? err.message : err);
      degraded = /agent not ready|gateway offline/i.test(message);
      update(agentId, {
        text: message,
        streaming: false,
        caveats: degraded ? [message, s.t("configureLlm")] : [message],
        degraded,
      });
    } finally {
      setThinking(false);
      if (streamRef.current === controller) streamRef.current = null;
    }
  };

  const replayPlaybook = async (pb: Playbook) => {
    if (busy) return;
    setBusy(true);
    const agentId = uid("m");
    const label = `Replay ${pb.name}`;
    s.setMessages((ms) => [...ms, { id: uid("user"), role: "user", text: label }, { id: agentId, role: "agent", text: "", streaming: true, tools: [] }]);
    try {
      const result = await runPlaybook(pb.name);
      update(agentId, {
        streaming: false,
        text: `Playbook ${pb.name} completed.`,
        table: { headers: ["Result"], rows: [[JSON.stringify(result)]] },
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

  /** Only the live gateway path exists — scripted replies are retired (F-095). */
  const send = async (text: string) => {
    if (!text.trim() || busy) return;
    if (!s.online) {
      s.toast(s.t("gatewayOfflineHint"), "bad");
      return;
    }
    s.setAgentDraft("");
    setBusy(true);
    try {
      await sendLive(text);
    } finally {
      setBusy(false);
    }
  };

  return (
    <aside className="max-md:absolute max-md:inset-x-0 max-md:top-12 max-md:bottom-12 max-md:z-30 max-md:w-full max-md:h-auto flex h-full w-[400px] shrink-0 border-s border-line bg-surface">
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center gap-2 border-b border-line px-3 py-2">
          <div className="grid h-6 w-6 place-items-center rounded bg-brand text-white">
            <Bot className="h-3.5 w-3.5" />
          </div>
          <div className="text-[12.5px] font-semibold">{s.t("geoAgent")}</div>
          <Badge tone={s.online ? "ok" : "warn"} className="ms-1">
            <span className={cn("h-1.5 w-1.5 rounded-full", s.online ? "bg-ok" : "bg-warn")} /> {s.online ? s.t("liveStream") : s.t("local")}
          </Badge>
          <Mono className="ms-auto truncate text-muted">{s.settings.llmModel}</Mono>
        </header>

        {!s.online && (
          <div className="flex items-center gap-1.5 border-b border-line bg-warn-50 px-3 py-1.5 text-[11px] text-warn">
            <AlertTriangle className="h-3.5 w-3.5 shrink-0" /> {s.t("gatewayOfflineHint")}
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
                {([s.t("suggestEt"), s.t("suggestRoi"), s.t("suggestTrain")] as const).map((x) => (
                  <button key={x} disabled={!s.online} onClick={() => send(x)} className="rounded-full border border-line px-2 py-0.5 text-[11px] hover:border-brand hover:text-brand-700 disabled:opacity-40">
                    {x}
                  </button>
                ))}
              </div>
            </div>
          )}
          {s.messages.map((m) => (
            <MessageBubble key={m.id} m={m} onChip={(i) => setProv({ msg: m, i })} onSave={() => void saveAsPlaybook(m)} />
          ))}
          {thinking && (
            <div role="status" className="flex items-center gap-1.5 text-[11px] text-muted">
              <Loader2 className="h-3 w-3 animate-spin" /> {s.t("thinking")}
            </div>
          )}
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
                if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
                  e.preventDefault();
                  send(draft);
                }
              }}
              rows={2}
              placeholder={s.t("typeMessage")}
              className="max-h-32 flex-1 resize-none bg-transparent px-1 text-[13px] outline-none"
            />
            <button aria-label={s.lang === "fa" ? "ارسال پیام" : "Send message"} type="submit" disabled={busy || !draft.trim()} className="grid h-7 w-7 place-items-center rounded-md bg-brand text-white disabled:opacity-40">
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
