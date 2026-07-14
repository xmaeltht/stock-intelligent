"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import TopNav from "../components/TopNav";
import Sparkline from "../components/Sparkline";
import {
  fetchWatchlistTickers,
  getJson,
  isFresh,
  money,
  pct,
  ratingFor,
  signalClass,
  timeAgo,
  toggleWatch,
  type ListItem,
  type SectorsResponse,
  type Summary,
} from "../lib/api";

const POLL_MS = 12000;

export default function Dashboard() {
  const [summary, setSummary] = useState<Summary | null>(null);
  const [analyses, setAnalyses] = useState<ListItem[]>([]);
  const [watched, setWatched] = useState<Set<string>>(new Set());
  const [minimum, setMinimum] = useState(-100);
  const [maxPrice, setMaxPrice] = useState(0);
  const [minVolume, setMinVolume] = useState(0);
  const [signal, setSignal] = useState("all");
  const [sortBy, setSortBy] = useState("rating");
  const [sortOrder, setSortOrder] = useState("desc");
  const [search, setSearch] = useState("");
  const [assetType, setAssetType] = useState("Stock");
  const [sector, setSector] = useState("all");
  const [sectors, setSectors] = useState<SectorsResponse | null>(null);
  const [watchedOnly, setWatchedOnly] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [flash, setFlash] = useState<Record<string, "up" | "down">>({});
  const [nowMs, setNowMs] = useState(() => Date.now());
  const [live, setLive] = useState(true);
  // Once the URL filters have been read back into state (so we can restore the
  // exact view on browser-back instead of resetting to the default screener).
  const [hydrated, setHydrated] = useState(false);

  const prices = useRef<Map<string, number>>(new Map());
  const reqId = useRef(0);
  const flashTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const load = useCallback(
    async (silent: boolean) => {
      const query = new URLSearchParams({
        min_upside: String(assetType === "ETF" ? -100 : minimum),
        asset_type: assetType,
        ...(maxPrice ? { max_price: String(maxPrice) } : {}),
        ...(minVolume ? { min_volume: String(minVolume) } : {}),
        ...(signal !== "all" ? { signal } : {}),
        ...(watchedOnly ? { watched_only: "true" } : {}),
        ...(search ? { search } : {}),
        ...(sector !== "all" ? { sector } : {}),
        sort_by: sortBy,
        sort_order: sortOrder,
        limit: "250",
      });
      const id = ++reqId.current;
      if (!silent) setLoading(true);
      try {
        const [nextSummary, nextAnalyses, nextWatched] = await Promise.all([
          getJson<Summary>("/api/research/opportunities/summary"),
          getJson<ListItem[]>(`/api/research/opportunities/list?${query}`),
          silent ? Promise.resolve(null) : fetchWatchlistTickers().catch(() => new Set<string>()),
        ]);
        if (id !== reqId.current) return; // a newer request superseded this one

        // Flash rows whose price moved since the previous poll.
        const nextFlash: Record<string, "up" | "down"> = {};
        for (const item of nextAnalyses) {
          const prev = prices.current.get(item.company.ticker);
          const now = Number(item.current_price);
          if (prev != null && now !== prev) nextFlash[item.company.ticker] = now > prev ? "up" : "down";
          prices.current.set(item.company.ticker, now);
        }
        setSummary(nextSummary);
        setAnalyses(nextAnalyses);
        if (nextWatched) setWatched(nextWatched);
        setError("");
        setLoading(false);
        if (Object.keys(nextFlash).length) {
          setFlash(nextFlash);
          if (flashTimer.current) clearTimeout(flashTimer.current);
          flashTimer.current = setTimeout(() => setFlash({}), 1100);
        }
      } catch {
        if (id === reqId.current && !silent) {
          setError("Research data is not available yet. Run the analyzer, then refresh.");
          setLoading(false);
        }
      }
    },
    [minimum, maxPrice, minVolume, signal, sortBy, sortOrder, search, sector, assetType, watchedOnly],
  );

  // Load the sector list (with counts) for the sector filter.
  useEffect(() => {
    getJson<SectorsResponse>(`/api/research/opportunities/sectors?asset_type=${assetType}`)
      .then(setSectors)
      .catch(() => setSectors(null));
  }, [assetType]);

  // Restore filters from the URL once on mount, so returning to this page (via
  // browser back or the detail page's Back button) rebuilds the view you left.
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const get = (key: string) => params.get(key);
    if (get("asset")) setAssetType(get("asset") as string);
    if (get("sector")) setSector(get("sector") as string);
    if (get("sort")) setSortBy(get("sort") as string);
    if (get("order")) setSortOrder(get("order") as string);
    if (get("min")) setMinimum(Number(get("min")));
    if (get("q")) setSearch(get("q") as string);
    if (get("signal")) setSignal(get("signal") as string);
    if (get("maxp")) setMaxPrice(Number(get("maxp")));
    if (get("vol")) setMinVolume(Number(get("vol")));
    if (get("watch") === "1") setWatchedOnly(true);
    setHydrated(true);
  }, []);

  // Mirror the active filters into the URL (replaceState → no history spam), so
  // the entry we leave when opening a stock already encodes the view.
  useEffect(() => {
    if (!hydrated) return;
    const params = new URLSearchParams();
    if (assetType !== "Stock") params.set("asset", assetType);
    if (sector !== "all") params.set("sector", sector);
    if (sortBy !== "rating") params.set("sort", sortBy);
    if (sortOrder !== "desc") params.set("order", sortOrder);
    if (minimum !== -100) params.set("min", String(minimum));
    if (search) params.set("q", search);
    if (signal !== "all") params.set("signal", signal);
    if (maxPrice) params.set("maxp", String(maxPrice));
    if (minVolume) params.set("vol", String(minVolume));
    if (watchedOnly) params.set("watch", "1");
    const qs = params.toString();
    window.history.replaceState(null, "", qs ? `?${qs}` : window.location.pathname);
  }, [hydrated, assetType, sector, sortBy, sortOrder, minimum, search, signal, maxPrice, minVolume, watchedOnly]);

  // Reload on any filter change (with the loading state), after URL restore.
  useEffect(() => {
    if (!hydrated) return;
    prices.current.clear();
    load(false);
  }, [load, hydrated]);

  // Silent auto-poll so the screen updates live without a manual refresh.
  useEffect(() => {
    if (!live) return;
    const timer = setInterval(() => {
      if (!document.hidden) load(true);
    }, POLL_MS);
    return () => clearInterval(timer);
  }, [live, load]);

  // Tick a clock so "updated Xs ago" labels count up between polls.
  useEffect(() => {
    const timer = setInterval(() => setNowMs(Date.now()), 1000);
    return () => clearInterval(timer);
  }, []);

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

  const toggleSort = (key: string) => {
    if (sortBy === key) {
      setSortOrder((order) => (order === "desc" ? "asc" : "desc"));
    } else {
      setSortBy(key);
      setSortOrder(key === "name" || key === "ticker" ? "asc" : "desc");
    }
  };
  const arrow = (key: string) => (sortBy === key ? (sortOrder === "desc" ? " ↓" : " ↑") : "");

  return (
    <>
      <TopNav online={summary ? true : error ? false : undefined} />
      <main className="shell">
        <div className="pageHead">
          <div>
            <span className="eyebrow">Evidence-first equity research</span>
            <h1>Opportunity screener</h1>
            <p>
              Transparent valuations from public SEC filings and live-refreshed prices. Every
              conclusion exposes its assumptions, catalysts, risks, and primary sources.
            </p>
          </div>
        </div>

        {summary && (
          <div className="liveStrip">
            <span className={`livePulse${summary.market_open ? " open" : ""}`}>
              <i />
              {summary.market_open ? "Market open · live scanning" : "Market closed · background scanning"}
            </span>
            <span className="liveMetric">
              <b className="num">{summary.prices_updated_last_min.toLocaleString()}</b> prices / min
            </span>
            <span className="liveMetric">
              <b className="num">{summary.analyses_last_5min.toLocaleString()}</b> re-analyzed / 5 min
            </span>
            <span className="liveMetric dim">
              newest quote {timeAgo(summary.newest_price_at, nowMs)} ago
            </span>
            <button
              className={`toggleChip liveToggle${live ? " on" : ""}`}
              onClick={() => setLive((value) => !value)}
              title="Toggle automatic live refresh"
            >
              {live ? "● Live" : "⏸ Paused"}
            </button>
          </div>
        )}

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
            <span>Last deep model run</span>
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
            Sector
            <select value={sector} onChange={(event) => setSector(event.target.value)}>
              <option value="all">All sectors</option>
              {sectors?.sectors.map((entry) => (
                <option key={entry.sector} value={entry.sector}>
                  {entry.sector} ({entry.count.toLocaleString()})
                </option>
              ))}
            </select>
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
              <option value="rating">Rating (Strong Buy first)</option>
              <option value="score">Opportunity score</option>
              <option value="upside">Upside</option>
              <option value="change_1d">1D change</option>
              <option value="change_5d">5D change</option>
              <option value="signal">Signal (bullish→bearish)</option>
              <option value="rsi">RSI-14</option>
              <option value="price">Share price</option>
              <option value="volume">Daily volume</option>
              <option value="confidence">Confidence grade</option>
              <option value="risk">Risk level</option>
              <option value="name">Company name</option>
              <option value="ticker">Ticker</option>
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

        <div className="resultBar">
          <span className="resultCount">
            {loading ? "Loading…" : `${analyses.length}${analyses.length >= 250 ? "+" : ""} securities`}
            {analyses.length >= 250 && <em> · showing top 250 — narrow filters or search to refine</em>}
          </span>
          <span className="resultHint">
            {assetType === "ETF"
              ? "ETFs ranked on trend & liquidity — no fabricated fair value."
              : "Technical confirmation supports timing, not the fair-value calc."}
          </span>
        </div>

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
                <th className={`sortable${sortBy === "ticker" ? " sorted" : ""}`} onClick={() => toggleSort("ticker")}>Company{arrow("ticker")}</th>
                <th className="r sortable" onClick={() => toggleSort("price")}>Price{arrow("price")}</th>
                <th className={`r sortable${sortBy === "change_1d" ? " sorted" : ""}`} onClick={() => toggleSort("change_1d")}>1D{arrow("change_1d")}</th>
                <th>Trend</th>
                <th className="r">Fair value</th>
                <th className={`r sortable${sortBy === "upside" ? " sorted" : ""}`} onClick={() => toggleSort("upside")} title="Potential upside from the current price to the modeled fair value">Upside{arrow("upside")}</th>
                <th className={`r sortable${sortBy === "volume" ? " sorted" : ""}`} onClick={() => toggleSort("volume")}>Volume{arrow("volume")}</th>
                <th className={`r sortable${sortBy === "score" ? " sorted" : ""}`} onClick={() => toggleSort("score")}>Score{arrow("score")}</th>
                <th className={`sortable${sortBy === "rating" ? " sorted" : ""}`} onClick={() => toggleSort("rating")}>Rating{arrow("rating")}</th>
                <th className={`sortable${sortBy === "signal" ? " sorted" : ""}`} onClick={() => toggleSort("signal")}>Signal{arrow("signal")}</th>
                <th className={`sortable${sortBy === "rsi" ? " sorted" : ""}`} onClick={() => toggleSort("rsi")}>RSI{arrow("rsi")}</th>
                <th className={`sortable${sortBy === "confidence" ? " sorted" : ""}`} onClick={() => toggleSort("confidence")}>Conf.{arrow("confidence")}</th>
                <th className={`sortable${sortBy === "risk" ? " sorted" : ""}`} onClick={() => toggleSort("risk")}>Risk{arrow("risk")}</th>
                <th>Updated</th>
              </tr>
            </thead>
            <tbody>
              {analyses.map((item) => {
                const technicalOnly =
                  item.company.asset_type === "ETF" || item.qualification === "Technical Screen Only";
                const indicators = item.technical_indicators ?? {};
                const change = indicators.change_1d_pct;
                const fresh = isFresh(item.price_as_of, nowMs);
                const flashDir = flash[item.company.ticker];
                const rating = ratingFor({
                  upsidePct: item.upside_pct,
                  technicalOnly,
                  signal: indicators.signal,
                  rsi: indicators.rsi14,
                  risk: item.risk_level,
                  score: item.opportunity_score,
                  trendCross: indicators.trend_cross,
                });
                return (
                  <tr key={item.company.ticker} className={flashDir ? `flash flash--${flashDir}` : ""}>
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
                      {item.company.sector && (
                        <button
                          className="sectorTag"
                          title={`Filter by ${item.company.sector}`}
                          onClick={() => setSector(item.company.sector as string)}
                        >
                          {item.company.sector}
                        </button>
                      )}
                    </td>
                    <td className="r num priceCell">
                      <i className={`freshDot${fresh ? " live" : ""}`} title={`Updated ${timeAgo(item.price_as_of ?? item.as_of, nowMs)} ago`} />
                      {money(item.current_price)}
                    </td>
                    <td className={`r num ${change == null ? "dim" : change >= 0 ? "up" : "down"}`}>{pct(change)}</td>
                    <td><Sparkline values={indicators.spark} /></td>
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
                      <span className={`ratingBadge rating--${rating.slug}`}>{rating.label}</span>
                    </td>
                    <td>
                      <span className={signalClass(indicators.signal ?? "pending")}>
                        {indicators.signal ?? "Pending"}
                      </span>
                    </td>
                    <td className="num">{indicators.rsi14 ?? <span className="dim">—</span>}</td>
                    <td><b className="gradeBadge">{item.confidence_grade}</b></td>
                    <td className={item.risk_level === "High" ? "down" : item.risk_level === "Low" ? "up" : ""}>{item.risk_level}</td>
                    <td className="dim updatedCell">{timeAgo(item.price_as_of ?? item.as_of, nowMs)}</td>
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
