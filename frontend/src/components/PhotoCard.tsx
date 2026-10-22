import { useState } from "react";
import { ImageOff } from "lucide-react";
import { cn, formatBytes } from "../lib/utils";
import type { Photo } from "../types";
import { MatchBadge } from "./ui";

export function PhotoThumb({ photo, className }: { photo: Photo; className?: string }) {
  const [failed, setFailed] = useState(false);
  if (failed) return <div className={cn("grid place-items-center bg-raised text-muted", className)}><ImageOff className="h-5 w-5" /></div>;
  return <img src={photo.thumb_url} alt={photo.filename} loading="lazy" onError={() => setFailed(true)} className={cn("bg-raised object-cover", className)} />;
}

export function PhotoCard({ photo, onOpen }: { photo: Photo; onOpen: () => void }) {
  return (
    <button onClick={onOpen} className="focus-ring group overflow-hidden rounded-2xl border border-line bg-panel text-left transition hover:-translate-y-0.5 hover:border-acid/30 hover:shadow-xl hover:shadow-black/30">
      <div className="relative">
        <PhotoThumb photo={photo} className="aspect-[4/3] w-full transition duration-300 group-hover:scale-[1.03]" />
        {photo.match && <div className="absolute left-2 top-2"><MatchBadge kind={photo.match} /></div>}
      </div>
      <div className="px-3 py-2.5">
        <p className="truncate text-sm font-medium">{photo.filename}</p>
        <p className="mt-0.5 text-xs text-muted">{photo.width} × {photo.height} · {formatBytes(photo.size)}</p>
      </div>
    </button>
  );
}

export function PhotoGrid({ photos, onOpen }: { photos: Photo[]; onOpen: (id: string) => void }) {
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5">
      {photos.map((photo) => <PhotoCard key={photo.id} photo={photo} onOpen={() => onOpen(photo.id)} />)}
    </div>
  );
}
