import { Activity, CheckCircle2, Cpu, Database, ExternalLink, HardDrive, Network, RefreshCw, Server, Sparkles, TriangleAlert } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Button, PageHeading } from "../components/ui";
import { api } from "../lib/api";
import type { ComponentStatus, SystemStatus } from "../types";

function ServiceCard({ name, detail, status, icon: Icon }: { name: string; detail: string | null; status: string; icon: typeof Server }) {
  const healthy = ["healthy", "idle"].includes(status);
  return <div className="panel rounded-2xl p-5"><div className="flex items-start justify-between"><div className={`grid h-10 w-10 place-items-center rounded-xl ${healthy ? "bg-acid/10 text-acid" : "bg-coral/10 text-coral"}`}><Icon className="h-4 w-4" /></div><span className={`rounded-full border px-2.5 py-1 font-mono text-[9px] uppercase ${healthy ? "border-acid/20 bg-acid/10 text-acid" : "border-coral/20 bg-coral/10 text-coral"}`}>{status}</span></div><h3 className="mt-7 font-semibold">{name}</h3><p className="mt-1 text-xs text-muted">{detail ?? "No detail"}</p></div>;
}

export function SystemPage() {
  const [data, setData] = useState<SystemStatus | null>(null);
  const [error, setError] = useState("");
  const [refreshing, setRefreshing] = useState(false);
  const load = useCallback(async () => { setRefreshing(true); try { setData(await api<SystemStatus>("/system/status")); setError(""); } catch (reason) { setError(reason instanceof Error ? reason.message : "Status unavailable"); } finally { setRefreshing(false); } }, []);
  useEffect(() => { void load(); const timer = window.setInterval(() => void load(), 15000); return () => window.clearInterval(timer); }, [load]);
  const services: [string, ComponentStatus, typeof Server][] = data ? [["API", data.api, Network], ["Database", data.database, Database], ["Storage", data.object_storage, HardDrive], ["AI worker", data.worker, Cpu], ["Visual model", data.embedding_model, Sparkles]] : [];
  return <>
    <PageHeading eyebrow="System" title="Service status" action={<Button variant="secondary" loading={refreshing} onClick={load}><RefreshCw className="h-4 w-4" />Refresh</Button>} />
    {error && <div className="mb-5 flex gap-3 rounded-2xl border border-coral/20 bg-coral/10 p-4 text-sm text-orange-100"><TriangleAlert className="h-4 w-4" />{error}</div>}
    {data && <div className="mb-5 flex flex-col justify-between gap-3 rounded-2xl border border-acid/20 bg-acid/[.055] p-5 sm:flex-row sm:items-center"><div className="flex items-center gap-3"><CheckCircle2 className="h-5 w-5 text-acid" /><p className="font-semibold">{data.status}</p></div><div className="flex gap-6 text-sm"><span>{data.pending_jobs} pending</span><span>{data.queue_size ?? 0} queued</span></div></div>}
    {!data ? <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">{Array.from({ length: 5 }, (_, index) => <div className="skeleton h-44 rounded-2xl" key={index} />)}</div> : <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">{services.map(([name, service, Icon]) => <ServiceCard key={name} name={name} detail={service.detail} status={service.status} icon={Icon} />)}</div>}
    <div className="mt-5 flex flex-wrap gap-3"><a href="http://localhost:3001" target="_blank" rel="noreferrer" className="focus-ring flex items-center gap-2 rounded-xl border border-line bg-white/[.025] px-4 py-3 text-sm font-semibold"><Activity className="h-4 w-4 text-acid" />Grafana<ExternalLink className="h-4 w-4 text-muted" /></a><a href="http://localhost:9090" target="_blank" rel="noreferrer" className="focus-ring flex items-center gap-2 rounded-xl border border-line bg-white/[.025] px-4 py-3 text-sm font-semibold"><Activity className="h-4 w-4 text-lilac" />Prometheus<ExternalLink className="h-4 w-4 text-muted" /></a></div>
  </>;
}
