"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import TopNav from "../../components/TopNav";
import { getJson, money, pct, signalClass, type Mover, type Overview } from "../../lib/api";

const BREADTH_COLORS: Record<string, string> = {
  Bullish: "#2fbf7f",
  Neutral: "#5f6b7c",
  Bearish: "#e66767",
  Pending: "#2a3648",
};

function BreadthBar({ counts }: { counts: Record<string, number> }) {
  const order = ["Bullish", "Neutral", "Bearish", "Pending"];
  const total = Object.values(counts).reduce((sum, value) => sum + value, 0) || 1;
  return (
    <>
      <div className="breadthBar">
        {order.filter((key) => counts[key]).map((key) => (
          <i key={key} style={{ width: `${(counts[key] / total) * 100}%`, background: BREADTH_COLORS[key] }} />
        ))}
      </div>
      <div className="breadthLegend">
        {order.filter((key) => counts[key]).map((key) => (
          <span key={key}>
            <i style={{ background: BREADTH_COLORS[key] }} />
            {key} {counts[key].toLocaleString()} ({((counts[key] / total) * 100).toFixed(0)}%)
          </span>
        ))}
      </div>
    </>
  );
}

function Distribution({ buckets, color }: { buckets: Array<{ label: string; count: number }>; color: string }) {
  const peak = Math.max(...buckets.map((bucket) => bucket.count), 1);
  return (
    <div className="distChart">
      {buckets.map((bucket) => (
        <div key={bucket.label}>
          <em className="distCount">{bucket.count > 0 ? bucket.count.toLocaleString() : ""}</em>
          <i style={{ height: `${Math.max((bucket.count / peak) * 100, 1.5)}%`, background: color }} />
          <small>{bucket.label}</small>
        </div>
      ))}
    </div>
  );
}

function MoverList({ title, movers, showChange = true }: { title: string; movers: Mover[]; showChange?: boolean }) {
  return (
    <section className="panel">
      <div className="panelTitle"><h2>{title}</h2></div>
      <div style={{ overflow: "auto" }}>
        <table className="moverTable">
          <thead>
            <tr>
              <th>Ticker</th>
              <th className="r">Price</th>
              <th className="r">{showChange ? "1D" : "Volume"}</th>
              <th className="r">Score</th>
              <th>Signal</th>
            </tr>
          </thead>
          <tbody>
            {movers.map((mover) => (
              <tr key={mover.ticker}>
                <td className="tickerCell">
                  <Link href={`/stocks/${mover.ticker}`}>
                    <strong>{mover.ticker}</strong>
                    <span style={{ maxWidth: 150 }}>{mover.name}</span>
                  </Link>
                </td>
                <td className="r num">{money(mover.current_price)}</td>
                {showChange ? (
                  <td className={`r num ${mover.change_1d_pct == null ? "dim" : mover.change_1d_pct >= 0 ? "up" : "down"}`}>
                    {pct(mover.change_1d_pct)}
                  </td>
                ) : (
                  <td className="r num">{mover.volume?.toLocaleString() ?? "—"}</td>
                )}
                <td className="r num">{mover.opportunity_score}</td>
                <td><span className={signalClass(mover.signal)}>{mover.signal ?? "—"}</span></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

export default function MarketPage() {
  const [overview, setOverview] = useState<Overview | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    getJson<Overview>("/api/research/opportunities/overview")
      .then(setOverview)
      .catch(() => setError("Market overview is not available yet. Run the analyzer, then refresh."));
  }, []);

  return (
    <>
      <TopNav online={overview ? true : error ? false : undefined} />
      <main className="shell">
        <div className="pageHead">
          <div>
            <span className="eyebrow">Analyzed universe</span>
            <h1>Market pulse</h1>
            <p>
              Breadth, distribution, and movers across every security the analyzer currently covers.
              Derived from the latest stored analysis of each company — delayed data, not a live feed.
            </p>
          </div>
        </div>

        {error && <div className="notice notice--error">{error}</div>}
        {!overview && !error && <p className="notice">Loading market overview…</p>}

        {overview && (
          <>
            <div className="statRow">
              <div className="stat">
                <span>Eligible securities</span>
                <strong>{overview.summary.eligible_count.toLocaleString()}</strong>
              </div>
              <div className="stat">
                <span>Coverage</span>
                <strong>{overview.summary.coverage_pct.toFixed(1)}%</strong>
                <small>{overview.summary.remaining_count.toLocaleString()} remaining</small>
              </div>
              <div className="stat stat--accent">
                <span>90%+ upside stocks</span>
                <strong>{overview.summary.qualified_count.toLocaleString()}</strong>
              </div>
              <div className="stat">
                <span>Provider failures queued</span>
                <strong>{overview.summary.failed_count.toLocaleString()}</strong>
                <small>retry after cooldown</small>
              </div>
              <div className="stat">
                <span>Last model run</span>
                <strong style={{ fontSize: 17 }}>
                  {overview.summary.last_analysis_at
                    ? new Date(overview.summary.last_analysis_at).toLocaleString(undefined, {
                        month: "short",
                        day: "numeric",
                        hour: "2-digit",
                        minute: "2-digit",
                      })
                    : "—"}
                </strong>
              </div>
            </div>

            <div className="panelGrid grid2" style={{ marginBottom: 14 }}>
              <section className="panel">
                <div className="panelTitle"><h2>Trend signal breadth</h2><span className="eyebrow">6-check confirmation</span></div>
                <BreadthBar counts={overview.signal_breadth} />
              </section>
              <section className="panel">
                <div className="panelTitle"><h2>Impulse MACD breadth</h2><span className="eyebrow">momentum direction</span></div>
                <BreadthBar counts={overview.impulse_breadth} />
              </section>
            </div>

            <div className="panelGrid grid2" style={{ marginBottom: 14 }}>
              <section className="panel">
                <div className="panelTitle"><h2>Opportunity score distribution</h2></div>
                <Distribution buckets={overview.score_distribution} color="#3987e5" />
              </section>
              <section className="panel">
                <div className="panelTitle"><h2>Modeled upside distribution</h2><span className="eyebrow">stocks only</span></div>
                <Distribution buckets={overview.upside_distribution} color="#199e70" />
              </section>
            </div>

            <div className="panelGrid grid2" style={{ marginBottom: 14 }}>
              <MoverList title="Top gainers (1 day)" movers={overview.top_gainers} />
              <MoverList title="Top losers (1 day)" movers={overview.top_losers} />
              <MoverList title="Most active by volume" movers={overview.most_active} showChange={false} />
              <MoverList title="Highest opportunity scores" movers={overview.highest_scores} />
            </div>

            <div className="panelGrid grid2">
              <section className="panel">
                <div className="panelTitle"><h2>By exchange</h2></div>
                {Object.entries(overview.exchange_counts).sort((a, b) => b[1] - a[1]).map(([exchange, count]) => (
                  <div className="kv" key={exchange}><span>{exchange}</span><b>{count.toLocaleString()}</b></div>
                ))}
              </section>
              <section className="panel">
                <div className="panelTitle"><h2>By asset type</h2></div>
                {Object.entries(overview.asset_type_counts).sort((a, b) => b[1] - a[1]).map(([assetType, count]) => (
                  <div className="kv" key={assetType}><span>{assetType}</span><b>{count.toLocaleString()}</b></div>
                ))}
              </section>
            </div>
          </>
        )}

        <footer className="siteFooter">
          <span>Breadth reflects the latest stored analysis per security</span>
          <span>Research support — not investment advice</span>
        </footer>
      </main>
    </>
  );
}
