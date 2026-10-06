import { motion } from "framer-motion";
import { ArrowRight, Boxes, Eye, EyeOff } from "lucide-react";
import { FormEvent, useEffect, useState } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";
import { Button } from "../components/ui";
import { api, ApiError } from "../lib/api";
import { useAuth } from "../providers/AuthProvider";

export function AuthPage() {
  const { pathname } = useLocation();
  const registerMode = pathname === "/register";
  const { user, login, register } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({ name: "", email: "", password: "", invitation: "" });
  const [config, setConfig] = useState<{ registration_enabled: boolean; registration_requires_code: boolean } | null>(null);
  const [showPassword, setShowPassword] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    setForm({ name: "", email: "", password: "", invitation: "" });
    setShowPassword(false);
    setBusy(false);
    setError("");
  }, [pathname]);

  useEffect(() => {
    const controller = new AbortController();
    api<{ registration_enabled: boolean; registration_requires_code: boolean }>("/auth/config", { signal: controller.signal })
      .then(setConfig)
      .catch(() => { if (!controller.signal.aborted && registerMode) setError("Could not load signup settings. Please reload to try again."); });
    return () => controller.abort();
  }, [registerMode]);

  if (user) return <Navigate to="/" replace />;
  async function submit(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError("");
    try { if (registerMode) await register(form.email, form.name, form.password, form.invitation); else await login(form.email, form.password); navigate("/"); }
    catch (reason) { setError(reason instanceof ApiError ? reason.message : "Could not connect"); }
    finally { setBusy(false); }
  }

  return <div className="grain min-h-screen bg-[#090b0e] lg:grid lg:grid-cols-[1fr_1fr]">
    <section className="relative hidden min-h-screen overflow-hidden border-r border-line p-12 lg:flex lg:flex-col xl:p-16"><div className="absolute -left-40 top-1/3 h-96 w-96 rounded-full bg-acid/10 blur-[110px]" /><div className="absolute -right-24 top-10 h-80 w-80 rounded-full bg-lilac/10 blur-[100px]" /><div className="relative flex items-center gap-3"><div className="grid h-10 w-10 place-items-center rounded-xl border border-acid/30 bg-acid/10"><Boxes className="h-5 w-5 text-acid" /></div><p className="font-semibold">ImageVault <span className="text-acid">AI</span></p></div><motion.h1 initial={{ opacity: 0, y: 24 }} animate={{ opacity: 1, y: 0 }} className="relative my-auto max-w-2xl text-6xl font-semibold leading-[1.02] tracking-[-.055em]">Find the photo<br /><span className="text-muted">you’re thinking of.</span></motion.h1></section>
    <section className="flex min-h-screen items-center justify-center p-5 sm:p-10"><motion.div key={pathname} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="w-full max-w-md"><div className="mb-10 flex items-center gap-3 lg:hidden"><div className="grid h-9 w-9 place-items-center rounded-xl bg-acid/10"><Boxes className="h-4 w-4 text-acid" /></div><p className="font-semibold">ImageVault <span className="text-acid">AI</span></p></div><p className="eyebrow mb-3">{registerMode ? "Create account" : "Welcome back"}</p><h2 className="text-3xl font-semibold tracking-[-.04em]">{registerMode ? "Create your vault" : "Sign in"}</h2>
      <form className="mt-8 space-y-4" onSubmit={submit}>
        {registerMode && <label className="block"><span className="mb-2 block text-xs font-medium text-muted">Display name</span><input required minLength={2} autoComplete="name" value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} placeholder="Your name" className="focus-ring h-12 w-full rounded-xl border border-line bg-panel px-4 text-sm placeholder:text-muted/50" /></label>}
        <label className="block"><span className="mb-2 block text-xs font-medium text-muted">Email address</span><input required type="email" autoComplete="email" value={form.email} onChange={(event) => setForm({ ...form, email: event.target.value })} placeholder="you@example.com" className="focus-ring h-12 w-full rounded-xl border border-line bg-panel px-4 text-sm placeholder:text-muted/50" /></label>
        <label className="block"><span className="mb-2 block text-xs font-medium text-muted">Password</span><div className="relative"><input required minLength={8} type={showPassword ? "text" : "password"} autoComplete={registerMode ? "new-password" : "current-password"} value={form.password} onChange={(event) => setForm({ ...form, password: event.target.value })} placeholder="At least 8 characters" className="focus-ring h-12 w-full rounded-xl border border-line bg-panel px-4 pr-12 text-sm placeholder:text-muted/50" /><button type="button" onClick={() => setShowPassword(!showPassword)} aria-label={showPassword ? "Hide password" : "Show password"} className="focus-ring absolute right-3 top-2.5 rounded-lg p-1.5 text-muted">{showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}</button></div></label>
        {registerMode && config?.registration_requires_code && <label className="block"><span className="mb-2 block text-xs font-medium text-muted">Invitation code</span><input required type="password" maxLength={256} autoComplete="off" value={form.invitation} onChange={(event) => setForm({ ...form, invitation: event.target.value })} placeholder="Ask the vault owner for an invitation" className="focus-ring h-12 w-full rounded-xl border border-line bg-panel px-4 text-sm placeholder:text-muted/50" /></label>}
        {registerMode && config?.registration_enabled === false && <p role="status" className="rounded-xl border border-line bg-panel p-4 text-sm text-muted">New accounts are closed. Existing members can still sign in.</p>}
        {error && <div role="alert" className="rounded-xl border border-red-500/20 bg-red-500/10 px-4 py-3 text-sm text-red-200">{error}</div>}
        <Button type="submit" loading={busy} disabled={registerMode && (!config || !config.registration_enabled)} className="mt-2 h-12 w-full">{registerMode ? "Create account" : "Sign in"}<ArrowRight className="h-4 w-4" /></Button>
      </form>{(registerMode || config?.registration_enabled) && <p className="mt-6 text-center text-sm text-muted">{registerMode ? "Already have an account?" : "New here?"} <Link className="focus-ring rounded text-ink underline decoration-line underline-offset-4 hover:decoration-acid" to={registerMode ? "/login" : "/register"}>{registerMode ? "Sign in" : "Create an account"}</Link></p>}
    </motion.div></section>
  </div>;
}
