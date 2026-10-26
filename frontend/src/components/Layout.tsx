import { useEffect, useRef, useState, type ReactNode } from "react";
import { Link, NavLink, useLocation } from "react-router-dom";
import { ArrowUp, CheckCircle2, Cloud, Copy, FolderOpen, House, ImagePlus, Images, LoaderCircle, LogOut, Menu, ReceiptText, RotateCcw, Upload, Users, X, XCircle } from "lucide-react";
import { api } from "../lib/api";
import { useSystem } from "../lib/system";
import { useToast } from "../lib/toast";
import { useUploads } from "../lib/uploads";
import { cn, formatBytes, rupees } from "../lib/utils";
import type { StorageUsage } from "../types";

const nav = [
  { to: "/", label: "Home", icon: House },
  { to: "/photos", label: "Photos", icon: Images },
  { to: "/albums", label: "Albums", icon: FolderOpen },
  { to: "/receipts", label: "Receipts", icon: ReceiptText },
  { to: "/people", label: "People", icon: Users },
  { to: "/duplicates", label: "Duplicates", icon: Copy },
  { to: "/upload", label: "Upload", icon: Upload },
  { to: "/cloud", label: "Cloud", icon: Cloud },
];

function UploadProgress() {
  const { items, busy } = useUploads();
  if (!busy) return null;
  const finished = items.filter((i) => i.state === "done" || i.state === "failed").length;
  const total = items.filter((i) => i.state !== "stored").length;
  return (
    <NavLink to="/upload" className="focus-ring flex items-center gap-2 rounded-xl border border-acid/30 bg-acid/[.06] px-3 py-2.5 text-sm">
      <LoaderCircle className="h-4 w-4 animate-spin text-acid" />Uploading {Math.min(finished + 1, total)} of {total}
    </NavLink>
  );
}

/** A small panel while photos upload, so the queue is visible on every page (and on phones,
 *  where the sidebar is hidden). It stays a few seconds after the last upload, then goes. */
function UploadDock() {
  const { items, busy, retryFailed } = useUploads();
  const { pathname } = useLocation();
  const [closed, setClosed] = useState(false);
  const [lingering, setLingering] = useState(false);
  useEffect(() => {
    if (busy) {
      setClosed(false);
      setLingering(true);
      return;
    }
    const timer = setTimeout(() => setLingering(false), 6000);
    return () => clearTimeout(timer);
  }, [busy]);
  const queue = items.filter((i) => i.state !== "stored" && i.state !== "checking");
  const failures = queue.filter((i) => i.state === "failed");
  // Failed uploads keep the panel open until they are retried or the panel is closed.
  if (pathname === "/upload" || closed || !(busy || lingering || failures.length)) return null;
  const done = queue.filter((i) => i.state === "done").length;
  const failed = failures.length;
  const retryable = failures.filter((i) => !i.final).length;
  const stored = items.filter((i) => i.state === "stored").length;
  const copies = queue.filter((i) => i.result?.match).length;
  const current = items.find((i) => i.state === "uploading");
  const share = queue.length ? (done + failed + (current ? current.progress / 100 : 0)) / queue.length : 1;
  return (
    <div role="status" className="fixed inset-x-3 bottom-3 z-40 rounded-2xl border border-line bg-raised/95 p-4 shadow-2xl backdrop-blur sm:inset-x-auto sm:right-20 sm:bottom-5 sm:w-80">
      <div className="flex items-center gap-2">
        {busy ? <LoaderCircle className="h-4 w-4 shrink-0 animate-spin text-acid" />
          : failed ? <XCircle className="h-4 w-4 shrink-0 text-coral" /> : <CheckCircle2 className="h-4 w-4 shrink-0 text-acid" />}
        <p className="flex-1 text-sm font-semibold">{busy ? `Uploading ${Math.min(done + failed + 1, queue.length)} of ${queue.length}` : `${done} uploaded`}</p>
        <button onClick={() => setClosed(true)} aria-label="Hide" className="focus-ring rounded-md p-1 text-muted hover:text-ink"><X className="h-4 w-4" /></button>
      </div>
      {current && <p className="mt-1 truncate text-xs text-muted">{current.file.name}</p>}
      {failures.length > 0 && !busy && <div className="mt-3 rounded-xl border border-coral/30 bg-coral/[.06] p-2.5">
        <ul className="max-h-28 space-y-1 overflow-y-auto text-xs">
          {failures.map((item) => (
            <li key={item.key} className="flex items-start gap-1.5" title={item.error}>
              <XCircle className="mt-px h-3.5 w-3.5 shrink-0 text-coral" />
              <span className="min-w-0"><span className="block truncate font-medium">{item.file.name}</span><span className="block truncate text-muted">{item.error}</span></span>
            </li>
          ))}
        </ul>
        {retryable > 0 && <button onClick={retryFailed} className="focus-ring mt-2 inline-flex items-center gap-1.5 rounded-lg bg-coral/15 px-2.5 py-1 text-xs font-medium text-coral hover:bg-coral/25">
          <RotateCcw className="h-3.5 w-3.5" />Retry {retryable === 1 ? (failed === 1 ? "it" : "1") : `${retryable === failed ? "all " : ""}${retryable}`}
        </button>}
      </div>}
      <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-canvas">
        <div className="h-full rounded-full bg-acid transition-[width] duration-300" style={{ width: `${Math.round(share * 100)}%` }} />
      </div>
      <div className="mt-2 flex items-center justify-between gap-2 text-xs text-muted">
        <span className="truncate">{[copies && `${copies} ${copies === 1 ? "copy" : "copies"} found`, stored && `${stored} already stored`, failed && `${failed} failed`].filter(Boolean).join(" · ") || "\u00a0"}</span>
        <Link to="/upload" className="shrink-0 font-medium text-acid hover:underline">View queue</Link>
      </div>
    </div>
  );
}

