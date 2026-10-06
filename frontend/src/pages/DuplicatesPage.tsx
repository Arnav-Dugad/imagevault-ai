import { AnimatePresence, motion } from "framer-motion";
import {
  AlertTriangle,
  Check,
  ChevronRight,
  Copy,
  HardDrive,
  Images,
  Layers3,
  RefreshCw,
  ScanSearch,
  Sparkles,
  Trash2,
  WandSparkles,
  X,
  Zap,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Button, EmptyState, PageHeading } from "../components/ui";
import { api } from "../lib/api";
import { formatBytes, percent } from "../lib/utils";
import type { DuplicateGroup, DuplicateReview } from "../types";

type Candidate = DuplicateGroup["candidates"][number];
type MatchFilter = "all" | "exact" | "perceptual" | "visual";

function Metric({ icon: Icon, label, value, tone = "default" }: { icon: typeof Copy; label: string; value: string; tone?: "default" | "acid" | "coral" }) {
  const toneClass = tone === "acid" ? "text-acid" : tone === "coral" ? "text-coral" : "text-lilac";
  return <div className="rounded-2xl border border-line bg-white/[.018] p-4">
    <div className="flex items-center gap-2 text-xs text-muted"><Icon className={`h-4 w-4 ${toneClass}`} />{label}</div>
    <p className="mt-3 text-2xl font-semibold tracking-[-.04em]">{value}</p>
  </div>;
}

function Signal({ label, value, accent = "acid" }: { label: string; value: number | null; accent?: "acid" | "lilac" | "coral" }) {
  if (value === null) return null;
  const bar = accent === "acid" ? "bg-acid" : accent === "lilac" ? "bg-lilac" : "bg-coral";
  return <div>
    <div className="mb-1.5 flex justify-between font-mono text-[9px] uppercase tracking-wider text-muted"><span>{label}</span><span>{percent(value)}</span></div>
    <div className="h-1 overflow-hidden rounded-full bg-white/[.06]"><div className={`h-full rounded-full ${bar}`} style={{ width: `${Math.max(3, value * 100)}%` }} /></div>
  </div>;
}

function CandidateCard({ candidate, selected, onToggle }: { candidate: Candidate; selected: boolean; onToggle: (id: string) => void }) {
  const typeLabel = candidate.match_type === "EXACT" ? "Exact copy" : candidate.match_type === "PERCEPTUAL" ? "Near duplicate" : "Similar content · review";
  return <article className={`overflow-hidden rounded-2xl border bg-[#101318] transition ${selected ? "border-acid ring-1 ring-acid/70" : "border-line hover:border-[#3a414c]"}`}>
    <div className="relative aspect-[16/10] overflow-hidden bg-[#171b21]">
      {candidate.image.thumbnail_url ? <img src={candidate.image.thumbnail_url} alt={candidate.image.original_filename} className="h-full w-full object-cover" /> : <div className="grid h-full place-items-center"><Images className="h-7 w-7 text-muted/40" /></div>}
      <div className="absolute inset-x-0 bottom-0 h-20 bg-gradient-to-t from-black/80 to-transparent" />
      <button onClick={() => onToggle(candidate.image.id)} className={`focus-ring absolute left-3 top-3 grid h-8 w-8 place-items-center rounded-full border shadow-lg ${selected ? "border-acid bg-acid text-canvas" : "border-white/30 bg-black/60 text-white"}`} aria-label={`${selected ? "Deselect" : "Select"} ${candidate.image.original_filename}`}>
        {selected ? <Check className="h-4 w-4" /> : <span className="h-2 w-2 rounded-full border border-current" />}
      </button>
      <span className="absolute right-3 top-3 rounded-full border border-white/10 bg-black/65 px-2.5 py-1 font-mono text-[9px] uppercase tracking-wide text-white backdrop-blur">{typeLabel}</span>
      <div className="absolute bottom-3 left-3 right-3 flex items-center justify-between">
        <span className="text-xs font-medium text-white">{candidate.classification}</span>
        <span className="rounded-full bg-white px-2.5 py-1 font-mono text-[10px] font-semibold text-black">{percent(candidate.similarity_score)}</span>
      </div>
    </div>
    <div className="p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0"><p className="truncate text-sm font-semibold" title={candidate.image.original_filename}>{candidate.image.original_filename}</p><p className="mt-1 font-mono text-[10px] uppercase text-muted">{formatBytes(candidate.image.file_size)}{candidate.same_batch ? " · same upload" : " · library match"}</p></div>
        <Link to={`/images/${candidate.image.id}`} className="focus-ring rounded-lg p-1 text-muted transition hover:bg-white/5 hover:text-ink" aria-label={`Open ${candidate.image.original_filename}`}><ChevronRight className="h-4 w-4" /></Link>
      </div>
      <div className="mt-4 grid grid-cols-2 gap-x-4 gap-y-3">
        <Signal label="AI" value={candidate.clip_score} accent="lilac" />
        <Signal label="Structure" value={candidate.perceptual_score} />
        <Signal label="Color" value={candidate.color_score} accent="coral" />
        <Signal label="Frame" value={candidate.aspect_score} />
      </div>
      <div className="mt-4 flex flex-wrap gap-1.5">{candidate.reasons.slice(0, 3).map((reason) => <span key={reason} className="rounded-full border border-line bg-white/[.025] px-2 py-1 text-[10px] text-muted">{reason}</span>)}</div>
    </div>
  </article>;
}

