import { AnimatePresence, motion } from "framer-motion";
import { AlertCircle, CheckCircle2, CloudUpload, FileImage, Fingerprint, Layers3, LockKeyhole, Palette, ScanSearch, ShieldCheck, Sparkles, X } from "lucide-react";
import { DragEvent, useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { Button, PageHeading } from "../components/ui";
import { ApiError, uploadFiles } from "../lib/api";
import { formatBytes } from "../lib/utils";
import type { UploadResponse } from "../types";

export function UploadPage() {
  const inputRef = useRef<HTMLInputElement>(null);
  const [files, setFiles] = useState<File[]>([]);
  const [dragging, setDragging] = useState(false);
  const [progress, setProgress] = useState(0);
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState<UploadResponse | null>(null);
  const [error, setError] = useState("");
  const abortRef = useRef<AbortController | null>(null);
  const previews = useMemo(() => files.map((file) => ({ file, url: URL.createObjectURL(file) })), [files]);
  useEffect(() => () => previews.forEach(({ url }) => URL.revokeObjectURL(url)), [previews]);

  function addFiles(incoming: FileList | File[]) {
    setError(""); setResult(null);
    const valid = Array.from(incoming).filter((file) => ["image/jpeg", "image/png", "image/webp"].includes(file.type) && file.size <= 15 * 1024 * 1024);
    if (valid.length !== Array.from(incoming).length) setError("Some files were skipped. Use JPG, PNG, or WebP files up to 15 MB each.");
    setFiles((current) => [...current, ...valid].slice(0, 20));
  }
  function drop(event: DragEvent) { event.preventDefault(); setDragging(false); addFiles(event.dataTransfer.files); }
  async function upload() {
    setUploading(true); setError(""); setProgress(0); abortRef.current = new AbortController();
    try { setResult(await uploadFiles(files, setProgress, abortRef.current.signal) as UploadResponse); setFiles([]); }
    catch (reason) { setError(reason instanceof ApiError ? reason.message : "Upload failed"); }
    finally { setUploading(false); abortRef.current = null; }
  }
  return <>
    <PageHeading eyebrow="Intelligent intake" title="Drop a batch. See every relationship." description="Each upload becomes one smart batch. ImageVault checks exact bytes, three visual fingerprints, color, geometry, and private local AI—then presents every duplicate family together." />
    <div className="grid gap-5 xl:grid-cols-[1.5fr_.7fr]">
      <section className="panel rounded-[28px] p-4 sm:p-6">
        <button type="button" onClick={() => inputRef.current?.click()} onDragOver={(event) => { event.preventDefault(); setDragging(true); }} onDragLeave={() => setDragging(false)} onDrop={drop} className={`focus-ring relative flex min-h-72 w-full flex-col items-center justify-center overflow-hidden rounded-[22px] border border-dashed px-6 text-center transition ${dragging ? "border-acid bg-acid/[.06]" : "border-[#3b424d] bg-white/[.015] hover:border-muted"}`}>
          <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,rgba(185,243,106,.06),transparent_52%)]" /><div className="relative grid h-16 w-16 place-items-center rounded-2xl border border-line bg-panel shadow-glow"><CloudUpload className="h-7 w-7 text-acid" /></div><h2 className="relative mt-6 text-xl font-semibold tracking-tight">Drag your image batch here</h2><p className="relative mt-2 text-sm text-muted">or click to choose from your device</p><div className="relative mt-5 flex flex-wrap justify-center gap-2 font-mono text-[10px] uppercase tracking-wider text-muted"><span className="rounded-full border border-line px-2.5 py-1">JPG</span><span className="rounded-full border border-line px-2.5 py-1">PNG</span><span className="rounded-full border border-line px-2.5 py-1">WEBP</span><span className="rounded-full border border-line px-2.5 py-1">15 MB max</span></div>
        </button><input ref={inputRef} className="hidden" type="file" accept="image/jpeg,image/png,image/webp" multiple onChange={(event) => event.target.files && addFiles(event.target.files)} />
        <AnimatePresence>{files.length > 0 && <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} className="mt-5"><div className="mb-3 flex items-center justify-between"><p className="text-sm font-semibold">Ready to upload · {files.length}</p><button disabled={uploading} onClick={() => setFiles([])} className="focus-ring rounded-lg px-2 py-1 text-xs text-muted hover:text-ink">Clear all</button></div><div className="max-h-64 space-y-2 overflow-y-auto pr-1">{previews.map(({ file, url }, index) => <div key={`${file.name}-${file.lastModified}`} className="flex items-center gap-3 rounded-xl border border-line bg-canvas/50 p-2"><img src={url} alt="" className="h-12 w-12 rounded-lg object-cover" /><div className="min-w-0 flex-1"><p className="truncate text-sm font-medium">{file.name}</p><p className="mt-1 font-mono text-[10px] uppercase text-muted">{formatBytes(file.size)}</p></div><button disabled={uploading} onClick={() => setFiles((items) => items.filter((_, itemIndex) => itemIndex !== index))} className="focus-ring rounded-lg p-2 text-muted hover:bg-white/5 hover:text-ink" aria-label={`Remove ${file.name}`}><X className="h-4 w-4" /></button></div>)}</div>
          {uploading && <div className="mt-4"><div className="mb-2 flex justify-between font-mono text-[10px] uppercase tracking-wider text-muted"><span>Encrypted transfer</span><span>{progress}%</span></div><div className="h-2 overflow-hidden rounded-full bg-white/5"><motion.div className="h-full bg-acid" animate={{ width: `${progress}%` }} /></div></div>}
          <div className="mt-4 flex flex-col gap-2 sm:flex-row"><Button onClick={upload} loading={uploading} className="flex-1"><CloudUpload className="h-4 w-4" />Upload {files.length} image{files.length === 1 ? "" : "s"}</Button>{uploading && <Button variant="secondary" onClick={() => abortRef.current?.abort()}>Cancel</Button>}</div></motion.div>}</AnimatePresence>
        {error && <div role="alert" className="mt-4 flex items-start gap-3 rounded-xl border border-coral/20 bg-coral/10 p-4 text-sm text-orange-100"><AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-coral" />{error}</div>}
        {result?.items && <div className="mt-5 overflow-hidden rounded-2xl border border-acid/20 bg-acid/[.055]"><div className="border-b border-acid/10 p-5"><div className="flex items-center gap-2"><CheckCircle2 className="h-5 w-5 text-acid" /><h3 className="font-semibold">Batch accepted for smart analysis</h3></div><p className="mt-2 text-xs leading-5 text-muted">The focused report refreshes while the local worker compares this batch internally and against your existing library.</p></div><div className="p-5"><div className="mb-4 grid grid-cols-2 gap-2"><div className="rounded-xl bg-black/15 p-3"><p className="font-mono text-[9px] uppercase tracking-wider text-muted">Images</p><p className="mt-1 text-lg font-semibold">{result.items.length}</p></div><div className="rounded-xl bg-black/15 p-3"><p className="font-mono text-[9px] uppercase tracking-wider text-muted">Instant exact matches</p><p className="mt-1 text-lg font-semibold text-coral">{result.items.filter((item) => item.exact_duplicate).length}</p></div></div><div className="max-h-52 space-y-2 overflow-y-auto">{result.items.map((item) => <div key={item.image.id} className="flex flex-col justify-between gap-1 rounded-xl bg-black/15 p-3 text-sm sm:flex-row sm:items-center"><span className="truncate font-medium">{item.image.original_filename}</span><span className={item.exact_duplicate ? "text-coral" : "text-muted"}>{item.exact_duplicate ? "Exact match found" : "Smart scan queued"}</span></div>)}</div><div className="mt-4 flex flex-wrap gap-2"><Link to={`/duplicates?batch=${result.batch_id}`}><Button><ScanSearch className="h-4 w-4" />Open batch intelligence</Button></Link><Link to="/gallery"><Button variant="secondary">Open gallery</Button></Link></div></div></div>}
      </section>
      <aside className="space-y-4"><div className="panel rounded-[24px] p-5"><p className="eyebrow">Smart evidence stack</p><div className="mt-6 space-y-5">{[["01",Fingerprint,"SHA-256 exact bytes"],["02",Layers3,"pHash + dHash + wHash"],["03",Sparkles,"Multi-view OpenCLIP AI"],["04",Palette,"Color + frame geometry"],["05",ShieldCheck,"Connected family grouping"]].map(([number,Icon,label]) => { const ItemIcon = Icon as typeof FileImage; return <div key={label as string} className="flex items-center gap-3"><span className="font-mono text-[10px] text-muted">{number as string}</span><div className="grid h-8 w-8 place-items-center rounded-lg bg-white/[.04]"><ItemIcon className="h-4 w-4 text-lilac" /></div><span className="text-sm">{label as string}</span></div>; })}</div></div><div className="rounded-[24px] border border-acid/20 bg-acid/[.06] p-5"><LockKeyhole className="h-5 w-5 text-acid" /><h3 className="mt-5 font-semibold">Nothing leaves your cloud</h3><p className="mt-2 text-sm leading-6 text-muted">Every signal is computed by your local worker. No commercial vision or AI service receives your files.</p></div></aside>
    </div>
  </>;
}
