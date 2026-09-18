import { motion } from "framer-motion";
import { ArrowRight, CheckCircle2, CircleAlert, CloudUpload, Copy, HardDrive, Images, ScanSearch, Sparkles } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Button, EmptyState, PageHeading } from "../components/ui";
import { api } from "../lib/api";
import { formatBytes } from "../lib/utils";
import { useAuth } from "../providers/AuthProvider";
import type { DashboardData, SystemStatus } from "../types";

function MetricCard({ label, value, detail, icon: Icon, tone = "acid" }: { label: string; value: string; detail: string; icon: typeof Images; tone?: "acid" | "lilac" | "coral" }) {
  const colors = { acid: "text-acid bg-acid/10", lilac: "text-lilac bg-lilac/10", coral: "text-coral bg-coral/10" };
  return <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="panel rounded-2xl p-5"><div className="flex items-start justify-between"><p className="eyebrow">{label}</p><div className={`grid h-9 w-9 place-items-center rounded-xl ${colors[tone]}`}><Icon className="h-4 w-4" /></div></div><p className="mt-7 text-3xl font-semibold tracking-[-.045em]">{value}</p><p className="mt-2 text-xs text-muted">{detail}</p></motion.div>;
}

export function DashboardPage() {
  const { user } = useAuth();
  const [data, setData] = useState<DashboardData | null>(null);
  const [error, setError] = useState("");
  const [system, setSystem] = useState<SystemStatus | null>(null);
  useEffect(() => {
    let active = true;
    const refresh = () => api<SystemStatus>("/system/status").then((value) => { if (active) setSystem(value); }).catch(() => { if (active) setSystem(null); });
    void refresh();
    const timer = window.setInterval(() => void refresh(), 30000);
    return () => { active = false; window.clearInterval(timer); };
  }, []);
  useEffect(() => { api<DashboardData>("/dashboard").then(setData).catch((reason: Error) => setError(reason.message)); }, []);
  const greeting = new Date().getHours() < 12 ? "Good morning" : new Date().getHours() < 18 ? "Good afternoon" : "Good evening";
  if (error) return <EmptyState icon={HardDrive} title="Dashboard unavailable" description={error} />;
  if (!data) return <div className="space-y-6"><div className="skeleton h-24 max-w-xl rounded-2xl" /><div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">{Array.from({ length: 4 }, (_, i) => <div key={i} className="skeleton h-44 rounded-2xl" />)}</div></div>;
  return <>
    <PageHeading eyebrow={`${greeting}, ${user?.display_name.split(" ")[0]}`} title="Overview" action={<Link to="/upload"><Button><CloudUpload className="h-4 w-4" />Upload images</Button></Link>} />
    {data.total_images === 0 ? <EmptyState icon={Sparkles} title="No images yet" description="Upload your first images." action={<Link to="/upload"><Button>Upload images<ArrowRight className="h-4 w-4" /></Button></Link>} /> : <>
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4"><MetricCard label="Total images" value={data.total_images.toLocaleString()} detail={`${data.unique_images.toLocaleString()} unique assets`} icon={Images} /><MetricCard label="Storage used" value={formatBytes(data.storage_used)} detail="Private original files" icon={HardDrive} tone="lilac" /><MetricCard label="Exact duplicates" value={data.exact_duplicates.toLocaleString()} detail={`${formatBytes(data.potential_savings)} recoverable`} icon={Copy} tone="coral" /><MetricCard label="Visual matches" value={data.similar_images.toLocaleString()} detail="Advisory AI suggestions" icon={ScanSearch} /></div>
      <div className="mt-4 grid gap-4 xl:grid-cols-[1.55fr_.9fr]">
        <section className="panel rounded-[24px] p-5 sm:p-6"><div className="mb-6 flex items-start justify-between"><div><p className="eyebrow">Seven-day activity</p><h2 className="mt-2 text-lg font-semibold">Uploads & duplicates</h2></div><span className="rounded-full border border-acid/20 bg-acid/10 px-3 py-1 font-mono text-[10px] uppercase tracking-wider text-acid">Live</span></div><div className="h-72"><ResponsiveContainer width="100%" height="100%"><AreaChart data={data.uploads_over_time}><defs><linearGradient id="uploadFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#b9f36a" stopOpacity={.3} /><stop offset="100%" stopColor="#b9f36a" stopOpacity={0} /></linearGradient></defs><CartesianGrid stroke="#252a32" vertical={false} /><XAxis dataKey="label" axisLine={false} tickLine={false} tick={{ fill: "#969da9", fontSize: 11 }} /><YAxis allowDecimals={false} axisLine={false} tickLine={false} tick={{ fill: "#969da9", fontSize: 11 }} /><Tooltip contentStyle={{ background: "#15191f", border: "1px solid #292e36", borderRadius: 12, fontSize: 12 }} /><Area type="monotone" dataKey="uploads" stroke="#b9f36a" fill="url(#uploadFill)" strokeWidth={2} /><Area type="monotone" dataKey="duplicates" stroke="#ff8d6b" fill="transparent" strokeWidth={2} /></AreaChart></ResponsiveContainer></div></section>
        <section className="panel rounded-[24px] p-5 sm:p-6"><p className="eyebrow">Service confidence</p><h2 className="mt-2 text-lg font-semibold">Private pipeline</h2><div className="mt-7 space-y-5">{[["API gateway", system?.api.detail ?? "Status unavailable", system?.api.status === "healthy"],["Object storage", system?.object_storage.detail ?? "Status unavailable", system?.object_storage.status === "healthy"],["AI processing", system?.worker.detail ?? "Status unavailable", system?.worker.status === "healthy"],["Privacy boundary","No external AI APIs",true]].map(([label, detail, healthy]) => <div key={String(label)} className="flex items-center gap-3"><div className="grid h-8 w-8 place-items-center rounded-full bg-acid/10">{healthy ? <CheckCircle2 className="h-4 w-4 text-acid" /> : <CircleAlert className="h-4 w-4 text-coral" />}</div><div><p className="text-sm font-medium">{label}</p><p className="text-xs text-muted">{detail}</p></div></div>)}</div><Link className="mt-7 inline-flex items-center gap-2 text-sm font-semibold text-acid" to="/system">Open system status <ArrowRight className="h-4 w-4" /></Link></section>
      </div>
      <section className="mt-4 panel rounded-[24px] p-5 sm:p-6"><div className="mb-5 flex items-center justify-between"><div><p className="eyebrow">Latest additions</p><h2 className="mt-2 text-lg font-semibold">Recent uploads</h2></div><Link to="/gallery" className="text-sm font-semibold text-acid">View gallery</Link></div><div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">{data.recent_images.map((image) => <Link key={image.id} to={`/images/${image.id}`} className="focus-ring group overflow-hidden rounded-xl bg-[#171b21]"><div className="aspect-square overflow-hidden">{image.thumbnail_url && <img src={image.thumbnail_url} alt={image.original_filename} className="h-full w-full object-cover transition duration-500 group-hover:scale-105" />}</div><p className="truncate px-3 py-2.5 text-xs font-medium">{image.original_filename}</p></Link>)}</div></section>
    </>}
  </>;
}
