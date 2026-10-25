import { useEffect, useState } from "react";
import { PiggyBank } from "lucide-react";
import { api } from "../lib/api";
import { cn, formatDate } from "../lib/utils";
import type { CostReport } from "../types";

function money(amount: number, currency = "USD") {
  return new Intl.NumberFormat("en", { style: "currency", currency, minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(amount);
}

/** This month's Azure spending for the project, read live from Azure Cost Management. */
export function CostCard() {
  const [report, setReport] = useState<CostReport | null>(null);
  const [shown, setShown] = useState(0); // animated count-up value
  useEffect(() => { api<CostReport>("/costs").then(setReport).catch(() => setReport({ configured: false, budget: null })); }, []);

  const amount = report?.amount ?? 0;
  useEffect(() => {
    if (!report?.amount) return;
    const start = performance.now();
    let frame = 0;
    const tick = (now: number) => {
      const progress = Math.min(1, (now - start) / 900);
      setShown(amount * (1 - (1 - progress) ** 3));
      if (progress < 1) frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [report, amount]);

  const budget = report?.budget ?? null;
  const used = budget ? Math.min(1, amount / budget) : 0;
  const tone = used >= 0.8 ? "bg-coral" : used >= 0.5 ? "bg-amber-300" : "bg-acid";

  return (
    <section className="panel p-5 sm:p-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="flex items-center gap-2 font-semibold"><PiggyBank className="h-4 w-4 text-acid" />This month's Azure cost</h2>
          <p className="mt-1 text-sm text-muted">From Azure Cost Management.</p>
        </div>
        {report?.configured && !report.error && (
          <p className="shrink-0 text-right text-3xl font-semibold tabular-nums tracking-tight">{money(shown, report.currency)}</p>
        )}
      </div>

      {!report && <div className="skeleton mt-5 h-3 w-full rounded-full" />}
      {report && !report.configured && (
        <p className="mt-4 text-sm text-muted">Shown when running on Azure.</p>
      )}
      {report?.error && <p className="mt-4 text-sm text-coral">{report.error}</p>}
      {report?.configured && !report.error && <>
        {budget && <div className="mt-5">
          <div className="h-2.5 overflow-hidden rounded-full bg-raised">
            <div className={cn("h-full rounded-full transition-[width] duration-1000 ease-out", tone)} style={{ width: `${Math.max(used * 100, amount > 0 ? 2 : 0)}%` }} />
          </div>
          <p className="mt-2 text-xs text-muted">{Math.round(used * 100)}% of the {money(budget, report.currency)} monthly budget</p>
        </div>}
        {report.services && report.services.length > 0 && (
          <ul className="mt-4 divide-y divide-line rounded-xl border border-line text-sm">
            {report.services.map((service) => (
              <li key={service.name} className="flex justify-between gap-4 px-3 py-2"><span className="text-muted">{service.name}</span><span className="tabular-nums">{money(service.amount, report.currency)}</span></li>
            ))}
          </ul>
        )}
        <p className="mt-3 text-xs text-muted">Azure updates costs a few times a day · checked {report.updated_at && formatDate(report.updated_at)}</p>
      </>}
    </section>
  );
}
