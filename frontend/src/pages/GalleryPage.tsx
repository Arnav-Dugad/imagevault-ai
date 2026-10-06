import { AnimatePresence, motion } from "framer-motion";
import { AlertTriangle, Check, CloudUpload, Images, Search, SlidersHorizontal, Sparkles, Trash2, X } from "lucide-react";
import { FormEvent, useDeferredValue, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { ImageCard } from "../components/ImageCard";
import { Button, EmptyState, LoadingGrid, PageHeading } from "../components/ui";
import { api } from "../lib/api";
import { formatBytes } from "../lib/utils";
import type { ImageList } from "../types";

const filters = [["all","All images"],["originals","Originals"],["exact","Exact duplicates"],["similar","Visually similar"],["recent","Recent"]] as const;
type SearchMode = "smart" | "filename";

export function GalleryPage() {
  const [data, setData] = useState<ImageList | null>(null);
  const [search, setSearch] = useState("");
  const [smartQuery, setSmartQuery] = useState("");
  const [searchMode, setSearchMode] = useState<SearchMode>("smart");
  const deferredSearch = useDeferredValue(search);
  const [filter, setFilter] = useState<(typeof filters)[number][0]>("all");
  const [sort, setSort] = useState("newest");
  const [page, setPage] = useState(1);
  const [refreshKey, setRefreshKey] = useState(0);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [selecting, setSelecting] = useState(false);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [confirming, setConfirming] = useState(false);
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    setData(null); setError("");
    const params = new URLSearchParams({ page: String(page), page_size: "24" });
    let path = "/images";
    if (searchMode === "smart" && smartQuery) {
      params.set("query", smartQuery); path += "/smart-search";
    } else {
      params.set("filter_by", filter); params.set("sort_by", sort);
      if (searchMode === "filename" && deferredSearch) params.set("search", deferredSearch);
    }
    api<ImageList>(`${path}?${params}`, { signal: controller.signal })
      .then((value) => { if (!controller.signal.aborted) setData(value); })
      .catch((reason: Error) => { if (!controller.signal.aborted) setError(reason.message); });
    return () => controller.abort();
  }, [deferredSearch, filter, page, refreshKey, searchMode, smartQuery, sort]);

  useEffect(() => { setSelected(new Set()); setConfirming(false); }, [deferredSearch, filter, page, searchMode, smartQuery, sort]);

  useEffect(() => {
    if (!data?.items.some((image) => image.analysis_pending || image.status === "PENDING" || image.status === "PROCESSING")) return;
    const timer = window.setTimeout(() => setRefreshKey((value) => value + 1), 4000);
    return () => window.clearTimeout(timer);
  }, [data]);

  const selectedBytes = useMemo(() => data?.items.filter((image) => selected.has(image.id)).reduce((total, image) => total + image.file_size, 0) ?? 0, [data, selected]);
  function changeFilter(next: typeof filter) { setFilter(next); setPage(1); setSelected(new Set()); }
  function setMode(next: SearchMode) { setSearchMode(next); setSmartQuery(""); setPage(1); setSelected(new Set()); }
  function submitSearch(event: FormEvent) { event.preventDefault(); if (searchMode === "smart") { setSmartQuery(search.trim()); setPage(1); setSelected(new Set()); } }
  function toggle(id: string) { setSelected((current) => { const next = new Set(current); if (next.has(id)) next.delete(id); else next.add(id); return next; }); }
  function toggleAll() { const visible = data?.items ?? []; setSelected((current) => current.size === visible.length ? new Set() : new Set(visible.map((image) => image.id))); }
  function stopSelecting() { setSelecting(false); setSelected(new Set()); }

  async function removeSelected() {
    if (deleting || !selected.size) return;
    setDeleting(true); setError("");
    try {
      const result = await api<{ deleted: number; recovered_bytes: number; cleanup_pending: number; message: string }>("/images/bulk-delete", { method: "POST", body: JSON.stringify({ image_ids: [...selected], confirm: true }) });
      setNotice(`${result.message} · ${formatBytes(result.recovered_bytes)} removed from vault`);
      setSelected(new Set()); setConfirming(false); setSelecting(false); setRefreshKey((value) => value + 1);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Could not delete selected images"); setConfirming(false); }
    finally { setDeleting(false); }
  }

  const hasSearch = searchMode === "smart" ? Boolean(smartQuery) : Boolean(deferredSearch);
  return <>
    <PageHeading eyebrow="Library" title="Your images" action={<div className="flex flex-wrap gap-2">{selecting ? <Button variant="secondary" onClick={stopSelecting}>Done</Button> : <Button variant="secondary" onClick={() => setSelecting(true)}><Check className="h-4 w-4" />Select</Button>}<Link to="/upload"><Button><CloudUpload className="h-4 w-4" />Upload</Button></Link></div>} />

    <form onSubmit={submitSearch} className="panel mb-4 rounded-2xl p-3"><div className="flex flex-col gap-3 lg:flex-row lg:items-center"><div className="flex shrink-0 rounded-xl border border-line bg-canvas p-1"><button type="button" onClick={() => setMode("smart")} className={`focus-ring flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-semibold ${searchMode === "smart" ? "bg-lilac/15 text-lilac" : "text-muted"}`}><Sparkles className="h-3.5 w-3.5" />Smart</button><button type="button" onClick={() => setMode("filename")} className={`focus-ring rounded-lg px-3 py-1.5 text-xs font-semibold ${searchMode === "filename" ? "bg-white/10 text-ink" : "text-muted"}`}>Filename</button></div><label className="relative min-w-0 flex-1"><Search className="pointer-events-none absolute left-3 top-3 h-4 w-4 text-muted" /><span className="sr-only">Search images</span><input value={search} onChange={(event) => { setSearch(event.target.value); if (searchMode === "filename") setPage(1); }} placeholder={searchMode === "smart" ? "Try: person wearing white near a car" : "Search filenames"} className="focus-ring h-10 w-full rounded-xl border border-line bg-canvas pl-9 pr-10 text-sm" />{search && <button type="button" onClick={() => { setSearch(""); setSmartQuery(""); }} aria-label="Clear search" className="focus-ring absolute right-2 top-2 rounded-lg p-1 text-muted"><X className="h-4 w-4" /></button>}</label>{searchMode === "smart" && <Button type="submit" disabled={search.trim().length < 2}>Search</Button>}</div></form>

    <div className="panel mb-5 rounded-2xl p-3"><div className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between"><div className="flex gap-2 overflow-x-auto pb-1 xl:pb-0">{filters.map(([value,label]) => <button key={value} disabled={Boolean(smartQuery)} onClick={() => changeFilter(value)} className={`focus-ring whitespace-nowrap rounded-xl px-3.5 py-2 text-xs font-semibold transition disabled:opacity-35 ${filter === value && !smartQuery ? "bg-ink text-canvas" : "text-muted hover:bg-white/5 hover:text-ink"}`}>{label}</button>)}</div><div className="flex flex-wrap gap-2">{selecting && data?.items.length ? <Button variant="ghost" onClick={toggleAll}>{selected.size === data.items.length ? "Clear page" : "Select page"}</Button> : null}<label className="relative"><SlidersHorizontal className="pointer-events-none absolute left-3 top-3 h-4 w-4 text-muted" /><span className="sr-only">Sort gallery</span><select value={sort} disabled={Boolean(smartQuery)} onChange={(event) => { setSort(event.target.value); setPage(1); }} className="focus-ring h-10 appearance-none rounded-xl border border-line bg-canvas pl-9 pr-8 text-xs disabled:opacity-35"><option value="newest">Newest first</option><option value="quality">Best quality</option><option value="oldest">Oldest first</option><option value="largest">Largest first</option><option value="smallest">Smallest first</option><option value="filename">Filename</option></select></label></div></div></div>

    {notice && <div role="status" className="mb-4 flex items-center justify-between rounded-xl border border-acid/20 bg-acid/[.05] p-4 text-sm"><span className="flex items-center gap-2"><Check className="h-4 w-4 text-acid" />{notice}</span><button onClick={() => setNotice("")} className="focus-ring rounded-lg p-1 text-muted"><X className="h-4 w-4" /></button></div>}
    {error ? <EmptyState icon={Images} title="Gallery unavailable" description={error} /> : !data ? <LoadingGrid /> : data.items.length === 0 ? <EmptyState icon={Images} title={hasSearch || filter !== "all" ? "No matching images" : "No images yet"} description={hasSearch || filter !== "all" ? "Try a different search." : "Upload your first images."} action={!hasSearch && filter === "all" ? <Link to="/upload"><Button>Upload images</Button></Link> : undefined} /> : <><div className="mb-4 flex items-center justify-between"><p className="text-xs text-muted">{data.total.toLocaleString()} image{data.total === 1 ? "" : "s"}{smartQuery ? ` for “${smartQuery}”` : ""}</p><p className="font-mono text-[10px] uppercase tracking-wider text-muted">Page {data.page} of {data.pages}</p></div><div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">{data.items.map((image) => <ImageCard key={image.id} image={image} selectable={selecting} selected={selected.has(image.id)} onSelect={toggle} />)}</div>{data.pages > 1 && <div className="mt-7 flex justify-center gap-2"><Button variant="secondary" disabled={page === 1} onClick={() => { setPage((value) => value - 1); setSelected(new Set()); }}>Previous</Button><Button variant="secondary" disabled={page === data.pages} onClick={() => { setPage((value) => value + 1); setSelected(new Set()); }}>Next</Button></div>}</>}

    <AnimatePresence>{selected.size > 0 && !confirming && <motion.div initial={{ opacity: 0, y: 30 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: 30 }} className="fixed bottom-5 left-1/2 z-40 flex w-[calc(100%-2rem)] max-w-xl -translate-x-1/2 items-center justify-between gap-4 rounded-2xl border border-line bg-[#15191f]/95 p-3 shadow-float backdrop-blur-xl"><div className="min-w-0 pl-2"><p className="text-sm font-semibold">{selected.size} selected</p><p className="truncate text-xs text-muted">{formatBytes(selectedBytes)}</p></div><div className="flex gap-2"><Button variant="ghost" onClick={() => setSelected(new Set())}>Clear</Button><Button variant="danger" onClick={() => setConfirming(true)}><Trash2 className="h-4 w-4" />Delete</Button></div></motion.div>}</AnimatePresence>
    <AnimatePresence>{confirming && <div className="fixed inset-0 z-50 grid place-items-center p-4"><motion.button aria-label="Close confirmation" className="absolute inset-0 bg-black/75 backdrop-blur-sm" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={() => { if (!deleting) setConfirming(false); }} /><motion.div role="dialog" aria-modal="true" aria-labelledby="gallery-delete-title" initial={{ opacity: 0, scale: .96, y: 10 }} animate={{ opacity: 1, scale: 1, y: 0 }} exit={{ opacity: 0, scale: .96 }} className="panel relative z-10 w-full max-w-md rounded-[28px] p-6"><div className="grid h-12 w-12 place-items-center rounded-2xl bg-coral/10"><AlertTriangle className="h-5 w-5 text-coral" /></div><h2 id="gallery-delete-title" className="mt-5 text-xl font-semibold">Delete {selected.size} image{selected.size === 1 ? "" : "s"}?</h2><p className="mt-2 text-sm text-muted">This cannot be undone.</p><div className="mt-6 flex justify-end gap-2"><Button variant="secondary" onClick={() => { if (!deleting) setConfirming(false); }}>Cancel</Button><Button variant="danger" loading={deleting} onClick={removeSelected}>Delete permanently</Button></div></motion.div></div>}</AnimatePresence>
  </>;
}
