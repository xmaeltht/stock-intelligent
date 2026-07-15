"use client";

import { useEffect, useMemo, useState } from "react";
import TopNav from "../../components/TopNav";
import { getJson, type BacktestBucket, type BacktestResponse } from "../../lib/api";

const RATING_TONE: Record<string, string> = {
  "Strong Buy": "strongbuy",
  Buy: "buy",
  Accumulate: "accumulate",
  Hold: "hold",
  Reduce: "reduce",
  Sell: "sell",
};

const fmtPct = (value: number | null | undefined) =>
  value == null ? "—" : `${value > 0 ? "+" : ""}${value.toFixed(2)}%`;

export default function BacktestPage() {
  const [data, setData] = useState<BacktestResponse | null>(null);
  const [error, setError] = useState("");
  const [horizon, setHorizon] = useState("3M");

  useEffect(() => {
    getJson<BacktestResponse>("/api/research/opportunities/backtest")
      .then((payload) => {
        setData(payload);
        if (payload.horizons.length) setHorizon(payload.horizons[1]?.label ?? payload.horizons[0].label);
      })
      .catch(() => setError("The backtest needs more accumulated history before it can report results."));
  }, []);

  const bench = data?.benchmark[horizon];
  const maxAbs = useMemo(() => {
    if (!data) return 1;
    const values = data.ratings
      .map((r) => r.by_horizon[horizon]?.avg_return_pct)
      .filter((v): v is number => v != null)
      .map(Math.abs);
    return Math.max(...values, Math.abs(bench?.avg_return_pct ?? 0), 1);
  }, [data, horizon, bench]);

  const thin = data && data.sample_size < 30;

  return (
    <>
      <TopNav online={data ? true : error ? false : undefined} />
      <main className="shell">
        <div className="pageHead">
          <div>
            <span className="eyebrow">Provable, not promised</span>
            <h1>Rating backtest</h1>
            <p>
              Every rating this engine has ever assigned, measured against what the security actually did next.
              We recompute each historical rating from the stored snapshot and track its forward return —
              so you can audit whether the ratings work instead of trusting a number. This is a diagnostic of
              the rules&apos; historical behavior, not a forecast or investment advice.
            </p>
          </div>
        </div>

        {error && <div className="notice notice--error">{error}</div>}
        {!data && !error && <p className="notice">Running the backtest…</p>}

        {data && (
          <>
            <div className="liveStrip">
              <span className="liveMetric"><b className="num">{data.sample_size.toLocaleString()}</b> rating observations</span>
              <span className="liveMetric"><b className="num">{data.universe.toLocaleString()}</b> securities</span>
              <span className="liveMetric dim">since {data.since ?? "—"}</span>
              <div className="rangePicker" style={{ marginLeft: "auto" }}>
                {data.horizons.map((h) => (
                  <button
                    key={h.label}
                    className={`rangeBtn${horizon === h.label ? " rangeBtn--reset" : ""}`}
                    onClick={() => setHorizon(h.label)}
                  >
                    {h.label}
                  </button>
                ))}
              </div>
            </div>

            {thin && (
              <div className="notice">
                Only {data.sample_size} matured observations so far — results will sharpen as the analyzer accumulates history.
              </div>
            )}

            <div className="tableWrap">
              <table>
                <thead>
                  <tr>
                    <th>Rating</th>
                    <th>Avg forward return ({horizon})</th>
                    <th className="r">Avg</th>
                    <th className="r">Median</th>
                    <th className="r">Hit rate</th>
                    <th className="r">Observations</th>
                  </tr>
                </thead>
                <tbody>
                  {data.ratings.map((row) => {
                    const bucket: BacktestBucket | undefined = row.by_horizon[horizon];
                    const avg = bucket?.avg_return_pct ?? null;
                    const width = avg == null ? 0 : (Math.abs(avg) / maxAbs) * 50;
                    const positive = (avg ?? 0) >= 0;
                    return (
                      <tr key={row.rating}>
                        <td><span className={`ratingBadge rating--${RATING_TONE[row.rating]}`}>{row.rating}</span></td>
                        <td>
                          <div className="btBarTrack">
                            <div className="btBarZero" />
                            <div
                              className={`btBar ${positive ? "btBar--up" : "btBar--down"}`}
                              style={{ width: `${width}%`, [positive ? "left" : "right"]: "50%" } as React.CSSProperties}
                            />
                          </div>
                        </td>
                        <td className={`r num ${avg == null ? "dim" : positive ? "up" : "down"}`}>{fmtPct(avg)}</td>
                        <td className={`r num ${(bucket?.median_return_pct ?? 0) >= 0 ? "" : "down"}`}>{fmtPct(bucket?.median_return_pct)}</td>
                        <td className="r num">{bucket?.hit_rate_pct != null ? `${bucket.hit_rate_pct}%` : "—"}</td>
                        <td className="r num dim">{bucket?.n?.toLocaleString() ?? "0"}</td>
                      </tr>
                    );
                  })}
                  <tr className="btBenchmark">
                    <td><b>Universe avg</b></td>
                    <td><span className="dim" style={{ fontSize: 12 }}>baseline — every observation</span></td>
                    <td className={`r num ${(bench?.avg_return_pct ?? 0) >= 0 ? "" : "down"}`}>{fmtPct(bench?.avg_return_pct)}</td>
                    <td className="r num">{fmtPct(bench?.median_return_pct)}</td>
                    <td className="r num">{bench?.hit_rate_pct != null ? `${bench.hit_rate_pct}%` : "—"}</td>
                    <td className="r num dim">{bench?.n?.toLocaleString() ?? "0"}</td>
                  </tr>
                </tbody>
              </table>
            </div>

            <p className="notice" style={{ marginTop: 4 }}>
              Read this as: does a higher rating actually precede a higher forward return, and beat the universe baseline?
              A working rating shows Strong Buy &gt; Buy &gt; … &gt; Sell in average return and a hit rate above 50% at the top.
              Forward returns use each security&apos;s own price series; past behavior does not guarantee future results.
            </p>
          </>
        )}

        <footer className="siteFooter">
          <span>Backtested on the analyzer&apos;s own rating history</span>
          <span>Research support — not investment advice</span>
        </footer>
      </main>
    </>
  );
}
