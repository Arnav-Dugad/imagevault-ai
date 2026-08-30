import { AnimatePresence, motion } from "framer-motion";
import { Aperture, Brain, CalendarDays, Check, Combine, Eye, EyeOff, Images, Pencil, Scissors, Sparkles, UserRoundCheck, UsersRound, X } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Button, EmptyState, LoadingGrid, PageHeading } from "../components/ui";
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
  const [selectedPeople, setSelectedPeople] = useState<Set<string>>(new Set());
  const [managing, setManaging] = useState(false);
  const [includeIgnored, setIncludeIgnored] = useState(false);
  const [splitMode, setSplitMode] = useState(false);
  const [splitImages, setSplitImages] = useState<Set<string>>(new Set());
  const [personName, setPersonName] = useState("");
  const [refreshKey, setRefreshKey] = useState(0);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    setData(null); setSelected(null); setSelectedPeople(new Set()); setError("");
    const suffix = tab === "people" && includeIgnored ? "?include_ignored=true" : "";
    api<SmartAlbums>(`/albums/${tab}${suffix}`).then(setData).catch((reason: Error) => setError(reason.message));
  }, [includeIgnored, refreshKey, tab]);

  useEffect(() => {
    setPersonName(selected?.title ?? ""); setSplitMode(false); setSplitImages(new Set());
  }, [selected]);

  function togglePerson(personId: string) {
    setSelectedPeople((current) => { const next = new Set(current); if (next.has(personId)) next.delete(personId); else next.add(personId); return next; });
  }

  async function runAction(action: () => Promise<{ message: string }>, close = true) {
    setBusy(true); setError("");
    try {
      const result = await action(); setNotice(result.message);
      if (close) setSelected(null);
      setManaging(false); setSelectedPeople(new Set()); setRefreshKey((value) => value + 1);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "People update failed"); }
    finally { setBusy(false); }
  }

  function feedback(feedbackType: "SAME" | "DIFFERENT") {
    const ids = [...selectedPeople];
    if (ids.length !== 2) return;
    void runAction(() => api("/albums/people/feedback", { method: "POST", body: JSON.stringify({ first_person_id: ids[0], second_person_id: ids[1], feedback_type: feedbackType }) }));
  }

  function saveName() {
    if (!selected?.person_id || !personName.trim()) return;
    void runAction(() => api(`/albums/people/${selected.person_id}/rename`, { method: "POST", body: JSON.stringify({ display_name: personName.trim() }) }));
  }

  function setIgnored(ignored: boolean) {
    if (!selected?.person_id) return;
    void runAction(() => api(`/albums/people/${selected.person_id}/ignore`, { method: "POST", body: JSON.stringify({ ignored }) }));
  }

  function splitPerson() {
    if (!selected?.person_id || splitImages.size === 0) return;
    void runAction(() => api(`/albums/people/${selected.person_id}/split`, { method: "POST", body: JSON.stringify({ image_ids: [...splitImages] }) }));
  }

  const active = tabs.find((item) => item.id === tab)!;
  const peopleAction = tab === "people" ? <div className="flex flex-wrap gap-2"><Button variant="secondary" onClick={() => { setManaging((value) => !value); setSelectedPeople(new Set()); }}><Brain className="h-4 w-4" />{managing ? "Done" : "Teach ImageVault"}</Button><Button variant="ghost" onClick={() => setIncludeIgnored((value) => !value)}>{includeIgnored ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}{includeIgnored ? "Hide ignored" : "Show ignored"}</Button></div> : undefined;

  return <>
    <PageHeading eyebrow="Organized for you" title="Smart albums" action={peopleAction} />
    <div className="panel mb-5 flex gap-2 overflow-x-auto rounded-2xl p-2">
      {tabs.map(({ id, label, icon: Icon }) => <button key={id} onClick={() => { setTab(id); setManaging(false); }} className={`focus-ring relative flex min-w-fit items-center gap-2 overflow-hidden rounded-xl px-4 py-2.5 text-xs font-semibold transition-colors ${tab === id ? "text-canvas" : "text-muted hover:text-ink"}`}>
        {tab === id && <motion.span layoutId="album-tab" className="absolute inset-0 bg-ink" transition={{ type: "spring", stiffness: 460, damping: 34 }} />}<Icon className="relative h-4 w-4" /><span className="relative">{label}</span>
      </button>)}
    </div>

    {notice && <motion.div role="status" initial={{ opacity: 0, y: -6 }} animate={{ opacity: 1, y: 0 }} className="mb-4 flex items-center justify-between rounded-xl border border-acid/20 bg-acid/[.06] p-4 text-sm"><span className="flex items-center gap-2"><UserRoundCheck className="h-4 w-4 text-acid" />{notice}</span><button onClick={() => setNotice("")} className="p-1 text-muted"><X className="h-4 w-4" /></button></motion.div>}
    {error && <div role="alert" className="mb-4 rounded-xl border border-coral/20 bg-coral/[.07] p-4 text-sm text-orange-100">{error}</div>}
    {managing && <div className="panel mb-5 rounded-2xl border-lilac/20 p-4"><div className="flex flex-col justify-between gap-4 lg:flex-row lg:items-center"><div><p className="flex items-center gap-2 text-sm font-semibold"><Brain className="h-4 w-4 text-lilac" />Private feedback learning</p><p className="mt-1 text-xs text-muted">Select exactly two people, then tell ImageVault whether they match. Feedback stays in your database.</p></div><div className="flex flex-wrap gap-2"><Button disabled={selectedPeople.size !== 2 || busy} onClick={() => feedback("SAME")}><Combine className="h-4 w-4" />Same person · merge</Button><Button variant="secondary" disabled={selectedPeople.size !== 2 || busy} onClick={() => feedback("DIFFERENT")}><UsersRound className="h-4 w-4" />Different people</Button></div></div></div>}

    <AnimatePresence mode="wait" initial={false}><motion.div key={`${tab}-${refreshKey}`} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -5 }} transition={{ duration: .2 }}>
      {error && !data ? <EmptyState icon={active.icon} title="Albums unavailable" description={error} /> : !data ? <LoadingGrid count={6} /> : data.items.length === 0 ? <EmptyState icon={active.icon} title={`No ${active.label.toLowerCase()} yet`} description={tab === "people" ? "People albums appear after the same face is confidently matched in at least two photos." : tab === "bursts" ? "Related shots taken seconds apart will appear here." : "Upload photos with dates to build event albums."} /> : <motion.div initial="hidden" animate="visible" variants={{ hidden: {}, visible: { transition: { staggerChildren: .055 } } }} className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {data.items.map((album) => { const chosen = Boolean(album.person_id && selectedPeople.has(album.person_id)); return <motion.button variants={{ hidden: { opacity: 0, y: 18, scale: .985 }, visible: { opacity: 1, y: 0, scale: 1 } }} whileHover={{ y: -6, scale: 1.006 }} whileTap={{ scale: .985 }} transition={{ type: "spring", stiffness: 360, damping: 30 }} key={album.id} onClick={() => album.person_id && managing ? togglePerson(album.person_id) : setSelected(album)} className={`panel premium-card focus-ring group overflow-hidden rounded-[24px] text-left ${chosen ? "ring-2 ring-lilac" : ""} ${album.ignored ? "opacity-60" : ""}`}>
          <div className="relative aspect-[16/10] overflow-hidden bg-[#171b21]">{album.cover.thumbnail_url ? <img src={album.cover.thumbnail_url} alt="" className="h-full w-full object-cover transition duration-700 ease-out group-hover:scale-[1.055]" style={album.cover_focus_x !== null && album.cover_focus_y !== null ? { objectPosition: `${album.cover_focus_x * 100}% ${album.cover_focus_y * 100}%` } : undefined} /> : <div className="grid h-full place-items-center"><Images className="h-8 w-8 text-muted" /></div>}<div className="card-sheen absolute inset-0 opacity-0 transition-opacity group-hover:opacity-100" /><div className="absolute inset-x-0 bottom-0 h-24 bg-gradient-to-t from-black/85 to-transparent" />{managing && <span className={`absolute left-3 top-3 grid h-8 w-8 place-items-center rounded-full border ${chosen ? "border-lilac bg-lilac text-canvas" : "border-white/30 bg-black/60"}`}>{chosen && <Check className="h-4 w-4" />}</span>}{album.ignored && <span className="absolute right-3 top-3 rounded-full bg-black/70 px-2.5 py-1 font-mono text-[9px] uppercase text-muted">Ignored</span>}{album.best_image_id && tab === "bursts" && <span className="absolute left-3 top-3 flex items-center gap-1.5 rounded-full bg-acid px-2.5 py-1 font-mono text-[9px] font-semibold uppercase text-canvas"><Sparkles className="h-3 w-3" />Best selected</span>}<span className="absolute bottom-3 right-3 rounded-full border border-white/10 bg-black/60 px-2.5 py-1 font-mono text-[9px] uppercase text-white">{album.image_count} photos</span></div><div className="p-4"><h2 className="font-semibold">{album.title}</h2><p className="mt-1 text-xs text-muted">{album.subtitle}</p></div>
        </motion.button>; })}
      </motion.div>}
    </motion.div></AnimatePresence>

    <AnimatePresence>{selected && <div className="fixed inset-0 z-50 grid place-items-center p-4"><motion.button aria-label="Close album" className="absolute inset-0 bg-black/80 backdrop-blur-sm" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={() => setSelected(null)} /><motion.section role="dialog" aria-modal="true" initial={{ opacity: 0, scale: .94, y: 24 }} animate={{ opacity: 1, scale: 1, y: 0 }} exit={{ opacity: 0, scale: .96, y: 12 }} transition={{ type: "spring", stiffness: 340, damping: 30 }} className="panel relative z-10 max-h-[88vh] w-full max-w-5xl overflow-y-auto rounded-[28px] p-5 shadow-float sm:p-6">
      <button onClick={() => setSelected(null)} aria-label="Close" className="focus-ring button-lift absolute right-4 top-4 rounded-lg p-2 text-muted hover:text-ink"><X className="h-5 w-5" /></button><p className="eyebrow">{active.label}</p>
      {tab === "people" && selected.person_id ? <div className="mt-3 flex flex-col gap-3 pr-10 sm:flex-row sm:items-center"><label className="relative max-w-sm flex-1"><Pencil className="pointer-events-none absolute left-3 top-3 h-4 w-4 text-muted" /><span className="sr-only">Person name</span><input value={personName} onChange={(event) => setPersonName(event.target.value)} maxLength={100} className="focus-ring h-10 w-full rounded-xl border border-line bg-canvas pl-9 pr-3 text-sm font-semibold" /></label><Button disabled={!personName.trim() || personName.trim() === selected.title} loading={busy} onClick={saveName}>Save name</Button><Button variant="ghost" onClick={() => setIgnored(!selected.ignored)}>{selected.ignored ? <Eye className="h-4 w-4" /> : <EyeOff className="h-4 w-4" />}{selected.ignored ? "Restore" : "Ignore"}</Button></div> : <h2 className="mt-2 pr-10 text-2xl font-semibold">{selected.title}</h2>}
      <div className="mt-3 flex flex-wrap items-center justify-between gap-3"><p className="text-sm text-muted">{selected.subtitle}</p>{tab === "people" && selected.images.length > 1 && <div className="flex gap-2">{splitMode ? <><Button variant="ghost" onClick={() => { setSplitMode(false); setSplitImages(new Set()); }}>Cancel split</Button><Button disabled={splitImages.size === 0 || splitImages.size >= selected.images.length} loading={busy} onClick={splitPerson}><Scissors className="h-4 w-4" />Move {splitImages.size} to new person</Button></> : <Button variant="secondary" onClick={() => setSplitMode(true)}><Scissors className="h-4 w-4" />Split photos</Button>}</div>}</div>
      {splitMode && <p className="mt-3 rounded-xl border border-lilac/20 bg-lilac/[.05] p-3 text-xs text-muted">Select photos that belong to a different person. At least one photo must remain here.</p>}
      <motion.div initial="hidden" animate="visible" variants={{ hidden: {}, visible: { transition: { staggerChildren: .04 } } }} className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">{selected.images.map((image) => { const chosen = splitImages.has(image.id); const body = <><div className="relative aspect-square overflow-hidden bg-[#171b21]">{image.thumbnail_url && <img src={image.thumbnail_url} alt={image.original_filename} className="h-full w-full object-cover transition duration-500 group-hover:scale-105" />}{splitMode && <span className={`absolute left-2 top-2 grid h-7 w-7 place-items-center rounded-full border ${chosen ? "border-lilac bg-lilac text-canvas" : "border-white/30 bg-black/60"}`}>{chosen && <Check className="h-3.5 w-3.5" />}</span>}{selected.best_image_id === image.id && !splitMode && <span className="absolute left-2 top-2 flex items-center gap-1 rounded-full bg-acid px-2 py-1 font-mono text-[9px] font-semibold uppercase text-canvas"><Check className="h-3 w-3" />Best</span>}</div><p className="truncate p-3 text-xs font-medium">{image.original_filename}</p></>; return <motion.div key={image.id} variants={{ hidden: { opacity: 0, scale: .96 }, visible: { opacity: 1, scale: 1 } }}>{splitMode ? <button onClick={() => setSplitImages((current) => { const next = new Set(current); if (next.has(image.id)) next.delete(image.id); else next.add(image.id); return next; })} className={`focus-ring group block w-full overflow-hidden rounded-2xl border bg-black/10 text-left ${chosen ? "border-lilac" : "border-line"}`}>{body}</button> : <Link to={`/images/${image.id}`} state={{ returnTo: "/albums" }} className={`focus-ring group block overflow-hidden rounded-2xl border bg-black/10 transition hover:-translate-y-1 ${selected.best_image_id === image.id ? "border-acid" : "border-line hover:border-white/20"}`}>{body}</Link>}</motion.div>; })}</motion.div>
    </motion.section></div>}</AnimatePresence>
  </>;
}
