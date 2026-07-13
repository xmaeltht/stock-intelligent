"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import TopNav from "../../components/TopNav";
import { getJson, money, pct, signalClass, toggleWatch, type WatchlistRow } from "../../lib/api";

export default function WatchlistPage() {
  const [rows, setRows] = useState<WatchlistRow[] | null>(null);
  const [error, setError] = useState("");

  const load = useCallback(() => {
    getJson<WatchlistRow[]>("/api/research/watchlist")
      .then(setRows)
      .catch(() => setError("The watchlist could not be loaded."));
  }, []);

  useEffect(load, [load]);

  const remove = async (ticker: string) => {
    setRows((current) => current?.filter((row) => row.ticker !== ticker) ?? null);
    try {
      await toggleWatch(ticker, true);
    } catch {
      load();
    }
  };

  const compareHref = rows?.length
    ? `/compare?tickers=${rows.slice(0, 6).map((row) => row.ticker).join(",")}`
    : "/compare";

  return (
    <>
      <TopNav online={rows ? true : error ? false : undefined} />
      <main className="shell">
        <div className="pageHead">
          <div>
            <span className="eyebrow">Tracked securities</span>
            <h1>Watchlist</h1>
            <p>Securities you starred, with their latest model rating. Ratings refresh automatically as the continuous analyzer re-rates each security.</p>
          </div>
          {rows && rows.length > 1 && (
            <Link className="btn" href={compareHref}>Compare side by side →</Link>
          )}
        </div>

        {error && <div className="notice notice--error">{error}</div>}
        {rows && rows.length === 0 && (
          <div className="notice">
            Nothing here yet. Star a security from the <Link href="/" style={{ color: "#74aef0" }}>screener</Link> or a stock page to track it.
          </div>
        )}

        {rows && rows.length > 0 && (
          <div className="tableWrap">
            <table>
              <thead>
                <tr>
                  <th style={{ width: 34 }} aria-label="Remove" />
                  <th>Company</th>
                  <th>Type</th>
                  <th className="r">Price</th>
                  <th className="r">1D</th>
                  <th className="r">Fair value</th>
                  <th className="r">Upside</th>
                  <th className="r">Score</th>
                  <th>Signal</th>
                  <th>Risk</th>
                  <th>Added</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => {
                  const latest = row.latest;
                  const indicators = latest?.technical_indicators ?? {};
                  const technicalOnly =
                    row.asset_type === "ETF" || latest?.qualification === "Technical Screen Only";
                  const change = indicators.change_1d_pct;
                  return (
                    <tr key={row.ticker}>
                      <td>
                        <button className="watchStar on" title="Remove from watchlist" onClick={() => remove(row.ticker)}>★</button>
                      </td>
                      <td className="tickerCell">
                        <Link href={`/stocks/${row.ticker}`}>
                          <strong>{row.ticker}</strong>
                          <span>{row.name}</span>
                        </Link>
                      </td>
                      <td><b className="assetBadge">{row.asset_type}</b></td>
                      <td className="r num">{latest ? money(latest.current_price) : <span className="dim">pending</span>}</td>
                      <td className={`r num ${change == null ? "dim" : change >= 0 ? "up" : "down"}`}>{pct(change)}</td>
                      <td className="r num">{latest && !technicalOnly ? money(latest.fair_value) : <span className="dim">n/a</span>}</td>
                      <td className={`r num ${latest && !technicalOnly && latest.upside_pct >= 90 ? "up" : ""}`}>
                        {latest && !technicalOnly ? `${latest.upside_pct.toFixed(1)}%` : <span className="dim">n/a</span>}
                      </td>
                      <td className="r">
                        {latest ? (
                          <b className={`scoreBadge${latest.opportunity_score >= 70 ? " scoreBadge--hi" : latest.opportunity_score >= 45 ? " scoreBadge--mid" : ""}`}>
                            {latest.opportunity_score}
                          </b>
                        ) : (
                          <span className="dim">—</span>
                        )}
                      </td>
                      <td><span className={signalClass(indicators.signal ?? "pending")}>{indicators.signal ?? "Pending"}</span></td>
                      <td className={latest?.risk_level === "High" ? "down" : latest?.risk_level === "Low" ? "up" : ""}>
                        {latest?.risk_level ?? "—"}
                      </td>
                      <td className="dim num">{new Date(row.created_at).toLocaleDateString()}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        <footer className="siteFooter">
          <span>Watchlist stored locally in your research database</span>
          <span>Research support — not investment advice</span>
        </footer>
      </main>
    </>
  );
}
