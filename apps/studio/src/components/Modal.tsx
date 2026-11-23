import { useEffect, useRef, type CSSProperties, type ReactNode } from "react";

interface ModalProps {
  open: boolean;
  /** Dismiss handler. When omitted the dialog is blocking (Escape does nothing). */
  onClose?: () => void;
  label: string;
  children: ReactNode;
  className?: string;
  placement?: "center" | "top";
  dir?: string;
  style?: CSSProperties;
}

const FOCUSABLE =
  'a[href],button:not([disabled]),input:not([disabled]),select:not([disabled]),textarea:not([disabled]),[tabindex]:not([tabindex="-1"])';

/**
 * Shared accessible dialog: role/aria-modal, focus trap, Escape to dismiss and
 * focus restoration. Matches the command palette contract (CORRECT-09).
 */
export function Modal({
  open,
  onClose,
  label,
  children,
  className = "",
  placement = "center",
  dir,
  style,
}: ModalProps) {
  const dialogRef = useRef<HTMLDivElement>(null);
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;

  useEffect(() => {
    if (!open) return;
    const previous = document.activeElement as HTMLElement | null;
    const dialog = dialogRef.current;
    // `offsetParent` is always null in jsdom, so filter on explicit hidden
    // attributes instead — this also works for conditionally-rendered controls.
    const focusables = () =>
      Array.from(dialog?.querySelectorAll<HTMLElement>(FOCUSABLE) ?? []).filter(
        (el) => !el.hasAttribute("hidden") && el.getAttribute("aria-hidden") !== "true",
      );

    // Prefer the element marked autoFocus, else the first focusable control.
    (dialog?.querySelector<HTMLElement>("[autofocus]") ?? focusables()[0])?.focus();

    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && onCloseRef.current) {
        e.preventDefault();
        onCloseRef.current();
        return;
      }
      if (e.key !== "Tab") return;
      const nodes = focusables();
      if (nodes.length === 0) return;
      const first = nodes[0];
      const last = nodes[nodes.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      previous?.focus?.();
    };
  }, [open]);

  if (!open) return null;

  const overlay =
    placement === "top"
      ? "fixed inset-0 z-50 flex items-start justify-center bg-ink/30 p-4 pt-24 backdrop-blur-[1px]"
      : "fixed inset-0 z-50 grid place-items-center bg-black/50 p-4";

  return (
    <div
      className={overlay}
      dir={dir}
      style={style}
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onCloseRef.current?.();
      }}
    >
      <div ref={dialogRef} role="dialog" aria-modal="true" aria-label={label} className={className}>
        {children}
      </div>
    </div>
  );
}
