import { useRef, useState, type DragEvent } from "react";
import { Link } from "react-router-dom";
import { CheckCircle2, Cloud, Copy, HardDrive, ImagePlus, LoaderCircle, Sparkles, XCircle } from "lucide-react";
import { Button, PageHeading } from "../components/ui";
import { uploadPhoto } from "../lib/api";
import { useSettings } from "../lib/settings";
import { cn, formatBytes, percent } from "../lib/utils";
import type { UploadResult } from "../types";

interface Item {
  key: string;
  file: File;
  state: "waiting" | "uploading" | "done" | "failed";
  progress: number;
  result?: UploadResult;
  error?: string;
}

function ItemStatus({ item }: { item: Item }) {
  if (item.state === "waiting") return <span className="text-muted">Waiting…</span>;
  if (item.state === "uploading") return <span className="flex items-center gap-1.5 text-muted"><LoaderCircle className="h-4 w-4 animate-spin text-acid" />{item.progress}%</span>;
  if (item.state === "failed") return <span className="flex items-center gap-1.5 text-coral"><XCircle className="h-4 w-4 shrink-0" />{item.error}</span>;
  const match = item.result?.match;
  if (match?.kind === "exact") return <span className="flex items-center gap-1.5 text-coral"><Copy className="h-4 w-4 shrink-0" />Exact copy of “{match.filename}”</span>;
  if (match) return <span className="flex items-center gap-1.5 text-lilac"><Sparkles className="h-4 w-4 shrink-0" />{percent(match.similarity)} similar to “{match.filename}”</span>;
  return <span className="flex items-center gap-1.5 text-acid"><CheckCircle2 className="h-4 w-4 shrink-0" />Saved</span>;
}

export function UploadPage() {
  const { settings } = useSettings();
  const [items, setItems] = useState<Item[]>([]);
  const [busy, setBusy] = useState(false);
  const [dragging, setDragging] = useState(false);
  const input = useRef<HTMLInputElement>(null);

  const update = (key: string, change: Partial<Item>) => setItems((all) => all.map((item) => item.key === key ? { ...item, ...change } : item));

  async function start(files: File[]) {
    if (!files.length || busy) return;
    const added = files.map((file, i) => ({ key: `${Date.now()}-${i}-${file.name}`, file, state: "waiting" as const, progress: 0 }));
    setItems((all) => [...added, ...all]);
    setBusy(true);
    for (const item of added) { // one at a time, so each photo is compared with the ones before it
      update(item.key, { state: "uploading" });
      try {
        const result = await uploadPhoto(item.file, (progress) => update(item.key, { progress }));
        update(item.key, { state: "done", result });
      } catch (e) {
        update(item.key, { state: "failed", error: (e as Error).message });
      }
    }
    setBusy(false);
  }

  function onDrop(event: DragEvent) {
    event.preventDefault();
    setDragging(false);
    start(Array.from(event.dataTransfer.files));
  }

  const done = items.filter((i) => i.state === "done");
  const duplicates = done.filter((i) => i.result?.match).length;
  const azure = settings?.storage === "azure";

  return <>
    <PageHeading title="Upload photos" description="Add JPG, PNG, WEBP, GIF or BMP photos up to 25 MB each. Every photo is checked against your vault for duplicates." />

    <button type="button" onClick={() => input.current?.click()} disabled={busy}
      onDragOver={(e) => { e.preventDefault(); setDragging(true); }} onDragLeave={() => setDragging(false)} onDrop={onDrop}
      className={cn("focus-ring grid w-full place-items-center rounded-3xl border-2 border-dashed px-6 py-16 text-center transition",
        dragging ? "border-acid bg-acid/[.07]" : "border-line bg-panel/60 hover:border-acid/40 hover:bg-panel", busy && "cursor-wait opacity-70")}>
      <div className="grid h-16 w-16 place-items-center rounded-2xl border border-acid/20 bg-acid/10"><ImagePlus className="h-7 w-7 text-acid" /></div>
      <p className="mt-5 text-lg font-semibold">{dragging ? "Drop to upload" : "Drag photos here, or click to choose"}</p>
      {settings && <p className="mt-2 flex items-center gap-1.5 text-sm text-muted">
        {azure ? <Cloud className="h-4 w-4 text-lilac" /> : <HardDrive className="h-4 w-4 text-acid" />}
        Saving to {azure ? `Azure (${settings.azure_account})` : "this computer"}
      </p>}
    </button>
    <input ref={input} type="file" multiple accept="image/jpeg,image/png,image/webp,image/gif,image/bmp" className="hidden"
      onChange={(e) => { start(Array.from(e.target.files ?? [])); e.target.value = ""; }} />

    {items.length > 0 && <div className="mt-8">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-lg font-semibold">{busy ? `Uploading ${done.length + 1} of ${items.length}…` : `${done.length} uploaded${duplicates ? `, ${duplicates} with duplicates` : ""}`}</h2>
        {!busy && <div className="flex gap-2">
          {duplicates > 0 && <Link to="/duplicates"><Button variant="secondary">Review duplicates</Button></Link>}
          <Link to="/photos"><Button variant="secondary">View photos</Button></Link>
        </div>}
      </div>
      <ul className="panel divide-y divide-line">
        {items.map((item) => (
          <li key={item.key} className="relative flex flex-col gap-1 overflow-hidden px-4 py-3 text-sm sm:flex-row sm:items-center sm:justify-between sm:gap-6">
            {item.state === "uploading" && <span className="absolute inset-y-0 left-0 bg-acid/[.06] transition-all" style={{ width: `${item.progress}%` }} />}
            <span className="relative min-w-0 truncate"><span className="font-medium">{item.file.name}</span><span className="ml-2 text-muted">{formatBytes(item.file.size)}</span></span>
            <span className="relative shrink-0 text-right"><ItemStatus item={item} /></span>
          </li>
        ))}
      </ul>
    </div>}
  </>;
}
