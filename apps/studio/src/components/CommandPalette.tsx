import { useEffect, useMemo, useState } from "react";
import { ArrowRight, Bot, Crosshair, Languages, Search } from "lucide-react";
import { useStore } from "@/lib/store";
import { NAV } from "./Topbar";
import { Modal } from "./Modal";
import { cn } from "@/utils/cn";
import type { Passage } from "@/lib/types";
import { hybridSearch } from "@/lib/api";

export function CommandPalette() {
  const s = useStore();
  const [q, setQ] = useState("");
  const [idx, setIdx] = useState(0);
  const [docs, setDocs] = useState<Passage[]>([]);

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
    const docItems = docs.map((d) => ({ id: d.id, label: `${d.assetName} · ${d.text.slice(0,70)}`, group: s.t("sources"), icon: Search, run: () => { s.setPaletteHit(d); s.setView("knowledge"); } }));
    return [...filtered, ...docItems];
    // Depend on stable callbacks/values, not the whole store object, which is
    // recreated on every streaming token (PERF-01).
  }, [q, docs, s.t, s.rois, s.lang, s.setView, s.setActiveRoi, s.requestFly, s.setLang, s.setRailOpen, s.setPaletteHit]);

  // Doc hits come from the gateway hybrid search — async, debounced by typing.
  useEffect(() => {
    setDocs([]);
    const ql = q.trim().toLowerCase();
    if (ql.length <= 3) {
      return;
    }
    let alive = true;
    const timer = setTimeout(()=>void hybridSearch(q)
      .then((ps) => {
        if (alive) setDocs(ps.slice(0, 3));
      })
      .catch(() => {
        if (alive) setDocs([]);
      }),250);
    return () => {clearTimeout(timer);
      alive = false;
    };
  }, [q]);

  useEffect(() => setIdx(0), [q]);
  useEffect(() => {
    if (!s.paletteOpen) setQ("");
  }, [s.paletteOpen]);

  if (!s.paletteOpen) return null;
  const run = (i: number) => {
    if (!items[i]) return;
    items[i].run();
    s.setPaletteOpen(false);
  };
  return (
    <Modal
      open={s.paletteOpen}
      onClose={() => s.setPaletteOpen(false)}
      label={s.t("search")}
      placement="top"
      className="w-[560px] overflow-hidden rounded-xl border border-line bg-surface shadow-2xl"
    >
        <div className="flex items-center gap-2 border-b border-line px-3">
          <Search className="h-4 w-4 text-muted" />
          <input
            autoFocus
            value={q}
            onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => {
              if(e.nativeEvent.isComposing) return;
              if (e.key === "ArrowDown") setIdx((i) => Math.min(items.length - 1, i + 1));
              if (e.key === "ArrowUp") setIdx((i) => Math.max(0, i - 1));
              if (e.key === "Enter") run(idx);
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
    </Modal>
  );
}
