import { useEffect, useState } from "react";
import { PiggyBank } from "lucide-react";
import { api } from "../lib/api";
import { cn, formatDate, rupees } from "../lib/utils";
import type { CostReport } from "../types";

/** If spending continues at the same rate, what the month will cost (Azure bills by UTC month). */
function forecast(amount: number) {
  const now = new Date();
  const days = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth() + 1, 0)).getUTCDate();
  const elapsed = Math.max(1, now.getUTCDate() - 1 + now.getUTCHours() / 24);
  return amount / elapsed * days;
}

/** This month's Azure spending for the project, read live from Azure Cost Management. */
export function CostCard() {
  const [report, setReport] = useState<CostReport | null>(null);
  const [shown, setShown] = useState(0); // animated count-up value
  useEffect(() => { api<CostReport>("/costs").then(setReport).catch(() => setReport({ configured: false, budget: null, inr_rate: 1 })); }, []);

  const rate = report?.inr_rate ?? 1; // Azure bills in US dollars; show rupees
  const amount = (report?.amount ?? 0) * rate;
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

  const budget = report?.budget ? report.budget * rate : null;
  const used = budget ? Math.min(1, amount / budget) : 0;
  const expected = forecast(amount);
  const expectedShare = budget ? Math.min(1, expected / budget) : 0;
  const tone = expectedShare >= 1 || used >= 0.8 ? "bg-coral" : used >= 0.5 ? "bg-amber-300" : "bg-acid";

  return (
    <section className="panel p-5 sm:p-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="flex items-center gap-2 font-semibold"><PiggyBank className="h-4 w-4 text-acid" />This month's Azure cost</h2>
          <p className="mt-1 text-sm text-muted">From Azure Cost Management.</p>
        </div>
        {report?.configured && !report.error && (
          <p className="shrink-0 text-right text-3xl font-semibold tabular-nums tracking-tight">{rupees(shown)}</p>
        )}
      </div>

      {!report && <div className="skeleton mt-5 h-3 w-full rounded-full" />}
      {report && !report.configured && (
        <p className="mt-4 text-sm text-muted">Shown when running on Azure.</p>
      )}
      {report?.error && <p className="mt-4 text-sm text-coral">{report.error}</p>}
      {report?.configured && !report.error && <>
        {budget && <div className="mt-5">
          <div className="relative">
            <div className="h-2.5 overflow-hidden rounded-full bg-raised">
              <div className={cn("h-full rounded-full transition-[width] duration-1000 ease-out", tone)} style={{ width: `${Math.max(used * 100, amount > 0 ? 2 : 0)}%` }} />
            </div>
            {expected > amount && <span title={`Forecast: ${rupees(expected)}`}
              className="absolute -top-1 h-[18px] w-0.5 -translate-x-1/2 rounded-full bg-ink/70" style={{ left: `${Math.max(expectedShare * 100, 1)}%` }} />}
          </div>
          <div className="mt-2 flex flex-wrap justify-between gap-x-4 gap-y-1 text-xs text-muted">
            <span>{Math.round(used * 100)}% of the {rupees(budget)} monthly budget</span>
            <span className={cn(expectedShare >= 1 && "text-coral")}>On track for <b className="font-semibold text-ink">{rupees(expected)}</b> by the end of the month</span>
          </div>
        </div>}
        {report.services && report.services.length > 0 && (
          <ul className="mt-4 divide-y divide-line rounded-xl border border-line text-sm">
            {report.services.map((service) => (
              <li key={service.name} className="flex justify-between gap-4 px-3 py-2"><span className="text-muted">{service.name}</span><span className="tabular-nums">{rupees(service.amount * rate)}</span></li>
            ))}
          </ul>
        )}
        <p className="mt-3 text-xs text-muted">
          {report.currency !== "INR" && `Billed in ${report.currency ?? "USD"}, shown at ₹${rate.toFixed(2)} per ${report.currency === "USD" || !report.currency ? "$1" : report.currency} · `}
          Azure updates costs a few times a day · checked {report.updated_at && formatDate(report.updated_at)}
        </p>
      </>}
    </section>
  );
}
