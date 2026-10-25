import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Link, useParams } from "react-router-dom";
import { ArrowLeft, Pencil, ShieldCheck, UserRound, Users } from "lucide-react";
import { PhotoGrid } from "../components/PhotoCard";
import { PhotoViewer } from "../components/PhotoViewer";
import { Button, EmptyState, ErrorNote, PageHeading, Spinner } from "../components/ui";
import { api } from "../lib/api";
import type { Person, PersonDetails } from "../types";

export const personName = (person: { name: string | null }) => person.name || "Unnamed person";

export function FaceAvatar({ src, className = "h-28 w-28" }: { src: string | null; className?: string }) {
  return src
    ? <img src={src} alt="" className={`${className} rounded-full border-2 border-line object-cover`} />
    : <div className={`${className} grid place-items-center rounded-full border-2 border-line bg-raised`}><UserRound className="h-1/3 w-1/3 text-muted" /></div>;
}

export function PeoplePage() {
  const [people, setPeople] = useState<Person[] | null>(null);
  const [error, setError] = useState("");
  useEffect(() => { api<Person[]>("/people").then(setPeople).catch((e: Error) => setError(e.message)); }, []);

  return <>
    <PageHeading title="People" description="Faces are recognised by free AI that runs inside ImageVault, so photos are never sent to another company. Anyone who appears in two or more photos is shown here." />
    {error && <ErrorNote message={error} />}
    {!people && !error && <Spinner />}
    {people?.length === 0 && (
      <EmptyState icon={Users} title="No people yet">
        Upload a few photos of the same person (for example, selfies of your team) and they'll appear here once the AI has looked at them, usually within seconds.
      </EmptyState>
    )}
    {people && people.length > 0 && (
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5">
        {people.map((person, i) => (
          <Link key={person.id} to={`/people/${person.id}`} style={{ animationDelay: `${i * 40}ms`, animationFillMode: "backwards" }}
            className="pop-in focus-ring group panel flex flex-col items-center p-5 text-center transition hover:-translate-y-0.5 hover:border-sky-300/40">
            <FaceAvatar src={person.image_url} className="h-24 w-24 transition group-hover:scale-105" />
            <p className={`mt-3 font-semibold ${person.name ? "" : "text-muted"}`}>{personName(person)}</p>
            <p className="text-xs text-muted">{person.photos} photos{!person.name && " · click to name"}</p>
          </Link>
        ))}
      </div>
    )}
    <p className="mt-8 flex items-center gap-2 text-xs text-muted"><ShieldCheck className="h-4 w-4 text-acid" />Face data stays in your own database and is deleted together with the photo.</p>
  </>;
}

export function PersonPage() {
  const { id } = useParams();
  const [person, setPerson] = useState<PersonDetails | null>(null);
  const [error, setError] = useState("");
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState("");
  const [openId, setOpenId] = useState<string | null>(null);

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

  if (error) return <ErrorNote message={error} />;
  if (!person) return <Spinner />;
  return <>
    <Link to="/people" className="focus-ring mb-6 inline-flex items-center gap-1.5 rounded-lg text-sm text-muted hover:text-ink"><ArrowLeft className="h-4 w-4" />All people</Link>
    <div className="mb-8 flex flex-col items-start gap-5 sm:flex-row sm:items-center">
      <FaceAvatar src={person.image_url} />
      <div>
        {editing ? (
          <form onSubmit={save} className="flex flex-wrap gap-2">
            <input autoFocus value={name} onChange={(e) => setName(e.target.value)} maxLength={100} placeholder="Name"
              className="focus-ring h-10 rounded-xl border border-line bg-canvas px-3 text-lg font-semibold" />
            <Button type="submit">Save</Button>
            <Button type="button" variant="ghost" onClick={() => setEditing(false)}>Cancel</Button>
          </form>
        ) : (
          <button onClick={() => setEditing(true)} className="focus-ring group flex items-center gap-2 rounded-lg text-left">
            <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">{personName(person)}</h1>
            <Pencil className="h-4 w-4 text-muted opacity-60 transition group-hover:opacity-100" />
          </button>
        )}
        <p className="mt-1 text-sm text-muted">Appears in {person.photos.length} photos{!person.name && " · click the name to add one"}</p>
      </div>
    </div>
    <PhotoGrid photos={person.photos} onOpen={setOpenId} />
    {openId && <PhotoViewer id={openId} ids={person.photos.map((p) => p.id)} onClose={() => setOpenId(null)} onDeleted={load} />}
  </>;
}
