import { useEffect, type ButtonHTMLAttributes, type ReactNode } from "react";
import { LoaderCircle, type LucideIcon } from "lucide-react";
import { cn, percent } from "../lib/utils";
import type { MatchKind } from "../types";

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "ghost" | "danger";
  loading?: boolean;
};

export function Button({ className, variant = "primary", loading, children, ...props }: ButtonProps) {
  const styles = {
    primary: "bg-acid text-[#11150c] hover:bg-[#c8ff80]",
    secondary: "border border-line bg-raised text-ink hover:bg-[#20252c]",
    ghost: "text-muted hover:bg-white/5 hover:text-ink",
    danger: "bg-coral text-[#1a0907] hover:bg-[#ffa78c]",
  };
  return (
    <button
      className={cn("focus-ring inline-flex h-10 items-center justify-center gap-2 rounded-xl px-4 text-sm font-semibold transition active:scale-[.98] disabled:cursor-not-allowed disabled:opacity-50", styles[variant], className)}
      disabled={loading || props.disabled}
      {...props}
    >
      {loading && <LoaderCircle className="h-4 w-4 animate-spin" aria-hidden="true" />}
      {children}
    </button>
  );
}

export function PageHeading({ title, description, action }: { title: string; description?: ReactNode; action?: ReactNode }) {
  return (
    <div className="mb-8 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
      <div>
        <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">{title}</h1>
        {description && <div className="mt-2 max-w-2xl text-sm leading-6 text-muted">{description}</div>}
      </div>
      {action && <div className="flex shrink-0 flex-wrap gap-2">{action}</div>}
    </div>
  );
}

export function EmptyState({ icon: Icon, title, children }: { icon: LucideIcon; title: string; children?: ReactNode }) {
  return (
    <div className="panel grid place-items-center px-6 py-16 text-center">
      <div className="grid h-14 w-14 place-items-center rounded-2xl border border-acid/20 bg-acid/10"><Icon className="h-6 w-6 text-acid" /></div>
      <h2 className="mt-5 text-lg font-semibold">{title}</h2>
      <div className="mt-2 max-w-md text-sm leading-6 text-muted">{children}</div>
    </div>
  );
}

export function ErrorNote({ message }: { message: string }) {
  return <p role="alert" className="rounded-xl border border-coral/30 bg-coral/10 px-4 py-3 text-sm text-coral">{message}</p>;
}

export function Spinner({ label = "Loading" }: { label?: string }) {
  return <div className="grid min-h-[40vh] place-items-center"><LoaderCircle className="h-6 w-6 animate-spin text-acid" aria-label={label} /></div>;
}

export type BadgeKind = MatchKind | "keep" | "burst" | "sharpest" | "meme";

export function MatchBadge({ kind, similarity }: { kind: BadgeKind; similarity?: number }) {
  const styles = {
    keep: "border-acid/40 text-acid",
    sharpest: "border-acid/40 text-acid",
    exact: "border-coral/40 text-coral",
    similar: "border-lilac/40 text-lilac",
    subject: "border-sky-300/40 text-sky-300",
    burst: "border-line text-muted",
    meme: "border-lilac/40 text-lilac",
  };
  const label = kind === "keep" ? "Best copy"
    : kind === "sharpest" ? "Sharpest"
    : kind === "exact" ? "Exact copy"
    : kind === "subject" ? "Same subject"
    : kind === "burst" ? "Burst shot"
    : kind === "meme" ? "Same picture"
    : similarity ? `${percent(similarity)} similar` : "Similar";
  return <span className={cn("inline-flex items-center rounded-full border bg-canvas/85 px-2.5 py-0.5 text-xs font-semibold shadow-sm backdrop-blur", styles[kind])}>{label}</span>;
}

export function Modal({ onClose, children, className }: { onClose: () => void; children: ReactNode; className?: string }) {
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => { if (event.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => { window.removeEventListener("keydown", onKey); document.body.style.overflow = ""; };
  }, [onClose]);
  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/75 p-3 backdrop-blur-sm sm:p-6" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
      <div role="dialog" aria-modal="true" className={cn("pop-in panel max-h-full w-full overflow-auto bg-panel shadow-2xl", className)}>{children}</div>
    </div>
  );
}

export function ConfirmDialog({ title, message, confirmLabel, onConfirm, onCancel, busy }: {
  title: string; message: ReactNode; confirmLabel: string; onConfirm: () => void; onCancel: () => void; busy?: boolean;
}) {
  return (
    <Modal onClose={onCancel} className="max-w-md p-6">
      <h2 className="text-lg font-semibold">{title}</h2>
      <div className="mt-2 text-sm leading-6 text-muted">{message}</div>
      <div className="mt-6 flex justify-end gap-2">
        <Button variant="secondary" onClick={onCancel}>Cancel</Button>
        <Button variant="danger" onClick={onConfirm} loading={busy} autoFocus>{confirmLabel}</Button>
      </div>
    </Modal>
  );
}
