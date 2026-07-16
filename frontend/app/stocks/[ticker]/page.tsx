"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import dynamic from "next/dynamic";
import Link from "next/link";
import TopNav from "../../../components/TopNav";
import DividendSection from "../../../components/DividendSection";
import FactorRadar from "../../../components/FactorRadar";
import {
  compact,
  fetchWatchlistTickers,
  getJson,
  isFresh,
  money,
  pct,
  ratingFor,
  signalClass,
  timeAgo,
  toggleWatch,
  type Detail,
  type HistoryPoint,
  type PricePoint,
} from "../../../lib/api";

const StockChart = dynamic(() => import("../../../components/StockChart"), {
  ssr: false,
  loading: () => <div className="chartLoading" aria-label="Loading interactive chart" />,
});

function HistoryChart({ history }: { history: HistoryPoint[] }) {
  if (history.length < 2) {
    return <p className="notice" style={{ margin: 0 }}>Analysis history builds up as the analyzer re-rates this security over time.</p>;
  }
  const width = 520;
  const height = 150;
  const pad = 34;
  const prices = history.map((point) => Number(point.current_price));
  const fairs = history.map((point) => Number(point.fair_value));
  const all = [...prices, ...fairs];
  const min = Math.min(...all);
  const max = Math.max(...all);
  const range = max - min || 1;
  const x = (index: number) => pad + (index / (history.length - 1)) * (width - pad * 2);
  const y = (value: number) => 12 + ((max - value) / range) * (height - 34);
  const line = (values: number[]) => values.map((value, index) => `${x(index).toFixed(1)},${y(value).toFixed(1)}`).join(" ");
  return (
    <div style={{ maxWidth: 760 }}>
      <div className="chartLegend">
        <span><i style={{ background: "#3987e5" }} /> Price</span>
        <span><i style={{ background: "#199e70" }} /> Fair value</span>
      </div>
      <svg className="stockChart" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Analysis history: price versus modeled fair value">
        <line x1={pad} x2={width - pad} y1={height - 20} y2={height - 20} className="gridLine" />
        <polyline points={line(prices)} fill="none" stroke="#3987e5" strokeWidth="2" />
        <polyline points={line(fairs)} fill="none" stroke="#199e70" strokeWidth="2" strokeDasharray="5 4" />
        <text x={pad} y={height - 5}>{history[0].price_date}</text>
        <text x={width - pad} y={height - 5} textAnchor="end">{history.at(-1)?.price_date}</text>
      </svg>
    </div>
  );
}

