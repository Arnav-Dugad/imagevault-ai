import { useEffect, useState } from "react";
import { Cloud, Download, HardDrive, LoaderCircle, Trash2, X } from "lucide-react";
import { api } from "../lib/api";
import { useSystem } from "../lib/system";
import { formatBytes, formatDate } from "../lib/utils";
import type { PhotoDetails } from "../types";
import { PhotoThumb } from "./PhotoCard";
import { Button, ConfirmDialog, ErrorNote, MatchBadge, Modal } from "./ui";

/** A pop-up showing one photo, its details and the photos it matches. */
export function PhotoViewer({ id, onClose, onDeleted }: { id: string; onClose: () => void; onDeleted: () => void }) {
  const { onAzureStorage } = useSystem();
  const [currentId, setCurrentId] = useState(id);
  const [photo, setPhoto] = useState<PhotoDetails | null>(null);
  const [error, setError] = useState("");
  const [confirming, setConfirming] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [imageLoaded, setImageLoaded] = useState(false);

  useEffect(() => {
    setPhoto(null); setError(""); setImageLoaded(false);
    api<PhotoDetails>(`/photos/${currentId}`).then(setPhoto).catch((e: Error) => setError(e.message));
  }, [currentId]);

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

  const rows = photo ? [
    ["Size", `${photo.width} × ${photo.height} px · ${formatBytes(photo.size)}`],
    ["Type", photo.content_type.replace("image/", "").toUpperCase()],
    ["Uploaded", formatDate(photo.uploaded_at)],
    ["Fingerprint", `${photo.sha256.slice(0, 16)}…`],
  ] : [];

  return (
    <Modal onClose={onClose} className="max-w-6xl">
      <div className="grid lg:grid-cols-[1fr_340px]">
        <div className="relative grid min-h-[40vh] place-items-center bg-black/40 p-3 lg:min-h-[75vh]">
          {photo && <img src={photo.file_url} alt={photo.filename} onLoad={() => setImageLoaded(true)} className="max-h-[75vh] w-auto rounded-lg object-contain"
            onError={() => setError("Couldn't load this photo from storage. The Cloud page shows whether storage is reachable.")} />}
          {(!photo || !imageLoaded) && !error && <LoaderCircle className="absolute h-6 w-6 animate-spin text-acid" />}
        </div>
        <aside className="flex flex-col border-t border-line p-5 lg:border-l lg:border-t-0">
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
      {confirming && photo && <ConfirmDialog title="Delete this photo?" message={<>“{photo.filename}” will be removed from ImageVault. This cannot be undone.</>} confirmLabel="Delete photo" busy={deleting} onConfirm={remove} onCancel={() => setConfirming(false)} />}
    </Modal>
  );
}
