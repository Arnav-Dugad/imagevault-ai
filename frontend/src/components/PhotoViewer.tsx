import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ChevronLeft, ChevronRight, Cloud, Download, HardDrive, LoaderCircle, Maximize2, Sparkles, Trash2, X } from "lucide-react";
import { FullscreenPhoto } from "./FullscreenPhoto";
import { FaceAvatar, personName } from "../pages/PeoplePage";
import { api } from "../lib/api";
import { useSystem } from "../lib/system";
import { formatBytes, formatDate } from "../lib/utils";
import type { PhotoDetails } from "../types";
import { PhotoThumb } from "./PhotoCard";
import { Button, ConfirmDialog, ErrorNote, MatchBadge, Modal } from "./ui";

/** A pop-up showing one photo, its details and the photos it matches.
 *  `ids` is the list the photo was opened from, so ← → can move through it. */
export function PhotoViewer({ id, ids, onClose, onDeleted }: { id: string; ids?: string[]; onClose: () => void; onDeleted: () => void }) {
  const { onAzureStorage } = useSystem();
  const [currentId, setCurrentId] = useState(id);
  const [photo, setPhoto] = useState<PhotoDetails | null>(null);
  const [error, setError] = useState("");
  const [confirming, setConfirming] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [imageLoaded, setImageLoaded] = useState(false);
  const [fullscreen, setFullscreen] = useState(false);

  useEffect(() => {
    setPhoto(null); setError(""); setImageLoaded(false);
    api<PhotoDetails>(`/photos/${currentId}`).then(setPhoto).catch((e: Error) => setError(e.message));
  }, [currentId]);

  const index = ids ? ids.indexOf(currentId) : -1;
  const prevId = index > 0 ? ids![index - 1] : null;
  const nextId = index >= 0 && index < ids!.length - 1 ? ids![index + 1] : null;
  const goPrev = useCallback(() => { if (prevId) setCurrentId(prevId); }, [prevId]);
  const goNext = useCallback(() => { if (nextId) setCurrentId(nextId); }, [nextId]);
  const closeFullscreen = useCallback(() => setFullscreen(false), []);

  useEffect(() => {
    if (fullscreen || confirming) return;
    const onKey = (event: KeyboardEvent) => {
      if ((event.target as HTMLElement).tagName === "INPUT") return;
      if (event.key === "ArrowLeft") goPrev();
      if (event.key === "ArrowRight") goNext();
      if (event.key.toLowerCase() === "f") setFullscreen(true);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [fullscreen, confirming, goPrev, goNext]);

  async function remove() {
    setDeleting(true);
    try {
      await api(`/photos/${currentId}`, { method: "DELETE" });
      onDeleted();
      onClose();
    } catch (e) {
      setError((e as Error).message);
      setConfirming(false);
    } finally {
      setDeleting(false);
    }
  }

  // Neighbouring name labels alternate above and below the face so they don't overlap.
  const named = photo?.people.filter((face) => face.name).map((face) => face.id) ?? [];
  const namedIndex = (faceId: string) => named.indexOf(faceId);

  const rows = photo ? [
    ["Size", `${photo.width} × ${photo.height} px · ${formatBytes(photo.size)}`],
    ["Type", photo.content_type.replace("image/", "").toUpperCase()],
    ["Uploaded", formatDate(photo.uploaded_at)],
    ["Fingerprint", `${photo.sha256.slice(0, 16)}…`],
  ] : [];

  return (
    <Modal onClose={onClose} className="max-w-6xl">
      <div className="grid lg:h-[86vh] lg:grid-cols-[1fr_340px]">
        <div className="relative grid min-h-[40vh] place-items-center bg-black/40 p-3 lg:min-h-0">
          {photo && <div className="relative">
            <img src={photo.file_url} alt={photo.filename} onLoad={() => setImageLoaded(true)} className="block max-h-[80vh] w-auto rounded-lg object-contain"
              onError={() => setError("Couldn't load this photo from storage. The Cloud page shows whether storage is reachable.")} />
            {imageLoaded && photo.people.map((face, i) => (
              <span key={face.id} title={face.name ?? "Recognised face"}
                className="face-box pointer-events-none absolute rounded-lg border-2 border-sky-300/80 shadow-[0_0_0_1px_rgba(0,0,0,.4)]"
                style={{ left: `${face.x * 100}%`, top: `${face.y * 100}%`, width: `${face.w * 100}%`, height: `${face.h * 100}%`, animationDelay: `${300 + i * 80}ms` }}>
                {face.name && <span className={`absolute left-1/2 -translate-x-1/2 whitespace-nowrap rounded-md bg-canvas/90 px-1.5 py-0.5 text-[11px] font-medium text-sky-200 ${namedIndex(face.id) % 2 ? "-top-6" : "-bottom-6"}`}>{face.name}</span>}
              </span>
            ))}
          </div>}
          {(!photo || !imageLoaded) && !error && <LoaderCircle className="absolute h-6 w-6 animate-spin text-acid" />}
          {photo && <button onClick={() => setFullscreen(true)} aria-label="Full screen (F)" title="Full screen (F)"
            className="focus-ring absolute right-5 top-5 rounded-full bg-black/50 p-2 text-white backdrop-blur transition hover:bg-black/70"><Maximize2 className="h-4 w-4" /></button>}
          {prevId && <button onClick={goPrev} aria-label="Previous photo (←)" className="focus-ring absolute left-5 top-1/2 -translate-y-1/2 rounded-full bg-black/50 p-2 text-white backdrop-blur transition hover:bg-black/70"><ChevronLeft className="h-5 w-5" /></button>}
          {nextId && <button onClick={goNext} aria-label="Next photo (→)" className="focus-ring absolute right-5 top-1/2 -translate-y-1/2 rounded-full bg-black/50 p-2 text-white backdrop-blur transition hover:bg-black/70"><ChevronRight className="h-5 w-5" /></button>}
          {ids && index >= 0 && <span className="absolute bottom-5 left-1/2 -translate-x-1/2 rounded-full bg-black/50 px-2.5 py-1 text-xs text-white/80 backdrop-blur">{index + 1} / {ids.length}</span>}
        </div>
        <aside className="flex flex-col border-t border-line p-5 lg:min-h-0 lg:overflow-y-auto lg:border-l lg:border-t-0">
          <div className="flex items-start justify-between gap-3">
            <h2 className="break-all text-lg font-semibold leading-snug">{photo?.filename ?? "Loading…"}</h2>
            <button onClick={onClose} aria-label="Close" className="focus-ring -mr-1 -mt-1 rounded-lg p-1.5 text-muted hover:bg-white/5 hover:text-ink"><X className="h-5 w-5" /></button>
          </div>
          {error && <div className="mt-4"><ErrorNote message={error} /></div>}
          {photo && <>
            <div className="mt-3 inline-flex w-fit items-center gap-1.5 rounded-full border border-line bg-raised px-2.5 py-1 text-xs text-muted">
              {onAzureStorage ? <Cloud className="h-3.5 w-3.5 text-lilac" /> : <HardDrive className="h-3.5 w-3.5 text-acid" />}
              {onAzureStorage ? "Stored in Azure Blob Storage" : "Stored in a local folder"}
            </div>
            <dl className="mt-5 space-y-3 text-sm">
              {rows.map(([label, value]) => <div key={label} className="flex justify-between gap-4"><dt className="text-muted">{label}</dt><dd className="text-right">{value}</dd></div>)}
            </dl>
            {(photo.ai_status === null || photo.ai_status === "processing") && (
              <p className="mt-4 flex items-center gap-2 rounded-xl border border-sky-300/20 bg-sky-300/[.06] px-3 py-2 text-xs text-sky-200">
                <Sparkles className="h-3.5 w-3.5 animate-pulse" />The free AI is still looking at this photo…
              </p>
            )}
            {photo.people.length > 0 && (() => {
              const known = photo.people.filter((face) => face.person_id && face.photos > 1);
              const others = photo.people.length - known.length;
              return <div className="mt-6">
                <h3 className="text-sm font-semibold">{photo.people.length} {photo.people.length === 1 ? "face" : "faces"} found</h3>
                {known.length > 0 && <ul className="mt-3 flex flex-wrap gap-2">
                  {known.map((face) => <li key={face.id}>
                    <Link to={`/people/${face.person_id}`} className="focus-ring flex items-center gap-2 rounded-full border border-sky-300/30 py-1 pl-1 pr-3 text-xs hover:border-sky-300/60 hover:bg-white/5">
                      <FaceAvatar src={face.image_url} className="h-7 w-7" />{personName(face)}<span className="text-muted">· {face.photos} photos</span>
                    </Link>
                  </li>)}
                </ul>}
                {others > 0 && <p className="mt-2 text-xs text-muted">{known.length ? `+ ${others} other` : `${others}`} {others === 1 ? "face" : "faces"} not seen in any other photo yet</p>}
              </div>;
            })()}
            {photo.matches.length > 0 && <div className="mt-6">
              <h3 className="text-sm font-semibold">Matches ({photo.matches.length})</h3>
              <ul className="mt-3 space-y-2">
                {photo.matches.map((match) => <li key={match.photo.id}>
                  <button onClick={() => setCurrentId(match.photo.id)} className="focus-ring flex w-full items-center gap-3 rounded-xl border border-line p-2 text-left hover:bg-white/5">
                    <PhotoThumb photo={match.photo} className="h-12 w-12 shrink-0 rounded-lg" />
                    <span className="min-w-0 flex-1"><span className="block truncate text-sm">{match.photo.filename}</span><span className="mt-1 block"><MatchBadge kind={match.kind} similarity={match.similarity} /></span></span>
                  </button>
                </li>)}
              </ul>
            </div>}
            <div className="mt-auto flex gap-2 pt-6">
              <a href={`${photo.file_url}?download=true`} download={photo.filename} className="focus-ring inline-flex h-10 flex-1 items-center justify-center gap-2 rounded-xl border border-line bg-raised text-sm font-semibold hover:bg-[#20252c]"><Download className="h-4 w-4" />Download</a>
              <Button variant="danger" className="flex-1" onClick={() => setConfirming(true)}><Trash2 className="h-4 w-4" />Delete</Button>
            </div>
          </>}
        </aside>
      </div>
      {fullscreen && photo && <FullscreenPhoto photo={photo} position={ids && index >= 0 ? `${index + 1} / ${ids.length}` : null}
        onPrev={prevId ? goPrev : undefined} onNext={nextId ? goNext : undefined} onClose={closeFullscreen} />}
      {confirming && photo && <ConfirmDialog title="Delete this photo?" message={<>“{photo.filename}” will be removed from ImageVault. This cannot be undone.</>} confirmLabel="Delete photo" busy={deleting} onConfirm={remove} onCancel={() => setConfirming(false)} />}
    </Modal>
  );
}
