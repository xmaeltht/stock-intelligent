"use client";

import { useMemo, useState } from "react";
import { money, type Fundamentals } from "../lib/api";

type Dividend = NonNullable<Fundamentals["dividend"]>;

function Metric({ label, value, tone }: { label: string; value: string; tone?: "up" | "down" | "dim" }) {
  return (
    <article className="divMetric">
      <span>{label}</span>
      <strong className={tone ?? ""}>{value}</strong>
    </article>
  );
}

function Bars({ data }: { data: Array<{ label: string; value: number }> }) {
  if (!data.length) return <p className="dim" style={{ fontSize: 12 }}>No history available.</p>;
  const peak = Math.max(...data.map((d) => d.value), 0.0001);
  return (
    <div className="divBars">
      {data.map((d) => (
        <div key={d.label} className="divBar">
          <em>{d.value >= 1 ? d.value.toFixed(2) : d.value.toFixed(3)}</em>
          <i style={{ height: `${Math.max((d.value / peak) * 100, 2)}%` }} />
          <small>{d.label}</small>
        </div>
      ))}
    </div>
  );
}

export default function DividendSection({ dividend, price }: { dividend?: Dividend; price: number }) {
  const [view, setView] = useState<"annual" | "payments">("annual");
  const [shares, setShares] = useState(100);

  const pays = dividend?.pays;
  const forwardAnnual = dividend?.forward_annual ?? 0;
  const forwardYield = dividend?.forward_yield_pct ?? null;

  const annualBars = useMemo(
    () => (dividend?.annual ?? []).map((a) => ({ label: a.year, value: a.value })),
    [dividend],
  );
  const paymentBars = useMemo(
    () =>
      [...(dividend?.payments ?? [])]
        .reverse()
        .slice(-16)
        .map((p) => ({ label: p.date.slice(2, 7), value: p.amount })),
    [dividend],
  );

  if (!pays) {
    return (
      <section className="panel" style={{ gridColumn: "1 / -1" }}>
        <div className="panelTitle"><h2>Dividend</h2><span className="eyebrow">Income</span></div>
        <p style={{ color: "var(--muted)", lineHeight: 1.6 }}>
          No dividend on record — this security does not currently pay a cash dividend.
        </p>
      </section>
    );
  }

  const projectedIncome = shares * forwardAnnual;
  const amountInvested = shares * price;
  const fmtPct = (v?: number | null) => (v == null ? "—" : `${v > 0 ? "+" : ""}${v}%`);

  return (
    <section className="panel" style={{ gridColumn: "1 / -1" }}>
      <div className="panelTitle">
        <h2>Dividend</h2>
        <span className="eyebrow">{dividend?.frequency ?? "Income"} · per-payment history</span>
      </div>

      <div className="divMetrics">
        <Metric label="Dividend yield (TTM)" value={dividend?.yield_pct != null ? `${dividend.yield_pct}%` : "—"} tone="up" />
        <Metric label="Forward yield" value={forwardYield != null ? `${forwardYield}%` : "—"} tone="up" />
        <Metric label="Annual dividend (TTM)" value={money(dividend?.annual_amount_ttm)} />
        <Metric label="Forward annual" value={money(forwardAnnual)} />
        <Metric label="Frequency" value={dividend?.frequency ?? "—"} />
        <Metric label="Payout ratio" value={dividend?.payout_ratio_pct != null ? `${dividend.payout_ratio_pct}%` : "—"} />
        <Metric label="Growth (1Y)" value={fmtPct(dividend?.growth_1y_pct)} tone={(dividend?.growth_1y_pct ?? 0) >= 0 ? "up" : "down"} />
        <Metric label="Growth streak" value={dividend?.growth_streak_years ? `${dividend.growth_streak_years} yrs` : "—"} />
        <Metric label="Buyback yield" value={dividend?.buyback_yield_pct != null ? `${dividend.buyback_yield_pct}%` : "—"} />
        <Metric label="Shareholder yield" value={dividend?.shareholder_yield_pct != null ? `${dividend.shareholder_yield_pct}%` : "—"} tone="up" />
        <Metric label="Last ex-date" value={dividend?.last_ex_date ?? "—"} />
        <Metric label="Last payment" value={money(dividend?.last_amount)} />
      </div>

      <div className="divChartHead">
        <span className="eyebrow">Dividend history</span>
        <div className="divToggle">
          <button className={view === "annual" ? "on" : ""} onClick={() => setView("annual")}>Annual</button>
          <button className={view === "payments" ? "on" : ""} onClick={() => setView("payments")}>Per payment</button>
        </div>
      </div>
      <Bars data={view === "annual" ? annualBars : paymentBars} />

      <div className="divGrid2">
        <div>
          <span className="eyebrow">Payment history</span>
          <div className="divTableWrap">
            <table className="divTable">
              <thead><tr><th>Ex-dividend date</th><th className="r">Cash amount</th></tr></thead>
              <tbody>
                {(dividend?.payments ?? []).slice(0, 16).map((p) => (
                  <tr key={p.date}><td>{p.date}</td><td className="r num">{money(p.amount)}</td></tr>
                ))}
                {!dividend?.payments?.length && (
                  <tr><td colSpan={2} className="dim">Per-payment schedule not available for this security.</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
        <div>
          <span className="eyebrow">Income calculator</span>
          <div className="divCalc">
            <label>
              Shares held
              <input
                type="number"
                min={0}
                value={shares}
                onChange={(event) => setShares(Math.max(0, Number(event.target.value)))}
              />
            </label>
            <dl className="facts">
              <div><dt>Invested at {money(price)}</dt><dd>{money(amountInvested)}</dd></div>
              <div><dt>Projected annual income</dt><dd className="up">{money(projectedIncome)}</dd></div>
              <div><dt>Per quarter (est.)</dt><dd>{money(projectedIncome / 4)}</dd></div>
              <div><dt>Forward yield</dt><dd>{forwardYield != null ? `${forwardYield}%` : "—"}</dd></div>
            </dl>
            <p className="dim" style={{ fontSize: 11, lineHeight: 1.5 }}>
              Estimate based on the forward annualized dividend run-rate. Not a guarantee of future payments.
            </p>
          </div>
        </div>
      </div>
    </section>
  );
}
