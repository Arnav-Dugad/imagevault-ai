import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { Activity, Boxes, CloudUpload, Copy, FolderHeart, Gauge, Images, LogOut, Menu, Settings, ShieldCheck, X } from "lucide-react";
import { useState, type ReactNode } from "react";
import { NavLink, useLocation } from "react-router-dom";
import { cn } from "../lib/utils";
import { useAuth } from "../providers/AuthProvider";
import { Button } from "./ui";

const nav = [
  { to: "/", label: "Overview", icon: Gauge },
  { to: "/gallery", label: "Gallery", icon: Images },
  { to: "/albums", label: "Smart albums", icon: FolderHeart },
  { to: "/upload", label: "Upload", icon: CloudUpload },
  { to: "/duplicates", label: "Duplicate review", icon: Copy },
  { to: "/system", label: "System status", icon: Activity },
  { to: "/settings", label: "Settings", icon: Settings },
];

function Brand() { return <div className="flex items-center gap-3"><div className="relative grid h-9 w-9 place-items-center rounded-xl border border-acid/30 bg-acid/10"><Boxes className="h-4 w-4 text-acid" /><span className="absolute -right-1 -top-1 h-2 w-2 rounded-full bg-acid shadow-[0_0_12px_#b9f36a]" /></div><div><p className="text-sm font-semibold tracking-tight">ImageVault <span className="text-acid">AI</span></p><p className="font-mono text-[9px] uppercase tracking-[.16em] text-muted">Private cloud</p></div></div>; }

function Navigation({ onNavigate }: { onNavigate?: () => void }) {
  const scope = onNavigate ? "mobile" : "desktop";
  return <nav className="mt-9 space-y-1" aria-label="Primary navigation">{nav.map(({ to, label, icon: Icon }) => <NavLink key={to} to={to} end={to === "/"} onClick={onNavigate} className="focus-ring group relative flex items-center gap-3 overflow-hidden rounded-xl px-3 py-2.5 text-sm text-muted transition-colors hover:text-ink">{({ isActive }) => <><AnimatePresence>{isActive && <motion.span layoutId={`active-navigation-${scope}`} className="absolute inset-0 rounded-xl border border-white/[.045] bg-white/[.07]" transition={{ type: "spring", stiffness: 420, damping: 34 }} />}</AnimatePresence><Icon className={cn("relative h-4 w-4 transition", isActive ? "text-acid" : "group-hover:text-ink")} /><span className={cn("relative", isActive && "font-medium text-ink")}>{label}</span>{isActive && <motion.span layoutId={`active-navigation-dot-${scope}`} className="absolute right-3 h-1.5 w-1.5 rounded-full bg-acid shadow-[0_0_10px_#b9f36a]" />}</>}</NavLink>)}</nav>;
}

export function AppLayout({ children }: { children: ReactNode }) {
  const { user, logout } = useAuth();
  const [mobileOpen, setMobileOpen] = useState(false);
  const location = useLocation();
  const reducedMotion = useReducedMotion();
  const pageLabel = nav.find((item) => item.to === location.pathname)?.label ?? (location.pathname.startsWith("/images/") ? "Image details" : "ImageVault");
  const initials = user?.display_name.split(" ").map((word) => word[0]).join("").slice(0, 2).toUpperCase();
  return <div className="app-backdrop grain min-h-screen">
    <aside className="fixed inset-y-0 left-0 z-30 hidden w-64 border-r border-line bg-[#0c0f13]/95 p-5 lg:flex lg:flex-col"><Brand /><Navigation /><div className="mt-auto rounded-2xl border border-line bg-white/[.025] p-4"><div className="mb-3 flex items-center gap-3"><div className="grid h-9 w-9 place-items-center rounded-full bg-lilac/15 text-xs font-bold text-lilac">{initials}</div><div className="min-w-0"><p className="truncate text-sm font-medium">{user?.display_name}</p><p className="truncate text-xs text-muted">{user?.email}</p></div></div><Button variant="ghost" className="w-full justify-start px-2" onClick={logout}><LogOut className="h-4 w-4" />Sign out</Button></div></aside>
    <header className="fixed inset-x-0 top-0 z-20 flex h-16 items-center justify-between border-b border-line bg-canvas/80 px-4 backdrop-blur-xl lg:left-64 lg:px-8"><div className="flex items-center gap-3"><button className="focus-ring rounded-lg p-2 transition active:scale-95 lg:hidden" aria-label="Open navigation" onClick={() => setMobileOpen(true)}><Menu className="h-5 w-5" /></button><AnimatePresence mode="wait" initial={false}><motion.p key={pageLabel} initial={reducedMotion ? false : { opacity: 0, y: 5 }} animate={{ opacity: 1, y: 0 }} exit={reducedMotion ? undefined : { opacity: 0, y: -5 }} className="text-sm font-semibold">{pageLabel}</motion.p></AnimatePresence></div><div className="relative flex items-center gap-2 overflow-hidden rounded-full border border-line bg-white/[.025] px-3 py-1.5"><motion.span className="absolute inset-y-0 w-12 bg-gradient-to-r from-transparent via-acid/10 to-transparent" animate={reducedMotion ? undefined : { x: [-80, 180] }} transition={{ duration: 3.2, repeat: Infinity, repeatDelay: 2.5 }} /><ShieldCheck className="relative h-3.5 w-3.5 text-acid" /><span className="relative font-mono text-[10px] uppercase tracking-wider text-muted">Local processing</span></div></header>
    <AnimatePresence>{mobileOpen && <><motion.button aria-label="Close navigation overlay" className="fixed inset-0 z-40 bg-black/70 lg:hidden" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={() => setMobileOpen(false)} /><motion.aside className="fixed inset-y-0 left-0 z-50 w-[85%] max-w-72 border-r border-line bg-[#0c0f13] p-5 lg:hidden" initial={{ x: "-100%" }} animate={{ x: 0 }} exit={{ x: "-100%" }}><div className="flex items-center justify-between"><Brand /><button className="focus-ring rounded-lg p-2" aria-label="Close navigation" onClick={() => setMobileOpen(false)}><X className="h-5 w-5" /></button></div><Navigation onNavigate={() => setMobileOpen(false)} /><button onClick={logout} className="focus-ring absolute bottom-6 left-5 flex items-center gap-2 rounded-lg px-3 py-2 text-sm text-muted"><LogOut className="h-4 w-4" />Sign out</button></motion.aside></>}</AnimatePresence>
    <main className="min-h-screen px-4 pb-16 pt-24 sm:px-6 lg:ml-64 lg:px-8 xl:px-10"><div className="mx-auto max-w-[1440px]"><AnimatePresence mode="wait" initial={false}><motion.div key={location.pathname} initial={reducedMotion ? false : { opacity: 0, y: 12, filter: "blur(5px)" }} animate={{ opacity: 1, y: 0, filter: "blur(0px)" }} exit={reducedMotion ? undefined : { opacity: 0, y: -7, filter: "blur(3px)" }} transition={{ duration: .24, ease: [0.22, 1, 0.36, 1] }}>{children}</motion.div></AnimatePresence></div></main>
  </div>;
}
