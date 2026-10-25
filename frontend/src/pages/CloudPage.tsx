import { useState, type ReactNode } from "react";
import { Activity, ArrowDown, ArrowRight, Cloud, Database, ExternalLink, GitBranch, Globe, HardDrive, Laptop, Layers, RefreshCw, Server, Sparkles, Wallet, type LucideIcon } from "lucide-react";
import { CostCard } from "../components/CostCard";
import { Button, PageHeading, Spinner } from "../components/ui";
import { useSystem } from "../lib/system";
import { cn, formatDate } from "../lib/utils";
import type { CloudService } from "../types";

const REPO = "https://github.com/Arnav-Dugad/imagevault-ai";
const ICONS: Record<CloudService["id"], LucideIcon> = { "app-service": Server, database: Database, storage: Cloud, monitoring: Activity, ai: Sparkles };

function StatusPill({ service }: { service: CloudService }) {
  if (!service.active) return <span className="inline-flex items-center gap-1.5 rounded-full border border-line px-2.5 py-0.5 text-xs text-muted"><span className="h-1.5 w-1.5 rounded-full bg-muted" />{service.id === "ai" ? "Turned off" : "Local mode"}</span>;
  if (!service.healthy && !service.error) return <span className="inline-flex items-center gap-1.5 rounded-full border border-sky-300/40 bg-sky-300/10 px-2.5 py-0.5 text-xs font-medium text-sky-300"><span className="h-1.5 w-1.5 animate-pulse rounded-full bg-sky-300" />Getting ready</span>;
  if (!service.healthy) return <span className="inline-flex items-center gap-1.5 rounded-full border border-coral/40 bg-coral/10 px-2.5 py-0.5 text-xs font-medium text-coral"><span className="h-1.5 w-1.5 rounded-full bg-coral" />Problem</span>;
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full border border-acid/40 bg-acid/10 px-2.5 py-0.5 text-xs font-medium text-acid">
      <span className="relative flex h-1.5 w-1.5"><span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-acid opacity-75" /><span className="relative h-1.5 w-1.5 rounded-full bg-acid" /></span>
      Healthy
    </span>
  );
}

function ServiceCard({ service, index }: { service: CloudService; index: number }) {
  const Icon = service.id === "storage" && !service.active ? HardDrive : ICONS[service.id];
  return (
    <article className="pop-in panel flex flex-col p-5" style={{ animationDelay: `${index * 60}ms`, animationFillMode: "backwards" }}>
      <div className="flex items-start justify-between gap-3">
        <div className={cn("grid h-11 w-11 place-items-center rounded-xl border", service.active ? "border-lilac/30 bg-lilac/10 text-lilac" : "border-line bg-raised text-muted")}><Icon className="h-5 w-5" /></div>
        <StatusPill service={service} />
      </div>
      <h3 className="mt-4 font-semibold">{service.name}</h3>
      <p className="mt-0.5 text-sm text-muted">{service.role}</p>
      <div className="mt-4 flex items-end justify-between gap-3 border-t border-line pt-3 text-xs">
        <span className="min-w-0 break-all text-muted">{service.detail}</span>
        {service.latency_ms !== null && <span className="shrink-0 tabular-nums text-ink">{service.latency_ms} ms</span>}
      </div>
      {service.error && <p className="mt-2 text-xs text-coral">{service.error}</p>}
    </article>
  );
}

function Box({ icon: Icon, title, subtitle, accent }: { icon: LucideIcon; title: string; subtitle: string; accent?: boolean }) {
  return (
    <div className={cn("flex items-center gap-3 rounded-xl border px-4 py-3", accent ? "border-acid/40 bg-acid/[.06]" : "border-line bg-canvas/60")}>
      <Icon className={cn("h-5 w-5 shrink-0", accent ? "text-acid" : "text-lilac")} />
      <div className="min-w-0"><p className="text-sm font-semibold leading-tight">{title}</p><p className="text-xs text-muted">{subtitle}</p></div>
    </div>
  );
}

