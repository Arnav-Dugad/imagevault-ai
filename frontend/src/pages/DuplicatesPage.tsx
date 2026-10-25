import { useCallback, useEffect, useState } from "react";
import { CheckCircle2, ChevronsLeftRight, Focus, Sparkles, Timer, Trash2 } from "lucide-react";
import { CompareSlider } from "../components/CompareSlider";
import { PhotoThumb } from "../components/PhotoCard";
import { PhotoViewer } from "../components/PhotoViewer";
import { Button, ConfirmDialog, EmptyState, ErrorNote, MatchBadge, PageHeading, Spinner } from "../components/ui";
import { api } from "../lib/api";
import { useToast } from "../lib/toast";
import { cn, formatBytes } from "../lib/utils";
import type { DuplicateGroup, Photo } from "../types";

type Confirm =
  | { kind: "one"; photo: Photo }
  | { kind: "exact"; count: number }
  | { kind: "burst"; keep: Photo; remove: Photo[] };
type GroupItem = DuplicateGroup["items"][number];

function GroupRow({ group, onOpen, onDelete, onCompare, action }: {
  group: DuplicateGroup; onOpen: (id: string) => void; onDelete: (photo: Photo) => void;
  onCompare: (first: GroupItem, other: GroupItem) => void; action?: React.ReactNode;
}) {
  return (
    <section className="pop-in panel p-4">
      {action && <div className="mb-3 flex justify-end">{action}</div>}
      <div className="flex gap-3 overflow-x-auto pb-1">
        {group.items.map((item, index) => {
          const { kind, similarity, photo } = item;
          const sharpest = photo.id === group.sharpest_id;
          return (
            <div key={photo.id} className={cn("w-44 shrink-0 overflow-hidden rounded-xl border bg-canvas/60 sm:w-52", kind === "keep" || sharpest ? "border-acid/40" : "border-line")}>
              <button onClick={() => onOpen(photo.id)} className="focus-ring relative block w-full">
                <PhotoThumb photo={photo} className="aspect-[4/3] w-full" />
                <span className="absolute left-2 top-2 flex flex-wrap gap-1">
                  {kind !== "burst" && <MatchBadge kind={kind} similarity={similarity} />}
                  {sharpest && kind !== "keep" && <MatchBadge kind="sharpest" />}
                </span>
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

function Section({ icon: Icon, title, hint, children }: { icon: typeof Sparkles; title: string; hint: string; children: React.ReactNode }) {
  return <>
    <div className="mb-4 mt-12">
      <h2 className="flex items-center gap-2 text-xl font-semibold"><Icon className="h-5 w-5 text-sky-300" />{title}</h2>
      <p className="mt-1 text-sm text-muted">{hint}</p>
    </div>
    <div className="space-y-4">{children}</div>
  </>;
}

export function DuplicatesPage() {
  const toast = useToast();
  const [groups, setGroups] = useState<DuplicateGroup[] | null>(null);
  const [related, setRelated] = useState<DuplicateGroup[]>([]);
  const [bursts, setBursts] = useState<DuplicateGroup[]>([]);
  const [error, setError] = useState("");
  const [confirm, setConfirm] = useState<Confirm | null>(null);
  const [busy, setBusy] = useState(false);
  const [openId, setOpenId] = useState<string | null>(null);
  const [comparing, setComparing] = useState<[GroupItem, GroupItem] | null>(null);
  const compare = (first: GroupItem, other: GroupItem) => setComparing([first, other]);

  const load = useCallback(() => {
    api<DuplicateGroup[]>("/duplicates").then(setGroups).catch((e: Error) => setError(e.message));
    api<DuplicateGroup[]>("/related").then(setRelated).catch(() => {});
    api<DuplicateGroup[]>("/bursts").then(setBursts).catch(() => {});
  }, []);
  useEffect(load, [load]);

  async function confirmed() {
    if (!confirm) return;
    setBusy(true);
    try {
      if (confirm.kind === "one") {
        await api(`/photos/${confirm.photo.id}`, { method: "DELETE" });
        toast("Photo deleted");
      } else if (confirm.kind === "exact") {
        const { removed } = await api<{ removed: number }>("/duplicates/remove-exact", { method: "POST" });
        toast(`${removed} exact ${removed === 1 ? "copy" : "copies"} removed`);
      } else {
        await api("/photos/batch", { method: "POST", body: JSON.stringify({ ids: confirm.remove.map((p) => p.id), action: "delete" }) });
        toast(`Kept the sharpest, deleted ${confirm.remove.length}`);
      }
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
  const row = (group: DuplicateGroup, action?: React.ReactNode) =>
    <GroupRow key={group.id} group={group} onOpen={setOpenId} onCompare={compare} onDelete={(photo) => setConfirm({ kind: "one", photo })} action={action} />;
  const nothing = groups?.length === 0 && related.length === 0 && bursts.length === 0;

  return <>
    <PageHeading title="Duplicates"
      description={groups?.length ? `${groups.length} ${groups.length === 1 ? "group" : "groups"} · up to ${formatBytes(extraBytes)} to free` : undefined}
      action={exactCount > 0 && <Button variant="danger" onClick={() => setConfirm({ kind: "exact", count: exactCount })}><Trash2 className="h-4 w-4" />Remove {exactCount} exact {exactCount === 1 ? "copy" : "copies"}</Button>} />

    {error && <div className="mb-6"><ErrorNote message={error} /></div>}
    {nothing && <EmptyState icon={CheckCircle2} title="No duplicates">New uploads are checked automatically.</EmptyState>}

    <div className="space-y-4">{groups?.map((group) => row(group))}</div>

    {bursts.length > 0 && <Section icon={Timer} title="Bursts" hint="Taken seconds apart. The sharpest one is first.">
      {bursts.map((group) => row(group,
        <Button variant="secondary" className="h-9" onClick={() => setConfirm({ kind: "burst", keep: group.items[0].photo, remove: group.items.slice(1).map((i) => i.photo) })}>
          <Focus className="h-4 w-4" />Keep sharpest, delete {group.items.length - 1}
        </Button>))}
    </Section>}

    {related.length > 0 && <Section icon={Sparkles} title="Same subject, different shot" hint="Not copies, so nothing here is removed automatically.">
      {related.map((group) => row(group))}
    </Section>}

    {confirm && <ConfirmDialog busy={busy} onCancel={() => setConfirm(null)} onConfirm={confirmed}
      title={confirm.kind === "one" ? "Delete this photo?" : confirm.kind === "exact" ? `Remove ${confirm.count} exact ${confirm.count === 1 ? "copy" : "copies"}?` : `Delete ${confirm.remove.length} blurrier ${confirm.remove.length === 1 ? "shot" : "shots"}?`}
      confirmLabel={confirm.kind === "one" ? "Delete" : confirm.kind === "exact" ? "Remove copies" : "Delete"}
      message={confirm.kind === "one" ? <>“{confirm.photo.filename}” will be deleted. This can't be undone.</>
        : confirm.kind === "exact" ? "The first upload of each photo is kept. Similar photos are never removed automatically."
        : <>“{confirm.keep.filename}” is kept. This can't be undone.</>} />}
    {openId && <PhotoViewer id={openId} ids={[...(groups ?? []), ...bursts, ...related].flatMap((g) => g.items.map((i) => i.photo.id))}
      onClose={() => setOpenId(null)} onDeleted={load} onChanged={load} />}
    {comparing && <CompareSlider left={comparing[0].photo} right={comparing[1].photo} leftKind={comparing[0].kind}
      kind={comparing[1].kind} similarity={comparing[1].similarity} onClose={() => setComparing(null)} />}
  </>;
}
