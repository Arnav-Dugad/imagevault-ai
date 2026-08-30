import { motion } from "framer-motion";
import { ArrowRight, Boxes, CheckCircle2, Database, Eye, EyeOff, Fingerprint, Server } from "lucide-react";
import { FormEvent, useState } from "react";
import { Navigate, Link, useLocation, useNavigate } from "react-router-dom";
import { ApiError } from "../lib/api";
import { useAuth } from "../providers/AuthProvider";
import { Button } from "../components/ui";

export function AuthPage() {
  const { pathname } = useLocation();
  const registerMode = pathname === "/register";
  const { user, login, register } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({ name: "", email: "", password: "" });
  const [showPassword, setShowPassword] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  if (user) return <Navigate to="/" replace />;

  async function submit(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError("");
    try {
      if (registerMode) await register(form.email, form.name, form.password);
      else await login(form.email, form.password);
      navigate("/");
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : "Could not reach your private vault");
    } finally { setBusy(false); }
  }

  return <div className="grain min-h-screen bg-[#090b0e] lg:grid lg:grid-cols-[1.08fr_.92fr]">
    <section className="relative hidden min-h-screen overflow-hidden border-r border-line p-12 lg:flex lg:flex-col xl:p-16">
      <div className="absolute -left-40 top-1/3 h-96 w-96 rounded-full bg-acid/10 blur-[110px]" /><div className="absolute -right-24 top-10 h-80 w-80 rounded-full bg-lilac/10 blur-[100px]" />
      <div className="relative flex items-center gap-3"><div className="grid h-10 w-10 place-items-center rounded-xl border border-acid/30 bg-acid/10"><Boxes className="h-5 w-5 text-acid" /></div><p className="font-semibold">ImageVault <span className="text-acid">AI</span></p></div>
      <motion.div initial={{ opacity: 0, y: 24 }} animate={{ opacity: 1, y: 0 }} className="relative my-auto max-w-2xl">
        <p className="eyebrow mb-5 text-acid">Private by architecture</p><h1 className="text-5xl font-semibold leading-[1.02] tracking-[-.055em] xl:text-7xl">Your photos.<br /><span className="text-muted">Less repetition.</span><br />More meaning.</h1><p className="mt-7 max-w-lg text-base leading-7 text-muted">Store images in your own S3-compatible cloud, surface byte-perfect copies instantly, and find visual variations with AI that never leaves your laptop.</p>
        <div className="mt-10 grid max-w-xl grid-cols-3 gap-3">{[[Fingerprint,"SHA-256","Exact files"],[Database,"pgvector","Similarity"],[Server,"Minikube","Private cloud"]].map(([Icon,label,copy]) => { const ItemIcon = Icon as typeof Fingerprint; return <div key={label as string} className="rounded-2xl border border-line bg-white/[.025] p-4"><ItemIcon className="mb-5 h-4 w-4 text-acid" /><p className="font-mono text-xs text-ink">{label as string}</p><p className="mt-1 text-xs text-muted">{copy as string}</p></div>; })}</div>
      </motion.div>
      <div className="relative flex items-center gap-2 font-mono text-[10px] uppercase tracking-widest text-muted"><CheckCircle2 className="h-3.5 w-3.5 text-acid" />No AI API · No cloud bill · Local control</div>
    </section>
    <section className="flex min-h-screen items-center justify-center p-5 sm:p-10"><motion.div key={pathname} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="w-full max-w-md">
      <div className="mb-10 flex items-center gap-3 lg:hidden"><div className="grid h-9 w-9 place-items-center rounded-xl bg-acid/10"><Boxes className="h-4 w-4 text-acid" /></div><p className="font-semibold">ImageVault <span className="text-acid">AI</span></p></div>
      <p className="eyebrow mb-3">{registerMode ? "Create private vault" : "Welcome back"}</p><h2 className="text-3xl font-semibold tracking-[-.04em]">{registerMode ? "Start organizing intelligently." : "Enter your image cloud."}</h2><p className="mt-3 text-sm leading-6 text-muted">{registerMode ? "Your account, objects, and similarity index remain inside your local environment." : "Sign in to your self-hosted ImageVault workspace."}</p>
      <form className="mt-8 space-y-4" onSubmit={submit}>
        {registerMode && <label className="block"><span className="mb-2 block text-xs font-medium text-muted">Display name</span><input required minLength={2} autoComplete="name" value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} placeholder="Your name" className="focus-ring h-12 w-full rounded-xl border border-line bg-panel px-4 text-sm placeholder:text-muted/50" /></label>}
        <label className="block"><span className="mb-2 block text-xs font-medium text-muted">Email address</span><input required type="email" autoComplete="email" value={form.email} onChange={(event) => setForm({ ...form, email: event.target.value })} placeholder="you@example.com" className="focus-ring h-12 w-full rounded-xl border border-line bg-panel px-4 text-sm placeholder:text-muted/50" /></label>
        <label className="block"><span className="mb-2 block text-xs font-medium text-muted">Password</span><div className="relative"><input required minLength={8} type={showPassword ? "text" : "password"} autoComplete={registerMode ? "new-password" : "current-password"} value={form.password} onChange={(event) => setForm({ ...form, password: event.target.value })} placeholder="At least 8 characters" className="focus-ring h-12 w-full rounded-xl border border-line bg-panel px-4 pr-12 text-sm placeholder:text-muted/50" /><button type="button" onClick={() => setShowPassword(!showPassword)} aria-label={showPassword ? "Hide password" : "Show password"} className="focus-ring absolute right-3 top-2.5 rounded-lg p-1.5 text-muted">{showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}</button></div></label>
        {error && <div role="alert" className="rounded-xl border border-red-500/20 bg-red-500/10 px-4 py-3 text-sm text-red-200">{error}</div>}
        <Button type="submit" loading={busy} className="mt-2 h-12 w-full">{registerMode ? "Create my vault" : "Open my vault"}<ArrowRight className="h-4 w-4" /></Button>
      </form>
      <p className="mt-6 text-center text-sm text-muted">{registerMode ? "Already have an account?" : "New to ImageVault?"} <Link className="focus-ring rounded text-ink underline decoration-line underline-offset-4 hover:decoration-acid" to={registerMode ? "/login" : "/register"}>{registerMode ? "Sign in" : "Create an account"}</Link></p>
    </motion.div></section>
  </div>;
}
