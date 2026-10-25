import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowRight, Cloud, Copy, Download, FolderOpen, HardDrive, Images, Sparkles, Upload, Users, type LucideIcon } from "lucide-react";
import { PhotoGrid } from "../components/PhotoCard";
import { PhotoViewer } from "../components/PhotoViewer";
import { Button, EmptyState, ErrorNote, PageHeading, Spinner } from "../components/ui";
import { api } from "../lib/api";
import { cn, formatBytes } from "../lib/utils";
import type { Stats } from "../types";

function StatCard({ icon: Icon, label, value, note, index }: { icon: LucideIcon; label: string; value: string; note: string; index: number }) {
  return (
    <div className="pop-in panel p-5" style={{ animationDelay: `${index * 60}ms`, animationFillMode: "backwards" }}>
      <div className="flex items-center gap-2 text-sm text-muted"><Icon className="h-4 w-4 text-acid" />{label}</div>
      <p className="mt-3 text-3xl font-semibold tracking-tight">{value}</p>
      <p className="mt-1 text-xs text-muted">{note}</p>
    </div>
  );
}

export function HomePage() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [error, setError] = useState("");
  const [openId, setOpenId] = useState<string | null>(null);
  const load = useCallback(() => { api<Stats>("/stats").then(setStats).catch((e: Error) => setError(e.message)); }, []);
  useEffect(load, [load]);
  // While the AI is still working, refresh every few seconds so new results appear on their own.
  const working = stats?.ai.enabled && (stats.ai.waiting > 0 || !stats.ai.ready);
  useEffect(() => {
    if (!working) return;
    const timer = setInterval(load, 3000);
    return () => clearInterval(timer);
  }, [working, load]);

  if (error) return <ErrorNote message={error} />;
  if (!stats) return <Spinner />;

  const uploadButton = <Link to="/upload"><Button><Upload className="h-4 w-4" />Upload</Button></Link>;
  if (stats.photos === 0) {
    return <>
      <PageHeading title="Welcome" />
      <EmptyState icon={Images} title="No photos yet">
        <p>Upload some photos, or try the demo set.</p>
        <div className="mt-6 flex flex-wrap justify-center gap-2">
          {uploadButton}
          <a href="/demo-photos.zip" download><Button variant="secondary"><Download className="h-4 w-4" />Demo photos</Button></a>
        </div>
      </EmptyState>
    </>;
  }

  const duplicates = stats.exact_copies + stats.similar_pairs;
  const shortcut = "focus-ring group flex items-center justify-between gap-3 rounded-2xl border p-4 transition";
  return <>
    <PageHeading title="Home" action={uploadButton} />
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
      <StatCard index={0} icon={Images} label="Photos" value={stats.photos.toLocaleString()} note={formatBytes(stats.total_bytes)} />
      <StatCard index={1} icon={stats.storage === "azure" ? Cloud : HardDrive} label="Storage used" value={formatBytes(stats.stored_bytes)} note={stats.storage === "azure" ? "Azure Blob Storage" : "Local folder"} />
      <StatCard index={2} icon={Copy} label="Exact copies" value={stats.exact_copies.toLocaleString()} note={stats.saved_bytes > 0 ? `${formatBytes(stats.saved_bytes)} saved` : "Stored once"} />
      <StatCard index={3} icon={Sparkles} label="Similar" value={stats.similar_pairs.toLocaleString()} note="Resized or edited" />
    </div>

    {stats.ai.enabled && (stats.ai.waiting > 0 || !stats.ai.ready) && (
      <p className="mt-4 flex items-center gap-2 rounded-xl border border-sky-300/25 bg-sky-300/[.05] px-4 py-3 text-sm">
        <Sparkles className="h-4 w-4 shrink-0 animate-pulse text-sky-300" />
        {stats.ai.waiting > 0 ? `Analysing ${stats.ai.waiting} ${stats.ai.waiting === 1 ? "photo" : "photos"}…` : stats.ai.message}
      </p>
    )}

    <div className="mt-4 grid gap-3 sm:grid-cols-3">
      <Link to="/duplicates" className={cn(shortcut, duplicates ? "border-coral/30 bg-coral/[.06] hover:bg-coral/10" : "border-line bg-panel hover:border-acid/30")}>
        <span className="flex items-center gap-2 font-medium"><Copy className={cn("h-4 w-4", duplicates ? "text-coral" : "text-muted")} />{duplicates ? `${duplicates} to review` : "No duplicates"}</span>
        <ArrowRight className="h-4 w-4 text-muted transition group-hover:translate-x-1" />
      </Link>
      <Link to="/people" className={cn(shortcut, "border-line bg-panel hover:border-sky-300/40")}>
        <span className="flex items-center gap-2 font-medium"><Users className="h-4 w-4 text-sky-300" />{stats.people} {stats.people === 1 ? "person" : "people"}</span>
        <ArrowRight className="h-4 w-4 text-muted transition group-hover:translate-x-1" />
      </Link>
      <Link to="/albums" className={cn(shortcut, "border-line bg-panel hover:border-acid/30")}>
        <span className="flex items-center gap-2 font-medium"><FolderOpen className="h-4 w-4 text-acid" />Albums</span>
        <ArrowRight className="h-4 w-4 text-muted transition group-hover:translate-x-1" />
      </Link>
    </div>

    <div className="mb-4 mt-10 flex items-center justify-between">
      <h2 className="text-lg font-semibold">Recent</h2>
      <Link to="/photos" className="focus-ring rounded-lg text-sm text-muted hover:text-ink">All photos →</Link>
    </div>
    <PhotoGrid photos={stats.recent} onOpen={setOpenId} />
    {openId && <PhotoViewer id={openId} ids={stats.recent.map((p) => p.id)} onClose={() => setOpenId(null)} onDeleted={load} onChanged={load} />}
  </>;
}
