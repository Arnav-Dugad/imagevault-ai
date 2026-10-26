import { useCallback, useEffect, useState } from "react";
import { Download, ReceiptText, Store } from "lucide-react";
import { PhotoThumb } from "../components/PhotoCard";
import { PhotoViewer } from "../components/PhotoViewer";
import { Button, EmptyState, ErrorNote, PageHeading, Spinner } from "../components/ui";
import { api } from "../lib/api";
import { csvFile } from "../lib/files";
import type { Spending } from "../types";

const money = (amount: number, currency: string) =>
  `${currency}${amount.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
const day = (iso: string) => new Date(`${iso}T00:00:00`).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });

/** Totals in each currency, e.g. "₹1,820.50 · €14.21" (receipts that don't say are shown without a sign). */
function Totals({ totals }: { totals: Record<string, number> }) {
  const entries = Object.entries(totals).sort((a, b) => (a[0] === "₹" ? -1 : b[0] === "₹" ? 1 : 0));
  if (!entries.length) return <>–</>;
  return <>{entries.map(([currency, amount], i) => <span key={currency}>{i > 0 && " · "}{money(amount, currency)}</span>)}</>;
}

export function ReceiptsPage() {
  const [spending, setSpending] = useState<Spending | null>(null);
  const [error, setError] = useState("");
  const [openId, setOpenId] = useState<string | null>(null);
  const load = useCallback(() => { api<Spending>("/receipts").then(setSpending).catch((e: Error) => setError(e.message)); }, []);
  useEffect(load, [load]);

  if (error) return <ErrorNote message={error} />;
  if (!spending) return <Spinner />;

  function exportCsv() {
    const rows: (string | number | null)[][] = [["Shop", "Date", "Total", "Currency", "Photo"]];
    for (const shop of spending!.shops) {
      for (const r of shop.receipts) rows.push([shop.name, r.date, r.total, r.currency, r.photo.filename]);
    }
    csvFile("imagevault-receipts.csv", rows);
  }

  const ids = spending.shops.flatMap((s) => s.receipts.map((r) => r.photo.id));
  const withTotal = spending.shops.reduce((n, s) => n + s.receipts.filter((r) => r.total !== null).length, 0);
  const rupees = spending.totals["₹"] ?? 0;
  return <>
    <PageHeading title="Receipts" description="Spending read from photos of your bills. Check each one against its photo."
      action={spending.count > 0 && <Button variant="secondary" onClick={exportCsv}><Download className="h-4 w-4" />Download CSV</Button>} />

    {spending.count === 0 ? (
      <EmptyState icon={ReceiptText} title="No receipts yet">
        Upload photos of bills and receipts. Once the AI has read them, the shop, date and total appear here.
      </EmptyState>
    ) : <>
      <div className="mb-8 grid grid-cols-2 gap-3 sm:grid-cols-3">
        <div className="panel col-span-2 p-5 sm:col-span-1"><p className="text-sm text-muted">Total spent</p><p className="mt-2 text-2xl font-semibold tabular-nums"><Totals totals={spending.totals} /></p>
          {withTotal < spending.count && <p className="mt-1 text-xs text-muted">From the {withTotal} of {spending.count} receipts with a total</p>}</div>
        <div className="panel p-5"><p className="text-sm text-muted">Receipts</p><p className="mt-2 text-2xl font-semibold">{spending.count}</p></div>
        <div className="panel p-5"><p className="text-sm text-muted">Shops</p><p className="mt-2 text-2xl font-semibold">{spending.shops.length}</p></div>
      </div>

      <div className="space-y-6">
        {spending.shops.map((shop, s) => (
          <section key={shop.name} className="pop-in panel overflow-hidden" style={{ animationDelay: `${s * 60}ms`, animationFillMode: "backwards" }}>
            <header className="flex flex-wrap items-center justify-between gap-2 border-b border-line px-4 py-3 sm:px-5">
              <h2 className="flex items-center gap-2 font-semibold"><Store className="h-4 w-4 text-acid" />{shop.name}
                <span className="text-sm font-normal text-muted">· {shop.receipts.length} {shop.receipts.length === 1 ? "receipt" : "receipts"}</span></h2>
              <span className="text-sm font-semibold tabular-nums"><Totals totals={shop.totals} /></span>
            </header>
            {rupees > 0 && (shop.totals["₹"] ?? 0) > 0 && <div className="h-1 bg-white/[.04]" title={`${Math.round((shop.totals["₹"] / rupees) * 100)}% of the spending in rupees`}>
              <div className="grow-x h-full origin-left bg-acid/70" style={{ width: `${(shop.totals["₹"] / rupees) * 100}%`, animationDelay: `${200 + s * 60}ms` }} />
            </div>}
            <ul className="divide-y divide-line">
              {shop.receipts.map((r) => (
                <li key={r.photo.id}>
                  <button onClick={() => setOpenId(r.photo.id)} className="focus-ring flex w-full items-center gap-3 px-4 py-2.5 text-left hover:bg-white/[.03] sm:px-5">
                    <PhotoThumb photo={r.photo} className="h-11 w-14 shrink-0 rounded-lg" />
                    <span className="min-w-0 flex-1">
                      <span className="block text-sm">{r.date ? day(r.date) : <span className="text-muted">No date found</span>}</span>
                      <span className="block truncate text-xs text-muted">{r.photo.filename}</span>
                    </span>
                    <span className="shrink-0 text-sm font-semibold tabular-nums">{r.total !== null ? money(r.total, r.currency) : <span className="font-normal text-muted">No total found</span>}</span>
                  </button>
                </li>
              ))}
            </ul>
          </section>
        ))}
      </div>
    </>}
    {openId && <PhotoViewer id={openId} ids={ids} onClose={() => setOpenId(null)} onDeleted={load} onChanged={load} />}
  </>;
}
