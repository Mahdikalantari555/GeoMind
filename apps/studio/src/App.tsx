import { useEffect } from "react";
import { StoreProvider, useStore } from "@/lib/store";
import { Topbar, NAV } from "@/components/Topbar";
import { CommandPalette } from "@/components/CommandPalette";
import { AgentRail } from "@/components/AgentRail";
import { MapView } from "@/views/MapView";
import { AcquireView } from "@/views/AcquireView";
import { ResourcesView } from "@/views/ResourcesView";
import { KnowledgeView } from "@/views/KnowledgeView";
import { TrainingView } from "@/views/TrainingView";
import { OpsView } from "@/views/OpsView";
import { SettingsView } from "@/views/SettingsView";
import { cn } from "@/utils/cn";

function Shell() {
  const s = useStore();

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if(e.repeat || e.isComposing) return;
      const mod = e.metaKey || e.ctrlKey;
      if (mod && e.key.toLowerCase() === "k") {
        e.preventDefault();
        s.setPaletteOpen(true);
      }
      if (mod && e.key.toLowerCase() === "b") {
        e.preventDefault();
        s.setRailOpen((b) => !b);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [s]);

  const view =
    s.view === "map" ? <MapView /> :
    s.view === "acquire" ? <AcquireView /> :
    s.view === "resources" ? <ResourcesView /> :
    s.view === "knowledge" ? <KnowledgeView /> :
    s.view === "training" ? <TrainingView /> :
    s.view === "ops" ? <OpsView /> :
    <SettingsView />;

  return (
    <div className={cn("flex h-screen flex-col overflow-hidden bg-canvas", s.settings.density === "comfortable" && "text-[14px]")}>
      <Topbar />
      <div className="flex min-h-0 flex-1">
        <main className="min-w-0 flex-1 overflow-hidden">{view}</main>
        {s.railOpen && <AgentRail />}
      </div>
      {/* Mobile nav */}
      <nav className="flex shrink-0 border-t border-line bg-surface md:hidden">
        {NAV.map((n) => (
          <button aria-label={s.t(n.key)} aria-current={s.view === n.id ? "page" : undefined} key={n.id} onClick={() => s.setView(n.id)} className={cn("flex flex-1 flex-col items-center gap-0.5 py-1.5 text-[10px]", s.view === n.id ? "text-brand-700" : "text-muted")}>
            <n.icon className="h-4 w-4" />
          </button>
        ))}
      </nav>
      <CommandPalette />
      {/* Toasts */}
      <div aria-live="polite" aria-relevant="additions" className="pointer-events-none fixed bottom-4 start-1/2 z-50 flex -translate-x-1/2 flex-col gap-2 rtl:translate-x-1/2">
        {s.toasts.map((t) => (
          <div
            key={t.id}
            className={cn(
              "rounded-md border px-3 py-2 text-[12.5px] shadow-lg",
              t.tone === "ok" && "border-ok/30 bg-ok-50 text-ok",
              t.tone === "warn" && "border-warn/30 bg-warn-50 text-warn",
              t.tone === "bad" && "border-bad/30 bg-bad-50 text-bad",
              (!t.tone || t.tone === "info") && "border-line bg-surface text-ink",
            )}
          >
            {t.text}
          </div>
        ))}
      </div>
    </div>
  );
}

export default function App() {
  return (
    <StoreProvider>
      <Shell />
    </StoreProvider>
  );
}
