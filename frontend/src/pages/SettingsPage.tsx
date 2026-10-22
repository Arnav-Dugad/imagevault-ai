import { useState, type FormEvent } from "react";
import { Cloud, ExternalLink, FolderOpen, HardDrive, Info } from "lucide-react";
import { Button, ConfirmDialog, ErrorNote, PageHeading } from "../components/ui";
import { api } from "../lib/api";
import { useSettings } from "../lib/settings";
import type { Settings } from "../types";

const GUIDE_URL = "https://github.com/Arnav-Dugad/imagevault-ai/blob/main/docs/azure.md";

function AzureForm({ onConnected }: { onConnected: (s: Settings) => void }) {
  const [connectionString, setConnectionString] = useState("");
  const [container, setContainer] = useState("photos");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true); setError("");
    try {
      onConnected(await api<Settings>("/settings/azure", { method: "PUT", body: JSON.stringify({ connection_string: connectionString, container }) }));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="mt-6 space-y-4">
      <ol className="space-y-1.5 rounded-xl border border-line bg-canvas/50 p-4 text-sm leading-6 text-muted">
        <li><span className="text-ink">1.</span> Sign in to <a className="text-lilac hover:underline" href="https://portal.azure.com" target="_blank" rel="noreferrer">portal.azure.com</a> with your Azure for Students account.</li>
        <li><span className="text-ink">2.</span> Create a <span className="text-ink">Storage account</span> (Standard performance, LRS redundancy).</li>
        <li><span className="text-ink">3.</span> Open it, then go to <span className="text-ink">Security + networking → Access keys</span>.</li>
        <li><span className="text-ink">4.</span> Click <span className="text-ink">Show</span> next to <span className="text-ink">Connection string</span>, copy it and paste it below.</li>
      </ol>
      <label className="block">
        <span className="text-sm font-medium">Connection string</span>
        <input type="password" required value={connectionString} onChange={(e) => setConnectionString(e.target.value)} autoComplete="off" spellCheck={false}
          placeholder="DefaultEndpointsProtocol=https;AccountName=…;AccountKey=…"
          className="focus-ring mt-1.5 h-11 w-full rounded-xl border border-line bg-canvas px-3 font-mono text-sm placeholder:font-sans placeholder:text-muted/60" />
      </label>
      <label className="block">
        <span className="text-sm font-medium">Container name</span>
        <input required value={container} onChange={(e) => setContainer(e.target.value)} spellCheck={false}
          className="focus-ring mt-1.5 block h-11 w-full rounded-xl border border-line bg-canvas px-3 text-sm sm:w-72" />
        <span className="mt-1.5 block text-xs text-muted">A folder inside your storage account. It is created for you if it doesn't exist.</span>
      </label>
      {error && <ErrorNote message={error} />}
      <div className="flex flex-wrap items-center gap-4">
        <Button type="submit" loading={busy}><Cloud className="h-4 w-4" />{busy ? "Testing connection…" : "Connect to Azure"}</Button>
        <a href={GUIDE_URL} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1.5 text-sm text-muted hover:text-ink">Full step-by-step guide <ExternalLink className="h-3.5 w-3.5" /></a>
      </div>
    </form>
  );
}

export function SettingsPage() {
  const { settings, update } = useSettings();
  const [confirm, setConfirm] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  if (!settings) return null;

  async function disconnect() {
    setBusy(true);
    try { update(await api<Settings>("/settings/azure", { method: "DELETE" })); }
    catch (e) { setError((e as Error).message); }
    finally { setBusy(false); setConfirm(false); }
  }

  const azure = settings.storage === "azure";
  return <>
    <PageHeading title="Settings" description="Choose where ImageVault stores your photos." />

    <section className="panel p-6">
      <div className="flex items-start gap-4">
        <div className={`grid h-11 w-11 shrink-0 place-items-center rounded-xl border ${azure ? "border-lilac/30 bg-lilac/10" : "border-acid/25 bg-acid/10"}`}>
          {azure ? <Cloud className="h-5 w-5 text-lilac" /> : <HardDrive className="h-5 w-5 text-acid" />}
        </div>
        <div className="min-w-0">
          <h2 className="font-semibold">{azure ? "Connected to Azure Blob Storage" : "Photos are stored on this computer"}</h2>
          <p className="mt-1 text-sm leading-6 text-muted">
            {azure
              ? <>New photos are uploaded to the <span className="text-ink">{settings.azure_container}</span> container in the <span className="text-ink">{settings.azure_account}</span> storage account.</>
              : "Connect your Azure for Students account to keep new photos in Microsoft's cloud. Photos you already added stay where they are."}
          </p>
        </div>
      </div>
      {error && <div className="mt-4"><ErrorNote message={error} /></div>}
      {!azure && <AzureForm onConnected={update} />}
      {azure && !settings.azure_set_by_environment && (
        <div className="mt-6"><Button variant="secondary" onClick={() => setConfirm(true)}>Disconnect Azure</Button></div>
      )}
      {settings.azure_set_by_environment && (
        <p className="mt-6 flex items-center gap-2 text-sm text-muted"><Info className="h-4 w-4" />Azure is configured by the server, so it can't be changed here.</p>
      )}
    </section>

    <section className="panel mt-4 p-6">
      <h2 className="flex items-center gap-2 font-semibold"><FolderOpen className="h-4 w-4 text-acid" />Data folder</h2>
      <p className="mt-1 text-sm text-muted">The database, previews and locally stored photos are kept here:</p>
      <code className="mt-3 block break-all rounded-lg border border-line bg-canvas px-3 py-2 text-sm">{settings.data_folder}</code>
    </section>

    <p className="mt-8 text-center text-xs text-muted">ImageVault {settings.version} · <a className="hover:text-ink" href="https://github.com/Arnav-Dugad/imagevault-ai" target="_blank" rel="noreferrer">GitHub</a></p>

    {confirm && <ConfirmDialog title="Disconnect Azure?" confirmLabel="Disconnect" busy={busy} onCancel={() => setConfirm(false)} onConfirm={disconnect}
      message="New photos will be saved on this computer again. Photos already in Azure stay there, but you won't be able to open them until you reconnect." />}
  </>;
}
