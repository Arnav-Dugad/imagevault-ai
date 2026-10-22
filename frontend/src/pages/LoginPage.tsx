import { useState, type FormEvent } from "react";
import { LockKeyhole } from "lucide-react";
import { Logo } from "../components/Layout";
import { Button, ErrorNote } from "../components/ui";
import { api } from "../lib/api";

export function LoginPage({ onLoggedIn }: { onLoggedIn: () => void }) {
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true); setError("");
    try {
      await api("/login", { method: "POST", body: JSON.stringify({ password }) });
      onLoggedIn();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="grid min-h-screen place-items-center p-4">
      <form onSubmit={submit} className="pop-in panel w-full max-w-sm p-7">
        <Logo />
        <h1 className="mt-8 flex items-center gap-2 text-xl font-semibold"><LockKeyhole className="h-5 w-5 text-acid" />Enter password</h1>
        <p className="mt-1 text-sm text-muted">This ImageVault is private.</p>
        <input type="password" autoFocus required value={password} onChange={(e) => setPassword(e.target.value)} aria-label="Password"
          className="focus-ring mt-5 h-11 w-full rounded-xl border border-line bg-canvas px-3 text-sm" />
        {error && <div className="mt-3"><ErrorNote message={error} /></div>}
        <Button type="submit" loading={busy} className="mt-4 w-full">Open vault</Button>
      </form>
    </div>
  );
}
