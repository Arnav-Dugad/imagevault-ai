import { CloudUpload, Images, Search, SlidersHorizontal } from "lucide-react";
import { useDeferredValue, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ImageCard } from "../components/ImageCard";
import { Button, EmptyState, LoadingGrid, PageHeading } from "../components/ui";
import { api } from "../lib/api";
import type { ImageList } from "../types";

const filters = [["all","All images"],["originals","Originals"],["exact","Exact duplicates"],["similar","Visually similar"],["recent","Recent"]] as const;

export function GalleryPage() {
  const [data, setData] = useState<ImageList | null>(null);
  const [search, setSearch] = useState("");
  const deferredSearch = useDeferredValue(search);
  const [filter, setFilter] = useState<(typeof filters)[number][0]>("all");
  const [sort, setSort] = useState("newest");
  const [page, setPage] = useState(1);
  const [refreshKey, setRefreshKey] = useState(0);
  const [error, setError] = useState("");
  useEffect(() => {
    setData(null); setError("");
    const params = new URLSearchParams({ page: String(page), page_size: "24", filter_by: filter, sort_by: sort });
    if (deferredSearch) params.set("search", deferredSearch);
    api<ImageList>(`/images?${params}`).then(setData).catch((reason: Error) => setError(reason.message));
  }, [deferredSearch, filter, sort, page, refreshKey]);
  useEffect(() => {
    if (!data?.items.some((image) => image.status === "PENDING" || image.status === "PROCESSING")) return;
    const timer = window.setTimeout(() => setRefreshKey((value) => value + 1), 4000);
    return () => window.clearTimeout(timer);
  }, [data]);
  function changeFilter(next: typeof filter) { setFilter(next); setPage(1); }
  return <>
    <PageHeading eyebrow="Private collection" title="Every image, intelligently indexed." description="Browse originals, exact copies, and visual matches. Signed object links expire automatically." action={<Link to="/upload"><Button><CloudUpload className="h-4 w-4" />Upload images</Button></Link>} />
    <div className="panel mb-5 rounded-2xl p-3"><div className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between"><div className="flex gap-2 overflow-x-auto pb-1 xl:pb-0">{filters.map(([value,label]) => <button key={value} onClick={() => changeFilter(value)} className={`focus-ring whitespace-nowrap rounded-xl px-3.5 py-2 text-xs font-semibold transition ${filter === value ? "bg-ink text-canvas" : "text-muted hover:bg-white/5 hover:text-ink"}`}>{label}</button>)}</div><div className="flex flex-col gap-2 sm:flex-row"><label className="relative"><Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-muted" /><span className="sr-only">Search filenames</span><input value={search} onChange={(event) => { setSearch(event.target.value); setPage(1); }} placeholder="Search filenames" className="focus-ring h-9 w-full rounded-xl border border-line bg-canvas pl-9 pr-3 text-xs sm:w-52" /></label><label className="relative"><SlidersHorizontal className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-muted" /><span className="sr-only">Sort gallery</span><select value={sort} onChange={(event) => { setSort(event.target.value); setPage(1); }} className="focus-ring h-9 w-full appearance-none rounded-xl border border-line bg-canvas pl-9 pr-8 text-xs sm:w-40"><option value="newest">Newest first</option><option value="oldest">Oldest first</option><option value="largest">Largest first</option><option value="smallest">Smallest first</option><option value="filename">Filename</option></select></label></div></div></div>
    {error ? <EmptyState icon={Images} title="Gallery unavailable" description={error} /> : !data ? <LoadingGrid /> : data.items.length === 0 ? <EmptyState icon={Images} title={search || filter !== "all" ? "No matching images" : "No images yet"} description={search || filter !== "all" ? "Try a different search or filter." : "Upload your first images and ImageVault AI will automatically analyze them for exact and visual duplicates."} action={!search && filter === "all" ? <Link to="/upload"><Button>Upload images</Button></Link> : undefined} /> : <><div className="mb-4 flex items-center justify-between"><p className="text-xs text-muted">{data.total.toLocaleString()} image{data.total === 1 ? "" : "s"}</p><p className="font-mono text-[10px] uppercase tracking-wider text-muted">Page {data.page} of {data.pages}</p></div><div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">{data.items.map((image) => <ImageCard key={image.id} image={image} />)}</div>{data.pages > 1 && <div className="mt-7 flex justify-center gap-2"><Button variant="secondary" disabled={page === 1} onClick={() => setPage((value) => value - 1)}>Previous</Button><Button variant="secondary" disabled={page === data.pages} onClick={() => setPage((value) => value + 1)}>Next</Button></div>}</>}
  </>;
}
