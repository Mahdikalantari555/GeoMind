import type { ButtonHTMLAttributes, ReactNode } from "react";
import { cn } from "@/utils/cn";
import type { JobStatus } from "@/lib/types";

export function Button({
  variant = "secondary",
  size = "md",
  className,
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "secondary" | "ghost" | "danger"; size?: "sm" | "md" }) {
  return (
    <button
      className={cn(
        "inline-flex items-center justify-center gap-1.5 rounded-md font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-50 focus-visible:outline-2 focus-visible:outline-brand",
        size === "sm" ? "h-7 px-2.5 text-xs" : "h-8 px-3 text-[13px]",
        variant === "primary" && "bg-brand text-white hover:bg-brand-600 active:bg-brand-700",
        variant === "secondary" && "border border-line bg-surface text-ink hover:bg-canvas",
        variant === "ghost" && "text-muted hover:bg-canvas hover:text-ink",
        variant === "danger" && "border border-bad/30 bg-bad-50 text-bad hover:bg-bad/10",
        className,
      )}
      {...rest}
    />
  );
}

export function Card({ children, className, title, actions }: { children: ReactNode; className?: string; title?: ReactNode; actions?: ReactNode }) {
  return (
    <section className={cn("rounded-lg border border-line bg-surface", className)}>
      {(title || actions) && (
        <header className="flex items-center justify-between gap-2 border-b border-line px-3 py-2">
          <h3 className="text-[13px] font-semibold text-ink">{title}</h3>
          <div className="flex items-center gap-2">{actions}</div>
        </header>
      )}
      {children}
    </section>
  );
}

export function Badge({ children, tone = "neutral", className }: { children: ReactNode; tone?: "neutral" | "ok" | "warn" | "bad" | "info" | "brand"; className?: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[11px] font-medium leading-none",
        tone === "neutral" && "bg-canvas text-muted border border-line",
        tone === "ok" && "bg-ok-50 text-ok",
        tone === "warn" && "bg-warn-50 text-warn",
        tone === "bad" && "bg-bad-50 text-bad",
        tone === "info" && "bg-info-50 text-info",
        tone === "brand" && "bg-brand-50 text-brand-600",
        className,
      )}
    >
      {children}
    </span>
  );
}

export const statusTone: Record<JobStatus, "ok" | "warn" | "bad" | "info" | "neutral"> = {
  running: "info",
  queued: "neutral",
  complete: "ok",
  failed: "bad",
  cancelled: "warn",
};

export function StatusBadge({ status, label }: { status: JobStatus; label: string }) {
  return (
    <Badge tone={statusTone[status]}>
      {status === "running" && <span className="pulse-dot inline-block h-1.5 w-1.5 rounded-full bg-info" />}
      {label}
    </Badge>
  );
}

export function Progress({ value, className, tone = "brand" }: { value: number; className?: string; tone?: "brand" | "bad" | "ok" }) {
  return (
    <div className={cn("h-1.5 w-full overflow-hidden rounded-full bg-line", className)}>
      <div
        className={cn("h-full rounded-full transition-all duration-500", tone === "brand" && "bg-brand", tone === "bad" && "bg-bad", tone === "ok" && "bg-ok")}
        style={{ width: `${Math.min(100, Math.max(0, value))}%` }}
      />
    </div>
  );
}

export function Field({ label, children, hint }: { label: ReactNode; children: ReactNode; hint?: ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1 block text-[11px] font-medium uppercase tracking-wide text-muted">{label}</span>
      {children}
      {hint && <span className="mt-1 block text-[11px] text-muted">{hint}</span>}
    </label>
  );
}

export const inputCls = "h-8 w-full rounded-md border border-line bg-surface px-2.5 text-[13px] text-ink outline-none focus:border-brand focus:ring-2 focus:ring-brand/20";

export function Mono({ children, className }: { children: ReactNode; className?: string }) {
  return <span className={cn("font-mono text-[11.5px] tabular-nums", className)} dir="ltr">{children}</span>;
}

export function PageHeader({ title, subtitle, actions }: { title: ReactNode; subtitle?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="text-lg font-semibold tracking-tight text-ink">{title}</h1>
        {subtitle && <p className="mt-0.5 text-[12.5px] text-muted">{subtitle}</p>}
      </div>
      {actions && <div className="flex items-center gap-2">{actions}</div>}
    </div>
  );
}

export function Toggle({ checked, onChange, label }: { checked: boolean; onChange: (b: boolean) => void; label?: ReactNode }) {
  return (
    <button type="button" onClick={() => onChange(!checked)} className="flex items-center gap-2 text-[13px]">
      <span className={cn("relative inline-block h-4.5 w-8 rounded-full transition-colors", checked ? "bg-brand" : "bg-line")}>
        <span className={cn("absolute top-0.5 h-3.5 w-3.5 rounded-full bg-white shadow transition-all", checked ? "start-4" : "start-0.5")} />
      </span>
      {label}
    </button>
  );
}

export function fmtBytes(b: number) {
  if (b > 1e9) return `${(b / 1e9).toFixed(2)} GB`;
  if (b > 1e6) return `${(b / 1e6).toFixed(1)} MB`;
  if (b > 1e3) return `${(b / 1e3).toFixed(0)} KB`;
  return `${b} B`;
}
