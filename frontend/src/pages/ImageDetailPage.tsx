import { AnimatePresence, motion } from "framer-motion";
import { ArrowLeft, Calendar, Camera, Copy, Cpu, FileImage, Film, HardDrive, Languages, Layers3, Maximize2, ScanText, Sparkles, Trash2, UsersRound, X } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";
import { Button, StatusBadge } from "../components/ui";
import { api } from "../lib/api";
import { formatBytes, formatDate, percent } from "../lib/utils";
import type { ImageDetail } from "../types";

function ScoreBar({ label, value, color = "bg-acid" }: { label: string; value: number | null; color?: string }) {
  if (value === null) return null;
  return <div><div className="mb-1.5 flex justify-between font-mono text-[9px] uppercase tracking-wide text-muted"><span>{label}</span><span>{percent(value)}</span></div><div className="h-1.5 overflow-hidden rounded-full bg-white/[.06]"><motion.div initial={{ width: 0 }} animate={{ width: `${Math.max(3, value * 100)}%` }} transition={{ type: "spring", stiffness: 90, damping: 18, delay: .12 }} className={`h-full rounded-full ${color}`} /></div></div>;
}

export function ImageDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const [image, setImage] = useState<ImageDetail | null>(null);
  const [error, setError] = useState("");
  const [confirming, setConfirming] = useState(false);
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    setImage(null); setError(""); setConfirming(false);
    if (id) api<ImageDetail>(`/images/${id}`, { signal: controller.signal })
      .then((value) => { if (!controller.signal.aborted) setImage(value); })
      .catch((reason: Error) => { if (!controller.signal.aborted) setError(reason.message); });
    return () => controller.abort();
  }, [id]);
  useEffect(() => {
    if (!id || !image || !(image.analysis_pending || ["PENDING", "PROCESSING"].includes(image.status))) return;
    const controller = new AbortController();
    const timer = window.setTimeout(() => api<ImageDetail>(`/images/${id}`, { signal: controller.signal })
      .then((value) => { if (!controller.signal.aborted) setImage(value); }).catch(() => undefined), 4000);
    return () => { window.clearTimeout(timer); controller.abort(); };
  }, [id, image]);

  async function remove() {
    if (!id || !image || image.id !== id || deleting) return;
    setDeleting(true);
    try { await api(`/images/${id}?confirm=true`, { method: "DELETE" }); navigate("/gallery"); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Deletion failed"); setConfirming(false); }
    finally { setDeleting(false); }
  }

  function goBack() {
    const returnTo = (location.state as { returnTo?: string } | null)?.returnTo;
    if (returnTo) navigate(returnTo, { replace: true });
    else if (window.history.state?.idx > 0) navigate(-1);
    else navigate("/gallery", { replace: true });
  }

  if (error) return <div className="panel rounded-2xl p-8"><h1 className="text-xl font-semibold">Image unavailable</h1><p className="mt-2 text-sm text-muted">{error}</p><Link to="/gallery"><Button className="mt-5" variant="secondary">Back to gallery</Button></Link></div>;
  if (!image || image.id !== id) return <div className="grid gap-5 xl:grid-cols-[1.3fr_.7fr]"><div className="skeleton aspect-[4/3] rounded-[28px]" /><div className="skeleton h-[34rem] rounded-[28px]" /></div>;

  const metadata = [
    [FileImage, "Format", image.mime_type.split("/")[1].toUpperCase()],
    [HardDrive, "File size", formatBytes(image.file_size)],
    [Maximize2, "Dimensions", image.width && image.height ? `${image.width} × ${image.height}` : "Processing"],
    [Calendar, "Uploaded", formatDate(image.created_at)],
    [Camera, "Camera", image.camera_model ?? "Not available"],
    [UsersRound, "Faces", String(image.face_count)],
    [Layers3, "Frames", image.frame_count.toLocaleString()],
    [Cpu, "AI device", image.processing_device ?? "Waiting"],
  ] as const;

  const preview = image.media_kind === "RAW" || ["image/heic", "image/heif"].includes(image.mime_type) ? image.thumbnail_url : image.original_url;

  return <>
    <div className="mb-6 flex items-center justify-between"><button onClick={goBack} className="focus-ring inline-flex items-center gap-2 rounded-lg text-sm text-muted hover:text-ink"><ArrowLeft className="h-4 w-4" />Back</button><Button variant="ghost" className="text-coral" onClick={() => setConfirming(true)}><Trash2 className="h-4 w-4" />Delete</Button></div>
    {image.error_message && <div role="status" className="mb-5 rounded-xl border border-coral/30 bg-coral/5 p-4 text-sm">{image.error_message}</div>}
    <div className="grid gap-5 xl:grid-cols-[1.35fr_.65fr]">
      <section className="panel overflow-hidden rounded-[28px]"><div className="relative grid min-h-[22rem] place-items-center bg-[#14181e] sm:min-h-[34rem]">{image.media_kind === "VIDEO" && image.original_url ? <video src={image.original_url} poster={image.thumbnail_url ?? undefined} controls preload="metadata" className="max-h-[72vh] w-full" /> : preview ? <img src={preview} alt={image.original_filename} className="max-h-[72vh] w-full object-contain" /> : <FileImage className="h-10 w-10 text-muted" />}<div className="absolute left-4 top-4"><StatusBadge status={image.status} /></div>{image.media_kind !== "PHOTO" && <span className="absolute right-4 top-4 flex items-center gap-1.5 rounded-full border border-white/10 bg-black/65 px-2.5 py-1 font-mono text-[9px] uppercase text-white">{image.media_kind === "VIDEO" ? <Film className="h-3 w-3 text-lilac" /> : <Layers3 className="h-3 w-3 text-acid" />}{image.media_kind.replace("_", " ")}{image.duration_seconds ? ` · ${image.duration_seconds.toFixed(1)}s` : ""}</span>}</div></section>
      <aside className="panel rounded-[28px] p-5 sm:p-6"><p className="eyebrow">Details</p><h1 className="mt-3 break-words text-2xl font-semibold tracking-[-.035em]">{image.original_filename}</h1>{image.smart_labels.length > 0 && <div className="mt-4 flex flex-wrap gap-2">{image.smart_labels.map((label) => <span key={label} className="rounded-full border border-line bg-white/[.025] px-2.5 py-1 text-[10px] capitalize text-muted">{label}</span>)}</div>}<div className="mt-6 grid grid-cols-2 gap-3">{metadata.map(([Icon,label,value]) => <div key={label} className="rounded-xl border border-line bg-white/[.018] p-3"><Icon className="h-4 w-4 text-muted" /><p className="mt-3 text-[10px] text-muted">{label}</p><p className="mt-1 truncate text-xs font-medium" title={value}>{value}</p></div>)}</div>{image.exact_duplicate_of && <Link to={`/images/${image.exact_duplicate_of.id}`} className="mt-5 block rounded-xl border border-coral/20 bg-coral/[.07] p-4"><div className="flex items-center gap-2 text-sm font-semibold text-coral"><Copy className="h-4 w-4" />Exact duplicate</div><p className="mt-1 truncate text-xs text-muted">{image.exact_duplicate_of.original_filename}</p></Link>}</aside>
    </div>

    <div className="mt-5 grid gap-5 lg:grid-cols-2">
      <section className="panel rounded-[28px] p-5 sm:p-6"><div className="flex items-center justify-between"><div><p className="eyebrow">Photo quality</p><h2 className="mt-2 text-xl font-semibold">{image.quality_score === null ? "Analyzing" : `${Math.round(image.quality_score * 100)} / 100`}</h2></div><Sparkles className="h-6 w-6 text-acid" /></div><div className="mt-6 grid gap-4 sm:grid-cols-2"><ScoreBar label="Sharpness" value={image.blur_score} /><ScoreBar label="Exposure" value={image.exposure_score} color="bg-lilac" /><ScoreBar label="Resolution" value={image.resolution_score} color="bg-coral" /><ScoreBar label="Screenshot" value={image.screenshot_quality_score} /></div></section>
      <section className="panel rounded-[28px] p-5 sm:p-6"><div className="flex items-center justify-between gap-3"><div className="flex items-center gap-2"><ScanText className="h-5 w-5 text-lilac" /><h2 className="font-semibold">Detected text</h2></div>{image.ocr_language && <span className="flex items-center gap-1.5 rounded-full border border-lilac/20 bg-lilac/[.06] px-2.5 py-1 font-mono text-[9px] uppercase text-lilac"><Languages className="h-3 w-3" />{image.ocr_language}</span>}</div>{image.ocr_text ? <><div className="mt-3 flex flex-wrap gap-2"><span className="rounded-full border border-line px-2.5 py-1 text-[10px] capitalize text-muted">{image.document_type ?? "unstructured text"}</span><span className="rounded-full border border-line px-2.5 py-1 text-[10px] text-muted">{image.ocr_layout.length} positioned words</span></div><p className="mt-3 max-h-40 overflow-y-auto whitespace-pre-wrap rounded-xl bg-black/20 p-4 text-xs leading-5 text-muted">{image.ocr_text}</p></> : <p className="mt-4 text-sm text-muted">No text found.</p>}</section>
    </div>

    <section className="panel mt-5 rounded-[28px] p-5 sm:p-6"><div className="mb-5 flex items-center justify-between gap-3"><div><p className="eyebrow">Related images</p><h2 className="mt-2 text-xl font-semibold">Visual matches</h2></div>{image.batch_id && <Link to={`/duplicates?batch=${image.batch_id}`}><Button variant="secondary">View batch</Button></Link>}</div>{image.similar_images.length === 0 ? <div className="rounded-2xl border border-dashed border-line py-12 text-center text-sm text-muted">No strong matches.</div> : <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">{image.similar_images.map((similar) => <article key={similar.image.id} className="overflow-hidden rounded-2xl border border-line bg-black/10"><Link to={`/images/${similar.image.id}`} className="focus-ring group block"><div className="relative aspect-[16/9] overflow-hidden bg-[#171b21]">{similar.image.thumbnail_url && <img src={similar.image.thumbnail_url} alt={similar.image.original_filename} className="h-full w-full object-cover transition group-hover:scale-[1.03]" />}<span className="absolute bottom-3 right-3 rounded-full bg-white px-2.5 py-1 font-mono text-[10px] font-semibold text-black">{percent(similar.similarity_score)}</span></div></Link><div className="p-4"><p className="truncate text-sm font-semibold">{similar.image.original_filename}</p><p className="mt-1 text-xs text-muted">{similar.classification}</p><div className="mt-4 grid grid-cols-2 gap-3"><ScoreBar label="AI" value={similar.clip_score} /><ScoreBar label="Structure" value={similar.perceptual_score} /><ScoreBar label="Color" value={similar.color_score} /><ScoreBar label="Frame" value={similar.aspect_score} /></div></div></article>)}</div>}</section>

    <AnimatePresence>{confirming && <div className="fixed inset-0 z-50 grid place-items-center p-4"><motion.button aria-label="Close confirmation" className="absolute inset-0 bg-black/75" initial={{ opacity: 0 }} animate={{ opacity: 1 }} onClick={() => { if (!deleting) setConfirming(false); }} /><motion.div role="dialog" aria-modal="true" className="panel relative z-10 w-full max-w-md rounded-[28px] p-6" initial={{ scale: .96, opacity: 0 }} animate={{ scale: 1, opacity: 1 }}><button onClick={() => { if (!deleting) setConfirming(false); }} aria-label="Close" className="absolute right-4 top-4 p-2 text-muted"><X className="h-4 w-4" /></button><h2 className="text-xl font-semibold">Delete this image?</h2><p className="mt-2 text-sm text-muted">This cannot be undone.</p><div className="mt-6 flex justify-end gap-2"><Button variant="secondary" onClick={() => { if (!deleting) setConfirming(false); }}>Cancel</Button><Button variant="danger" loading={deleting} onClick={remove}>Delete permanently</Button></div></motion.div></div>}</AnimatePresence>
  </>;
}
