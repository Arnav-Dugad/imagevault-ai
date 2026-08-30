import { AnimatePresence, motion } from "framer-motion";
import { AlertCircle, CheckCircle2, CloudUpload, FileImage, Film, ScanSearch, X } from "lucide-react";
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
    const all = Array.from(incoming);
    const richExtensions = new Set(["heic","heif","dng","cr2","nef","arw","raw","mp4","mov","webm","mkv","avi"]);
    const supportedExtensions = new Set(["jpg","jpeg","png","webp","gif", ...richExtensions]);
    const valid = all.filter((file) => {
      const extension = file.name.split(".").pop()?.toLowerCase() ?? "";
      const limit = richExtensions.has(extension) ? 300 * 1024 * 1024 : 15 * 1024 * 1024;
      return supportedExtensions.has(extension) && file.size <= limit;
    });
    if (valid.length !== all.length) setError("Some files were skipped. Photos and animations can be up to 15 MB; RAW files and videos can be up to 300 MB.");
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
    <PageHeading eyebrow="Upload" title="Add photos and videos" />
    <section className="panel mx-auto max-w-5xl rounded-[28px] p-4 sm:p-6">
      <button type="button" onClick={() => inputRef.current?.click()} onDragOver={(event) => { event.preventDefault(); setDragging(true); }} onDragLeave={() => setDragging(false)} onDrop={drop} className={`focus-ring relative flex min-h-72 w-full flex-col items-center justify-center overflow-hidden rounded-[22px] border border-dashed px-6 text-center transition ${dragging ? "border-acid bg-acid/[.06]" : "border-[#3b424d] bg-white/[.015] hover:border-muted"}`}>
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,rgba(185,243,106,.06),transparent_52%)]" /><div className="relative grid h-16 w-16 place-items-center rounded-2xl border border-line bg-panel shadow-glow"><CloudUpload className="h-7 w-7 text-acid" /></div><h2 className="relative mt-6 text-xl font-semibold">Drop your media here</h2><p className="relative mt-2 text-sm text-muted">Photos, RAW, animations, and videos stay in your private vault</p><div className="relative mt-5 flex flex-wrap justify-center gap-2 font-mono text-[10px] uppercase tracking-wider text-muted"><span className="rounded-full border border-line px-2.5 py-1">JPG · PNG · GIF</span><span className="rounded-full border border-line px-2.5 py-1">HEIC · RAW</span><span className="rounded-full border border-line px-2.5 py-1">MP4 · MOV · WEBM</span><span className="rounded-full border border-line px-2.5 py-1">300 MB max</span></div>
      </button>
      <input ref={inputRef} className="hidden" type="file" accept=".jpg,.jpeg,.png,.webp,.gif,.heic,.heif,.dng,.cr2,.nef,.arw,.raw,.mp4,.mov,.webm,.mkv,.avi,image/*,video/*" multiple onChange={(event) => event.target.files && addFiles(event.target.files)} />
      <AnimatePresence>{files.length > 0 && <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} className="mt-5"><div className="mb-3 flex items-center justify-between"><p className="text-sm font-semibold">{files.length} ready</p><button disabled={uploading} onClick={() => setFiles([])} className="focus-ring rounded-lg px-2 py-1 text-xs text-muted hover:text-ink">Clear all</button></div><div className="max-h-64 space-y-2 overflow-y-auto pr-1">{previews.map(({ file, url }, index) => { const extension = file.name.split(".").pop()?.toLowerCase(); const previewable = ["jpg","jpeg","png","webp","gif"].includes(extension ?? ""); const video = ["mp4","mov","webm","mkv","avi"].includes(extension ?? ""); return <div key={`${file.name}-${file.lastModified}`} className="flex items-center gap-3 rounded-xl border border-line bg-canvas/50 p-2">{previewable ? <img src={url} alt="" className="h-12 w-12 rounded-lg object-cover" /> : <div className="grid h-12 w-12 place-items-center rounded-lg bg-white/[.04]">{video ? <Film className="h-5 w-5 text-lilac" /> : <FileImage className="h-5 w-5 text-acid" />}</div>}<div className="min-w-0 flex-1"><p className="truncate text-sm font-medium">{file.name}</p><p className="mt-1 font-mono text-[10px] uppercase text-muted">{formatBytes(file.size)} · {video ? "video" : extension}</p></div><button disabled={uploading} onClick={() => setFiles((items) => items.filter((_, itemIndex) => itemIndex !== index))} className="focus-ring rounded-lg p-2 text-muted hover:bg-white/5 hover:text-ink" aria-label={`Remove ${file.name}`}><X className="h-4 w-4" /></button></div>; })}</div>
        {uploading && <div className="mt-4"><div className="mb-2 flex justify-between font-mono text-[10px] uppercase tracking-wider text-muted"><span>Uploading</span><span>{progress}%</span></div><div className="h-2 overflow-hidden rounded-full bg-white/5"><motion.div className="h-full bg-acid" animate={{ width: `${progress}%` }} /></div></div>}
        <div className="mt-4 flex flex-col gap-2 sm:flex-row"><Button onClick={upload} loading={uploading} className="flex-1"><CloudUpload className="h-4 w-4" />Upload {files.length}</Button>{uploading && <Button variant="secondary" onClick={() => abortRef.current?.abort()}>Cancel</Button>}</div></motion.div>}</AnimatePresence>
      {error && <div role="alert" className="mt-4 flex items-start gap-3 rounded-xl border border-coral/20 bg-coral/10 p-4 text-sm text-orange-100"><AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-coral" />{error}</div>}
      {result?.items && <div className="mt-5 rounded-2xl border border-acid/20 bg-acid/[.055] p-5"><div className="flex items-center gap-2"><CheckCircle2 className="h-5 w-5 text-acid" /><h3 className="font-semibold">Upload complete</h3></div><p className="mt-2 text-sm text-muted">{result.items.length} file{result.items.length === 1 ? "" : "s"} queued for private media analysis.</p><div className="mt-4 flex flex-wrap gap-2"><Link to={`/duplicates?batch=${result.batch_id}`}><Button><ScanSearch className="h-4 w-4" />View batch</Button></Link><Link to="/gallery"><Button variant="secondary">Open gallery</Button></Link></div></div>}
    </section>
  </>;
}