/** Drop photos anywhere in the window to upload them. */
function DropAnywhere() {
  const { add } = useUploads();
  const toast = useToast();
  const [active, setActive] = useState(false);
  const depth = useRef(0);
  useEffect(() => {
    const hasFiles = (e: DragEvent) => Array.from(e.dataTransfer?.types ?? []).includes("Files");
    const enter = (e: DragEvent) => { if (hasFiles(e)) { depth.current += 1; setActive(true); } };
    const leave = () => { depth.current = Math.max(0, depth.current - 1); if (!depth.current) setActive(false); };
    const reset = () => { depth.current = 0; setActive(false); }; // drag cancelled, or the window lost focus
    const over = (e: DragEvent) => { if (hasFiles(e)) e.preventDefault(); };
    const drop = (e: DragEvent) => {
      depth.current = 0;
      setActive(false);
      if (!hasFiles(e)) return;
      e.preventDefault();
      const files = Array.from(e.dataTransfer?.files ?? []);
      if (!files.length) return;
      void add(files).then(({ stored }) => {
        if (stored) toast(`${stored} already stored, not uploaded again`);
      });
    };
    window.addEventListener("dragenter", enter);
    window.addEventListener("dragleave", leave);
    window.addEventListener("dragover", over);
    window.addEventListener("drop", drop);
    window.addEventListener("dragend", reset);
    window.addEventListener("blur", reset);
    return () => {
      window.removeEventListener("dragend", reset);
      window.removeEventListener("blur", reset);
      window.removeEventListener("dragenter", enter);
      window.removeEventListener("dragleave", leave);
      window.removeEventListener("dragover", over);
      window.removeEventListener("drop", drop);
    };
  }, [add, toast]);
  if (!active) return null;
  return (
    <div className="pointer-events-none fixed inset-3 z-[65] grid place-items-center rounded-3xl border-2 border-dashed border-acid bg-canvas/80 backdrop-blur-sm">
      <p className="flex items-center gap-3 text-xl font-semibold"><ImagePlus className="h-7 w-7 text-acid" />Drop to upload</p>
    </div>
  );
}

