import { useRef, useState, type DragEvent } from "react";
import { Link } from "react-router-dom";
import { CheckCircle2, Cloud, Copy, HardDrive, ImagePlus, LoaderCircle, RotateCcw, Sparkles, XCircle } from "lucide-react";
import { Button, PageHeading } from "../components/ui";
import { useSystem } from "../lib/system";
import { useUploads, type UploadItem } from "../lib/uploads";
import { cn, formatBytes, percent } from "../lib/utils";

function ItemStatus({ item }: { item: UploadItem }) {
  if (item.state === "waiting") return <span className="text-muted">Waiting</span>;
  if (item.state === "uploading") return <span className="flex items-center gap-1.5 text-muted"><LoaderCircle className="h-4 w-4 animate-spin text-acid" />{item.progress}%</span>;
  if (item.state === "failed") return <span className="flex items-center gap-1.5 text-coral"><XCircle className="h-4 w-4 shrink-0" />{item.error}</span>;
  const match = item.result?.match;
  if (match?.kind === "exact") return <span className="flex items-center gap-1.5 text-coral"><Copy className="h-4 w-4 shrink-0" />Copy of “{match.filename}”</span>;
  if (match) return <span className="flex items-center gap-1.5 text-lilac"><Sparkles className="h-4 w-4 shrink-0" />{percent(match.similarity)} like “{match.filename}”</span>;
  return <span className="flex items-center gap-1.5 text-acid"><CheckCircle2 className="h-4 w-4 shrink-0" />Saved</span>;
}

export function UploadPage() {
  const { system, onAzureStorage: azure } = useSystem();
  const { items, busy, add, retryFailed, clearFinished } = useUploads();
  const [dragging, setDragging] = useState(false);
  const input = useRef<HTMLInputElement>(null);

  function onDrop(event: DragEvent) {
    event.preventDefault();
    event.stopPropagation(); // the whole-window drop zone must not add them a second time
    setDragging(false);
    add(Array.from(event.dataTransfer.files));
  }

  const done = items.filter((i) => i.state === "done");
  const failed = items.filter((i) => i.state === "failed").length;
  const duplicates = done.filter((i) => i.result?.match).length;

  return <>
    <PageHeading title="Upload" description="JPG, PNG, WEBP, GIF or BMP, up to 25 MB each. You can also drop photos anywhere on the page." />

    <button type="button" onClick={() => input.current?.click()}
      onDragOver={(e) => { e.preventDefault(); setDragging(true); }} onDragLeave={() => setDragging(false)} onDrop={onDrop}
      className={cn("focus-ring grid w-full place-items-center rounded-3xl border-2 border-dashed px-6 py-16 text-center transition",
        dragging ? "border-acid bg-acid/[.07]" : "border-line bg-panel/60 hover:border-acid/40 hover:bg-panel")}>
      <div className="grid h-16 w-16 place-items-center rounded-2xl border border-acid/20 bg-acid/10"><ImagePlus className="h-7 w-7 text-acid" /></div>
      <p className="mt-5 text-lg font-semibold">{dragging ? "Drop to upload" : "Drag photos here, or click to choose"}</p>
      {system && <p className="mt-2 flex items-center gap-1.5 text-sm text-muted">
        {azure ? <Cloud className="h-4 w-4 text-lilac" /> : <HardDrive className="h-4 w-4 text-acid" />}
        Saved to {azure ? "Azure Blob Storage" : "a local folder"}
      </p>}
    </button>
    <input ref={input} type="file" multiple accept="image/jpeg,image/png,image/webp,image/gif,image/bmp" className="hidden"
      onChange={(e) => { add(Array.from(e.target.files ?? [])); e.target.value = ""; }} />

    {items.length > 0 && <div className="mt-8">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-lg font-semibold">{busy ? `Uploading ${done.length + failed + 1} of ${items.length}` : `${done.length} uploaded${duplicates ? ` · ${duplicates} duplicates` : ""}${failed ? ` · ${failed} failed` : ""}`}</h2>
        <div className="flex flex-wrap gap-2">
          {failed > 0 && !busy && <Button variant="secondary" onClick={retryFailed}><RotateCcw className="h-4 w-4" />Retry failed</Button>}
          {!busy && <Button variant="ghost" onClick={clearFinished}>Clear list</Button>}
          {!busy && duplicates > 0 && <Link to="/duplicates"><Button variant="secondary">Review duplicates</Button></Link>}
          {!busy && <Link to="/photos"><Button variant="secondary">View photos</Button></Link>}
        </div>
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
