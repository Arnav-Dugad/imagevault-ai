import { BrainCircuit, KeyRound, LockKeyhole, RefreshCw, ScanFace, ScanText } from "lucide-react";
import { useState } from "react";
import { Button, PageHeading } from "../components/ui";
import { api } from "../lib/api";
import { useAuth } from "../providers/AuthProvider";

export function SettingsPage() {
  const { user } = useAuth();
  const [reindexing, setReindexing] = useState(false);
  const [reindexMessage, setReindexMessage] = useState("");
  const initials = user?.display_name.split(" ").map((part) => part[0]).join("").slice(0, 2).toUpperCase();
  const features = [
    [BrainCircuit, "Smart search", "Enabled"],
    [ScanText, "Text recognition", "Enabled"],
    [ScanFace, "Private face matching", "Enabled"],
    [LockKeyhole, "Private storage", "Enabled"],
    [KeyRound, "Signed previews", "Enabled"],
  ] as const;
  async function reindex() {
    setReindexing(true);
    setReindexMessage("");
    try {
      const result = await api<{ queued: number; message: string }>("/images/reindex?missing_only=true", { method: "POST" });
      setReindexMessage(result.message);
    } catch (reason) {
      setReindexMessage(reason instanceof Error ? reason.message : "Could not refresh the library");
    } finally {
      setReindexing(false);
    }
  }
  return <>
    <PageHeading eyebrow="Settings" title="Account and privacy" />
    <div className="grid gap-5 lg:grid-cols-[.8fr_1.2fr]">
      <section className="panel rounded-[28px] p-6"><p className="eyebrow">Account</p><div className="mt-6 flex items-center gap-4"><div className="grid h-14 w-14 place-items-center rounded-full bg-lilac/15 font-semibold text-lilac">{initials}</div><div className="min-w-0"><p className="truncate font-semibold">{user?.display_name}</p><p className="truncate text-sm text-muted">{user?.email}</p></div></div></section>
      <section className="panel rounded-[28px] p-6"><p className="eyebrow">Features</p><div className="mt-6 grid gap-3 sm:grid-cols-2">{features.map(([Icon, label, value]) => <div key={label} className="group flex items-center justify-between rounded-xl border border-line bg-white/[.02] p-4 transition hover:-translate-y-0.5 hover:border-white/15"><span className="flex items-center gap-3 text-sm"><Icon className="h-4 w-4 text-acid transition group-hover:scale-110" />{label}</span><span className="font-mono text-[9px] uppercase text-acid">{value}</span></div>)}</div></section>
      <section className="panel rounded-[28px] p-6 lg:col-span-2"><div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center"><div><p className="eyebrow">AI accuracy</p><h2 className="mt-3 font-semibold">Refresh smart analysis</h2><p className="mt-1 text-sm text-muted">Applies the newest face, quality, and tagging engine to older photos.</p></div><Button variant="secondary" loading={reindexing} onClick={reindex}><RefreshCw className="h-4 w-4" />Re-analyze library</Button></div>{reindexMessage && <p role="status" className="mt-4 rounded-xl border border-acid/20 bg-acid/[.055] p-3 text-sm text-acid">{reindexMessage}</p>}</section>
    </div>
  </>;
}
