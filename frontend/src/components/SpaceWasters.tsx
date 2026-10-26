import { useEffect, useState } from "react";
import { Check, ChevronDown, Eraser } from "lucide-react";
import { api } from "../lib/api";
import { useToast } from "../lib/toast";
import { cn, formatBytes } from "../lib/utils";
import type { CleanupItem } from "../types";
import { PhotoThumb } from "./PhotoCard";
import { Button, ConfirmDialog } from "./ui";

const SHOWN = 6;
const TONE: Record<CleanupItem["reason"], string> = {
  "Lower-quality copy": "border-lilac/40 text-lilac",
  "Blurrier shot of a burst": "border-sky-300/40 text-sky-300",
  "Very blurry": "border-amber-300/40 text-amber-300",
  Screenshot: "border-line text-muted",
  Meme: "border-line text-muted",
  "Forwarded image": "border-line text-muted",
};

/** The photos that waste the most space, biggest first, ready to delete in one go. */
export function SpaceWasters({ version, onOpen, onDeleted }: { version: number; onOpen: (id: string) => void; onDeleted: () => void }) {
  const [items, setItems] = useState<CleanupItem[] | null>(null);
  const [picked, setPicked] = useState<Set<string>>(new Set());
  const [all, setAll] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const toast = useToast();

  useEffect(() => {
    api<{ items: CleanupItem[] }>("/cleanup").then(({ items }) => {
      setItems(items);
      setPicked(new Set(items.filter((i) => i.suggested).map((i) => i.photo.id)));
    }).catch(() => setItems([]));
  }, [version]);

  if (!items?.length) return null;
  const chosen = items.filter((i) => picked.has(i.photo.id));
  const freed = chosen.reduce((sum, i) => sum + i.bytes, 0);
  const suggested = items.filter((i) => i.suggested);
  const total = suggested.reduce((sum, i) => sum + i.bytes, 0);
  const screenshots = items.length - suggested.length;
  const ordered = [...suggested, ...items.filter((i) => !i.suggested)]; // the ticked ones first
  const toggle = (id: string) => setPicked((p) => { const next = new Set(p); if (next.has(id)) next.delete(id); else next.add(id); return next; });

  async function remove() {
    setBusy(true);
    try {
      await api("/photos/batch", { method: "POST", body: JSON.stringify({ ids: chosen.map((i) => i.photo.id), action: "delete", duplicate: true }) });
      toast(`Deleted ${chosen.length} ${chosen.length === 1 ? "photo" : "photos"}, freed ${formatBytes(freed)}`);
      onDeleted();
    } catch (e) {
      toast((e as Error).message, true);
    } finally {
      setBusy(false);
      setConfirming(false);
    }
  }

  return (
    <section className="pop-in panel mb-8 overflow-hidden">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line p-4 sm:p-5">
        <div>
          <h2 className="flex items-center gap-2 font-semibold"><Eraser className="h-4 w-4 text-acid" />Free up {formatBytes(total)}</h2>
          <p className="mt-0.5 text-sm text-muted">
            {suggested.length} {suggested.length === 1 ? "photo" : "photos"} you probably don't need, biggest first.
            {screenshots > 0 && ` ${screenshots} more (screenshots, memes, forwarded images) listed too, not ticked.`}
          </p>
        </div>
        <Button variant="danger" disabled={!chosen.length} onClick={() => setConfirming(true)}>
          Delete {chosen.length} · {formatBytes(freed)}
        </Button>
      </div>
      <ul className="divide-y divide-line">
        {(all ? ordered : ordered.slice(0, SHOWN)).map((item) => {
          const on = picked.has(item.photo.id);
          return (
            <li key={item.photo.id} className={cn("flex items-center gap-3 px-4 py-2.5 transition sm:px-5", !on && "opacity-55")}>
              <button onClick={() => toggle(item.photo.id)} aria-pressed={on} aria-label={`Delete ${item.photo.filename}`}
                className={cn("focus-ring grid h-7 w-7 shrink-0 place-items-center rounded-lg border-2 transition sm:h-5 sm:w-5 sm:rounded-md", on ? "border-acid bg-acid text-[#11150c]" : "border-line")}>
                {on && <Check className="h-3.5 w-3.5" strokeWidth={3} />}
              </button>
              <button onClick={() => onOpen(item.photo.id)} aria-label={`Open ${item.photo.filename}`} className="focus-ring shrink-0 overflow-hidden rounded-lg">
                <PhotoThumb photo={item.photo} className="h-11 w-14" />
              </button>
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium">{item.photo.filename}</p>
                <p className="flex flex-wrap items-center gap-x-2 text-xs text-muted">
                  <span className={cn("rounded-full border px-2 py-px", TONE[item.reason])}>{item.reason}</span>
                  {item.keep && <span className="truncate">keeps “{item.keep.filename}”</span>}
                </p>
              </div>
              <span className="shrink-0 text-sm tabular-nums text-muted" title={item.bytes ? undefined : "Identical to the photo above; the file is stored once"}>{item.bytes ? formatBytes(item.bytes) : "same file"}</span>
            </li>
          );
        })}
      </ul>
      {items.length > SHOWN && (
        <button onClick={() => setAll(!all)} className="focus-ring flex w-full items-center justify-center gap-1.5 border-t border-line py-2.5 text-sm text-muted hover:text-ink">
          <ChevronDown className={cn("h-4 w-4 transition", all && "rotate-180")} />{all ? "Show fewer" : `Show all ${items.length}`}
        </button>
      )}
      {confirming && <ConfirmDialog busy={busy} title={`Delete ${chosen.length} ${chosen.length === 1 ? "photo" : "photos"}?`} confirmLabel="Delete"
        message={<>This frees {formatBytes(freed)}. The better copy of each photo is kept. This can't be undone.</>}
        onCancel={() => setConfirming(false)} onConfirm={remove} />}
    </section>
  );
}
