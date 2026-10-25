import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { FileText, Images, Search, Sparkles, Upload } from "lucide-react";
import { PhotoGrid } from "../components/PhotoCard";
import { PhotoViewer } from "../components/PhotoViewer";
import { Button, EmptyState, ErrorNote, PageHeading, Spinner } from "../components/ui";
import { api } from "../lib/api";
import { cn } from "../lib/utils";
import type { Photo, PhotoList } from "../types";

const PAGE_SIZE = 60;

export function PhotosPage() {
  const [search, setSearch] = useState("");
  const [smart, setSmart] = useState(false);
  const [duplicatesOnly, setDuplicatesOnly] = useState(false);
  const [photos, setPhotos] = useState<Photo[] | null>(null);
  const [total, setTotal] = useState(0);
  const [error, setError] = useState("");
  const [loadingMore, setLoadingMore] = useState(false);
  const [openId, setOpenId] = useState<string | null>(null);

  const fetchPage = useCallback((offset: number) => {
    const query = new URLSearchParams({ search, smart: String(smart), duplicates_only: String(duplicatesOnly && !smart), offset: String(offset), limit: String(PAGE_SIZE) });
    return api<PhotoList>(`/photos?${query}`);
  }, [search, smart, duplicatesOnly]);

  const reload = useCallback(() => {
    fetchPage(0).then((page) => { setPhotos(page.items); setTotal(page.total); setError(""); }).catch((e: Error) => setError(e.message));
  }, [fetchPage]);

  useEffect(() => {
    const timer = setTimeout(reload, 200); // wait until the user stops typing
    return () => clearTimeout(timer);
  }, [reload]);

  async function loadMore() {
    if (!photos) return;
    setLoadingMore(true);
    try {
      const page = await fetchPage(photos.length);
      setPhotos([...photos, ...page.items]);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoadingMore(false);
    }
  }

  const filtered = search !== "" || (duplicatesOnly && !smart);
  return <>
    <PageHeading title="Photos" description={photos ? `${total.toLocaleString()} ${total === 1 ? "photo" : "photos"}${filtered ? " match your filters" : " in your vault"}.` : undefined}
      action={<Link to="/upload"><Button><Upload className="h-4 w-4" />Upload</Button></Link>} />

    <div className="mb-6 flex flex-col gap-3 lg:flex-row">
      <div className={cn("flex flex-1 items-center rounded-xl border bg-panel transition",
        smart ? "border-sky-300/40 shadow-[0_0_0_3px_rgba(125,211,252,.08)] focus-within:border-sky-300/80" : "border-line focus-within:border-acid/60")}>
        <label className="relative flex-1">
          <span className="sr-only">{smart ? "Describe what is in the photo" : "Search by file name"}</span>
          {smart ? <Sparkles className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-sky-300" />
            : <Search className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />}
          <input value={search} onChange={(e) => setSearch(e.target.value)}
            placeholder={smart ? "Describe it: a dog on a beach, a bridge in fog, food…" : "Search by file name…"}
            className="h-11 w-full rounded-xl bg-transparent pl-10 pr-4 text-sm outline-none placeholder:text-muted" />
        </label>
        <div className="mr-1 flex shrink-0 rounded-lg bg-canvas/60 p-0.5" role="group" aria-label="Search type">
          <button onClick={() => setSmart(false)} aria-pressed={!smart} title="Search by file name"
            className={cn("focus-ring flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-xs transition", !smart ? "bg-white/10 font-medium text-ink" : "text-muted hover:text-ink")}>
            <FileText className="h-3.5 w-3.5" />Name
          </button>
          <button onClick={() => setSmart(true)} aria-pressed={smart} title="Search by what is in the photo (free AI)"
            className={cn("focus-ring flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-xs transition", smart ? "bg-sky-300/15 font-medium text-sky-300" : "text-muted hover:text-ink")}>
            <Sparkles className="h-3.5 w-3.5" />Smart
          </button>
        </div>
      </div>
      <div className={cn("flex rounded-xl border border-line bg-panel p-1", smart && "pointer-events-none opacity-40")} role="group" aria-label="Filter">
        {[["All photos", false], ["Duplicates only", true]].map(([label, value]) => (
          <button key={String(label)} onClick={() => setDuplicatesOnly(value as boolean)} aria-pressed={duplicatesOnly === value}
            className={cn("focus-ring rounded-lg px-4 text-sm transition", duplicatesOnly === value ? "bg-white/10 font-medium text-ink" : "text-muted hover:text-ink")}>
            {label}
          </button>
        ))}
      </div>
    </div>

    {error && <ErrorNote message={error} />}
    {!photos && !error && <Spinner />}
    {photos?.length === 0 && (
      <EmptyState icon={Images} title={filtered ? "No photos found" : "No photos yet"}>
        {filtered ? (smart ? "Nothing matches that description. Try simpler words, like \"cat\" or \"mountains\"." : "Try a different search or show all photos.") :<>Head to <Link to="/upload" className="text-acid hover:underline">Upload</Link> to add your first photos.</>}
      </EmptyState>
    )}
    {photos && photos.length > 0 && <PhotoGrid photos={photos} onOpen={setOpenId} />}
    {photos && photos.length < total && (
      <div className="mt-8 text-center"><Button variant="secondary" loading={loadingMore} onClick={loadMore}>Load more photos</Button></div>
    )}
    {openId && <PhotoViewer id={openId} ids={photos?.map((p) => p.id)} onClose={() => setOpenId(null)} onDeleted={reload} />}
  </>;
}