function BackToTop() {
  const [show, setShow] = useState(false);
  useEffect(() => {
    const onScroll = () => setShow(window.scrollY > 1200);
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);
  if (!show) return null;
  return (
    <button onClick={() => window.scrollTo({ top: 0, behavior: "smooth" })} aria-label="Back to top"
      className="pop-in focus-ring fixed bottom-36 right-4 z-30 grid h-11 w-11 sm:bottom-6 sm:right-6 place-items-center rounded-full border border-line bg-raised shadow-xl hover:bg-[#20252c]">
      <ArrowUp className="h-5 w-5" />
    </button>
  );
}

/** Shows the current page in the browser tab, e.g. "People · ImageVault". */
function usePageTitle() {
  const { pathname } = useLocation();
  useEffect(() => {
    const page = nav.find((n) => n.to !== "/" && pathname.startsWith(n.to));
    document.title = page ? `${page.label} · ImageVault` : "ImageVault";
  }, [pathname]);
}

export function Logo() {
  return (
    <div className="flex items-center gap-3">
      <img src="/icon.svg" alt="" className="h-9 w-9" />
      <div>
        <p className="text-[15px] font-semibold tracking-tight">ImageVault</p>
        <p className="text-[11px] text-muted">Your photos, sorted</p>
      </div>
    </div>
  );
}

const FREE_STORAGE = 5 * 1024 ** 3; // Azure's free allowance: 5 GB of Blob Storage for the first 12 months

/** How much space the photos use, with a bar against the free allowance. Refreshes after uploads. */
function StorageMeter() {
  const { busy } = useUploads();
  const { pathname } = useLocation();
  const [usage, setUsage] = useState<StorageUsage | null>(null);
  useEffect(() => {
    if (busy) return;
    api<StorageUsage>("/storage").then(setUsage).catch(() => {});
  }, [busy, pathname]);
  if (!usage) return null;
  const azure = usage.kind === "azure";
  const share = Math.min(1, usage.total_bytes / FREE_STORAGE);
  return (
    <NavLink to="/cloud" className="focus-ring block rounded-xl border border-line bg-white/[.02] p-3 hover:bg-white/[.04]"
      title={azure ? "Azure gives 5 GB of Blob Storage free for the first 12 months" : undefined}>
      <p className="flex items-baseline justify-between text-[11px] font-medium uppercase tracking-wider text-muted">
        Storage<span className="normal-case tracking-normal">{azure ? `${rupees(usage.monthly_cost * usage.inr_rate, true)}/month` : "free"}</span>
      </p>
      <p className="mt-1.5 text-sm font-medium tabular-nums">{formatBytes(usage.total_bytes)}{azure && <span className="font-normal text-muted"> of 5 GB free</span>}</p>
      {azure && <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-raised">
        <div className={cn("h-full rounded-full transition-[width] duration-700", share > 0.8 ? "bg-coral" : "bg-acid")} style={{ width: `${Math.max(share * 100, usage.total_bytes ? 1.5 : 0)}%` }} />
      </div>}
    </NavLink>
  );
}

function CloudStatus() {
  const { system } = useSystem();
  if (!system) return null;
  const healthy = system.services.every((s) => !s.active || s.healthy);
  const onAzure = system.environment === "Azure";
  return (
    <NavLink to="/cloud" className="focus-ring block rounded-xl border border-line bg-white/[.02] p-3 hover:bg-white/[.04]">
      <p className="text-[11px] font-medium uppercase tracking-wider text-muted">Running on</p>
      <p className="mt-1.5 flex items-center gap-2 text-sm font-medium">
        <span className="relative flex h-2 w-2">
          {healthy && <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-acid opacity-60" />}
          <span className={cn("relative h-2 w-2 rounded-full", healthy ? "bg-acid" : "bg-coral")} />
        </span>
        {onAzure ? "Microsoft Azure" : "This computer"}
      </p>
    </NavLink>
  );
}

function Navigation({ onNavigate, showLogout }: { onNavigate?: () => void; showLogout: boolean }) {
  async function logout() {
    await api("/logout", { method: "POST" }).catch(() => {});
    window.dispatchEvent(new Event("imagevault:logged-out"));
  }
  return (
    <>
      <nav className="mt-8 space-y-1" aria-label="Main">
        {nav.map(({ to, label, icon: Icon }) => (
          <NavLink key={to} to={to} end={to === "/"} onClick={onNavigate}
            className={({ isActive }) => cn("focus-ring flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm transition", isActive ? "bg-white/[.07] font-medium text-ink" : "text-muted hover:bg-white/[.04] hover:text-ink")}>
            {({ isActive }) => <><Icon className={cn("h-4 w-4", isActive && "text-acid")} />{label}</>}
          </NavLink>
        ))}
      </nav>
      <div className="mt-auto space-y-2 pt-6">
        <UploadProgress />
        <StorageMeter />
        <CloudStatus />
        {showLogout && <button onClick={logout} className="focus-ring flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-sm text-muted hover:bg-white/[.04] hover:text-ink"><LogOut className="h-4 w-4" />Log out</button>}
      </div>
    </>
  );
}

export function Layout({ children, showLogout }: { children: ReactNode; showLogout: boolean }) {
  const [open, setOpen] = useState(false);
  usePageTitle();
  return (
    <div className="min-h-screen">
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-60 flex-col border-r border-line bg-[#0c0f13]/95 p-5 lg:flex">
        <Logo />
        <Navigation showLogout={showLogout} />
      </aside>

      <header className="sticky top-0 z-20 flex h-16 items-center justify-between border-b border-line bg-canvas/85 px-4 backdrop-blur-xl lg:hidden">
        <Logo />
        <button onClick={() => setOpen(true)} aria-label="Open menu" className="focus-ring rounded-lg p-2"><Menu className="h-5 w-5" /></button>
      </header>
      {open && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div className="absolute inset-0 bg-black/70" onClick={() => setOpen(false)} />
          <aside className="pop-in absolute inset-y-0 left-0 flex w-72 max-w-[85%] flex-col border-r border-line bg-[#0c0f13] p-5">
            <div className="flex items-center justify-between"><Logo /><button onClick={() => setOpen(false)} aria-label="Close menu" className="focus-ring rounded-lg p-2"><X className="h-5 w-5" /></button></div>
            <Navigation onNavigate={() => setOpen(false)} showLogout={showLogout} />
          </aside>
        </div>
      )}

      <main className="px-4 pb-24 pt-8 sm:px-6 lg:ml-60 lg:px-10 lg:pt-12">
        <div className="mx-auto max-w-6xl">{children}</div>
      </main>
      <DropAnywhere />
      <UploadDock />
      <BackToTop />
    </div>
  );
}
