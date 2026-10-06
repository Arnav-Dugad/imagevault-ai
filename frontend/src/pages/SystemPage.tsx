import { Activity, CheckCircle2, Cpu, Database, Download, ExternalLink, HardDrive, Network, RefreshCw, Server, Sparkles, TriangleAlert } from "lucide-react";
import { motion, useReducedMotion } from "framer-motion";
import { useCallback, useEffect, useRef, useState } from "react";
import { Button, PageHeading } from "../components/ui";
import { api } from "../lib/api";
import { formatBytes } from "../lib/utils";
import type { ComponentStatus, SystemStatus } from "../types";

function ServiceCard({ name, detail, status, icon: Icon }: { name: string; detail: string | null; status: string; icon: typeof Server }) {
  const healthy = ["healthy", "idle"].includes(status);
  const reducedMotion = useReducedMotion();
  return <motion.div initial={reducedMotion ? false : { opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} whileHover={reducedMotion ? undefined : { y: -4 }} className="panel premium-card rounded-2xl p-5">
    <div className="flex items-start justify-between">
      <div className={`grid h-10 w-10 place-items-center rounded-xl ${healthy ? "bg-acid/10 text-acid" : "bg-coral/10 text-coral"}`}><Icon className="h-4 w-4" /></div>
      <span className={`rounded-full border px-2.5 py-1 font-mono text-[9px] uppercase ${healthy ? "border-acid/20 bg-acid/10 text-acid" : "border-coral/20 bg-coral/10 text-coral"}`}>{status}</span>
    </div>
    <h3 className="mt-7 font-semibold">{name}</h3><p className="mt-1 text-xs text-muted">{detail ?? "No detail"}</p>
  </motion.div>;
}

function isWebUrl(value: string | null): value is string {
  if (!value) return false;
  try { return ["http:", "https:"].includes(new URL(value).protocol); } catch { return false; }
}

export function SystemPage() {
  const [data, setData] = useState<SystemStatus | null>(null);
  const [error, setError] = useState("");
  const [refreshing, setRefreshing] = useState(false);
  const request = useRef<AbortController | null>(null);
  const load = useCallback(async () => {
    if (request.current && !request.current.signal.aborted) return;
    const controller = new AbortController();
    request.current = controller;
    setRefreshing(true);
    try { setData(await api<SystemStatus>("/system/status", { signal: controller.signal })); setError(""); }
    catch (reason) { if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : "Status unavailable"); }
    finally { if (!controller.signal.aborted) setRefreshing(false); if (request.current === controller) request.current = null; }
  }, []);
  useEffect(() => {
    void load();
    const timer = window.setInterval(() => { if (!document.hidden) void load(); }, 15000);
    return () => { window.clearInterval(timer); request.current?.abort(); };
  }, [load]);
  const services: [string, ComponentStatus, typeof Server][] = data ? [["API", data.api, Network], ["Database", data.database, Database], ["Storage", data.object_storage, HardDrive], ["AI worker", data.worker, Cpu], ["Visual model", data.embedding_model, Sparkles]] : [];
  const monitoring = data ? [{ name: "Grafana", url: data.grafana_url }, { name: "Prometheus", url: data.prometheus_url }].filter((item) => isWebUrl(item.url)) : [];
  const healthy = data?.status === "healthy";
  return <>
    <PageHeading eyebrow="System" title="Service status" action={<Button variant="secondary" loading={refreshing} onClick={() => void load()}><RefreshCw className="h-4 w-4" />Refresh</Button>} />
    {error && <div role="alert" className="mb-5 flex gap-3 rounded-2xl border border-coral/20 bg-coral/10 p-4 text-sm text-orange-100"><TriangleAlert className="h-4 w-4 shrink-0" />{error}</div>}
    {data && <div className={`mb-5 flex flex-col justify-between gap-3 rounded-2xl border p-5 sm:flex-row sm:items-center ${healthy ? "border-acid/20 bg-acid/[.055]" : "border-coral/20 bg-coral/10"}`}>
      <div className="flex items-center gap-3">{healthy ? <CheckCircle2 className="h-5 w-5 text-acid" /> : <TriangleAlert className="h-5 w-5 text-coral" />}<p className="font-semibold">{healthy ? "All services ready" : "Some services need attention"}</p></div>
      <div className="flex gap-6 text-sm"><span>{data.pending_jobs} pending</span><span>{data.queue_size ?? "—"} queued</span></div>
    </div>}
    {!data && !error ? <div aria-label="Loading service status" className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">{Array.from({ length: 5 }, (_, index) => <div className="skeleton h-44 rounded-2xl" key={index} />)}</div> : <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">{services.map(([name, service, Icon]) => <ServiceCard key={name} name={name} detail={service.detail} status={service.status} icon={Icon} />)}</div>}
    {data && <section className="panel mt-5 rounded-2xl p-5"><p className="eyebrow mb-4">Your deployment</p><dl className="grid gap-4 text-sm sm:grid-cols-2 xl:grid-cols-4">
      <div><dt className="text-muted">Storage</dt><dd className="mt-1 font-semibold">{data.storage_backend === "azure" ? "Azure Blob Storage" : "Private MinIO"}</dd></div>
      <div><dt className="text-muted">Environment</dt><dd className="mt-1 font-semibold">{data.environment}</dd></div>
      <div><dt className="text-muted">Version</dt><dd className="mt-1 font-mono">{data.version}</dd></div>
      <div><dt className="text-muted">Original-file limit per account</dt><dd className="mt-1 font-semibold">{data.max_user_storage_bytes ? formatBytes(data.max_user_storage_bytes) : "No configured limit"}</dd></div>
    </dl>{data.storage_backend === "azure" && <p className="mt-5 text-xs text-muted">AI runs privately on this server. Azure compute, storage, and network usage consume your subscription credit.</p>}</section>}
    {monitoring.length > 0 && <section className="mt-5"><p className="eyebrow mb-3">Monitoring</p><div className="grid gap-3 md:grid-cols-2">{monitoring.map(({ name, url }) => <a key={name} href={url!} target="_blank" rel="noreferrer" className="panel premium-card focus-ring flex items-center justify-between rounded-2xl p-4"><span className="flex items-center gap-3"><Activity className="h-4 w-4 text-acid" /><span className="text-sm font-semibold">{name}</span></span><ExternalLink className="h-4 w-4 text-muted" /></a>)}</div></section>}
    <a href="https://github.com/Arnav-Dugad/imagevault-ai/releases/latest" target="_blank" rel="noreferrer" className="panel focus-ring mt-5 flex items-center justify-between gap-4 rounded-2xl p-5"><span className="flex items-center gap-3"><Download className="h-4 w-4 text-acid" /><span><span className="block text-sm font-semibold">Download ImageVault</span><span className="mt-1 block text-xs text-muted">Installation bundles, checksums, and release notes on GitHub</span></span></span><ExternalLink className="h-4 w-4 shrink-0 text-muted" /></a>
  </>;
}
