import { useState, type ReactNode } from "react";
import { NavLink } from "react-router-dom";
import { Cloud, Copy, House, Images, LogOut, Menu, Upload, X } from "lucide-react";
import { api } from "../lib/api";
import { useSystem } from "../lib/system";
import { cn } from "../lib/utils";

const nav = [
  { to: "/", label: "Home", icon: House },
  { to: "/photos", label: "Photos", icon: Images },
  { to: "/upload", label: "Upload", icon: Upload },
  { to: "/duplicates", label: "Duplicates", icon: Copy },
  { to: "/cloud", label: "Cloud", icon: Cloud },
];

export function Logo() {
  return (
    <div className="flex items-center gap-3">
      <img src="/icon.svg" alt="" className="h-9 w-9" />
      <div>
        <p className="text-[15px] font-semibold tracking-tight">ImageVault</p>
        <p className="text-[11px] text-muted">Photos & duplicates</p>
      </div>
    </div>
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
        <CloudStatus />
        {showLogout && <button onClick={logout} className="focus-ring flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-sm text-muted hover:bg-white/[.04] hover:text-ink"><LogOut className="h-4 w-4" />Log out</button>}
      </div>
    </>
  );
}

export function Layout({ children, showLogout }: { children: ReactNode; showLogout: boolean }) {
  const [open, setOpen] = useState(false);
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

      <main className="px-4 pb-16 pt-8 sm:px-6 lg:ml-60 lg:px-10 lg:pt-12">
        <div className="mx-auto max-w-6xl">{children}</div>
      </main>
    </div>
  );
}
