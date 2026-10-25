import { useCallback, useEffect, useState } from "react";
import { HardDrive, Recycle, Trash2 } from "lucide-react";
import { api } from "../lib/api";
import { useSystem } from "../lib/system";
import { useToast } from "../lib/toast";
import { cn, formatBytes, rupees } from "../lib/utils";
import type { StorageUsage } from "../types";
import { Button, ConfirmDialog } from "./ui";

// Fixed colour per part (checked for colour-blind readers on the dark background).
const PARTS: Record<StorageUsage["parts"][number]["key"], { label: string; color: string }> = {
  originals: { label: "Photos", color: "#3987e5" },
  thumbnails: { label: "Thumbnails", color: "#d95926" },
  faces: { label: "Face crops", color: "#199e70" },
};

const RADIUS = 52;
const CIRCLE = 2 * Math.PI * RADIUS;
const GAP = 2.5; // space between segments, in px along the ring

function Donut({ usage, active, onActive }: { usage: StorageUsage; active: string | null; onActive: (key: string | null) => void }) {
  const total = usage.total_bytes;
  const parts = usage.parts.filter((p) => p.bytes > 0);
  let offset = 0;
  return (
    <div className="relative h-40 w-40 shrink-0">
      <svg viewBox="0 0 128 128" className="h-full w-full -rotate-90" role="img" aria-label={`Storage used: ${formatBytes(total)}`}>
        <circle cx="64" cy="64" r={RADIUS} fill="none" stroke="var(--color-raised)" strokeWidth="14" />
        {total > 0 && parts.map((part) => {
          const length = (part.bytes / total) * CIRCLE;
          const visible = parts.length > 1 ? Math.max(length - GAP, 1) : length;
          const segment = (
            <circle key={part.key} cx="64" cy="64" r={RADIUS} fill="none" stroke={PARTS[part.key].color}
              strokeWidth={active === part.key ? 18 : 14} strokeDasharray={`${visible} ${CIRCLE - visible}`} strokeDashoffset={-offset}
              className="cursor-default transition-[stroke-width] duration-200"
              onMouseEnter={() => onActive(part.key)} onMouseLeave={() => onActive(null)} />
          );
          offset += length;
          return segment;
        })}
      </svg>
      <div className="pointer-events-none absolute inset-0 grid place-items-center text-center">
        <div>
          <p className="text-xl font-semibold tabular-nums">{formatBytes(total)}</p>
          <p className="text-xs text-muted">{active ? PARTS[active as keyof typeof PARTS].label : "in total"}</p>
        </div>
      </div>
    </div>
  );
}

/** How much space the photos take, what that costs each month, and what deleting duplicates saved. */
export function StorageCard() {
  const [usage, setUsage] = useState<StorageUsage | null>(null);
  const [error, setError] = useState("");
  const [active, setActive] = useState<string | null>(null);
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const { refresh } = useSystem();
  const toast = useToast();

  const load = useCallback(() => {
    api<StorageUsage>("/storage").then(setUsage).catch((e: Error) => setError(e.message));
  }, []);
  useEffect(load, [load]);

  async function deleteEverything() {
    setBusy(true);
    try {
      await api("/reset", { method: "POST", body: JSON.stringify({ confirm: "delete everything" }) });
      toast("Everything deleted. Ready for a fresh start.");
      load();
      void refresh();
    } catch (e) {
      toast((e as Error).message, true);
    } finally {
      setBusy(false);
      setConfirming(false);
    }
  }

  const onAzure = usage?.kind === "azure";
  return (
    <section className="panel p-5 sm:p-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="flex items-center gap-2 font-semibold"><HardDrive className="h-4 w-4 text-acid" />Storage</h2>
          <p className="mt-1 text-sm text-muted">{onAzure ? "Azure Blob Storage" : "A folder on this computer"}</p>
        </div>
        <Button variant="ghost" className="h-9 text-sm hover:text-coral" onClick={() => setConfirming(true)} disabled={!usage}>
          <Trash2 className="h-4 w-4" />Delete everything
        </Button>
      </div>

      {error && <p className="mt-4 text-sm text-coral">{error}</p>}
      {!usage && !error && <div className="skeleton mt-5 h-40 w-full rounded-2xl" />}
      {usage && (
        <div className="mt-5 flex flex-col gap-6 sm:flex-row sm:items-center">
          <Donut usage={usage} active={active} onActive={setActive} />
          <div className="min-w-0 flex-1">
            <ul className="space-y-1.5 text-sm">
              {usage.parts.map((part) => (
                <li key={part.key} onMouseEnter={() => setActive(part.key)} onMouseLeave={() => setActive(null)}
                  className={cn("flex items-center gap-3 rounded-lg px-2 py-1 transition", active === part.key && "bg-white/5")}>
                  <span className="h-2.5 w-2.5 shrink-0 rounded-sm" style={{ background: PARTS[part.key].color }} />
                  <span className="flex-1 text-muted">{PARTS[part.key].label}</span>
                  <span className="tabular-nums">{formatBytes(part.bytes)}</span>
                  <span className="w-11 text-right text-xs tabular-nums text-muted">
                    {usage.total_bytes ? `${Math.round((part.bytes / usage.total_bytes) * 100)}%` : "0%"}
                  </span>
                </li>
              ))}
            </ul>
            <div className="mt-4 grid gap-3 border-t border-line pt-4 sm:grid-cols-2">
              <div>
                <p className="text-xs text-muted">Estimated cost</p>
                <p className="mt-0.5 font-semibold">{onAzure ? rupees(usage.monthly_cost * usage.inr_rate, true) : "Free (local)"}</p>
                {onAzure && <p className="text-xs text-muted">per month · {rupees(usage.price_per_gb * usage.inr_rate)} per GB</p>}
              </div>
              <div>
                <p className="flex items-center gap-1.5 text-xs text-muted"><Recycle className="h-3.5 w-3.5 text-acid" />Saved from duplicates</p>
                <p className="mt-0.5 font-semibold">{formatBytes(usage.saved_bytes)}</p>
                {onAzure && <p className="text-xs text-muted">{rupees(usage.saved_monthly * usage.inr_rate, true)} per month</p>}
              </div>
            </div>
          </div>
        </div>
      )}

      {confirming && <ConfirmDialog busy={busy} title="Delete everything?" confirmLabel="Delete everything"
        message="Every photo, person and album is deleted from the database and from storage. Useful before a demo. This can't be undone."
        onCancel={() => setConfirming(false)} onConfirm={deleteEverything} />}
    </section>
  );
}
