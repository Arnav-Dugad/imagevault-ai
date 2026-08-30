import type { ButtonHTMLAttributes, ReactNode } from "react";
import { LoaderCircle, type LucideIcon } from "lucide-react";
import { cn } from "../lib/utils";
import type { ProcessingStatus } from "../types";

export function Button({ className, variant = "primary", loading, children, ...props }: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "secondary" | "ghost" | "danger"; loading?: boolean }) {
  const styles = {
    primary: "bg-acid text-[#11150c] hover:bg-[#c8ff80]",
    secondary: "border border-line bg-[#181c22] text-ink hover:bg-[#20252c]",
    ghost: "text-muted hover:bg-white/5 hover:text-ink",
    danger: "bg-[#ff765f] text-[#1a0907] hover:bg-[#ff927e]",
  };
  return <button className={cn("focus-ring inline-flex h-10 items-center justify-center gap-2 rounded-xl px-4 text-sm font-semibold transition disabled:cursor-not-allowed disabled:opacity-50", styles[variant], className)} disabled={loading || props.disabled} {...props}>
    {loading && <LoaderCircle className="h-4 w-4 animate-spin" aria-hidden="true" />}{children}
  </button>;
}

export function StatusBadge({ status }: { status: ProcessingStatus }) {
  const styles: Record<ProcessingStatus, string> = {
    READY: "bg-acid/10 text-acid border-acid/20",
    PROCESSING: "bg-lilac/10 text-lilac border-lilac/20",
    PENDING: "bg-white/5 text-muted border-line",
    EXACT_DUPLICATE: "bg-coral/10 text-coral border-coral/20",
    FAILED: "bg-red-500/10 text-red-300 border-red-500/20",
  };
  const label = status === "EXACT_DUPLICATE" ? "Exact duplicate" : status.toLowerCase();
  return <span className={cn("inline-flex rounded-full border px-2.5 py-1 font-mono text-[10px] font-medium uppercase tracking-wider", styles[status])}>{label}</span>;
}

export function PageHeading({ eyebrow, title, description, action }: { eyebrow: string; title: string; description: string; action?: ReactNode }) {
  return <div className="mb-7 flex flex-col justify-between gap-5 md:flex-row md:items-end">
    <div><p className="eyebrow mb-3">{eyebrow}</p><h1 className="text-3xl font-semibold tracking-[-.04em] md:text-4xl">{title}</h1><p className="mt-2 max-w-2xl text-sm leading-6 text-muted">{description}</p></div>
    {action}
  </div>;
}

export function EmptyState({ icon: Icon, title, description, action }: { icon: LucideIcon; title: string; description: string; action?: ReactNode }) {
  return <div className="panel flex min-h-80 flex-col items-center justify-center rounded-[28px] px-6 py-14 text-center">
    <div className="mb-5 grid h-14 w-14 place-items-center rounded-2xl border border-line bg-white/[.03]"><Icon className="h-6 w-6 text-acid" /></div>
    <h2 className="text-xl font-semibold tracking-tight">{title}</h2><p className="mt-2 max-w-md text-sm leading-6 text-muted">{description}</p>{action && <div className="mt-6">{action}</div>}
  </div>;
}

export function LoadingGrid({ count = 8 }: { count?: number }) {
  return <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">{Array.from({ length: count }, (_, index) => <div key={index} className="panel overflow-hidden rounded-2xl"><div className="skeleton aspect-[4/3]" /><div className="space-y-2 p-4"><div className="skeleton h-4 w-3/4 rounded" /><div className="skeleton h-3 w-1/2 rounded" /></div></div>)}</div>;
}
