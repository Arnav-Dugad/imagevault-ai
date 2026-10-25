import { useEffect, useRef, useState, type FormEvent } from "react";
import { Download, FolderMinus, FolderPlus, Heart, HeartOff, Plus, Trash2, X } from "lucide-react";
import { api } from "../lib/api";
import { useToast } from "../lib/toast";
import type { Album } from "../types";
import { NameSuggestions } from "./NameSuggestions";
import { Button, ConfirmDialog } from "./ui";

const plural = (n: number) => `${n} ${n === 1 ? "photo" : "photos"}`;

function AlbumMenu({ ids, onPick, onClose }: { ids: string[]; onPick: (album: { id?: string; name?: string }) => void; onClose: () => void }) {
  const [albums, setAlbums] = useState<Album[] | null>(null);
  const [name, setName] = useState("");
  const box = useRef<HTMLDivElement>(null);
  useEffect(() => { api<{ mine: Album[] }>("/albums").then((r) => setAlbums(r.mine)).catch(() => setAlbums([])); }, []);
  useEffect(() => {
    const away = (e: Event) => { if (!box.current?.contains(e.target as Node)) onClose(); };
    window.addEventListener("pointerdown", away);
    return () => window.removeEventListener("pointerdown", away);
  }, [onClose]);
  function create(event: FormEvent) {
    event.preventDefault();
    if (name.trim()) onPick({ name: name.trim() });
  }
  return (
    <div ref={box} className="pop-in absolute bottom-full left-1/2 mb-2 w-64 -translate-x-1/2 rounded-2xl border border-line bg-raised p-2 shadow-2xl">
      <p className="px-2 py-1 text-xs font-medium text-muted">Add to album</p>
      <div className="max-h-56 overflow-y-auto">
        {albums?.map((album) => (
          <button key={album.id} onClick={() => onPick({ id: album.id })} className="focus-ring flex w-full items-center justify-between rounded-lg px-2 py-1.5 text-left text-sm hover:bg-white/5">
            <span className="truncate">{album.name}</span><span className="text-xs text-muted">{album.count}</span>
          </button>
        ))}
        {albums?.length === 0 && <p className="px-2 py-1.5 text-sm text-muted">No albums yet.</p>}
      </div>
      <form onSubmit={create} className="mt-1 flex gap-1 border-t border-line pt-2">
        <input autoFocus value={name} onChange={(e) => setName(e.target.value)} placeholder="New album" maxLength={100}
          className="focus-ring h-9 min-w-0 flex-1 rounded-lg border border-line bg-canvas px-2 text-sm" />
        <Button type="submit" className="h-9 px-2.5" aria-label="Create album"><Plus className="h-4 w-4" /></Button>
      </form>
      <div className="mt-2 px-1"><NameSuggestions ids={ids} onPick={setName} /></div>
    </div>
  );
}

/** The bar at the bottom of the screen for doing something to all selected photos. */
export function SelectionBar({ selected, total, albumId, onSelectAll, onClear, onChanged }: {
  selected: Set<string>; total: number; albumId?: string; onSelectAll: () => void; onClear: () => void; onChanged: () => void;
}) {
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [albumMenu, setAlbumMenu] = useState(false);
  const ids = [...selected];

  async function run(action: string, extra: Record<string, string> = {}, message = "") {
    setBusy(true);
    try {
      const result = await api<{ done: number }>("/photos/batch", { method: "POST", body: JSON.stringify({ ids, action, ...extra }) });
      toast(message || `${plural(result.done)} updated`);
      onChanged();
      if (action === "delete" || action === "remove_from_album") onClear();
    } catch (e) {
      toast((e as Error).message, true);
    } finally {
      setBusy(false);
      setConfirming(false);
      setAlbumMenu(false);
    }
  }

  if (!selected.size) return null;
  const icon = "flex h-9 shrink-0 items-center gap-1.5 rounded-lg px-2 text-sm sm:px-2.5 transition hover:bg-white/10 disabled:opacity-50";
  return <>
    <div className="pop-in fixed bottom-5 left-1/2 z-40 flex max-w-[calc(100vw-1rem)] -translate-x-1/2 items-center gap-0.5 rounded-2xl sm:gap-1 border border-line bg-raised/95 p-1.5 shadow-2xl backdrop-blur lg:ml-30">
      <button onClick={onClear} aria-label="Clear selection" title="Clear selection" className={icon}><X className="h-4 w-4" /></button>
      <span className="whitespace-nowrap px-1 text-sm font-semibold">{selected.size}<span className="hidden sm:inline"> selected</span></span>
      {selected.size < total && <button onClick={onSelectAll} className={`${icon} whitespace-nowrap text-muted hover:text-ink`}><span className="sm:hidden">All</span><span className="hidden sm:inline">Select all {total}</span></button>}
      <span className="mx-1 hidden h-6 w-px bg-line sm:block" />
      <button disabled={busy} onClick={() => run("favorite", {}, `${plural(selected.size)} added to favourites`)} className={icon} title="Favourite"><Heart className="h-4 w-4" /><span className="hidden sm:inline">Favourite</span></button>
      <button disabled={busy} onClick={() => run("unfavorite", {}, `${plural(selected.size)} removed from favourites`)} className={icon} title="Remove from favourites"><HeartOff className="h-4 w-4" /></button>
      <div className="relative">
        <button disabled={busy} onClick={() => setAlbumMenu(!albumMenu)} className={icon}><FolderPlus className="h-4 w-4" /><span className="hidden sm:inline">Album</span></button>
        {albumMenu && <AlbumMenu ids={ids} onClose={() => setAlbumMenu(false)} onPick={(album) => run("add_to_album",
          album.id ? { album_id: album.id } : { new_album: album.name! }, `${plural(selected.size)} added to ${album.name ? `“${album.name}”` : "the album"}`)} />}
      </div>
      {albumId && !albumId.startsWith("auto:") && (
        <button disabled={busy} onClick={() => run("remove_from_album", { album_id: albumId }, `${plural(selected.size)} removed from this album`)} className={icon} title="Remove from this album">
          <FolderMinus className="h-4 w-4" /><span className="hidden sm:inline">Remove</span>
        </button>
      )}
      <a href={`/api/zip?ids=${ids.slice(0, 100).join(",")}`} download className={icon} title={selected.size > 100 ? "Downloads the first 100" : "Download as ZIP"}>
        <Download className="h-4 w-4" /><span className="hidden sm:inline">Download</span>
      </a>
      <button disabled={busy} onClick={() => setConfirming(true)} className={`${icon} text-coral hover:bg-coral/10`}><Trash2 className="h-4 w-4" /><span className="hidden sm:inline">Delete</span></button>
    </div>
    {confirming && <ConfirmDialog title={`Delete ${plural(selected.size)}?`} confirmLabel="Delete" busy={busy}
      message="They will be removed from ImageVault and from cloud storage. This can't be undone."
      onCancel={() => setConfirming(false)} onConfirm={() => run("delete", {}, `${plural(selected.size)} deleted`)} />}
  </>;
}
