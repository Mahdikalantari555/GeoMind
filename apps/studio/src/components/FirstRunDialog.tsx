import { useEffect, useState } from "react";
import { FolderOpen, PlusCircle } from "lucide-react";
import { useStore } from "@/lib/store";
import { Button, Field, inputCls } from "@/components/ui";
import { Modal } from "@/components/Modal";
import { cn } from "@/utils/cn";
import { fetchWorkspaceSuggestions, type WorkspaceSuggestion } from "@/lib/api";

type Tab = "create" | "open";

/**
 * First-run workspace setup (change: add-studio-first-run-workspace).
 * Blocking while the gateway has no open workspace — Create-new needs only a
 * name (path defaults to the platform root); Open-existing accepts a workspace
 * path or a parent directory and lists suggestions from the gateway.
 */
export function FirstRunDialog() {
  const s = useStore();
  const [tab, setTab] = useState<Tab>("create");
  const [name, setName] = useState("");
  const [createPath, setCreatePath] = useState("");
  const [openPath, setOpenPath] = useState("");
  const [suggestions, setSuggestions] = useState<WorkspaceSuggestion[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!s.wizardOpen) return;
    fetchWorkspaceSuggestions().then((list) => {
      setSuggestions(list);
      if (list[0]) setOpenPath((cur) => cur || list[0].path);
    }).catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [s.wizardOpen]);

  if (!s.wizardOpen) return null;

  const submit = async () => {
    setBusy(true);
    setError(null);
    try {
      if (tab === "create") await s.createWorkspaceAction(name.trim(), createPath.trim());
      else await s.openWorkspaceAction(openPath.trim());
    } catch (e) {
      setError(String((e as Error)?.message ?? e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal
      open={s.wizardOpen}
      label={s.t("firstRunTitle")}
      dir={s.dir}
      className="w-full max-w-md rounded-xl border border-line bg-surface shadow-lg"
    >
        <div className="border-b border-line px-4 py-3">
          <div className="text-[14px] font-semibold text-ink">{s.t("firstRunTitle")}</div>
          <div className="mt-0.5 text-[11.5px] text-muted">{s.t("firstRunSub")}</div>
        </div>
        <div className="flex gap-1 px-4 pt-3">
          {([["create", "tabCreate", PlusCircle], ["open", "tabOpen", FolderOpen]] as const).map(([id, key, Icon]) => (
            <button
              key={id}
              onClick={() => { setTab(id); setError(null); }}
              className={cn("flex h-8 flex-1 items-center justify-center gap-1.5 rounded-md text-[12.5px] font-medium", tab === id ? "bg-brand-50 text-brand-700" : "text-muted hover:bg-canvas")}
            >
              <Icon className="h-3.5 w-3.5" /> {s.t(key)}
            </button>
          ))}
        </div>
        <div className="space-y-3 px-4 py-3">
          {tab === "create" ? (
            <>
              <Field label={s.t("wsName")}>
                <input value={name} onChange={(e) => setName(e.target.value)} placeholder="karkheh-2026" autoFocus
                  className={cn(inputCls, "font-mono")} dir="ltr" onKeyDown={(e) => e.key === "Enter" && name.trim() && void submit()} />
              </Field>
              <Field label={s.t("wsPathOptional")}>
                <input value={createPath} onChange={(e) => setCreatePath(e.target.value)} placeholder="D:\RS\Data"
                  className={cn(inputCls, "font-mono")} dir="ltr" />
              </Field>
            </>
          ) : (
            <>
              <Field label={s.t("openWsPath")}>
                <input value={openPath} onChange={(e) => setOpenPath(e.target.value)} placeholder="D:\RS\Data\karkheh-2026"
                  className={cn(inputCls, "font-mono")} dir="ltr" onKeyDown={(e) => e.key === "Enter" && openPath.trim() && void submit()} />
              </Field>
              {suggestions.length > 0 && (
                <div className="space-y-1">
                  <div className="text-[11px] text-muted">{s.t("wsSuggestions")}</div>
                  {suggestions.map((w) => (
                    <button key={w.path} onClick={() => setOpenPath(w.path)}
                      className="flex w-full items-center gap-1.5 rounded-md border border-line px-2 py-1.5 text-start font-mono text-[11.5px] text-ink hover:border-brand hover:bg-canvas" dir="ltr">
                      <FolderOpen className="h-3.5 w-3.5 shrink-0 text-muted" />
                      <span className="truncate">{w.name}</span>
                    </button>
                  ))}
                </div>
              )}
              {suggestions.length === 0 && <div className="text-[11px] text-muted">{s.t("wsNoSuggestions")}</div>}
            </>
          )}
          {error && <div className="rounded-md border border-red-200 bg-red-50 px-2.5 py-1.5 text-[11.5px] text-red-700" role="alert">{error}</div>}
          <Button variant="primary" className="w-full" disabled={busy || (tab === "create" ? !name.trim() : !openPath.trim())} onClick={() => void submit()}>
            {busy ? "…" : s.t(tab === "create" ? "createWs" : "openWs")}
          </Button>
        </div>
    </Modal>
  );
}
