import { useCallback, useEffect, useState, type FormEvent } from "react";
import { ChevronLeft, ChevronRight, Eye, LoaderCircle, ReceiptText, RotateCcw, Smartphone, X, XCircle } from "lucide-react";
import { api } from "../lib/api";
import { useToast } from "../lib/toast";
import { cn, squeeze } from "../lib/utils";
import type { PhotoDetails, Receipt } from "../types";
import { Button, ErrorNote, Modal } from "./ui";

type Field = "shop" | "date" | "total";
type Box = [number, number, number, number];
const FIELDS: { key: Field; label: string; color: string; dot: string }[] = [
  { key: "shop", label: "Shop", color: "border-acid text-acid", dot: "bg-acid" },
  { key: "date", label: "Date", color: "border-sky-300 text-sky-300", dot: "bg-sky-300" },
  { key: "total", label: "Total", color: "border-amber-300 text-amber-300", dot: "bg-amber-300" },
];
const money = (amount: number, currency: string) =>
  `${currency}${amount.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

interface Form { shop: string; date: string; total: string; currency: string }
const toForm = (r: Receipt | null): Form =>
  ({ shop: r?.shop ?? "", date: r?.date ?? "", total: r?.total != null ? String(r.total) : "", currency: r?.currency || "₹" });

/** Where the shop name, the date and the total are written on the photo, to outline them. */
function findBoxes(photo: PhotoDetails, receipt: Receipt): Partial<Record<Field, Box[]>> {
  const boxes: Partial<Record<Field, Box[]>> = {};
  const shop = receipt.shop ? squeeze(receipt.shop) : "";
  const first = shop ? photo.words.find((w) => squeeze(w.text).length >= 3 && shop.includes(squeeze(w.text))) : undefined;
  if (first) boxes.shop = photo.words.filter((w) => w.line === first.line && shop.includes(squeeze(w.text))).map((w) => w.box);
  const written = photo.found.dates.find((d) => d.iso === receipt.date)?.text;
  const date = written && photo.words.find((w) => /\d/.test(w.text) && (written.includes(w.text) || w.text.includes(written)));
  if (date) boxes.date = [date.box];
  if (receipt.total !== null) {
    const digits = receipt.total.toFixed(2).replace(/\D/g, "");
    const total = photo.words.filter((w) => w.text.replace(/\D/g, "") === digits).at(-1);
    if (total) boxes.total = [total.box];
  }
  return boxes;
}

/** A receipt next to what was read from it, to check and correct by hand. ← → move through `ids`. */
export function ReceiptView({ id, ids, onClose, onChanged, onOpenPhoto }: {
  id: string; ids: string[]; onClose: () => void; onChanged: () => void; onOpenPhoto: (id: string) => void;
}) {
  const toast = useToast();
  const [currentId, setCurrentId] = useState(id);
  const [photo, setPhoto] = useState<PhotoDetails | null>(null);
  const [form, setForm] = useState<Form>(toForm(null));
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState<"save" | "undo" | "remove" | null>(null);

  useEffect(() => {
    setPhoto(null); setLoaded(false); setError("");
    api<PhotoDetails>(`/photos/${currentId}`)
      .then((p) => { setPhoto(p); setForm(toForm(p.receipt)); })
      .catch((e: Error) => setError(e.message));
  }, [currentId]);

  const index = ids.indexOf(currentId);
  const prevId = index > 0 ? ids[index - 1] : null;
  const nextId = index >= 0 && index < ids.length - 1 ? ids[index + 1] : null;
  const go = useCallback((target: string | null) => { if (target) setCurrentId(target); }, []);
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if ((event.target as HTMLElement).closest("input, select")) return;
      if (event.key === "ArrowLeft") go(prevId);
      if (event.key === "ArrowRight") go(nextId);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [go, prevId, nextId]);

  const receipt = photo?.receipt ?? null;
  const saved = toForm(receipt);
  const dirty = (Object.keys(form) as (keyof Form)[]).filter((key) => form[key] !== saved[key]);
  const edited = receipt?.edited ?? [];
  const boxes = photo && receipt ? findBoxes(photo, receipt) : {};
  const itemsTotal = receipt?.items.reduce((sum, item) => sum + item.amount, 0) ?? 0;

  async function send(action: "save" | "undo" | "remove", request: () => Promise<{ receipt: Receipt | null }>, message: string) {
    setBusy(action);
    try {
      const { receipt: fresh } = await request();
      onChanged();
      toast(message);
      if (!fresh) { // no longer a receipt: show the next one
        if (nextId || prevId) go(nextId ?? prevId); else onClose();
        return;
      }
      setPhoto((p) => (p ? { ...p, receipt: fresh } : p));
      setForm(toForm(fresh));
    } catch (e) {
      toast((e as Error).message, true);
    } finally {
      setBusy(null);
    }
  }

  function save(event: FormEvent) {
    event.preventDefault();
    if (!dirty.length) return;
    const body: Record<string, unknown> = receipt ? {} : { receipt: true };
    for (const key of dirty) {
      if (key === "total") body.total = form.total.trim() === "" ? null : Number(form.total);
      else if (key === "shop") body.shop = form.shop.trim() || null;
      else body[key] = form[key] || null;
    }
    void send("save", () => api(`/photos/${currentId}/receipt`, { method: "PUT", body: JSON.stringify(body) }), "Saved");
  }

  return (
    <Modal onClose={onClose} className="max-w-5xl">
      <div className="grid grid-cols-[minmax(0,1fr)] lg:h-[86vh] lg:grid-cols-[minmax(0,1fr)_360px]">
        <div className="relative grid min-h-[40vh] place-items-center bg-black/40 p-3 lg:min-h-0">
          {photo && <div className="relative">
            <img src={photo.file_url} alt={photo.filename} onLoad={() => setLoaded(true)} className="block max-h-[80vh] w-auto rounded-lg object-contain" />
            {loaded && <span key={photo.id} className="scan-line once" aria-hidden />}
            {loaded && FIELDS.flatMap(({ key, label, color }, f) => (boxes[key] ?? []).map((box, i) => (
              <span key={`${photo.id}-${key}-${i}`} className={cn("face-box pointer-events-none absolute rounded-md border-2 shadow-[0_0_0_1px_rgba(0,0,0,.45)]", color)}
                style={{ left: `${box[0] * 100}%`, top: `${box[1] * 100}%`, width: `${box[2] * 100}%`, height: `${box[3] * 100}%`, animationDelay: `${1100 + f * 150}ms` }}>
                {i === 0 && <span className="absolute -top-5 left-0 whitespace-nowrap rounded bg-canvas/90 px-1 text-[10px] font-semibold uppercase tracking-wide">{label}</span>}
              </span>)))}
          </div>}
          {(!photo || !loaded) && !error && <LoaderCircle className="absolute h-6 w-6 animate-spin text-acid" />}
          {prevId && <button onClick={() => go(prevId)} aria-label="Previous receipt (←)" className="focus-ring absolute left-5 top-1/2 -translate-y-1/2 rounded-full bg-black/50 p-2 text-white backdrop-blur transition hover:bg-black/70"><ChevronLeft className="h-5 w-5" /></button>}
          {nextId && <button onClick={() => go(nextId)} aria-label="Next receipt (→)" className="focus-ring absolute right-5 top-1/2 -translate-y-1/2 rounded-full bg-black/50 p-2 text-white backdrop-blur transition hover:bg-black/70"><ChevronRight className="h-5 w-5" /></button>}
          {index >= 0 && <span className="absolute bottom-5 left-1/2 -translate-x-1/2 rounded-full bg-black/50 px-2.5 py-1 text-xs text-white/80 backdrop-blur">{index + 1} / {ids.length}</span>}
        </div>

        <aside className="flex flex-col border-t border-line p-5 lg:min-h-0 lg:overflow-y-auto lg:border-l lg:border-t-0">
          <div className="flex items-start gap-3">
            <span className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-acid/10 text-acid">
              {receipt?.kind === "payment" ? <Smartphone className="h-4 w-4" /> : <ReceiptText className="h-4 w-4" />}</span>
            <div className="min-w-0 flex-1">
              <h2 className="font-semibold">{receipt?.kind === "payment" ? "Payment screenshot" : "Receipt"}</h2>
              <p className="truncate text-xs text-muted" title={photo?.filename}>{photo?.filename ?? " "}</p>
            </div>
            <button onClick={onClose} aria-label="Close" className="focus-ring rounded-lg p-1.5 text-muted hover:bg-white/5 hover:text-ink"><X className="h-5 w-5" /></button>
          </div>
          {error && <div className="mt-4"><ErrorNote message={error} /></div>}

          {photo && <>
            <p className="mt-4 text-sm text-muted">Check what was read against the photo, and fix anything that's wrong.</p>
            <form onSubmit={save} className="mt-4 space-y-3">
              {FIELDS.map(({ key, label, dot }) => (
                <label key={key} className="block">
                  <span className="mb-1 flex items-center gap-1.5 text-xs font-medium text-muted">
                    <span className={cn("h-2 w-2 rounded-full", dot, !boxes[key] && "opacity-30")} />{label}
                    {edited.includes(key) && <span className="rounded-full border border-line px-1.5 text-[10px]">corrected</span>}
                  </span>
                  {key === "total" ? <div className="flex gap-2">
                    <select value={form.currency} onChange={(e) => setForm({ ...form, currency: e.target.value })} aria-label="Currency"
                      className="focus-ring h-10 rounded-xl border border-line bg-panel px-2 text-sm [color-scheme:dark]">
                      {["₹", "$", "€", "£"].map((c) => <option key={c}>{c}</option>)}
                    </select>
                    <input type="number" inputMode="decimal" min="0" step="0.01" value={form.total} placeholder="Not found"
                      onChange={(e) => setForm({ ...form, total: e.target.value })} className="focus-ring h-10 min-w-0 flex-1 rounded-xl border border-line bg-panel px-3 text-sm tabular-nums" />
                  </div> : <input type={key === "date" ? "date" : "text"} value={form[key]} maxLength={80} placeholder="Not found"
                    onChange={(e) => setForm({ ...form, [key]: e.target.value })} className="focus-ring h-10 w-full rounded-xl border border-line bg-panel px-3 text-sm [color-scheme:dark]" />}
                </label>
              ))}
              <div className="flex flex-wrap gap-2 pt-1">
                {(dirty.length > 0 || !edited.length) && <Button type="submit" disabled={!dirty.length} loading={busy === "save"}>Save changes</Button>}
                {dirty.length > 0 && <Button type="button" variant="ghost" onClick={() => setForm(saved)}>Cancel</Button>}
                {!dirty.length && edited.length > 0 && <Button type="button" variant="ghost" loading={busy === "undo"}
                  onClick={() => void send("undo", () => api(`/photos/${currentId}/receipt`, { method: "DELETE" }), "Back to what the AI read")}>
                  <RotateCcw className="h-4 w-4" />Use the AI's reading</Button>}
              </div>
            </form>

            {receipt && receipt.items.length > 0 && <section className="mt-6">
              <h3 className="text-xs font-semibold uppercase tracking-wide text-muted">Items</h3>
              <ul className="mt-2 divide-y divide-line rounded-xl border border-line text-sm">
                {receipt.items.map((item, i) => (
                  <li key={i} className="pop-in flex justify-between gap-3 px-3 py-2" style={{ animationDelay: `${i * 40}ms`, animationFillMode: "backwards" }}>
                    <span className="min-w-0 truncate">{item.name}</span><span className="shrink-0 tabular-nums text-muted">{money(item.amount, receipt.currency)}</span>
                  </li>))}
              </ul>
              {receipt.total !== null && Math.abs(itemsTotal - receipt.total) > 0.01 && <p className="mt-2 text-xs text-muted">
                The items add up to {money(itemsTotal, receipt.currency)}; the rest is usually tax.</p>}
            </section>}

            <div className="mt-auto flex flex-wrap gap-2 pt-6">
              <Button variant="secondary" onClick={() => onOpenPhoto(currentId)}><Eye className="h-4 w-4" />Open photo</Button>
              {receipt && <Button variant="ghost" className="hover:text-coral" loading={busy === "remove"}
                onClick={() => void send("remove", () => api(`/photos/${currentId}/receipt`, { method: "PUT", body: JSON.stringify({ receipt: false }) }), "Removed from Receipts")}>
                <XCircle className="h-4 w-4" />Not a receipt</Button>}
            </div>
          </>}
        </aside>
      </div>
    </Modal>
  );
}
