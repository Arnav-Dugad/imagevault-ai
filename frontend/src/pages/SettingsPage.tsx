import { BrainCircuit, KeyRound, LockKeyhole, ScanText } from "lucide-react";
import { PageHeading } from "../components/ui";
import { useAuth } from "../providers/AuthProvider";

export function SettingsPage() {
  const { user } = useAuth();
  const initials = user?.display_name.split(" ").map((part) => part[0]).join("").slice(0, 2).toUpperCase();
  const features = [
    [BrainCircuit, "Smart search", "Enabled"],
    [ScanText, "Text recognition", "Enabled"],
    [LockKeyhole, "Private storage", "Enabled"],
    [KeyRound, "Signed previews", "Enabled"],
  ] as const;
  return <>
    <PageHeading eyebrow="Settings" title="Account and privacy" />
    <div className="grid gap-5 lg:grid-cols-[.8fr_1.2fr]">
      <section className="panel rounded-[28px] p-6"><p className="eyebrow">Account</p><div className="mt-6 flex items-center gap-4"><div className="grid h-14 w-14 place-items-center rounded-full bg-lilac/15 font-semibold text-lilac">{initials}</div><div className="min-w-0"><p className="truncate font-semibold">{user?.display_name}</p><p className="truncate text-sm text-muted">{user?.email}</p></div></div></section>
      <section className="panel rounded-[28px] p-6"><p className="eyebrow">Features</p><div className="mt-6 grid gap-3 sm:grid-cols-2">{features.map(([Icon, label, value]) => <div key={label} className="flex items-center justify-between rounded-xl border border-line bg-white/[.02] p-4"><span className="flex items-center gap-3 text-sm"><Icon className="h-4 w-4 text-acid" />{label}</span><span className="font-mono text-[9px] uppercase text-acid">{value}</span></div>)}</div></section>
    </div>
  </>;
}