function FiscalBars({ title, series }: { title: string; series: Array<{ fy_end: string; value: number }> }) {
  if (!series.length) return null;
  const peak = Math.max(...series.map((item) => Math.abs(item.value)), 1);
  return (
    <div>
      <span className="eyebrow">{title}</span>
      <div className="miniBars">
        {series.map((item) => (
          <div key={item.fy_end}>
            <em className="miniBarValue">{compact(item.value)}</em>
            <i className={item.value < 0 ? "neg" : ""} style={{ height: `${Math.max((Math.abs(item.value) / peak) * 100, 3)}%` }} />
            <small>{item.fy_end.slice(0, 4)}</small>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function StockPage({ params }: { params: Promise<{ ticker: string }> }) {
  const router = useRouter();
  const goBack = () => {
    // Return to the exact previous view (filtered screener, watchlist, etc.).
    if (typeof window !== "undefined" && window.history.length > 1) router.back();
    else router.push("/");
  };
  const [ticker, setTicker] = useState("");
  const [data, setData] = useState<Detail | null>(null);
  const [history, setHistory] = useState<HistoryPoint[]>([]);
  // The interactive chart binds to a stable history so live polls don't reset zoom.
  const [chartHistory, setChartHistory] = useState<PricePoint[]>([]);
  const [watchedSet, setWatchedSet] = useState<Set<string>>(new Set());
  const [error, setError] = useState("");
  const [nowMs, setNowMs] = useState(() => Date.now());
  const [priceFlash, setPriceFlash] = useState<"up" | "down" | "">("");

  const prevPrice = useRef<number | null>(null);
  const flashTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const load = useCallback(async (value: string, silent: boolean) => {
    try {
      const detail = await getJson<Detail>(`/api/research/opportunities/stocks/${value}`);
      const next = Number(detail.current_price);
      if (prevPrice.current != null && next !== prevPrice.current) {
        setPriceFlash(next > prevPrice.current ? "up" : "down");
        if (flashTimer.current) clearTimeout(flashTimer.current);
        flashTimer.current = setTimeout(() => setPriceFlash(""), 1100);
      }
      prevPrice.current = next;
      setData(detail);
      setChartHistory((current) => (current.length ? current : detail.price_history ?? []));
      if (!silent) {
        getJson<HistoryPoint[]>(`/api/research/opportunities/stocks/${value}/history`)
          .then(setHistory)
          .catch(() => setHistory([]));
      }
    } catch {
      if (!silent) setError("This security has not been analyzed yet.");
    }
  }, []);

  useEffect(() => {
    params.then(({ ticker: value }) => {
      setTicker(value);
      prevPrice.current = null;
      setChartHistory([]);
      load(value, false);
      fetchWatchlistTickers().then(setWatchedSet).catch(() => undefined);
    });
  }, [params, load]);

  // Silent live refresh of the header/indicators (the chart stays put).
  useEffect(() => {
    if (!ticker) return;
    const timer = setInterval(() => {
      if (!document.hidden) load(ticker, true);
    }, 10000);
    return () => clearInterval(timer);
  }, [ticker, load]);

  useEffect(() => {
    const timer = setInterval(() => setNowMs(Date.now()), 1000);
    return () => clearInterval(timer);
  }, []);

  const watched = watchedSet.has(ticker.toUpperCase());
  const onToggleWatch = async () => {
    setWatchedSet((current) => {
      const next = new Set(current);
      if (watched) next.delete(ticker.toUpperCase());
      else next.add(ticker.toUpperCase());
      return next;
    });
    try {
      await toggleWatch(ticker.toUpperCase(), watched);
    } catch {
      setWatchedSet((current) => {
        const next = new Set(current);
        if (watched) next.add(ticker.toUpperCase());
        else next.delete(ticker.toUpperCase());
        return next;
      });
    }
  };

  if (error) {
    return (
      <>
        <TopNav online />
        <main className="shell">
          <button className="backLink" onClick={goBack}>← Back</button>
          <div className="notice notice--error">{error}</div>
        </main>
      </>
    );
  }
  if (!data) {
    return (
      <>
        <TopNav />
        <main className="shell"><p className="notice">Loading {ticker} research…</p></main>
      </>
    );
  }

  const isEtf = data.company.asset_type === "ETF";
  const technicalOnly = isEtf || (data.valuation_methods ?? []).length === 0;
  const indicators = data.technical_indicators ?? {};
  const fundamentals = data.fundamentals ?? {};
  const margins = fundamentals.margins ?? {};
  const ratios = fundamentals.ratios ?? {};
  const change = indicators.change_1d_pct;
  const rating = ratingFor({
    upsidePct: data.upside_pct,
    technicalOnly,
    signal: indicators.signal,
    rsi: indicators.rsi14,
    risk: data.risk_level,
    score: data.opportunity_score,
    trendCross: indicators.trend_cross,
  });

  return (
    <>
      <TopNav online />
      <main className="shell">
        <button className="backLink" onClick={goBack}>← Back</button>
        <div className="stockHead">
          <div>
            <span className="eyebrow">
              {data.company.exchange ?? "US listed"} · {data.company.asset_type}
              {data.company.sector ? ` · ${data.company.sector}` : ""} · {data.qualification}
            </span>
            <h1>{data.company.ticker}</h1>
            <p className="companyName">{data.company.name}</p>
          </div>
          <div style={{ display: "flex", gap: 18, alignItems: "end" }}>
            <Link
              className="btn btn--primary"
              href={`/portfolio?ticker=${encodeURIComponent(data.company.ticker)}&price=${data.current_price}&target=${technicalOnly ? "" : data.fair_value}&stop=${indicators.support ?? (technicalOnly ? "" : data.bear_value)}`}
            >
              Plan paper trade
            </Link>
            <button className={`watchBtn${watched ? " on" : ""}`} onClick={onToggleWatch}>
              {watched ? "★ Watching" : "☆ Watch"}
            </button>
            <div className="priceBlock">
              <span>
                <i className={`freshDot${isFresh(data.price_as_of, nowMs) ? " live" : ""}`} />
                {isFresh(data.price_as_of, nowMs) ? "Live" : "Last"} · updated {timeAgo(data.price_as_of ?? data.as_of, nowMs)} ago
              </span>
              <strong className={priceFlash ? `flashPrice flashPrice--${priceFlash}` : ""}>{money(data.current_price)}</strong>
              <span className={change == null ? "dim" : change >= 0 ? "up" : "down"}>
                {pct(change)} today · {pct(indicators.change_20d_pct)} 20d
              </span>
            </div>
          </div>
        </div>

        <div className="scenarioRow">
          <div className="scenario scenario--rating">
            <span>Rules-based rating</span>
            <strong className={`ratingBadge ratingBadge--lg rating--${rating.slug}`}>{rating.label}</strong>
          </div>
          {!technicalOnly && (
            <>
              <div className="scenario"><span>Bear case</span><strong>{money(data.bear_value)}</strong></div>
              <div className="scenario scenario--fair">
                <span>Base fair value</span>
                <strong>{money(data.fair_value)}</strong>
              </div>
              <div className="scenario"><span>Bull case</span><strong>{money(data.bull_value)}</strong></div>
              <div className="scenario" title="Potential move from the current price to the modeled fair value">
                <span>Upside from current price</span>
                <strong className={data.upside_pct >= 0 ? "up" : "down"}>{data.upside_pct.toFixed(1)}%</strong>
              </div>
            </>
          )}
          <div className="scenario">
            <span>{isEtf ? "Technical score" : "Opportunity score"}</span>
            <strong>{data.opportunity_score}/100</strong>
          </div>
          <div className="scenario">
            <span>Confidence / Risk</span>
            <strong>{data.confidence_grade} / {data.risk_level}</strong>
          </div>
        </div>

        <div className="panelTitle" style={{ marginTop: 26 }}>
          <h2>Price, trend & liquidity</h2>
          <span className={signalClass(indicators.signal)}>{indicators.signal ?? "Pending refresh"}</span>
        </div>

        <div className="indicatorGrid">
          <article><span>Daily volume</span><strong>{data.volume?.toLocaleString() ?? "—"}</strong></article>
          <article>
            <span>Volume trend 20/50</span>
            <strong>{indicators.volume_trend ?? "—"}</strong>
          </article>
          <article><span>RSI 14</span><strong>{indicators.rsi14 ?? "—"}</strong></article>
          <article>
            <span>SMA 20 / 50 / 200</span>
            <strong style={{ fontSize: 12.5 }}>
              {money(indicators.sma20)} / {money(indicators.sma50)} / {money(indicators.sma200)}
            </strong>
          </article>
          <article>
            <span>Bollinger %B</span>
            <strong>{indicators.bb_percent_b != null ? `${indicators.bb_percent_b}%` : "—"}</strong>
          </article>
          <article>
            <span>ATR 14 (volatility)</span>
            <strong>{indicators.atr14 != null ? `${money(indicators.atr14)} · ${indicators.atr_pct}%` : "—"}</strong>
          </article>
          <article>
            <span>Support / Resistance</span>
            <strong style={{ fontSize: 12.5 }}>{money(indicators.support)} / {money(indicators.resistance)}</strong>
          </article>
          <article>
            <span>52-week range</span>
            <strong style={{ fontSize: 12.5 }}>
              {money(indicators.low_52w)} – {money(indicators.high_52w)} ({indicators.range_position_pct ?? "—"}%)
            </strong>
          </article>
          <article>
            <span>Trend cross 50/200</span>
            <strong className={indicators.trend_cross === "Golden cross" ? "up" : indicators.trend_cross === "Death cross" ? "down" : "dim"} style={{ fontSize: 12.5 }}>
              {indicators.trend_cross ? `${indicators.trend_cross} · ${indicators.trend_cross_age_days}d ago` : "None recent"}
            </strong>
          </article>
          <article>
            <span>Impulse MACD</span>
            <strong>{indicators.impulse_macd ?? "—"}</strong>
          </article>
        </div>

        {indicators.checks && (
          <div className="checkList">
            {indicators.checks.map((check) => (
              <span key={check.name} className={`check${check.passed ? " pass" : ""}`}>
                <i>{check.passed ? "✔" : "✕"}</i> {check.name}
              </span>
            ))}
          </div>
        )}

        <StockChart history={chartHistory.length ? chartHistory : data.price_history ?? []} />
        <p className="notice" style={{ marginTop: 0 }}>
          Trend indicators help assess entry timing and liquidity; they do not independently validate the fundamental fair value.
        </p>

        <div className="detailGrid">
          {technicalOnly ? (
            <section className="panel">
              <span className="eyebrow">{isEtf ? "ETF methodology" : "Technical screen only"}</span>
              <h2 style={{ margin: "10px 0" }}>What this score means</h2>
              <p style={{ color: "var(--muted)", lineHeight: 1.6 }}>
                {isEtf
                  ? "This fund is ranked using price trend, RSI, moving averages, and trading liquidity. A corporate earnings-based fair value is intentionally not calculated for a fund."
                  : "No positive revenue, earnings, cash flow, book value, or operating income anchors a valuation for this company, so it is ranked on transparent trend and liquidity signals only. A fair value is intentionally not fabricated."}
              </p>
            </section>
          ) : (
            <>
              <section className="panel">
                <div className="panelTitle"><h2>How the target was calculated</h2><span className="eyebrow">Valuation methods</span></div>
                {data.valuation_methods.map((method) => (
                  <div className="item" key={method.model}>
                    <div><strong>{method.model}</strong><span>{method.multiple}× deterministic multiple</span></div>
                    <b>{money(method.value)}</b>
                  </div>
                ))}
              </section>
              <section className="panel">
                <div className="panelTitle"><h2>What the filing says</h2><span className="eyebrow">Financial evidence</span></div>
                <dl className="facts">
                  <div><dt>Market cap</dt><dd>{compact(fundamentals.market_cap)}</dd></div>
                  <div><dt>Revenue growth (YoY)</dt><dd>{data.revenue_growth_pct != null ? `${data.revenue_growth_pct.toFixed(1)}%` : "—"}</dd></div>
                  <div><dt>Revenue CAGR (multi-year)</dt><dd>{fundamentals.revenue_cagr_pct != null ? `${fundamentals.revenue_cagr_pct}%` : "—"}</dd></div>
                  <div><dt>Net income</dt><dd>{compact(data.net_income)}</dd></div>
                  <div><dt>Free cash flow</dt><dd>{compact(data.free_cash_flow)}</dd></div>
                  <div><dt>Cash / Debt</dt><dd>{compact(data.cash)} / {compact(data.debt)}</dd></div>
                  <div><dt>Shareholder equity</dt><dd>{compact(fundamentals.equity)}</dd></div>
                  <div><dt>Book value / share</dt><dd>{fundamentals.book_value_per_share != null ? money(fundamentals.book_value_per_share) : "—"}</dd></div>
                </dl>
              </section>
              <section className="panel">
                <div className="panelTitle"><h2>Margins & multiples</h2><span className="eyebrow">Profitability</span></div>
                <dl className="facts">
                  <div><dt>Gross margin</dt><dd>{margins.gross_pct != null ? `${margins.gross_pct}%` : "—"}</dd></div>
                  <div><dt>Operating margin</dt><dd>{margins.operating_pct != null ? `${margins.operating_pct}%` : "—"}</dd></div>
                  <div><dt>Net margin</dt><dd>{margins.net_pct != null ? `${margins.net_pct}%` : "—"}</dd></div>
                  <div><dt>FCF margin</dt><dd>{margins.fcf_pct != null ? `${margins.fcf_pct}%` : "—"}</dd></div>
                  <div><dt>P/S · P/E</dt><dd>{ratios.price_to_sales ?? "—"} · {ratios.price_to_earnings ?? "—"}</dd></div>
                  <div><dt>P/FCF · P/B</dt><dd>{ratios.price_to_fcf ?? "—"} · {ratios.price_to_book ?? "—"}</dd></div>
                </dl>
              </section>
              <section className="panel">
                <div className="panelTitle"><h2>Fiscal-year trend</h2><span className="eyebrow">From SEC annual filings</span></div>
                <FiscalBars title="Revenue" series={fundamentals.revenue_history ?? []} />
                <FiscalBars title="Net income" series={fundamentals.net_income_history ?? []} />
              </section>
            </>
          )}

          <section className="panel">
            <div className="panelTitle"><h2>What could unlock value</h2><span className="eyebrow">Catalysts</span></div>
            {data.catalysts.length ? (
              data.catalysts.map((catalyst) => (
                <div className="item" key={catalyst.title}>
                  <div><strong>{catalyst.title}</strong><span>{catalyst.detail}</span></div>
                  <b>{catalyst.status}</b>
                </div>
              ))
            ) : (
              <p style={{ color: "var(--muted)" }}>No deterministic positive catalyst rule triggered.</p>
            )}
          </section>
          <section className="panel">
            <div className="panelTitle"><h2>What could disprove it</h2><span className="eyebrow">Risks & thesis breakers</span></div>
            {data.risks.map((risk) => (
              <div className="item" key={risk.title}>
                <div><strong>{risk.title}</strong></div>
                <b className={risk.severity === "High" ? "riskHigh" : "riskMod"}>{risk.severity}</b>
              </div>
            ))}
            <ul className="breakerList">
              {data.thesis_breakers.map((breaker) => <li key={breaker}>{breaker}</li>)}
            </ul>
          </section>

          <FactorRadar ticker={data.company.ticker} fallback={data.factor_scores} />

          <DividendSection dividend={fundamentals.dividend} price={Number(data.current_price)} />

          <section className="panel" style={{ gridColumn: "1 / -1" }}>
            <div className="panelTitle"><h2>Analysis history</h2><span className="eyebrow">How the model rating evolved</span></div>
            <HistoryChart history={history} />
          </section>
        </div>

        <div className="sources">
          <span className="eyebrow">Primary sources</span>
          {data.sources.map((source) => (
            <a key={source.url} href={source.url} target="_blank" rel="noreferrer">{source.name} ↗</a>
          ))}
        </div>
        <footer className="siteFooter">
          <span>Models are estimates, not price promises</span>
          <span>Research support — not investment advice</span>
        </footer>
      </main>
    </>
  );
}
