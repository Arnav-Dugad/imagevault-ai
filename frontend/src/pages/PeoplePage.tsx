import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, Check, Combine, Pencil, Split, UserRound, Users, X } from "lucide-react";
import { PhotoGrid } from "../components/PhotoCard";
import { PhotoViewer } from "../components/PhotoViewer";
import { Button, EmptyState, ErrorNote, PageHeading, Spinner } from "../components/ui";
import { api } from "../lib/api";
import { useToast } from "../lib/toast";
import { cn } from "../lib/utils";
import type { Person, PersonDetails } from "../types";

export const personName = (person: { name: string | null }) => person.name || "Unnamed";

export function FaceAvatar({ src, className = "h-28 w-28" }: { src: string | null; className?: string }) {
  return src
    ? <img src={src} alt="" className={`${className} rounded-full border-2 border-line object-cover`} />
    : <div className={`${className} grid place-items-center rounded-full border-2 border-line bg-raised`}><UserRound className="h-1/3 w-1/3 text-muted" /></div>;
}

export function PeoplePage() {
  const [people, setPeople] = useState<Person[] | null>(null);
  const [error, setError] = useState("");
  const [picking, setPicking] = useState<Set<string> | null>(null); // merge mode: which people are picked
  const toast = useToast();
  const load = useCallback(() => { api<Person[]>("/people").then(setPeople).catch((e: Error) => setError(e.message)); }, []);
  useEffect(load, [load]);

  async function merge() {
    if (!picking || picking.size < 2) return;
    await api("/people/merge", { method: "POST", body: JSON.stringify({ ids: [...picking] }) });
    toast(`${picking.size} people merged into one`);
    setPicking(null);
    load();
  }
  const toggle = (id: string) => setPicking((p) => { const next = new Set(p); if (next.has(id)) next.delete(id); else next.add(id); return next; });

  return <>
    <PageHeading title="People"
      action={people && people.length > 1 && (picking
        ? <><Button variant="ghost" onClick={() => setPicking(null)}><X className="h-4 w-4" />Cancel</Button>
            <Button onClick={merge} disabled={picking.size < 2}><Combine className="h-4 w-4" />Merge {picking.size || ""}</Button></>
        : <Button variant="secondary" onClick={() => setPicking(new Set())}><Combine className="h-4 w-4" />Merge people</Button>)} />
    {picking && <p className="-mt-4 mb-6 text-sm text-sky-300">Pick the people who are the same person.</p>}
    {error && <ErrorNote message={error} />}
    {!people && !error && <Spinner />}
    {people?.length === 0 && (
      <EmptyState icon={Users} title="No people yet">Upload a few photos of the same person and they'll show up here.</EmptyState>
    )}
    {people && people.length > 0 && (
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5">
        {people.map((person, i) => {
          const picked = picking?.has(person.id);
          const body = <>
            <div className="relative">
              <FaceAvatar src={person.image_url} className="h-24 w-24 transition group-hover:scale-105" />
              {picking && <span className={cn("absolute -right-1 -top-1 grid h-7 w-7 place-items-center rounded-full border-2", picked ? "border-sky-300 bg-sky-300 text-canvas" : "border-white/70 bg-black/40 text-transparent")}><Check className="h-4 w-4" strokeWidth={3} /></span>}
            </div>
            <p className={cn("mt-3 font-semibold", !person.name && "text-muted")}>{personName(person)}</p>
            <p className="text-xs text-muted">{person.photos} {person.photos === 1 ? "photo" : "photos"}</p>
          </>;
          const style = { animationDelay: `${i * 40}ms`, animationFillMode: "backwards" as const };
          const classes = cn("pop-in focus-ring group panel flex flex-col items-center p-5 text-center transition hover:-translate-y-0.5",
            picked ? "border-sky-300/70 ring-2 ring-sky-300/30" : "hover:border-sky-300/40");
          return picking
            ? <button key={person.id} onClick={() => toggle(person.id)} style={style} className={classes}>{body}</button>
            : <Link key={person.id} to={`/people/${person.id}`} style={style} className={classes}>{body}</Link>;
        })}
      </div>
    )}
  </>;
}

