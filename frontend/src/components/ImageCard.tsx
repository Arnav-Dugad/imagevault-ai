import { motion } from "framer-motion";
import { Check, ImageIcon, ScanSearch, Sparkles } from "lucide-react";
import { Link } from "react-router-dom";
import { formatBytes, formatDate, percent } from "../lib/utils";
import type { VaultImage } from "../types";
import { StatusBadge } from "./ui";

export function ImageCard({ image, index = 0, selectable, selected, onSelect }: { image: VaultImage; index?: number; selectable?: boolean; selected?: boolean; onSelect?: (id: string) => void }) {
  return <motion.article layout initial={{ opacity: 0, y: 14, scale: .985 }} animate={{ opacity: 1, y: 0, scale: 1 }} whileHover={{ y: -6, scale: 1.006 }} transition={{ layout: { type: "spring", stiffness: 360, damping: 32 }, opacity: { delay: Math.min(index, 12) * .035 }, y: { delay: Math.min(index, 12) * .035, duration: .3 }, scale: { duration: .22 } }} className={`panel premium-card group relative overflow-hidden rounded-2xl ${selected ? "ring-2 ring-acid" : ""}`}>
    {selectable && <button onClick={() => onSelect?.(image.id)} aria-label={`${selected ? "Deselect" : "Select"} ${image.original_filename}`} className={`focus-ring absolute left-3 top-3 z-20 grid h-8 w-8 place-items-center rounded-full border ${selected ? "border-acid bg-acid text-canvas" : "border-white/25 bg-black/55"}`}>{selected && <Check className="h-4 w-4" />}</button>}
    <Link to={`/images/${image.id}`} className="focus-ring block">
      <div className="relative aspect-[4/3] overflow-hidden bg-[#171b21]">
        {image.thumbnail_url ? <img src={image.thumbnail_url} alt={image.original_filename} loading="lazy" className="h-full w-full object-cover transition duration-700 ease-out group-hover:scale-[1.055]" /> : <div className="grid h-full place-items-center"><ImageIcon className="h-8 w-8 text-muted/40" /></div>}
        <div className="card-sheen absolute inset-0 opacity-0 transition-opacity duration-300 group-hover:opacity-100" />
        <div className="absolute inset-x-0 bottom-0 h-20 bg-gradient-to-t from-black/75 to-transparent" />
        <div className="absolute bottom-3 left-3 right-3 flex items-end justify-between gap-2"><StatusBadge status={image.status} />{image.best_similarity !== null && <span className="rounded-full bg-white px-2.5 py-1 font-mono text-[10px] font-semibold text-black">{percent(image.best_similarity)}</span>}</div>
      </div>
      <div className="p-4"><h3 className="truncate text-sm font-semibold" title={image.original_filename}>{image.original_filename}</h3><div className="mt-2 flex items-center justify-between font-mono text-[10px] uppercase tracking-wide text-muted"><span>{image.width && image.height ? `${image.width}×${image.height}` : "Analyzing"}</span><span>{formatBytes(image.file_size)}</span></div>{image.smart_labels.length > 0 && <div className="mt-3 flex gap-1.5 overflow-hidden">{image.smart_labels.slice(0, 3).map((label) => <span key={label} className="whitespace-nowrap rounded-full border border-line px-2 py-1 text-[9px] capitalize text-muted">{label}</span>)}</div>}<div className="mt-3 flex items-center justify-between text-xs text-muted"><span>{formatDate(image.created_at)}</span>{image.quality_score !== null && <span className="flex items-center gap-1 text-acid"><Sparkles className="h-3 w-3" />{Math.round(image.quality_score * 100)} quality</span>}</div></div>
    </Link>
    {image.status !== "PENDING" && image.status !== "PROCESSING" && <Link to={`/images/${image.id}`} aria-label={`Find images similar to ${image.original_filename}`} className="focus-ring absolute right-3 top-3 z-10 flex translate-y-1 items-center gap-1.5 rounded-full border border-white/10 bg-black/70 px-2.5 py-1.5 text-[10px] font-medium text-white opacity-0 backdrop-blur transition group-hover:translate-y-0 group-hover:opacity-100 focus:translate-y-0 focus:opacity-100"><ScanSearch className="h-3.5 w-3.5 text-acid" />Find similar</Link>}
  </motion.article>;
}
