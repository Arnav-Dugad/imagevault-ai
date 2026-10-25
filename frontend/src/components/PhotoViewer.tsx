import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { CalendarDays, ChevronLeft, ChevronRight, Cloud, Copy, Download, FolderOpen, HardDrive, Heart, IndianRupee, Link2, LoaderCircle, Mail, Maximize2, Phone, ScanText, Sparkles, Trash2, X, type LucideIcon } from "lucide-react";
import { FullscreenPhoto } from "./FullscreenPhoto";
import { FaceAvatar, personName } from "../pages/PeoplePage";
import { api } from "../lib/api";
import { useSystem } from "../lib/system";
import { useToast } from "../lib/toast";
import { cn, formatBytes, formatDate, wordMatches } from "../lib/utils";
import type { PhotoDetails, TextFinds } from "../types";
import { PhotoThumb } from "./PhotoCard";
import { Button, ConfirmDialog, ErrorNote, MatchBadge, Modal } from "./ui";

const WORDS_SHOWN = 40; // a full page of text has hundreds of words; show the first ones until asked

/** Phone numbers, dates, prices, emails and links found in a photo's text, ready to use. */
function Finds({ found, copy }: { found: TextFinds; copy: (value: string, message: string) => Promise<void> }) {
  const chip = "focus-ring inline-flex max-w-full items-center gap-1.5 truncate rounded-lg border border-sky-300/30 bg-sky-300/[.07] px-2 py-1 text-xs text-sky-200 hover:border-sky-300/60";
  const items: { icon: LucideIcon; label: string; href?: string; copyText?: string; title: string }[] = [
    ...found.phones.map((p) => ({ icon: Phone, label: p.text, href: `tel:${p.dial}`, title: "Call" })),
    ...found.emails.map((e) => ({ icon: Mail, label: e.text, href: `mailto:${e.text}`, title: "Write an email" })),
    ...found.links.map((l) => ({ icon: Link2, label: l.text, href: l.url, title: "Open the link" })),
    ...found.dates.map((d) => ({ icon: CalendarDays, label: formatDay(d.iso), copyText: d.text, title: `Written as "${d.text}". Click to copy.` })),
    ...found.prices.map((p) => ({ icon: IndianRupee, label: p.text, copyText: p.text, title: "Click to copy" })),
  ];
  if (!items.length) return null;
  return (
    <div className="mb-3 flex flex-wrap gap-1.5">
      {items.map(({ icon: Icon, label, href, copyText, title }, i) => href
        ? <a key={i} href={href} target={href.startsWith("http") ? "_blank" : undefined} rel="noreferrer" className={chip} title={title}><Icon className="h-3.5 w-3.5 shrink-0" />{label}</a>
        : <button key={i} onClick={() => void copy(copyText ?? label, `Copied ${label}`)} className={chip} title={title}><Icon className="h-3.5 w-3.5 shrink-0" />{label}</button>)}
    </div>
  );
}

function formatDay(iso: string) {
  return new Date(`${iso}T00:00:00`).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
}

/** A pop-up showing one photo, its details and the photos it matches.
 *  `ids` is the list the photo was opened from, so ← → can move through it. */