export function PersonPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const toast = useToast();
  const [person, setPerson] = useState<PersonDetails | null>(null);
  const [error, setError] = useState("");
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState("");
  const [openId, setOpenId] = useState<string | null>(null);
  const [wrong, setWrong] = useState<Set<string> | null>(null); // split mode: faces that are someone else

  const load = useCallback(() => {
    api<PersonDetails>(`/people/${id}`).then((p) => { setPerson(p); setName(p.name ?? ""); }).catch((e: Error) => setError(e.message));
  }, [id]);
  useEffect(load, [load]);

  async function save(event: FormEvent) {
    event.preventDefault();
    await api(`/people/${id}`, { method: "PUT", body: JSON.stringify({ name }) }).catch((e: Error) => setError(e.message));
    setEditing(false);
    load();
  }

  async function split() {
    if (!wrong?.size) return;
    const result = await api<{ id: string }>(`/people/${id}/split`, { method: "POST", body: JSON.stringify({ face_ids: [...wrong] }) });
    toast(`Moved ${wrong.size} ${wrong.size === 1 ? "face" : "faces"} to a new person`);
    setWrong(null);
    if (wrong.size === person?.faces.length) navigate(`/people/${result.id}`);
    else load();
  }

  if (error) return <ErrorNote message={error} />;
  if (!person) return <Spinner />;
  return <>
    <Link to="/people" className="focus-ring mb-6 inline-flex items-center gap-1.5 rounded-lg text-sm text-muted hover:text-ink"><ArrowLeft className="h-4 w-4" />People</Link>
    <div className="mb-8 flex flex-col items-start gap-5 sm:flex-row sm:items-center">
      <FaceAvatar src={person.image_url} />
      <div className="flex-1">
        {editing ? (
          <form onSubmit={save} className="flex flex-wrap gap-2">
            <input autoFocus value={name} onChange={(e) => setName(e.target.value)} maxLength={100} placeholder="Name"
              onKeyDown={(e) => e.key === "Escape" && setEditing(false)} className="focus-ring h-10 rounded-xl border border-line bg-canvas px-3 text-lg font-semibold" />
            <Button type="submit">Save</Button>
          </form>
        ) : (
          <button onClick={() => setEditing(true)} className="focus-ring group flex items-center gap-2 rounded-lg text-left" title="Rename">
            <h1 className={cn("text-3xl font-semibold tracking-tight sm:text-4xl", !person.name && "text-muted")}>{person.name || "Add a name"}</h1>
            <Pencil className="h-4 w-4 text-muted opacity-60 transition group-hover:opacity-100" />
          </button>
        )}
        <p className="mt-1 text-sm text-muted">{person.photos.length} {person.photos.length === 1 ? "photo" : "photos"}</p>
      </div>
      {person.faces.length > 1 && !wrong && <Button variant="secondary" onClick={() => setWrong(new Set())}><Split className="h-4 w-4" />Not all the same person?</Button>}
    </div>

    {wrong && <section className="panel mb-8 p-4">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm">Pick the faces that are <b>someone else</b>. They'll become a new person.</p>
        <div className="flex gap-2">
          <Button variant="ghost" onClick={() => setWrong(null)}>Cancel</Button>
          <Button onClick={split} disabled={!wrong.size}><Split className="h-4 w-4" />Move {wrong.size || ""}</Button>
        </div>
      </div>
      <div className="flex flex-wrap gap-3">
        {person.faces.map((face) => {
          const picked = wrong.has(face.id);
          return (
            <button key={face.id} onClick={() => setWrong((w) => { const next = new Set(w); if (next.has(face.id)) next.delete(face.id); else next.add(face.id); return next; })}
              className={cn("focus-ring relative rounded-full transition", picked && "scale-95")} aria-pressed={picked}>
              <FaceAvatar src={face.image_url} className={cn("h-20 w-20", picked && "!border-coral opacity-70")} />
              {picked && <span className="absolute inset-0 grid place-items-center"><X className="h-8 w-8 text-coral drop-shadow" strokeWidth={3} /></span>}
            </button>
          );
        })}
      </div>
    </section>}

    <PhotoGrid photos={person.photos} onOpen={setOpenId} />
    {openId && <PhotoViewer id={openId} ids={person.photos.map((p) => p.id)} onClose={() => setOpenId(null)} onDeleted={load} onChanged={load} />}
  </>;
}
