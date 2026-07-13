"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import TopNav from "../components/TopNav";
import {
  fetchWatchlistTickers,
  getJson,
  money,
  pct,
  signalClass,
  toggleWatch,
  type ListItem,
  type Summary,
} from "../lib/api";

export default function Dashboard() {
  const [summary, setSummary] = useState<Summary | null>(null);
  const [analyses, setAnalyses] = useState<ListItem[]>([]);
  const [watched, setWatched] = useState<Set<string>>(new Set());
  const [minimum, setMinimum] = useState(95);
  const [maxPrice, setMaxPrice] = useState(0);
  const [minVolume, setMinVolume] = useState(0);
  const [signal, setSignal] = useState("all");
  const [sortBy, setSortBy] = useState("score");
  const [sortOrder, setSortOrder] = useState("desc");
  const [search, setSearch] = useState("");
  const [assetType, setAssetType] = useState("Stock");
  const [watchedOnly, setWatchedOnly] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const controller = new AbortController();
    const query = new URLSearchParams({
      min_upside: String(assetType === "ETF" ? -100 : minimum),
      asset_type: assetType,
      ...(maxPrice ? { max_price: String(maxPrice) } : {}),
      ...(minVolume ? { min_volume: String(minVolume) } : {}),
      ...(signal !== "all" ? { signal } : {}),
      ...(watchedOnly ? { watched_only: "true" } : {}),
      ...(search ? { search } : {}),
      sort_by: sortBy,
      sort_order: sortOrder,
      limit: "250",
    });
    setLoading(true);
    Promise.all([
      getJson<Summary>("/api/research/opportunities/summary", controller.signal),
      getJson<ListItem[]>(`/api/research/opportunities/list?${query}`, controller.signal),
      fetchWatchlistTickers().catch(() => new Set<string>()),
    ])
      .then(([nextSummary, nextAnalyses, nextWatched]) => {
        setSummary(nextSummary);
        setAnalyses(nextAnalyses);
        setWatched(nextWatched);
        setError("");
        setLoading(false);
      })
      .catch((reason) => {
        if (reason.name !== "AbortError") {
          setError("Research data is not available yet. Run the analyzer, then refresh.");
          setLoading(false);
        }
      });
    return () => controller.abort();
  }, [minimum, maxPrice, minVolume, signal, sortBy, sortOrder, search, assetType, watchedOnly]);

  const onToggleWatch = useCallback(
    async (ticker: string) => {
      const isWatched = watched.has(ticker);
      setWatched((current) => {
        const next = new Set(current);
        if (isWatched) next.delete(ticker);
        else next.add(ticker);
        return next;
      });
      try {
        await toggleWatch(ticker, isWatched);
      } catch {
        setWatched((current) => {
          const next = new Set(current);
          if (isWatched) next.add(ticker);
          else next.delete(ticker);
          return next;
        });
      }
    },
    [watched],
  );

  return (
    <>
      <TopNav online={summary ? true : error ? false : undefined} />
      <main className="shell">
        <div className="pageHead">
          <div>
            <span className="eyebrow">Evidence-first equity research</span>
            <h1>Opportunity screener</h1>
            <p>
              Transparent valuations from public SEC filings and delayed end-of-day prices. Every
              conclusion exposes its assumptions, catalysts, risks, and primary sources.
            </p>
          </div>
        </div>

        <div className="statRow">
          <div className="stat">
            <span>Eligible securities</span>
            <strong>{summary?.eligible_count.toLocaleString() ?? "—"}</strong>
          </div>
          <div className="stat">
            <span>Analyzed</span>
            <strong>{summary?.analysis_count.toLocaleString() ?? "—"}</strong>
            <small>{summary ? `${summary.failed_count.toLocaleString()} retrying` : ""}</small>
          </div>
          <div className="stat stat--accent">
            <span>90%+ modeled upside</span>
            <strong>{summary?.qualified_count ?? "—"}</strong>
          </div>
          <div className="stat">
            <span>Last model run</span>
            <strong style={{ fontSize: 17 }}>
              {summary?.last_analysis_at
                ? new Date(summary.last_analysis_at).toLocaleString(undefined, {
                    month: "short",
                    day: "numeric",
                    hour: "2-digit",
                    minute: "2-digit",
                  })
                : "—"}
            </strong>
          </div>
        </div>

        {summary && (
          <div className="coverage">
            <b className="num">{summary.coverage_pct.toFixed(1)}%</b>
            <div className="coverageTrack" aria-label={`${summary.coverage_pct}% analyzed`}>
              <i style={{ width: `${Math.min(summary.coverage_pct, 100)}%` }} />
            </div>
            <p>
              {summary.analysis_count.toLocaleString()} analyzed · {summary.remaining_count.toLocaleString()} remaining
            </p>
          </div>
        )}

        <div className="filterBar">
          <label>
            Asset type
            <select value={assetType} onChange={(event) => setAssetType(event.target.value)}>
              <option value="Stock">Stocks</option>
              <option value="ETF">ETFs</option>
              <option value="all">All</option>
            </select>
          </label>
          <label>
            Search
            <input
              type="search"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Ticker or company"
            />
          </label>
          <label>
            Min upside
            <select value={minimum} disabled={assetType === "ETF"} onChange={(event) => setMinimum(Number(event.target.value))}>
              <option value={-100}>All analyzed</option>
              <option value={50}>50%+</option>
              <option value={90}>90%+</option>
              <option value={95}>95%+</option>
              <option value={100}>100%+</option>
              <option value={200}>200%+</option>
            </select>
          </label>
          <label>
            Max price
            <select value={maxPrice} onChange={(event) => setMaxPrice(Number(event.target.value))}>
              <option value={0}>Any</option>
              <option value={5}>Below $5</option>
              <option value={10}>Below $10</option>
              <option value={20}>Below $20</option>
              <option value={50}>Below $50</option>
            </select>
          </label>
          <label>
            Min volume
            <select value={minVolume} onChange={(event) => setMinVolume(Number(event.target.value))}>
              <option value={0}>Any</option>
              <option value={100000}>100K+</option>
              <option value={500000}>500K+</option>
              <option value={1000000}>1M+</option>
              <option value={5000000}>5M+</option>
            </select>
          </label>
          <label>
            Signal
            <select value={signal} onChange={(event) => setSignal(event.target.value)}>
              <option value="all">All signals</option>
              <option value="Bullish">Bullish</option>
              <option value="Neutral">Neutral</option>
              <option value="Bearish">Bearish</option>
            </select>
          </label>
          <label>
            Rank by
            <select value={sortBy} onChange={(event) => setSortBy(event.target.value)}>
              <option value="score">Opportunity score</option>
              <option value="upside">Upside</option>
              <option value="name">Company name</option>
              <option value="ticker">Ticker</option>
              <option value="price">Share price</option>
              <option value="volume">Daily volume</option>
            </select>
          </label>
          <label>
            Direction
            <select value={sortOrder} onChange={(event) => setSortOrder(event.target.value)}>
              <option value="desc">Highest first</option>
              <option value="asc">Lowest first</option>
            </select>
          </label>
          <button className={`toggleChip${watchedOnly ? " on" : ""}`} onClick={() => setWatchedOnly((value) => !value)}>
            ★ Watchlist only
          </button>
        </div>

        <p className="notice" style={{ marginTop: 0 }}>
          {assetType === "ETF"
            ? "ETF mode ranks transparent trend and liquidity signals. It does not invent a corporate fair value for a fund."
            : "Technical confirmation supports timing, not the fair-value calculation. Open a stock for the full evidence trail."}
        </p>

        {error && <div className="notice notice--error">{error}</div>}
        {!error && !loading && analyses.length === 0 && (
          <div className="notice">
            {watchedOnly
              ? "No watchlisted securities match the current filters."
              : "No securities meet this threshold in the current model run. That is a valid result — not a fabricated opportunity."}
          </div>
        )}

        <div className="tableWrap">
          <table>
            <thead>
              <tr>
                <th style={{ width: 34 }} aria-label="Watch" />
                <th>Company</th>
                <th>Type</th>
                <th className="r">Price</th>
                <th className="r">1D</th>
                <th className="r">Fair value</th>
                <th className="r">Upside</th>
                <th className="r">Volume</th>
                <th className="r">Score</th>
                <th>Signal</th>
                <th>Conf.</th>
                <th>Risk</th>
                <th>Primary evidence</th>
              </tr>
            </thead>
            <tbody>
              {analyses.map((item) => {
                const technicalOnly =
                  item.company.asset_type === "ETF" || item.qualification === "Technical Screen Only";
                const indicators = item.technical_indicators ?? {};
                const change = indicators.change_1d_pct;
                return (
                  <tr key={item.company.ticker}>
                    <td>
                      <button
                        className={`watchStar${watched.has(item.company.ticker) ? " on" : ""}`}
                        title={watched.has(item.company.ticker) ? "Remove from watchlist" : "Add to watchlist"}
                        onClick={() => onToggleWatch(item.company.ticker)}
                      >
                        {watched.has(item.company.ticker) ? "★" : "☆"}
                      </button>
                    </td>
                    <td className="tickerCell">
                      <Link href={`/stocks/${item.company.ticker}`}>
                        <strong>{item.company.ticker}</strong>
                        <span>{item.company.name}</span>
                      </Link>
                    </td>
                    <td><b className="assetBadge">{item.company.asset_type}</b></td>
                    <td className="r num">{money(item.current_price)}</td>
                    <td className={`r num ${change == null ? "dim" : change >= 0 ? "up" : "down"}`}>{pct(change)}</td>
                    <td className="r num">{technicalOnly ? <span className="dim">n/a</span> : money(item.fair_value)}</td>
                    <td className={`r num ${technicalOnly ? "dim" : item.upside_pct >= 90 ? "up" : ""}`}>
                      {technicalOnly ? "n/a" : `${item.upside_pct.toFixed(1)}%`}
                    </td>
                    <td className="r num">{item.volume ? item.volume.toLocaleString() : <span className="dim">—</span>}</td>
                    <td className="r">
                      <b className={`scoreBadge${item.opportunity_score >= 70 ? " scoreBadge--hi" : item.opportunity_score >= 45 ? " scoreBadge--mid" : ""}`}>
                        {item.opportunity_score}
                      </b>
                    </td>
                    <td>
                      <span className={signalClass(indicators.signal ?? "pending")}>
                        {indicators.signal ?? "Pending"}
                      </span>
                    </td>
                    <td><b className="gradeBadge">{item.confidence_grade}</b></td>
                    <td className={item.risk_level === "High" ? "down" : item.risk_level === "Low" ? "up" : ""}>{item.risk_level}</td>
                    <td style={{ maxWidth: 240, overflow: "hidden", textOverflow: "ellipsis" }}>
                      {item.catalysts[0]?.title ?? <span className="dim">No positive rule triggered</span>}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        <footer className="siteFooter">
          <span>Stock Intelligence · deterministic research terminal</span>
          <span>Research support — not investment advice</span>
        </footer>
      </main>
    </>
  );
}