export function PhotoViewer({ id, ids, onClose, onDeleted, onChanged, highlight = "" }: {
  id: string; ids?: string[]; onClose: () => void; onDeleted: () => void; onChanged?: () => void;
  highlight?: string; // a search: words in the photo that match it stay highlighted
}) {
  const { onAzureStorage } = useSystem();
  const toast = useToast();
  const [renaming, setRenaming] = useState(false);
  const [newName, setNewName] = useState("");
  const [currentId, setCurrentId] = useState(id);
  const [photo, setPhoto] = useState<PhotoDetails | null>(null);
  const [error, setError] = useState("");
  const [confirming, setConfirming] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [imageLoaded, setImageLoaded] = useState(false);
  const [fullscreen, setFullscreen] = useState(false);
  const [pointed, setPointed] = useState<number | null>(null); // the word under the mouse in the list
  const [allWords, setAllWords] = useState(false);
  const copy = useCallback(async (value: string, message: string) => {
    try {
      await navigator.clipboard.writeText(value);
      toast(message);
    } catch {
      toast("Couldn't copy. Select the text and copy it instead.", true);
    }
  }, [toast]);

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

  const toggleFavorite = useCallback(async () => {
    if (!photo) return;
    const updated = await api<PhotoDetails>(`/photos/${photo.id}`, { method: "PATCH", body: JSON.stringify({ favorite: !photo.favorite }) });
    setPhoto({ ...photo, favorite: updated.favorite });
    toast(updated.favorite ? "Added to favourites" : "Removed from favourites");
    onChanged?.();
  }, [photo, toast, onChanged]);

  async function rename(event: FormEvent) {
    event.preventDefault();
    if (!photo || !newName.trim() || newName === photo.filename) { setRenaming(false); return; }
    try {
      const updated = await api<PhotoDetails>(`/photos/${photo.id}`, { method: "PATCH", body: JSON.stringify({ filename: newName }) });
      setPhoto({ ...photo, filename: updated.filename });
      onChanged?.();
    } catch (e) {
      toast((e as Error).message, true);
    }
    setRenaming(false);
  }

  useEffect(() => {
    if (fullscreen || confirming || renaming) return;
    const onKey = (event: KeyboardEvent) => {
      if ((event.target as HTMLElement).tagName === "INPUT") return;
      if (event.key === "ArrowLeft") goPrev();
      if (event.key === "ArrowRight") goNext();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [fullscreen, confirming, renaming, goPrev, goNext]);

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
    ...(photo.taken_at ? [["Taken", formatDate(photo.taken_at)]] : []),
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
            {imageLoaded && photo.words.map((word, i) => {
              const match = !!highlight && wordMatches(word.text, highlight);
              return <span key={`${photo.id}-${i}`} title={word.text}
                className={cn("word-box pointer-events-none absolute rounded-md border-2 border-acid bg-acid/10",
                  match && "match border-[3px] bg-acid/20 shadow-[0_0_0_2px_rgb(0_0_0_/_.45),0_0_18px_rgb(185_243_106_/_.75)]", pointed === i && "pointed")}
                style={{ left: `${word.box[0] * 100}%`, top: `${word.box[1] * 100}%`, width: `${word.box[2] * 100}%`, height: `${word.box[3] * 100}%`, animationDelay: `${200 + i * 90}ms` }} />;
            })}
          </div>}
          {(!photo || !imageLoaded) && !error && <LoaderCircle className="absolute h-6 w-6 animate-spin text-acid" />}
          {photo && <button onClick={() => setFullscreen(true)} aria-label="Full screen" title="Full screen"
            className="focus-ring absolute right-5 top-5 rounded-full bg-black/50 p-2 text-white backdrop-blur transition hover:bg-black/70"><Maximize2 className="h-4 w-4" /></button>}
          {prevId && <button onClick={goPrev} aria-label="Previous photo (←)" className="focus-ring absolute left-5 top-1/2 -translate-y-1/2 rounded-full bg-black/50 p-2 text-white backdrop-blur transition hover:bg-black/70"><ChevronLeft className="h-5 w-5" /></button>}
          {nextId && <button onClick={goNext} aria-label="Next photo (→)" className="focus-ring absolute right-5 top-1/2 -translate-y-1/2 rounded-full bg-black/50 p-2 text-white backdrop-blur transition hover:bg-black/70"><ChevronRight className="h-5 w-5" /></button>}
          {ids && index >= 0 && <span className="absolute bottom-5 left-1/2 -translate-x-1/2 rounded-full bg-black/50 px-2.5 py-1 text-xs text-white/80 backdrop-blur">{index + 1} / {ids.length}</span>}
        </div>
        <aside className="flex flex-col border-t border-line p-5 lg:min-h-0 lg:overflow-y-auto lg:border-l lg:border-t-0">
          <div className="flex items-start justify-between gap-2">
            {renaming && photo
              ? <form onSubmit={rename} className="min-w-0 flex-1"><input autoFocus value={newName} onChange={(e) => setNewName(e.target.value)} onBlur={rename} maxLength={255}
                  onKeyDown={(e) => e.key === "Escape" && (e.stopPropagation(), setRenaming(false))} className="focus-ring h-9 w-full rounded-lg border border-line bg-canvas px-2 text-base font-semibold" /></form>
              : <button onClick={() => { if (photo) { setNewName(photo.filename); setRenaming(true); } }} title="Rename"
                  className="focus-ring min-w-0 rounded-lg text-left"><h2 className="break-all text-lg font-semibold leading-snug hover:underline hover:decoration-line">{photo?.filename ?? "Loading…"}</h2></button>}
            <div className="-mr-1 -mt-1 flex shrink-0">
              {photo && <button onClick={toggleFavorite} aria-label={photo.favorite ? "Remove from favourites" : "Add to favourites"} title="Favourite"
                className="focus-ring rounded-lg p-1.5 text-muted hover:bg-white/5 hover:text-coral"><Heart className={cn("h-5 w-5 transition", photo.favorite && "scale-110 fill-coral text-coral")} /></button>}
              <button onClick={onClose} aria-label="Close" className="focus-ring rounded-lg p-1.5 text-muted hover:bg-white/5 hover:text-ink"><X className="h-5 w-5" /></button>
            </div>
          </div>
          {error && <div className="mt-4"><ErrorNote message={error} /></div>}
          {photo && <>
            <div className="mt-3 inline-flex w-fit items-center gap-1.5 rounded-full border border-line bg-raised px-2.5 py-1 text-xs text-muted">
              {onAzureStorage ? <Cloud className="h-3.5 w-3.5 text-lilac" /> : <HardDrive className="h-3.5 w-3.5 text-acid" />}
              {onAzureStorage ? "Stored in Azure Blob Storage" : "Stored in a local folder"}
            </div>
            {photo.albums.length > 0 && <div className="mt-3 flex flex-wrap gap-1.5">
              {photo.albums.map((album) => <Link key={album.id} to={`/albums/${album.id}`} className="inline-flex items-center gap-1 rounded-full border border-line px-2.5 py-1 text-xs text-muted hover:text-ink"><FolderOpen className="h-3.5 w-3.5" />{album.name}</Link>)}
            </div>}
            <dl className="mt-5 space-y-3 text-sm">
              {rows.map(([label, value]) => <div key={label} className="flex justify-between gap-4"><dt className="text-muted">{label}</dt><dd className="text-right">{value}</dd></div>)}
            </dl>
            {photo.text && <div className="mt-5">
              <div className="mb-2 flex items-center justify-between gap-2">
                <p className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-muted"><ScanText className="h-3.5 w-3.5" />Text in the photo</p>
                <button onClick={() => void copy(photo.text, "Text copied")} className="focus-ring inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-xs text-muted hover:bg-white/5 hover:text-ink">
                  <Copy className="h-3.5 w-3.5" />Copy
                </button>
              </div>
              <Finds found={photo.found} copy={copy} />
              <p className="flex flex-wrap gap-1.5">{photo.words.slice(0, allWords ? undefined : WORDS_SHOWN).map((word, i) => (
                <button key={`${word.text}-${i}`} onMouseEnter={() => setPointed(i)} onMouseLeave={() => setPointed(null)}
                  onFocus={() => setPointed(i)} onBlur={() => setPointed(null)} title="Show where it is"
                  className={cn("focus-ring rounded-md border px-2 py-0.5 text-xs transition",
                    highlight && wordMatches(word.text, highlight) ? "border-acid/60 bg-acid/15 text-acid" : "border-line bg-canvas/60 hover:border-acid/40")}>{word.text}</button>
              ))}
              {photo.words.length > WORDS_SHOWN && <button onClick={() => setAllWords(!allWords)} className="focus-ring rounded-md px-2 py-0.5 text-xs text-acid hover:underline">
                {allWords ? "Show fewer" : `Show all ${photo.words.length}`}
              </button>}</p>
            </div>}
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
