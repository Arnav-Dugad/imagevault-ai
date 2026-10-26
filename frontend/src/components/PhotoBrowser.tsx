import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { CalendarRange, FileText, Grid2x2, Grid3x3, Images, Search, Sparkles, Square, X } from "lucide-react";
import { api } from "../lib/api";
import { useSelection } from "../lib/selection";
import { cn } from "../lib/utils";
import type { Photo, PhotoList, SortKey } from "../types";
import { PhotoGrid, type GridSize } from "./PhotoCard";
import { PhotoViewer } from "./PhotoViewer";
import { SelectionBar } from "./SelectionBar";
import { EmptyState, ErrorNote, Spinner } from "./ui";

const PAGE_SIZE = 60;
const SORTS: { key: SortKey; label: string }[] = [
  { key: "newest", label: "Newest uploads" },
  { key: "oldest", label: "Oldest uploads" },
  { key: "taken_new", label: "Date taken (newest)" },
  { key: "taken_old", label: "Date taken (oldest)" },
  { key: "largest", label: "Largest files" },
  { key: "smallest", label: "Smallest files" },
  { key: "name", label: "Name (A–Z)" },
];
type Filter = "all" | "duplicates" | "favorites" | "text";

interface Options { smart: boolean; filter: Filter; sort: SortKey; size: GridSize }

/** Remembers the last sort and filter between visits (per page). */
function useRemembered(key: string): [Options, (change: Partial<Options>) => void] {
  const [options, setOptions] = useState<Options>(() => {
    const fallback: Options = { smart: false, filter: "all", sort: "newest", size: "medium" };
    try { return { ...fallback, ...JSON.parse(localStorage.getItem(`imagevault.${key}`) ?? "{}") }; } catch { return fallback; }
  });
  const update = useCallback((change: Partial<Options>) => setOptions((current) => {
    const next = { ...current, ...change };
    try { localStorage.setItem(`imagevault.${key}`, JSON.stringify(next)); } catch { /* private window */ }
    return next;
  }), [key]);
  return [options, update];
}