/** A simple picture of how the pieces connect. */
function Architecture({ laptopOnline }: { laptopOnline: boolean }) {
  return (
    <section className="panel overflow-hidden p-5 sm:p-6">
      <h2 className="font-semibold">Architecture</h2>
      <p className="mt-1 text-sm text-muted">Built with Terraform, deployed by GitHub Actions.</p>
      <div className="mt-5 grid items-center gap-3 lg:grid-cols-[180px_auto_1fr]">
        <Box icon={Globe} title="Browser" subtitle="React website" />
        <div className="grid place-items-center text-muted"><ArrowRight className="hidden h-5 w-5 lg:block" /><ArrowDown className="h-5 w-5 lg:hidden" /></div>
        <div className="rounded-2xl border border-dashed border-lilac/30 p-3 sm:p-4">
          <p className="mb-3 text-[11px] font-semibold uppercase tracking-wider text-lilac">Microsoft Azure · resource group imagevault-rg</p>
          <Box icon={Server} title="App Service" subtitle={`Python FastAPI · HTTPS · managed identity${laptopOnline ? " · AI on standby" : " · free AI models"}`} accent />
          <div className="my-2 grid place-items-center text-muted"><ArrowDown className="h-4 w-4" /></div>
          <div className="grid gap-2 sm:grid-cols-3">
            <Box icon={Database} title="PostgreSQL" subtitle="Photo details" />
            <Box icon={Cloud} title="Blob Storage" subtitle="Photos & thumbnails" />
            <Box icon={Activity} title="App Insights" subtitle="Logs & metrics" />
          </div>
        </div>
      </div>
      <div className="mt-3 grid items-center gap-3 lg:grid-cols-[180px_auto_1fr]">
        <div className={cn("flex items-center gap-3 rounded-xl border px-4 py-3 transition", laptopOnline ? "border-sky-300/50 bg-sky-300/[.07]" : "border-dashed border-line opacity-70")}>
          <Laptop className={cn("h-5 w-5 shrink-0", laptopOnline ? "text-sky-300" : "text-muted")} />
          <div className="min-w-0"><p className="text-sm font-semibold leading-tight">Your laptop</p><p className="text-xs text-muted">{laptopOnline ? "Edge AI · online" : "Edge AI · offline"}</p></div>
        </div>
        <div className="grid place-items-center text-muted"><ArrowRight className="hidden h-5 w-5 lg:block" /><ArrowDown className="h-5 w-5 lg:hidden" /></div>
        <p className="text-sm leading-6 text-muted">
          {laptopOnline
            ? <>Your laptop is doing the AI work and saving results to Azure.</>
            : <>Run <code className="text-ink">python -m app.worker</code> to do the AI work on your laptop. Until then, App Service does it.</>}
        </p>
      </div>
    </section>
  );
}

function DevOpsCard({ icon: Icon, title, children }: { icon: LucideIcon; title: string; children: ReactNode }) {
  return (
    <article className="panel p-5">
      <h3 className="flex items-center gap-2 font-semibold"><Icon className="h-4 w-4 text-acid" />{title}</h3>
      <div className="mt-2 text-sm leading-6 text-muted">{children}</div>
    </article>
  );
}

const link = "inline-flex items-center gap-1 text-lilac hover:underline";

export function CloudPage() {
  const { system, refresh } = useSystem();
  const [refreshing, setRefreshing] = useState(false);
  if (!system) return <Spinner />;

  async function recheck() {
    setRefreshing(true);
    await refresh();
    setRefreshing(false);
  }

  const onAzure = system.environment === "Azure";
  const build = system.build;
  return <>
    <PageHeading title="Cloud" description="The Azure services behind ImageVault."
      action={<Button variant="secondary" onClick={recheck} loading={refreshing}>{!refreshing && <RefreshCw className="h-4 w-4" />}Check again</Button>} />

    <div className={cn("mb-6 flex items-center gap-3 rounded-2xl border p-4 text-sm", onAzure ? "border-acid/30 bg-acid/[.06]" : "border-lilac/25 bg-lilac/[.06]")}>
      <Cloud className={cn("h-5 w-5 shrink-0", onAzure ? "text-acid" : "text-lilac")} />
      {onAzure
        ? <span>Running on <b>Microsoft Azure</b> · version {system.version}</span>
        : <span>Running <b>locally</b> (SQLite and a folder instead of Azure).</span>}
    </div>

    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
      {system.services.map((service, i) => <ServiceCard key={service.id} service={service} index={i} />)}
    </div>

    <div className="mt-6"><CostCard /></div>

    <div className="mt-6"><Architecture laptopOnline={system.ai_runs_on === "laptop"} /></div>

    <h2 className="mb-3 mt-8 text-lg font-semibold">DevOps</h2>
    <div className="grid gap-3 lg:grid-cols-3">
      <DevOpsCard icon={GitBranch} title="CI/CD · GitHub Actions">
        {build ? <>
          Deployed commit <a className={link} href={`${build.repository}/commit/${build.commit}`} target="_blank" rel="noreferrer"><code>{build.commit.slice(0, 7)}</code></a> on {formatDate(build.deployed_at)}.{" "}
          <a className={link} href={build.run_url} target="_blank" rel="noreferrer">View pipeline run <ExternalLink className="h-3 w-3" /></a>
        </> : <>Every push is tested; <code>main</code> deploys automatically. <a className={link} href={`${REPO}/actions`} target="_blank" rel="noreferrer">See runs <ExternalLink className="h-3 w-3" /></a></>}
      </DevOpsCard>
      <DevOpsCard icon={Layers} title="Infrastructure as Code · Terraform">
        Every Azure resource is defined in code. <a className={link} href={`${REPO}/tree/main/infra`} target="_blank" rel="noreferrer">View infra/ <ExternalLink className="h-3 w-3" /></a>
      </DevOpsCard>
      <DevOpsCard icon={Wallet} title="Cost control · Budget alerts">
        Free tiers only, capped logs, and a US$5 monthly budget with email alerts.
      </DevOpsCard>
    </div>
  </>;
}
