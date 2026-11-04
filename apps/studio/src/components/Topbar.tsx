import { Activity, Bot, ChevronDown, Command, Database, FlaskConical, Globe2, Layers, Library, Lock, Map as MapIcon, Settings, ShieldCheck, Wifi, WifiOff } from "lucide-react";
import { useStore } from "@/lib/store";
import type { View } from "@/lib/types";
import { cn } from "@/utils/cn";
import type { TKey } from "@/lib/i18n";

export const NAV: { id: View; key: TKey; icon: typeof MapIcon }[] = [
  { id: "map", key: "nav_map", icon: MapIcon },
  { id: "acquire", key: "nav_acquire", icon: Database },
  { id: "resources", key: "nav_resources", icon: Library },
  { id: "knowledge", key: "nav_knowledge", icon: Globe2 },
  { id: "training", key: "nav_training", icon: FlaskConical },
  { id: "ops", key: "nav_ops", icon: Activity },
  { id: "settings", key: "nav_settings", icon: Settings },
];

export function Topbar() {
  const s = useStore();
  const activeJobs = s.jobs.filter((j) => j.status === "running" || j.status === "queued").length;
  return (
    <header className="flex h-12 shrink-0 items-center gap-2 border-b border-line bg-surface px-3">
      <div className="flex items-center gap-2 pe-2">
        <div className="grid h-7 w-7 place-items-center rounded-md bg-brand text-white">
          <Layers className="h-4 w-4" />
        </div>
        <span className="hidden text-[13.5px] font-semibold tracking-tight lg:inline">{s.t("appName")}</span>
      </div>

      <div className="relative">
        <select
          value={s.workspace}
          onChange={(e) => s.setWorkspace(e.target.value)}
          className="h-8 appearance-none rounded-md border border-line bg-canvas ps-2.5 pe-7 font-mono text-[12px] text-ink outline-none focus:border-brand"
          title={s.t("workspace")}
        >
          {s.workspaces.map((w) => (
            <option key={w}>{w}</option>
          ))}
        </select>
        <ChevronDown className="pointer-events-none absolute end-2 top-2.5 h-3.5 w-3.5 text-muted" />
      </div>

      <nav className="ms-2 hidden items-center gap-0.5 md:flex">
        {NAV.map((n) => (
          <button
            key={n.id}
            onClick={() => s.setView(n.id)}
            className={cn(
              "flex h-8 items-center gap-1.5 rounded-md px-2.5 text-[12.5px] font-medium transition-colors",
              s.view === n.id ? "bg-brand-50 text-brand-700" : "text-muted hover:bg-canvas hover:text-ink",
            )}
          >
            <n.icon className="h-3.5 w-3.5" />
            <span className="hidden xl:inline">{s.t(n.key)}</span>
          </button>
        ))}
      </nav>

      <button
        onClick={() => s.setPaletteOpen(true)}
        className="ms-auto flex h-8 w-56 items-center gap-2 rounded-md border border-line bg-canvas px-2.5 text-[12px] text-muted hover:border-brand/50"
      >
        <Command className="h-3.5 w-3.5" />
        <span className="flex-1 truncate text-start">{s.t("search")}</span>
        <kbd className="rounded border border-line bg-surface px-1 font-mono text-[10px]">⌘K</kbd>
      </button>

      <button onClick={() => s.setView("ops")} className="relative flex h-8 items-center gap-1.5 rounded-md border border-line px-2 text-[12px] text-muted hover:bg-canvas" title={s.t("jobQueue")}>
        <Activity className={cn("h-3.5 w-3.5", activeJobs && "text-info")} />
        <span className="tabular-nums">{s.fmt.num(activeJobs)}</span>
        <span className="hidden lg:inline">{s.t("jobs")}</span>
        {activeJobs > 0 && <span className="pulse-dot absolute -end-0.5 -top-0.5 h-2 w-2 rounded-full bg-info" />}
      </button>

      <div
        className={cn("flex h-8 items-center gap-1.5 rounded-md px-2 text-[12px] font-medium", s.online ? "bg-ok-50 text-ok" : "bg-warn-50 text-warn")}
        title={s.online ? `${s.t("gateway")} /api/v1` : s.t("offline")}
      >
        {s.online ? <Wifi className="h-3.5 w-3.5" /> : <WifiOff className="h-3.5 w-3.5" />}
        <span className="hidden lg:inline">{s.online ? s.t("gateway") : s.t("offline")}</span>
      </div>

      <button onClick={() => s.setView("settings")} className="hidden h-8 items-center gap-1.5 rounded-md border border-line px-2 text-[12px] text-muted hover:bg-canvas lg:flex" title={s.t("privacy")}>
        <ShieldCheck className="h-3.5 w-3.5 text-ok" />
        <Lock className="h-3 w-3" />
        <span className="max-w-36 truncate font-mono text-[11px]" dir="ltr">
          {s.settings.llmModel}
        </span>
      </button>

      <div className="flex h-8 overflow-hidden rounded-md border border-line text-[12px] font-medium">
        {(["en", "fa"] as const).map((l) => (
          <button key={l} onClick={() => s.setLang(l)} className={cn("px-2.5", s.lang === l ? "bg-brand text-white" : "text-muted hover:bg-canvas")}>
            {l === "en" ? "EN" : "فا"}
          </button>
        ))}
      </div>

      <button
        onClick={() => s.setRailOpen((b) => !b)}
        title={s.t("toggleRail")}
        className={cn("grid h-8 w-8 place-items-center rounded-md border border-line", s.railOpen ? "bg-brand-50 text-brand-700" : "text-muted hover:bg-canvas")}
      >
        <Bot className="h-4 w-4" />
      </button>
    </header>
  );
}
