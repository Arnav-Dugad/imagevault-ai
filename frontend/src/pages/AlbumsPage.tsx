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
    api<SmartAlbums>(`/albums/${tab}`)
      .then(setData)
      .catch((reason: Error) => setError(reason.message));
  }, [tab]);

  const active = tabs.find((item) => item.id === tab)!;
  return <>
    <PageHeading eyebrow="Organized for you" title="Smart albums" />
    <div className="panel mb-5 flex gap-2 overflow-x-auto rounded-2xl p-2">
      {tabs.map(({ id, label, icon: Icon }) => <button key={id} onClick={() => setTab(id)} className={`focus-ring relative flex min-w-fit items-center gap-2 overflow-hidden rounded-xl px-4 py-2.5 text-xs font-semibold transition-colors ${tab === id ? "text-canvas" : "text-muted hover:text-ink"}`}>
        {tab === id && <motion.span layoutId="album-tab" className="absolute inset-0 bg-ink" transition={{ type: "spring", stiffness: 460, damping: 34 }} />}
        <Icon className="relative h-4 w-4" /><span className="relative">{label}</span>
      </button>)}
    </div>

    <AnimatePresence mode="wait" initial={false}>
      <motion.div key={tab} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -5 }} transition={{ duration: .2 }}>
        {error ? <EmptyState icon={active.icon} title="Albums unavailable" description={error} /> : !data ? <LoadingGrid count={6} /> : data.items.length === 0 ? <EmptyState icon={active.icon} title={`No ${active.label.toLowerCase()} yet`} description={tab === "people" ? "People albums appear after the same face is confidently matched in at least two photos." : tab === "bursts" ? "Related shots taken seconds apart will appear here." : "Upload photos with dates to build event albums."} /> : <motion.div initial="hidden" animate="visible" variants={{ hidden: {}, visible: { transition: { staggerChildren: .055 } } }} className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {data.items.map((album) => <motion.button variants={{ hidden: { opacity: 0, y: 18, scale: .985 }, visible: { opacity: 1, y: 0, scale: 1 } }} whileHover={{ y: -6, scale: 1.006 }} whileTap={{ scale: .985 }} transition={{ type: "spring", stiffness: 360, damping: 30 }} key={album.id} onClick={() => setSelected(album)} className="panel premium-card focus-ring group overflow-hidden rounded-[24px] text-left">
            <div className="relative aspect-[16/10] overflow-hidden bg-[#171b21]">
              {album.cover.thumbnail_url ? <img src={album.cover.thumbnail_url} alt="" className="h-full w-full object-cover transition duration-700 ease-out group-hover:scale-[1.055]" style={album.cover_focus_x !== null && album.cover_focus_y !== null ? { objectPosition: `${album.cover_focus_x * 100}% ${album.cover_focus_y * 100}%` } : undefined} /> : <div className="grid h-full place-items-center"><Images className="h-8 w-8 text-muted" /></div>}
              <div className="card-sheen absolute inset-0 opacity-0 transition-opacity group-hover:opacity-100" />
              <div className="absolute inset-x-0 bottom-0 h-24 bg-gradient-to-t from-black/85 to-transparent" />
              {album.best_image_id && tab === "bursts" && <motion.span initial={{ opacity: 0, scale: .8 }} animate={{ opacity: 1, scale: 1 }} className="absolute left-3 top-3 flex items-center gap-1.5 rounded-full bg-acid px-2.5 py-1 font-mono text-[9px] font-semibold uppercase text-canvas"><Sparkles className="h-3 w-3" />Best selected</motion.span>}
              <span className="absolute bottom-3 right-3 rounded-full border border-white/10 bg-black/60 px-2.5 py-1 font-mono text-[9px] uppercase text-white">{album.image_count} photos</span>
            </div>
            <div className="p-4"><h2 className="font-semibold">{album.title}</h2><p className="mt-1 text-xs text-muted">{album.subtitle}</p></div>
          </motion.button>)}
        </motion.div>}
      </motion.div>
    </AnimatePresence>

    <AnimatePresence>{selected && <div className="fixed inset-0 z-50 grid place-items-center p-4">
      <motion.button aria-label="Close album" className="absolute inset-0 bg-black/80 backdrop-blur-sm" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={() => setSelected(null)} />
      <motion.section role="dialog" aria-modal="true" initial={{ opacity: 0, scale: .94, y: 24 }} animate={{ opacity: 1, scale: 1, y: 0 }} exit={{ opacity: 0, scale: .96, y: 12 }} transition={{ type: "spring", stiffness: 340, damping: 30 }} className="panel relative z-10 max-h-[88vh] w-full max-w-5xl overflow-y-auto rounded-[28px] p-5 shadow-float sm:p-6">
        <button onClick={() => setSelected(null)} aria-label="Close" className="focus-ring button-lift absolute right-4 top-4 rounded-lg p-2 text-muted hover:text-ink"><X className="h-5 w-5" /></button>
        <p className="eyebrow">{active.label}</p><h2 className="mt-2 pr-10 text-2xl font-semibold">{selected.title}</h2><p className="mt-1 text-sm text-muted">{selected.subtitle}</p>
        <motion.div initial="hidden" animate="visible" variants={{ hidden: {}, visible: { transition: { staggerChildren: .04 } } }} className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {selected.images.map((image) => <motion.div key={image.id} variants={{ hidden: { opacity: 0, scale: .96 }, visible: { opacity: 1, scale: 1 } }}><Link to={`/images/${image.id}`} className={`focus-ring group block overflow-hidden rounded-2xl border bg-black/10 transition hover:-translate-y-1 ${selected.best_image_id === image.id ? "border-acid" : "border-line hover:border-white/20"}`}><div className="relative aspect-square overflow-hidden bg-[#171b21]">{image.thumbnail_url && <img src={image.thumbnail_url} alt={image.original_filename} className="h-full w-full object-cover transition duration-500 group-hover:scale-105" />}{selected.best_image_id === image.id && <span className="absolute left-2 top-2 flex items-center gap-1 rounded-full bg-acid px-2 py-1 font-mono text-[9px] font-semibold uppercase text-canvas"><Check className="h-3 w-3" />Best</span>}</div><p className="truncate p-3 text-xs font-medium">{image.original_filename}</p></Link></motion.div>)}
        </motion.div>
      </motion.section>
    </div>}</AnimatePresence>
  </>;
}
