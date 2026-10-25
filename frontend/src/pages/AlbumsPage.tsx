import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, FolderOpen, ImageOff, Pencil, Plus, Sparkles, Trash2 } from "lucide-react";
import { NameSuggestions } from "../components/NameSuggestions";
import { PhotoBrowser } from "../components/PhotoBrowser";
import { Button, ConfirmDialog, EmptyState, ErrorNote, PageHeading, Spinner } from "../components/ui";
import { api } from "../lib/api";
import { useToast } from "../lib/toast";
import { formatBytes } from "../lib/utils";
import type { Album } from "../types";

function AlbumTile({ album, index }: { album: Album; index: number }) {
  return (
    <Link to={`/albums/${encodeURIComponent(album.id)}`} style={{ animationDelay: `${index * 40}ms`, animationFillMode: "backwards" }}
      className="pop-in focus-ring group overflow-hidden rounded-2xl border border-line bg-panel transition hover:-translate-y-0.5 hover:border-acid/30">
      {album.cover_url
        ? <img src={album.cover_url} alt="" loading="lazy" className="aspect-[4/3] w-full object-cover transition duration-300 group-hover:scale-[1.03]" />
        : <div className="grid aspect-[4/3] place-items-center bg-raised text-muted"><ImageOff className="h-6 w-6" /></div>}
      <div className="px-3 py-2.5">
        <p className="truncate text-sm font-semibold">{album.name}</p>
        <p className="text-xs text-muted">{album.count} {album.count === 1 ? "photo" : "photos"}{album.count > 0 && ` · ${formatBytes(album.bytes)}`}</p>
      </div>
    </Link>
  );
}

export function AlbumsPage() {
  const [albums, setAlbums] = useState<{ mine: Album[]; auto: Album[] } | null>(null);
  const [error, setError] = useState("");
  const [name, setName] = useState("");
  const [creating, setCreating] = useState(false);
  const toast = useToast();
  const load = useCallback(() => { api<{ mine: Album[]; auto: Album[] }>("/albums").then(setAlbums).catch((e: Error) => setError(e.message)); }, []);
  useEffect(load, [load]);

  async function create(event: FormEvent) {
    event.preventDefault();
    if (!name.trim()) return;
    await api("/albums", { method: "POST", body: JSON.stringify({ name }) });
    toast(`Album “${name.trim()}” created`);
    setName(""); setCreating(false); load();
  }

  if (error) return <ErrorNote message={error} />;
  if (!albums) return <Spinner />;
  const grid = "grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5";
  return <>
    <PageHeading title="Albums" action={creating
      ? <form onSubmit={create} className="flex gap-2"><input autoFocus value={name} onChange={(e) => setName(e.target.value)} placeholder="Album name" maxLength={100}
          onKeyDown={(e) => e.key === "Escape" && setCreating(false)} className="focus-ring h-10 rounded-xl border border-line bg-panel px-3 text-sm" /><Button type="submit">Create</Button></form>
      : <Button onClick={() => setCreating(true)}><Plus className="h-4 w-4" />New album</Button>} />

    <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-muted">Your albums</h2>
    {albums.mine.length === 0
      ? <p className="mb-10 text-sm text-muted">None yet. Select photos on the Photos page and choose <b className="text-ink">Album</b>, or create one above.</p>
      : <div className={`${grid} mb-10`}>{albums.mine.map((a, i) => <AlbumTile key={a.id} album={a} index={i} />)}</div>}

    <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold uppercase tracking-wider text-muted"><Sparkles className="h-4 w-4 text-sky-300" />Made automatically</h2>
    {albums.auto.length === 0
      ? <EmptyState icon={FolderOpen} title="Nothing to sort yet">Albums like Pets, Food and Mountains appear here once your photos have been analysed.</EmptyState>
      : <div className={grid}>{albums.auto.map((a, i) => <AlbumTile key={a.id} album={a} index={i} />)}</div>}
  </>;
}

export function AlbumPage() {
  const id = decodeURIComponent(useParams().id ?? "");
  const navigate = useNavigate();
  const toast = useToast();
  const [album, setAlbum] = useState<Album | null>(null);
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState("");
  const [deleting, setDeleting] = useState(false);
  const [photoIds, setPhotoIds] = useState<string[]>([]); // for name suggestions while renaming
  const auto = id.startsWith("auto:");
  useEffect(() => {
    if (!editing) return;
    api<{ items: { id: string }[] }>(`/photos?album=${encodeURIComponent(id)}&limit=200`)
      .then((r) => setPhotoIds(r.items.map((p) => p.id))).catch(() => setPhotoIds([]));
  }, [editing, id]);

  const load = useCallback(() => {
    api<{ mine: Album[]; auto: Album[] }>("/albums").then((all) => {
      const found = [...all.mine, ...all.auto].find((a) => a.id === id) ?? null;
      setAlbum(found);
      setName(found?.name ?? "");
    }).catch(() => {});
  }, [id]);
  useEffect(load, [load]);

  async function rename(event: FormEvent) {
    event.preventDefault();
    await api(`/albums/${id}`, { method: "PATCH", body: JSON.stringify({ name }) });
    setEditing(false); load();
  }
  async function remove() {
    await api(`/albums/${id}`, { method: "DELETE" });
    toast(`Album “${album?.name}” deleted (its photos are kept)`);
    navigate("/albums");
  }

  return <>
    <Link to="/albums" className="focus-ring mb-6 inline-flex items-center gap-1.5 rounded-lg text-sm text-muted hover:text-ink"><ArrowLeft className="h-4 w-4" />Albums</Link>
    <PhotoBrowser albumId={id} rememberAs="album" emptyText={auto ? "No photos here yet." : "Empty. Select photos on the Photos page and choose Album."} header={(total) => (
      <div className="mb-8 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          {editing
            ? <div className="space-y-2">
                <form onSubmit={rename} className="flex gap-2"><input autoFocus value={name} onChange={(e) => setName(e.target.value)} maxLength={100}
                  onKeyDown={(e) => e.key === "Escape" && setEditing(false)} className="focus-ring h-11 rounded-xl border border-line bg-canvas px-3 text-2xl font-semibold" /><Button type="submit">Save</Button></form>
                <NameSuggestions ids={photoIds} onPick={setName} />
              </div>
            : <h1 className="flex items-center gap-2 text-3xl font-semibold tracking-tight sm:text-4xl">{auto && <Sparkles className="h-6 w-6 text-sky-300" />}{album?.name ?? "Album"}</h1>}
          <p className="mt-2 text-sm text-muted">{total ?? "…"} {total === 1 ? "photo" : "photos"}{auto && " · sorted by the AI"}</p>
        </div>
        {!auto && album && !editing && <div className="flex gap-2">
          <Button variant="secondary" onClick={() => setEditing(true)}><Pencil className="h-4 w-4" />Rename</Button>
          <Button variant="secondary" onClick={() => setDeleting(true)} className="hover:text-coral"><Trash2 className="h-4 w-4" />Delete album</Button>
        </div>}
      </div>
    )} />
    {deleting && <ConfirmDialog title="Delete this album?" confirmLabel="Delete album" message="Only the album is deleted. The photos stay in ImageVault."
      onCancel={() => setDeleting(false)} onConfirm={remove} />}
  </>;
}
