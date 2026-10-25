import { useCallback, useEffect, useState } from "react";
import { CheckCircle2, ChevronsLeftRight, Sparkles, Trash2 } from "lucide-react";
import { CompareSlider } from "../components/CompareSlider";
import { PhotoThumb } from "../components/PhotoCard";
import { PhotoViewer } from "../components/PhotoViewer";
import { Button, ConfirmDialog, EmptyState, ErrorNote, MatchBadge, PageHeading, Spinner } from "../components/ui";
import { api } from "../lib/api";
import { cn, formatBytes } from "../lib/utils";
import type { DuplicateGroup, Photo } from "../types";

type Confirm = { kind: "one"; photo: Photo } | { kind: "exact"; count: number };
type GroupItem = DuplicateGroup["items"][number];

function GroupRow({ group, onOpen, onDelete, onCompare }: {
  group: DuplicateGroup; onOpen: (id: string) => void; onDelete: (photo: Photo) => void; onCompare: (first: GroupItem, other: GroupItem) => void;
}) {
  return (
    <section className="pop-in panel p-4">
      <div className="flex gap-3 overflow-x-auto pb-1">
        {group.items.map((item, index) => {
          const { kind, similarity, photo } = item;
          return (
          <div key={photo.id} className={cn("w-44 shrink-0 overflow-hidden rounded-xl border bg-canvas/60 sm:w-52", kind === "keep" ? "border-acid/40" : "border-line")}>
            <button onClick={() => onOpen(photo.id)} className="focus-ring relative block w-full">
              <PhotoThumb photo={photo} className="aspect-[4/3] w-full" />
              <span className="absolute left-2 top-2"><MatchBadge kind={kind} similarity={similarity} /></span>
            </button>
            <div className="p-3">
              <p className="truncate text-sm font-medium" title={photo.filename}>{photo.filename}</p>
              <p className="mt-0.5 text-xs text-muted">{photo.width} × {photo.height} · {formatBytes(photo.size)}</p>
              <div className="-ml-2 mt-1 flex gap-1">
                {index > 0 && <Button variant="ghost" className="h-8 px-2 text-xs hover:text-sky-300" onClick={() => onCompare(group.items[0], item)}><ChevronsLeftRight className="h-3.5 w-3.5" />Compare</Button>}
                <Button variant="ghost" className="h-8 px-2 text-xs hover:text-coral" onClick={() => onDelete(photo)}><Trash2 className="h-3.5 w-3.5" />Delete</Button>
              </div>
            </div>
          </div>
          );
        })}
      </div>
    </section>
  );
}

export function DuplicatesPage() {
  const [groups, setGroups] = useState<DuplicateGroup[] | null>(null);
  const [related, setRelated] = useState<DuplicateGroup[]>([]);
  const [error, setError] = useState("");
  const [confirm, setConfirm] = useState<Confirm | null>(null);
  const [busy, setBusy] = useState(false);
  const [openId, setOpenId] = useState<string | null>(null);
  const [comparing, setComparing] = useState<[GroupItem, GroupItem] | null>(null);
  const compare = (first: GroupItem, other: GroupItem) => setComparing([first, other]);

  const load = useCallback(() => {
    api<DuplicateGroup[]>("/duplicates").then(setGroups).catch((e: Error) => setError(e.message));
    api<DuplicateGroup[]>("/related").then(setRelated).catch(() => {});
  }, []);
  useEffect(load, [load]);

  async function confirmed() {
    if (!confirm) return;
    setBusy(true);
    try {
      if (confirm.kind === "one") await api(`/photos/${confirm.photo.id}`, { method: "DELETE" });
      else await api("/duplicates/remove-exact", { method: "POST" });
      load();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
      setConfirm(null);
    }
  }

  if (!groups && !error) return <Spinner />;
  // Identical photos share a fingerprint, so every repeated fingerprint is one removable copy.
  const exactCount = groups?.reduce((sum, g) => sum + g.items.length - new Set(g.items.map((i) => i.photo.sha256)).size, 0) ?? 0;
  const extraBytes = groups?.reduce((sum, g) => sum + g.extra_bytes, 0) ?? 0;

  return <>
    <PageHeading title="Duplicates"
      description={groups?.length ? <>{groups.length} {groups.length === 1 ? "group" : "groups"} of matching photos. Removing the extra copies would free up to {formatBytes(extraBytes)}. The best copy (highest resolution and quality) is shown first.</> : "Photos that are copies of each other appear here."}
      action={exactCount > 0 && <Button variant="danger" onClick={() => setConfirm({ kind: "exact", count: exactCount })}><Trash2 className="h-4 w-4" />Remove {exactCount} exact {exactCount === 1 ? "copy" : "copies"}</Button>} />

    {error && <div className="mb-6"><ErrorNote message={error} /></div>}
    {groups?.length === 0 && <EmptyState icon={CheckCircle2} title="No duplicates found">Every photo in your vault is unique. New uploads are checked automatically.</EmptyState>}

    <div className="space-y-4">
      {groups?.map((group) => <GroupRow key={group.id} group={group} onOpen={setOpenId} onCompare={compare} onDelete={(photo) => setConfirm({ kind: "one", photo })} />)}
    </div>

    {related.length > 0 && <>
      <div className="mb-4 mt-12">
        <h2 className="flex items-center gap-2 text-xl font-semibold"><Sparkles className="h-5 w-5 text-sky-300" />Same subject, different shot</h2>
        <p className="mt-1 max-w-2xl text-sm leading-6 text-muted">
          The free AI thinks these photos show the same subject or scene, taken at a different moment, angle or in different colours. They are <b className="text-ink">not copies</b>, so nothing here is removed automatically. Keep the ones you like.
        </p>
      </div>
      <div className="space-y-4">
        {related.map((group) => <GroupRow key={group.id} group={group} onOpen={setOpenId} onCompare={compare} onDelete={(photo) => setConfirm({ kind: "one", photo })} />)}
      </div>
    </>}

    {confirm && <ConfirmDialog busy={busy} onCancel={() => setConfirm(null)} onConfirm={confirmed}
      title={confirm.kind === "one" ? "Delete this photo?" : `Remove ${confirm.count} exact ${confirm.count === 1 ? "copy" : "copies"}?`}
      confirmLabel={confirm.kind === "one" ? "Delete photo" : "Remove copies"}
      message={confirm.kind === "one" ? <>“{confirm.photo.filename}” will be removed from ImageVault. This cannot be undone.</> : "For every set of identical photos, the first upload is kept and the other copies are removed. Similar (not identical) photos are never removed automatically."} />}
    {openId && <PhotoViewer id={openId} ids={[...(groups ?? []), ...related].flatMap((g) => g.items.map((i) => i.photo.id))}
      onClose={() => setOpenId(null)} onDeleted={load} />}
    {comparing && <CompareSlider left={comparing[0].photo} right={comparing[1].photo} leftKind={comparing[0].kind}
      kind={comparing[1].kind} similarity={comparing[1].similarity} onClose={() => setComparing(null)} />}
  </>;
}
