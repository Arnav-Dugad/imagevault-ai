import { useState, type MouseEvent } from "react";
import { Check, Heart, ImageOff } from "lucide-react";
import { cn, formatBytes } from "../lib/utils";
import type { Photo } from "../types";
import { MatchBadge } from "./ui";

/** Where the searched words are, on a 4:3 thumbnail that crops the photo to fill it (object-cover). */
function Highlights({ photo }: { photo: Photo }) {
  if (!photo.highlights?.length || !photo.width || !photo.height) return null;
  const photoShape = photo.width / photo.height;
  const boxShape = 4 / 3;
  // The share of the photo's width (or height) that is visible, and how much is cut off on each side.
  const shownX = photoShape > boxShape ? boxShape / photoShape : 1;
  const shownY = photoShape > boxShape ? 1 : photoShape / boxShape;
  return <>{photo.highlights.map(([x, y, w, h], i) => {
    const left = (x - (1 - shownX) / 2) / shownX, top = (y - (1 - shownY) / 2) / shownY;
    const width = w / shownX, height = h / shownY;
    if (left + width < 0 || left > 1 || top + height < 0 || top > 1) return null;
    return <span key={i} className="word-box match pointer-events-none absolute rounded-sm border-2 border-acid bg-acid/20 shadow-[0_0_10px_rgb(185_243_106_/_.7)]"
      style={{ left: `${left * 100}%`, top: `${top * 100}%`, width: `${width * 100}%`, height: `${height * 100}%`, animationDelay: `${i * 60}ms` }} />;
  })}</>;
}

export function PhotoThumb({ photo, className }: { photo: Photo; className?: string }) {
  const [failed, setFailed] = useState(false);
  const [loaded, setLoaded] = useState(false);
  if (failed) return <div className={cn("grid place-items-center bg-raised text-muted", className)}><ImageOff className="h-5 w-5" /></div>;
  return <img src={photo.thumb_url} alt={photo.filename} loading="lazy" onError={() => setFailed(true)} onLoad={() => setLoaded(true)}
    className={cn("bg-raised object-cover transition-[filter,opacity] duration-500", loaded ? "opacity-100 blur-0" : "opacity-60 blur-md", className)} />;
}

interface CardProps {
  photo: Photo;
  onOpen: () => void;
  selecting?: boolean;
  selected?: boolean;
  onSelect?: (event: MouseEvent) => void;
  compact?: boolean;
}

export function PhotoCard({ photo, onOpen, selecting, selected, onSelect, compact }: CardProps) {
  function click(event: MouseEvent) {
    // In select mode (or with Ctrl/Shift held) a click selects instead of opening.
    if (onSelect && (selecting || event.ctrlKey || event.metaKey || event.shiftKey)) onSelect(event);
    else onOpen();
  }
  return (
    <div className={cn("group relative overflow-hidden rounded-2xl border bg-panel transition hover:-translate-y-0.5 hover:shadow-xl hover:shadow-black/30",
      selected ? "border-acid ring-2 ring-acid/40" : "border-line hover:border-acid/30")}>
      <button onClick={click} className="focus-ring block w-full text-left">
        <div className="relative overflow-hidden">
          <PhotoThumb photo={photo} className={cn("aspect-[4/3] w-full transition duration-300 group-hover:scale-[1.03]", selected && "scale-[.94] rounded-xl")} />
          <Highlights photo={photo} />
          {photo.ai_status === "processing" && <span className="scan-line" aria-hidden />}
          {photo.match && <div className="absolute left-2 top-2"><MatchBadge kind={photo.match} /></div>}
          {photo.favorite && <Heart className="absolute bottom-2 right-2 h-4 w-4 fill-coral text-coral drop-shadow" />}
        </div>
        {!compact && <div className="px-3 py-2.5">
          <p className="truncate text-sm font-medium">{photo.filename}</p>
          <p className="mt-0.5 text-xs text-muted">{photo.width} × {photo.height} · {formatBytes(photo.size)}</p>
        </div>}
      </button>
      {onSelect && (
        <button onClick={(e) => { e.stopPropagation(); onSelect(e); }} aria-label={selected ? "Unselect" : "Select"} aria-pressed={selected}
          className={cn("focus-ring absolute right-2 top-2 grid h-6 w-6 place-items-center rounded-full border-2 transition",
            selected ? "border-acid bg-acid text-[#11150c]" : "border-white/80 bg-black/30 text-transparent opacity-0 group-hover:opacity-100 focus-visible:opacity-100",
            selecting && "opacity-100")}>
          <Check className="h-3.5 w-3.5" strokeWidth={3} />
        </button>
      )}
    </div>
  );
}

interface GridProps {
  photos: Photo[];
  onOpen: (id: string) => void;
  selection?: Set<string>;
  onSelect?: (id: string, event: MouseEvent) => void;
  size?: GridSize;
}

export type GridSize = "small" | "medium" | "large";
const COLUMNS: Record<GridSize, string> = {
  small: "grid-cols-3 gap-1.5 sm:grid-cols-5 lg:grid-cols-6 xl:grid-cols-8",
  medium: "grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5",
  large: "grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3",
};

export function PhotoGrid({ photos, onOpen, selection, onSelect, size = "medium" }: GridProps) {
  const selecting = !!selection && selection.size > 0;
  return (
    <div className={cn("grid", COLUMNS[size])}>
      {photos.map((photo) => (
        <PhotoCard key={photo.id} photo={photo} onOpen={() => onOpen(photo.id)} selecting={selecting} compact={size === "small"}
          selected={selection?.has(photo.id)} onSelect={onSelect && ((e) => onSelect(photo.id, e))} />
      ))}
    </div>
  );
}