export function PhotoBrowser({ albumId, rememberAs, header, emptyText }: {
  albumId?: string; rememberAs: string; header: (total: number | null) => ReactNode; emptyText?: ReactNode;
}) {
  const [{ smart, filter, sort, size }, setOptions] = useRemembered(rememberAs);
  const [search, setSearch] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [photos, setPhotos] = useState<Photo[] | null>(null);
  const [total, setTotal] = useState(0);
  const [error, setError] = useState("");
  const [loadingMore, setLoadingMore] = useState(false);
  const [openId, setOpenId] = useState<string | null>(null);
  const end = useRef<HTMLDivElement>(null);

  const order = useMemo(() => photos?.map((p) => p.id) ?? [], [photos]);
  const { selected, toggle, clear, selectAll } = useSelection(order);

  const fetchPage = useCallback((offset: number) => {
    const query = new URLSearchParams({ search, smart: String(smart), filter, sort, date_from: dateFrom, date_to: dateTo,
      offset: String(offset), limit: String(PAGE_SIZE), ...(albumId ? { album: albumId } : {}) });
    return api<PhotoList>(`/photos?${query}`);
  }, [search, smart, filter, sort, dateFrom, dateTo, albumId]);

  const reload = useCallback(() => {
    fetchPage(0).then((page) => { setPhotos(page.items); setTotal(page.total); setError(""); }).catch((e: Error) => setError(e.message));
  }, [fetchPage]);

  useEffect(() => {
    const timer = setTimeout(reload, 200); // wait until the user stops typing
    return () => clearTimeout(timer);
  }, [reload]);

  // Infinite scroll: load the next page when the end of the grid comes into view.
  const loadMore = useCallback(async () => {
    if (!photos || loadingMore || photos.length >= total) return;
    setLoadingMore(true);
    try {
      const page = await fetchPage(photos.length);
      setPhotos([...photos, ...page.items]);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoadingMore(false);
    }
  }, [photos, total, loadingMore, fetchPage]);
  useEffect(() => {
    const target = end.current;
    if (!target) return;
    const observer = new IntersectionObserver((entries) => { if (entries[0].isIntersecting) void loadMore(); }, { rootMargin: "600px" });
    observer.observe(target);
    return () => observer.disconnect();
  }, [loadMore]);

  const clearFilters = () => { setSearch(""); setDateFrom(""); setDateTo(""); setOptions({ filter: "all" }); };
  const filtered = search !== "" || filter !== "all" || dateFrom !== "" || dateTo !== "";
  const pill = (active: boolean) => cn("focus-ring whitespace-nowrap rounded-lg px-3 py-1.5 text-sm transition", active ? "bg-white/10 font-medium text-ink" : "text-muted hover:text-ink");
  return <>
    {header(photos ? total : null)}

    <div className="mb-3 flex flex-col gap-3 lg:flex-row">
      <div className={cn("flex flex-1 items-center rounded-xl border bg-panel transition",
        smart ? "border-sky-300/40 focus-within:border-sky-300/80" : "border-line focus-within:border-acid/60")}>
        <label className="relative flex-1">
          <span className="sr-only">{smart ? "Describe what is in the photo" : "Search by file name or text in the photo"}</span>
          {smart ? <Sparkles className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-sky-300" />
            : <Search className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />}
          <input value={search} onChange={(e) => setSearch(e.target.value)}
            placeholder={smart ? "Describe it: a dog on a beach, food, a bridge in fog…" : "Search by name or by text in the photo"}
            className="h-11 w-full rounded-xl bg-transparent pl-10 pr-9 text-sm outline-none placeholder:text-muted" />
          {search && <button onClick={() => setSearch("")} aria-label="Clear search" className="absolute right-2 top-1/2 -translate-y-1/2 rounded p-1 text-muted hover:text-ink"><X className="h-4 w-4" /></button>}
        </label>
        <div className="mr-1 flex shrink-0 rounded-lg bg-canvas/60 p-0.5" role="group" aria-label="Search type">
          <button onClick={() => setOptions({ smart: false })} aria-pressed={!smart} className={cn("focus-ring flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-xs", !smart ? "bg-white/10 font-medium text-ink" : "text-muted hover:text-ink")}><FileText className="h-3.5 w-3.5" />Name</button>
          <button onClick={() => setOptions({ smart: true })} aria-pressed={smart} title="Search by what's in the photo" className={cn("focus-ring flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-xs", smart ? "bg-sky-300/15 font-medium text-sky-300" : "text-muted hover:text-ink")}><Sparkles className="h-3.5 w-3.5" />Smart</button>
        </div>
      </div>
      <div className="flex overflow-x-auto rounded-xl border border-line bg-panel p-1" role="group" aria-label="Filter">
        {([["all", "All"], ["text", "Text"], ["duplicates", "Duplicates"], ["favorites", "Favourites"]] as [Filter, string][]).map(([key, label]) => (
          <button key={key} onClick={() => setOptions({ filter: key })} aria-pressed={filter === key} className={pill(filter === key)}>{label}</button>
        ))}
      </div>
    </div>

    <div className="mb-6 flex flex-wrap items-center gap-2 text-sm">
      <select value={sort} onChange={(e) => setOptions({ sort: e.target.value as SortKey })} disabled={smart && !!search} aria-label="Sort"
        className="focus-ring h-9 rounded-lg border border-line bg-panel px-2.5 text-sm disabled:opacity-50">
        {SORTS.map((s) => <option key={s.key} value={s.key}>{s.label}</option>)}
      </select>
      <label className="order-last flex h-9 w-full items-center gap-2 rounded-lg border border-line bg-panel px-2.5 text-muted sm:order-none sm:w-auto">
        <CalendarRange className="h-4 w-4" /><span className="sr-only">From</span>
        <input type="date" value={dateFrom} max={dateTo || undefined} onChange={(e) => setDateFrom(e.target.value)} className="bg-transparent text-ink outline-none [color-scheme:dark]" />
        <span>–</span>
        <input type="date" value={dateTo} min={dateFrom || undefined} onChange={(e) => setDateTo(e.target.value)} aria-label="To" className="bg-transparent text-ink outline-none [color-scheme:dark]" />
      </label>
      {(dateFrom || dateTo) && <button onClick={() => { setDateFrom(""); setDateTo(""); }} className="order-last text-muted hover:text-ink sm:order-none">Clear dates</button>}
      <div className="ml-auto flex rounded-lg border border-line bg-panel p-0.5" role="group" aria-label="Thumbnail size">
        {([["small", Grid3x3], ["medium", Grid2x2], ["large", Square]] as const).map(([key, Icon]) => (
          <button key={key} onClick={() => setOptions({ size: key })} aria-pressed={size === key} title={`${key[0].toUpperCase()}${key.slice(1)} thumbnails`}
            className={cn("focus-ring grid h-8 w-8 place-items-center rounded-md", size === key ? "bg-white/10 text-ink" : "text-muted hover:text-ink")}><Icon className="h-4 w-4" /></button>
        ))}
      </div>
    </div>

    {error && <ErrorNote message={error} />}
    {!photos && !error && <Spinner />}
    {photos?.length === 0 && (
      <EmptyState icon={Images} title={filtered ? "Nothing found" : "No photos yet"}>
        {filtered ? <>{smart && search ? "Try simpler words, like “cat” or “mountains”. " : ""}
          <button onClick={clearFilters} className="text-acid hover:underline">Clear filters</button></>
          : emptyText ?? <><Link to="/upload" className="text-acid hover:underline">Upload</Link> your first photos.</>}
      </EmptyState>
    )}
    {photos && photos.length > 0 && <PhotoGrid photos={photos} onOpen={setOpenId} selection={selected} onSelect={toggle} size={size} />}
    <div ref={end} className="h-px" />
    {loadingMore && <Spinner />}
    <SelectionBar selected={selected} total={total} albumId={albumId} onSelectAll={selectAll} onClear={clear} onChanged={reload} />
    {openId && <PhotoViewer id={openId} ids={order} onClose={() => setOpenId(null)} onDeleted={reload} onChanged={reload} highlight={search} />}
  </>;
}
