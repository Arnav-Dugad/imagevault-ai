import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowRight, Cloud, Copy, HardDrive, Images, Sparkles, Upload, type LucideIcon } from "lucide-react";
import { PhotoGrid } from "../components/PhotoCard";
import { PhotoViewer } from "../components/PhotoViewer";
import { Button, EmptyState, ErrorNote, PageHeading, Spinner } from "../components/ui";
import { api } from "../lib/api";
import { formatBytes } from "../lib/utils";
import type { Stats } from "../types";

const RELEASES_URL = "https://github.com/Arnav-Dugad/imagevault-ai/releases/latest";

function StatCard({ icon: Icon, label, value, note }: { icon: LucideIcon; label: string; value: string; note: string }) {
  return (
    <div className="panel p-5">
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

  if (error) return <ErrorNote message={error} />;
  if (!stats) return <Spinner />;

  const uploadButton = <Link to="/upload"><Button><Upload className="h-4 w-4" />Upload photos</Button></Link>;
  if (stats.photos === 0) {
    return <>
      <PageHeading title="Welcome to ImageVault" description="Keep your photos in one place and let ImageVault spot exact copies and look-alike photos for you." />
      <EmptyState icon={Images} title="Your vault is empty">
        <p>Upload a few photos to get started. Want to try it first? Download <a className="text-acid hover:underline" href={RELEASES_URL} target="_blank" rel="noreferrer">demo-photos.zip</a>: it includes an exact copy, a resized copy and a compressed copy of the same picture.</p>
        <div className="mt-6">{uploadButton}</div>
      </EmptyState>
    </>;
  }

  const duplicates = stats.exact_copies + stats.similar_pairs;
  return <>
    <PageHeading title="Home" description="An overview of your photo vault." action={uploadButton} />
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
      <StatCard icon={Images} label="Photos" value={stats.photos.toLocaleString()} note={`${formatBytes(stats.total_bytes)} in total`} />
      <StatCard icon={stats.storage === "azure" ? Cloud : HardDrive} label="Space used" value={formatBytes(stats.stored_bytes)} note={stats.storage === "azure" ? "New photos go to Azure" : "On this computer"} />
      <StatCard icon={Copy} label="Exact copies" value={stats.exact_copies.toLocaleString()} note={stats.saved_bytes > 0 ? `${formatBytes(stats.saved_bytes)} saved by storing them once` : "Same file uploaded more than once"} />
      <StatCard icon={Sparkles} label="Similar pairs" value={stats.similar_pairs.toLocaleString()} note="Resized, compressed or edited" />
    </div>

    {duplicates > 0 && (
      <Link to="/duplicates" className="focus-ring group mt-4 flex items-center justify-between gap-4 rounded-2xl border border-coral/25 bg-coral/[.07] p-5 transition hover:bg-coral/10">
        <div><p className="font-semibold">You have duplicates to review</p><p className="mt-1 text-sm text-muted">Compare them side by side and delete the copies you don't need.</p></div>
        <ArrowRight className="h-5 w-5 shrink-0 text-coral transition group-hover:translate-x-1" />
      </Link>
    )}
    {stats.storage === "local" && (
      <Link to="/settings" className="focus-ring group mt-4 flex items-center justify-between gap-4 rounded-2xl border border-lilac/25 bg-lilac/[.06] p-5 transition hover:bg-lilac/10">
        <div><p className="font-semibold">Back up to the cloud</p><p className="mt-1 text-sm text-muted">Connect an Azure Storage account so new photos are stored in Microsoft Azure.</p></div>
        <ArrowRight className="h-5 w-5 shrink-0 text-lilac transition group-hover:translate-x-1" />
      </Link>
    )}

    <div className="mb-4 mt-10 flex items-center justify-between">
      <h2 className="text-lg font-semibold">Recently added</h2>
      <Link to="/photos" className="focus-ring rounded-lg text-sm text-muted hover:text-ink">See all photos →</Link>
    </div>
    <PhotoGrid photos={stats.recent} onOpen={setOpenId} />
    {openId && <PhotoViewer id={openId} onClose={() => setOpenId(null)} onDeleted={load} />}
  </>;
}
