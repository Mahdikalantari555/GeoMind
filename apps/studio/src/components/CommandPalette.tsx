import { useEffect, useMemo, useState } from "react";
import { ArrowRight, Bot, Crosshair, Languages, Search } from "lucide-react";
import { useStore } from "@/lib/store";
import { NAV } from "./Topbar";
import { cn } from "@/utils/cn";
import { hybridSearch } from "@/lib/api";

export function CommandPalette() {
  const s = useStore();
  const [q, setQ] = useState("");
  const [idx, setIdx] = useState(0);
  const [docs, setDocs] = useState<{ id: string; label: string }[]>([]);

  const items = useMemo(() => {
    const nav = NAV.map((n) => ({ id: `nav-${n.id}`, label: s.t(n.key), group: s.t("commands"), icon: n.icon, run: () => s.setView(n.id) }));
    const rois = s.rois.map((r) => ({
      id: `roi-${r.id}`,
      label: r.name,
      group: s.t("rois"),
      icon: Crosshair,
      run: () => {
        s.setActiveRoi(r.id);
        s.setView("map");
        s.requestFly(r.centroid);
      },
    }));
    const misc = [
      { id: "lang", label: s.lang === "en" ? "Switch to Persian (فارسی)" : "Switch to English", group: s.t("commands"), icon: Languages, run: () => s.setLang(s.lang === "en" ? "fa" : "en") },
      { id: "rail", label: s.t("toggleRail"), group: s.t("commands"), icon: Bot, run: () => s.setRailOpen((b) => !b) },
    ];
    const all = [...nav, ...rois, ...misc];
    const ql = q.trim().toLowerCase();
    const filtered = ql ? all.filter((i) => i.label.toLowerCase().includes(ql)) : all;
    const docItems = docs.map((d) => ({ id: d.id, label: d.label, group: s.t("sources"), icon: Search, run: () => { s.setView("knowledge"); } }));
    return [...filtered, ...docItems];
  }, [q, s, docs]);

  // Doc hits come from the gateway hybrid search — async, debounced by typing.
  useEffect(() => {
    const ql = q.trim().toLowerCase();
    if (ql.length <= 3) {
      setDocs([]);
      return;
    }
    let alive = true;
    hybridSearch(q)
      .then((ps) => {
        if (alive) setDocs(ps.slice(0, 3).map((p) => ({ id: p.id, label: `${p.assetName} · ${p.text.slice(0, 70)}…` })));
      })
      .catch(() => {
        if (alive) setDocs([]);
      });
    return () => {
      alive = false;
    };
  }, [q]);

  useEffect(() => setIdx(0), [q]);
  useEffect(() => {
    if (!s.paletteOpen) setQ("");
  }, [s.paletteOpen]);

  if (!s.paletteOpen) return null;
  const run = (i: number) => {
    items[i]?.run();
    s.setPaletteOpen(false);
  };
  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center bg-ink/30 pt-24 backdrop-blur-[1px]" onClick={() => s.setPaletteOpen(false)}>
      <div className="w-[560px] overflow-hidden rounded-xl border border-line bg-surface shadow-2xl" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center gap-2 border-b border-line px-3">
          <Search className="h-4 w-4 text-muted" />
          <input
            autoFocus
            value={q}
            onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "ArrowDown") setIdx((i) => Math.min(items.length - 1, i + 1));
              if (e.key === "ArrowUp") setIdx((i) => Math.max(0, i - 1));
              if (e.key === "Enter") run(idx);
              if (e.key === "Escape") s.setPaletteOpen(false);
            }}
            placeholder={s.t("search")}
            className="h-11 flex-1 bg-transparent text-[14px] outline-none"
          />
          <kbd className="rounded border border-line px-1 font-mono text-[10px] text-muted">esc</kbd>
        </div>
        <ul className="scroll-thin max-h-80 overflow-y-auto p-1.5">
          {items.length === 0 && <li className="px-3 py-6 text-center text-muted">{s.t("noResults")}</li>}
          {items.map((it, i) => (
            <li key={it.id}>
              <button
                onMouseEnter={() => setIdx(i)}
                onClick={() => run(i)}
                className={cn("flex w-full items-center gap-2.5 rounded-md px-2.5 py-2 text-start text-[13px]", i === idx ? "bg-brand-50 text-brand-700" : "text-ink")}
              >
                <it.icon className="h-4 w-4 shrink-0 text-muted" />
                <span className="flex-1 truncate">{it.label}</span>
                <span className="text-[10.5px] uppercase tracking-wide text-muted">{it.group}</span>
                {i === idx && <ArrowRight className="h-3.5 w-3.5 rtl:rotate-180" />}
              </button>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
