import { motion } from "framer-motion";
import { ImageIcon } from "lucide-react";
import { Link } from "react-router-dom";
import { formatBytes, formatDate, percent } from "../lib/utils";
import type { VaultImage } from "../types";
import { StatusBadge } from "./ui";

export function ImageCard({ image, selectable, selected, onSelect }: { image: VaultImage; selectable?: boolean; selected?: boolean; onSelect?: (id: string) => void }) {
  return <motion.article layout whileHover={{ y: -4 }} transition={{ duration: .2 }} className={`panel group relative overflow-hidden rounded-2xl ${selected ? "ring-2 ring-acid" : ""}`}>
    {selectable && <button onClick={() => onSelect?.(image.id)} aria-label={`${selected ? "Deselect" : "Select"} ${image.original_filename}`} className={`focus-ring absolute left-3 top-3 z-10 grid h-7 w-7 place-items-center rounded-full border ${selected ? "border-acid bg-acid text-canvas" : "border-white/25 bg-black/45"}`}><span className="text-xs font-bold">{selected ? "✓" : ""}</span></button>}
    <Link to={`/images/${image.id}`} className="focus-ring block">
      <div className="relative aspect-[4/3] overflow-hidden bg-[#171b21]">
        {image.thumbnail_url ? <img src={image.thumbnail_url} alt={image.original_filename} loading="lazy" className="h-full w-full object-cover transition duration-500 group-hover:scale-[1.03]" /> : <div className="grid h-full place-items-center"><ImageIcon className="h-8 w-8 text-muted/40" /></div>}
        <div className="absolute inset-x-0 bottom-0 h-20 bg-gradient-to-t from-black/70 to-transparent" />
        <div className="absolute bottom-3 left-3 right-3 flex items-end justify-between gap-2"><StatusBadge status={image.status} />{image.best_similarity !== null && <span className="rounded-full bg-black/65 px-2.5 py-1 font-mono text-[10px] text-white">{percent(image.best_similarity)}</span>}</div>
      </div>
      <div className="p-4"><h3 className="truncate text-sm font-semibold" title={image.original_filename}>{image.original_filename}</h3><div className="mt-2 flex items-center justify-between font-mono text-[10px] uppercase tracking-wide text-muted"><span>{image.width && image.height ? `${image.width}×${image.height}` : "Analyzing"}</span><span>{formatBytes(image.file_size)}</span></div><p className="mt-2 text-xs text-muted">{formatDate(image.created_at)}</p></div>
    </Link>
  </motion.article>;
}