export function DuplicatesPage() {
  const [searchParams] = useSearchParams();
  const batchId = searchParams.get("batch");
  const [report, setReport] = useState<DuplicateReview | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [filter, setFilter] = useState<MatchFilter>("all");
  const [sort, setSort] = useState<"confidence" | "savings">("confidence");
  const [confirming, setConfirming] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [reindexing, setReindexing] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");

  const requestRef = useRef<AbortController | null>(null);
  const load = useCallback(() => {
    requestRef.current?.abort();
    const controller = new AbortController(); requestRef.current = controller;
    const query = batchId ? `?batch_id=${encodeURIComponent(batchId)}` : "";
    return api<DuplicateReview>(`/duplicates/review${query}`, { signal: controller.signal })
      .then((value) => {
        if (controller.signal.aborted) return;
        setReport(value); setError("");
        const candidates = new Set(value.groups.flatMap((group) => group.candidates.map((item) => item.image.id)));
        setSelected((current) => new Set([...current].filter((id) => candidates.has(id))));
      }).catch((reason: Error) => { if (!controller.signal.aborted) setError(reason.message); });
  }, [batchId]);

  useEffect(() => { setReport(null); setSelected(new Set()); setError(""); setConfirming(false); void load(); return () => requestRef.current?.abort(); }, [load]);
  useEffect(() => {
    if (!report?.processing_images) return;
    const timer = window.setTimeout(() => void load(), 2500);
    return () => window.clearTimeout(timer);
  }, [load, report]);

  const visibleGroups = useMemo(() => {
    if (!report) return [];
    const groups = report.groups.map((group) => ({
      ...group,
      candidates: group.candidates.filter((candidate) => filter === "all" || candidate.match_type.toLowerCase() === filter),
    })).filter((group) => group.candidates.length > 0);
    return groups.sort((a, b) => sort === "savings" ? b.recoverable_bytes - a.recoverable_bytes : b.highest_similarity - a.highest_similarity);
  }, [filter, report, sort]);

  const allCandidates = report?.groups.flatMap((group) => group.candidates) ?? [];
  const selectedBytes = allCandidates.filter((item) => selected.has(item.image.id)).reduce((sum, item) => sum + item.image.file_size, 0);
  function toggle(id: string) { setSelected((current) => { const next = new Set(current); if (next.has(id)) next.delete(id); else next.add(id); return next; }); }
  function selectExact() { setSelected(new Set(allCandidates.filter((item) => item.match_type === "EXACT").map((item) => item.image.id))); }


  async function removeSelected() {
    if (deleting || !selected.size) return;
    setDeleting(true); setError("");
    try {
      const result = await api<{ message: string }>("/images/bulk-delete", { method: "POST", body: JSON.stringify({ image_ids: [...selected], confirm: true }) });
      setSelected(new Set()); setConfirming(false); setNotice(result.message); await load();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Could not delete selected images"); }
    finally { setDeleting(false); }
  }

  async function rebuildIndex() {
    setReindexing(true); setError("");
    try {
      const response = await api<{ queued: number; message: string }>("/images/reindex", { method: "POST" });
      setNotice(response.message); await load();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Could not rebuild the smart index"); }
    finally { setReindexing(false); }
  }

  return <>
    <PageHeading
      eyebrow={batchId ? "Upload batch" : "Duplicate review"}
      title={batchId ? "Batch matches" : "Duplicates and similar images"}
      action={<div className="flex flex-wrap gap-2">{batchId && <Link to="/duplicates"><Button variant="secondary"><Layers3 className="h-4 w-4" />All library</Button></Link>}<Button variant="secondary" loading={reindexing} onClick={rebuildIndex}><WandSparkles className="h-4 w-4" />Upgrade smart index</Button></div>}
    />

    <p className="mb-5 text-sm leading-6 text-muted">Exact copies match file bytes. Near duplicates pass fingerprint and pixel checks. Similar content needs manual review. Scores describe resemblance, not the probability that deletion is safe.</p>

    {report && <div className="mb-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
      <Metric icon={Layers3} label="Visual families" value={report.total_groups.toLocaleString()} />
      <Metric icon={Copy} label="Exact copies" value={report.exact_duplicates.toLocaleString()} tone="coral" />
      <Metric icon={Sparkles} label="Smart matches" value={report.similar_images.toLocaleString()} tone="acid" />
      <Metric icon={HardDrive} label="Recoverable" value={formatBytes(report.recoverable_bytes)} tone="coral" />
      <Metric icon={ScanSearch} label={report.processing_images ? "Still analyzing" : "Images scanned"} value={(report.processing_images || report.total_images_scanned).toLocaleString()} tone={report.processing_images ? "acid" : "default"} />
    </div>}

    {report?.processing_images ? <div className="mb-5 overflow-hidden rounded-2xl border border-acid/20 bg-acid/[.055] p-4"><div className="flex items-center gap-3"><RefreshCw className="h-4 w-4 animate-spin text-acid" /><div><p className="text-sm font-semibold">Smart analysis is still running</p><p className="mt-1 text-xs text-muted">This report refreshes automatically. Completed matches appear immediately.</p></div></div><div className="mt-3 h-1 overflow-hidden rounded-full bg-white/5"><motion.div className="h-full w-1/3 bg-acid" animate={{ x: ["-100%", "300%"] }} transition={{ repeat: Infinity, duration: 1.4, ease: "linear" }} /></div></div> : null}
    {notice && <div role="status" className="mb-4 flex items-center justify-between gap-3 rounded-xl border border-acid/20 bg-acid/[.05] p-4 text-sm"><span className="flex items-center gap-2"><Check className="h-4 w-4 text-acid" />{notice}</span><button onClick={() => setNotice("")} className="focus-ring rounded-lg p-1 text-muted"><X className="h-4 w-4" /></button></div>}
    {error && <div role="alert" className="mb-4 rounded-xl border border-red-500/20 bg-red-500/10 p-4 text-sm text-red-200">{error}</div>}

    <div className="panel mb-5 rounded-2xl p-3"><div className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
      <div className="flex gap-2 overflow-x-auto">{([['all','All evidence'],['exact','Exact'],['perceptual','Near duplicates'],['visual','AI matches']] as const).map(([value, label]) => <button key={value} onClick={() => setFilter(value)} className={`focus-ring whitespace-nowrap rounded-xl px-3.5 py-2 text-xs font-semibold transition ${filter === value ? "bg-ink text-canvas" : "text-muted hover:bg-white/5 hover:text-ink"}`}>{label}</button>)}</div>
      <div className="flex flex-wrap gap-2"><Button variant="ghost" onClick={selectExact} disabled={!allCandidates.some((item) => item.match_type === "EXACT")}><Zap className="h-4 w-4" />Select exact</Button><select value={sort} onChange={(event) => setSort(event.target.value as typeof sort)} className="focus-ring h-10 rounded-xl border border-line bg-canvas px-3 text-xs"><option value="confidence">Highest match score</option><option value="savings">Most space saved</option></select></div>
    </div></div>

    {!report ? <div className="space-y-4">{Array.from({ length: 2 }, (_, index) => <div key={index} className="skeleton h-80 rounded-[28px]" />)}</div> : visibleGroups.length === 0 ? <EmptyState icon={report.processing_images ? ScanSearch : Copy} title={report.processing_images ? "Analyzing your visual families" : "No matches in this view"} description={report.processing_images ? "The background worker is comparing every image. This page will update automatically." : filter === "all" ? "Your library is clean—no exact, near-duplicate, or strong Similar content · reviewes were found." : "Try another evidence filter or upload more images."} /> : <div className="space-y-5">{visibleGroups.map((group, index) => <motion.section initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} key={group.group_id} className="panel rounded-[28px] p-4 sm:p-6">
      <div className="mb-5 flex flex-col justify-between gap-3 lg:flex-row lg:items-end"><div><div className="flex flex-wrap items-center gap-2"><p className="eyebrow">Visual family #{String(index + 1).padStart(2, "0")}</p>{group.all_same_batch && <span className="rounded-full border border-lilac/20 bg-lilac/[.08] px-2 py-1 font-mono text-[9px] uppercase text-lilac">same upload</span>}</div><h2 className="mt-2 text-lg font-semibold">{group.candidates.length + 1} related images · {percent(group.highest_similarity)} strongest match</h2></div><p className="font-mono text-[10px] uppercase tracking-wider text-coral">Up to {formatBytes(group.recoverable_bytes)} recoverable</p></div>
      <div className="grid gap-4 xl:grid-cols-[.72fr_2.28fr]">
        <Link to={`/images/${group.original.id}`} className="focus-ring overflow-hidden rounded-2xl border border-acid/20 bg-acid/[.025]"><div className="relative aspect-[16/10] overflow-hidden bg-[#171b21]">{group.original.thumbnail_url ? <img src={group.original.thumbnail_url} alt={group.original.original_filename} className="h-full w-full object-cover" /> : <div className="grid h-full place-items-center"><Images className="h-7 w-7 text-muted/40" /></div>}<span className="absolute left-3 top-3 rounded-full bg-acid px-2.5 py-1 font-mono text-[9px] font-semibold uppercase text-canvas">Recommended keeper</span></div><div className="p-4"><p className="truncate text-sm font-semibold">{group.original.original_filename}</p><p className="mt-1 text-xs text-muted">Suggested original · {formatBytes(group.original.file_size)}</p></div></Link>
        <div className="grid gap-3 md:grid-cols-2 2xl:grid-cols-3">{group.candidates.map((candidate) => <CandidateCard key={candidate.image.id} candidate={candidate} selected={selected.has(candidate.image.id)} onToggle={toggle} />)}</div>
      </div>
    </motion.section>)}</div>}

    <AnimatePresence>{selected.size > 0 && !confirming && <motion.div initial={{ opacity: 0, y: 30 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: 30 }} className="fixed bottom-5 left-1/2 z-40 flex w-[calc(100%-2rem)] max-w-xl -translate-x-1/2 items-center justify-between gap-4 rounded-2xl border border-line bg-[#15191f]/95 p-3 shadow-float backdrop-blur-xl"><div className="min-w-0 pl-2"><p className="text-sm font-semibold">{selected.size} selected</p><p className="truncate text-xs text-muted">Free {formatBytes(selectedBytes)} after confirmation</p></div><div className="flex gap-2"><Button variant="ghost" onClick={() => setSelected(new Set())}>Clear</Button><Button variant="danger" onClick={() => setConfirming(true)}><Trash2 className="h-4 w-4" />Review delete</Button></div></motion.div>}</AnimatePresence>

    <AnimatePresence>{confirming && <div className="fixed inset-0 z-50 grid place-items-center p-4"><motion.button aria-label="Close confirmation" className="absolute inset-0 bg-black/75 backdrop-blur-sm" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={() => { if (!deleting) setConfirming(false); }} /><motion.div role="dialog" aria-modal="true" aria-labelledby="delete-title" initial={{ opacity: 0, scale: .96, y: 10 }} animate={{ opacity: 1, scale: 1, y: 0 }} exit={{ opacity: 0, scale: .96 }} className="panel relative z-10 w-full max-w-md rounded-[28px] p-6 shadow-float"><button onClick={() => { if (!deleting) setConfirming(false); }} aria-label="Close" className="focus-ring absolute right-4 top-4 rounded-lg p-2 text-muted"><X className="h-4 w-4" /></button><div className="grid h-12 w-12 place-items-center rounded-2xl bg-coral/10"><AlertTriangle className="h-5 w-5 text-coral" /></div><h2 id="delete-title" className="mt-5 text-xl font-semibold">Delete {selected.size} image{selected.size === 1 ? "" : "s"}?</h2><p className="mt-2 text-sm leading-6 text-muted">This permanently removes originals, thumbnails, metadata, and vectors. The recommended keeper in each family is protected from bulk selection.</p><div className="mt-4 rounded-xl border border-line bg-black/20 p-3"><p className="text-xs text-muted">Estimated space recovered</p><p className="mt-1 text-lg font-semibold text-coral">{formatBytes(selectedBytes)}</p></div><div className="mt-6 flex justify-end gap-2"><Button variant="secondary" onClick={() => { if (!deleting) setConfirming(false); }}>Keep images</Button><Button variant="danger" loading={deleting} onClick={removeSelected}>Delete permanently</Button></div></motion.div></div>}</AnimatePresence>
  </>;
}
