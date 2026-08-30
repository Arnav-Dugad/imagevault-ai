import { AnimatePresence, motion } from "framer-motion";
import { Aperture, CalendarDays, Check, Images, Sparkles, UsersRound, X } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { EmptyState, LoadingGrid, PageHeading } from "../components/ui";
import { api } from "../lib/api";
import type { SmartAlbum, SmartAlbums } from "../types";

const tabs = [
  { id: "events", label: "Events", icon: CalendarDays },
  { id: "people", label: "People", icon: UsersRound },
  { id: "bursts", label: "Best shots", icon: Aperture },
] as const;

export function AlbumsPage() {
  const [tab, setTab] = useState<(typeof tabs)[number]["id"]>("events");
  const [data, setData] = useState<SmartAlbums | null>(null);
  const [selected, setSelected] = useState<SmartAlbum | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    setData(null);
    setSelected(null);
    setError("");
    api<SmartAlbums>(`/albums/${tab}`).then(setData).catch((reason: Error) => setError(reason.message));
  }, [tab]);

  const active = tabs.find((item) => item.id === tab)!;
  return <>
    <PageHeading eyebrow="Organized for you" title="Smart albums" />
    <div className="panel mb-5 flex gap-2 overflow-x-auto rounded-2xl p-2">{tabs.map(({ id, label, icon: Icon }) => <button key={id} onClick={() => setTab(id)} className={`focus-ring flex min-w-fit items-center gap-2 rounded-xl px-4 py-2.5 text-xs font-semibold transition ${tab === id ? "bg-ink text-canvas" : "text-muted hover:bg-white/5 hover:text-ink"}`}><Icon className="h-4 w-4" />{label}</button>)}</div>
    {error ? <EmptyState icon={active.icon} title="Albums unavailable" description={error} /> : !data ? <LoadingGrid count={6} /> : data.items.length === 0 ? <EmptyState icon={active.icon} title={`No ${active.label.toLowerCase()} yet`} description={tab === "people" ? "People groups appear after faces are found in analyzed photos." : tab === "bursts" ? "Related shots taken seconds apart will appear here." : "Upload photos with dates to build event albums."} /> : <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">{data.items.map((album) => <motion.button whileHover={{ y: -4 }} key={album.id} onClick={() => setSelected(album)} className="panel focus-ring group overflow-hidden rounded-[24px] text-left"><div className="relative aspect-[16/10] overflow-hidden bg-[#171b21]">{album.cover.thumbnail_url ? <img src={album.cover.thumbnail_url} alt="" className="h-full w-full object-cover transition duration-500 group-hover:scale-[1.03]" /> : <div className="grid h-full place-items-center"><Images className="h-8 w-8 text-muted" /></div>}<div className="absolute inset-x-0 bottom-0 h-24 bg-gradient-to-t from-black/85 to-transparent" />{album.best_image_id && tab === "bursts" && <span className="absolute left-3 top-3 flex items-center gap-1.5 rounded-full bg-acid px-2.5 py-1 font-mono text-[9px] font-semibold uppercase text-canvas"><Sparkles className="h-3 w-3" />Best selected</span>}<span className="absolute bottom-3 right-3 rounded-full border border-white/10 bg-black/60 px-2.5 py-1 font-mono text-[9px] uppercase text-white">{album.image_count} photos</span></div><div className="p-4"><h2 className="font-semibold">{album.title}</h2><p className="mt-1 text-xs text-muted">{album.subtitle}</p></div></motion.button>)}</div>}

    <AnimatePresence>{selected && <div className="fixed inset-0 z-50 grid place-items-center p-4"><motion.button aria-label="Close album" className="absolute inset-0 bg-black/80 backdrop-blur-sm" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={() => setSelected(null)} /><motion.section role="dialog" aria-modal="true" initial={{ opacity: 0, scale: .97, y: 12 }} animate={{ opacity: 1, scale: 1, y: 0 }} exit={{ opacity: 0, scale: .97 }} className="panel relative z-10 max-h-[88vh] w-full max-w-5xl overflow-y-auto rounded-[28px] p-5 sm:p-6"><button onClick={() => setSelected(null)} aria-label="Close" className="focus-ring absolute right-4 top-4 rounded-lg p-2 text-muted hover:text-ink"><X className="h-5 w-5" /></button><p className="eyebrow">{active.label}</p><h2 className="mt-2 pr-10 text-2xl font-semibold">{selected.title}</h2><p className="mt-1 text-sm text-muted">{selected.subtitle}</p><div className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">{selected.images.map((image) => <Link key={image.id} to={`/images/${image.id}`} className={`focus-ring overflow-hidden rounded-2xl border bg-black/10 ${selected.best_image_id === image.id ? "border-acid" : "border-line"}`}><div className="relative aspect-square bg-[#171b21]">{image.thumbnail_url && <img src={image.thumbnail_url} alt={image.original_filename} className="h-full w-full object-cover" />}{selected.best_image_id === image.id && <span className="absolute left-2 top-2 flex items-center gap-1 rounded-full bg-acid px-2 py-1 font-mono text-[9px] font-semibold uppercase text-canvas"><Check className="h-3 w-3" />Best</span>}</div><p className="truncate p-3 text-xs font-medium">{image.original_filename}</p></Link>)}</div></motion.section></div>}</AnimatePresence>
  </>;
}
