import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowRight, Cloud, Copy, Download, HardDrive, Images, Search, Sparkles, Upload, Users, type LucideIcon } from "lucide-react";
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

  const uploadButton = <Link to="/upload"><Button><Upload className="h-4 w-4" />Upload photos</Button></Link>;
  if (stats.photos === 0) {
    return <>
      <PageHeading title="Welcome to ImageVault" description="Keep your photos in one place and let ImageVault spot exact copies and look-alike photos for you." />
      <EmptyState icon={Images} title="Your vault is empty">
        <p>Upload a few photos to get started. Want to see duplicate detection straight away? Download the demo photos, unzip them and upload them all: they include exact copies, resized, compressed and edited versions, and look-alikes that are <i>not</i> duplicates.</p>
        <div className="mt-6 flex flex-wrap justify-center gap-2">
          {uploadButton}
          <a href="/demo-photos.zip" download><Button variant="secondary"><Download className="h-4 w-4" />Demo photos (5 MB)</Button></a>
        </div>
      </EmptyState>
    </>;
  }

  const duplicates = stats.exact_copies + stats.similar_pairs;
  return <>
    <PageHeading title="Home" description="An overview of your photo vault." action={uploadButton} />
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
      <StatCard index={0} icon={Images} label="Photos" value={stats.photos.toLocaleString()} note={`${formatBytes(stats.total_bytes)} in total`} />
      <StatCard index={1} icon={stats.storage === "azure" ? Cloud : HardDrive} label="Storage used" value={formatBytes(stats.stored_bytes)} note={stats.storage === "azure" ? "In Azure Blob Storage" : "In a local folder"} />
      <StatCard index={2} icon={Copy} label="Exact copies" value={stats.exact_copies.toLocaleString()} note={stats.saved_bytes > 0 ? `${formatBytes(stats.saved_bytes)} saved by storing them once` : "Identical files are stored once"} />
      <StatCard index={3} icon={Sparkles} label="Similar pairs" value={stats.similar_pairs.toLocaleString()} note="Resized, compressed or edited" />
    </div>

    {stats.ai.enabled && (
      <div className="mt-4 flex flex-col gap-3 rounded-2xl border border-sky-300/25 bg-sky-300/[.05] p-5 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-start gap-3">
          <Sparkles className={cn("mt-0.5 h-5 w-5 shrink-0 text-sky-300", stats.ai.waiting > 0 && "animate-pulse")} />
          <div>
            <p className="font-semibold">
              {stats.ai.waiting > 0 ? `The free AI is looking at ${stats.ai.waiting} ${stats.ai.waiting === 1 ? "photo" : "photos"}…`
                : !stats.ai.ready ? "The free AI is getting ready" : "Free AI recognition is on"}
            </p>
            <p className="mt-1 text-sm text-muted">
              {stats.ai.ready ? `${stats.ai.analysed} photos analysed · ${stats.people} ${stats.people === 1 ? "person" : "people"} recognised`
                : stats.ai.message}
            </p>
          </div>
        </div>
        {stats.ai.ready && <div className="flex gap-2">
          <Link to="/people"><Button variant="secondary"><Users className="h-4 w-4" />People</Button></Link>
          <Link to="/photos"><Button variant="secondary"><Search className="h-4 w-4" />Smart search</Button></Link>
        </div>}
      </div>
    )}
    {duplicates > 0 && (
      <Link to="/duplicates" className="focus-ring group mt-4 flex items-center justify-between gap-4 rounded-2xl border border-coral/25 bg-coral/[.07] p-5 transition hover:bg-coral/10">
        <div><p className="font-semibold">You have duplicates to review</p><p className="mt-1 text-sm text-muted">Compare them side by side and delete the copies you don't need.</p></div>
        <ArrowRight className="h-5 w-5 shrink-0 text-coral transition group-hover:translate-x-1" />
      </Link>
    )}
    <Link to="/cloud" className="focus-ring group mt-4 flex items-center justify-between gap-4 rounded-2xl border border-lilac/25 bg-lilac/[.06] p-5 transition hover:bg-lilac/10">
      <div><p className="font-semibold">See the cloud behind ImageVault</p><p className="mt-1 text-sm text-muted">Live status of App Service, PostgreSQL, Blob Storage and Application Insights.</p></div>
      <ArrowRight className="h-5 w-5 shrink-0 text-lilac transition group-hover:translate-x-1" />
    </Link>

    <div className="mb-4 mt-10 flex items-center justify-between">
      <h2 className="text-lg font-semibold">Recently added</h2>
      <Link to="/photos" className="focus-ring rounded-lg text-sm text-muted hover:text-ink">See all photos →</Link>
    </div>
    <PhotoGrid photos={stats.recent} onOpen={setOpenId} />
    {openId && <PhotoViewer id={openId} ids={stats.recent.map((p) => p.id)} onClose={() => setOpenId(null)} onDeleted={load} />}
  </>;
}
