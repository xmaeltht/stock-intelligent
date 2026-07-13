"use client";

import { Suspense, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import TopNav from "../../components/TopNav";
import { compact, getJson, money, pct, signalClass, type Detail } from "../../lib/api";

function CompareContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const tickersParam = searchParams.get("tickers") ?? "";
  const [input, setInput] = useState("");
  const [results, setResults] = useState<Detail[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!tickersParam) {
      setResults([]);
      return;
    }
    setLoading(true);
    getJson<Detail[]>(`/api/research/opportunities/compare?tickers=${encodeURIComponent(tickersParam)}`)
      .then((data) => {
        setResults(data);
        setError(data.length ? "" : "None of those tickers have been analyzed yet.");
        setLoading(false);
      })
      .catch(() => {
        setError("Comparison data could not be loaded.");
        setLoading(false);
      });
  }, [tickersParam]);

  const currentTickers = tickersParam ? tickersParam.split(",").filter(Boolean) : [];

  const updateTickers = useCallback(
    (next: string[]) => {
      router.replace(next.length ? `/compare?tickers=${next.join(",")}` : "/compare");
    },
    [router],
  );

  const addTickers = () => {
    const added = input
      .split(/[\s,]+/)
      .map((value) => value.trim().toUpperCase())
      .filter(Boolean);
    if (!added.length) return;
    updateTickers(Array.from(new Set([...currentTickers, ...added])).slice(0, 6));
    setInput("");
  };

  const rows: Array<{ label: string; render: (item: Detail) => React.ReactNode }> = [
    { label: "Price", render: (item) => money(item.current_price) },
    {
      label: "1D change",
      render: (item) => {
        const change = item.technical_indicators?.change_1d_pct;
        return <span className={change == null ? "dim" : change >= 0 ? "up" : "down"}>{pct(change)}</span>;
      },
    },
    {
      label: "Fair value",
      render: (item) => (item.company.asset_type === "ETF" ? <span className="dim">n/a</span> : money(item.fair_value)),
    },
    {
      label: "Upside",
      render: (item) =>
        item.company.asset_type === "ETF" ? (
          <span className="dim">n/a</span>
        ) : (
          <span className={item.upside_pct >= 0 ? "up" : "down"}>{item.upside_pct.toFixed(1)}%</span>
        ),
    },
    { label: "Score", render: (item) => `${item.opportunity_score}/100` },
    { label: "Confidence / Risk", render: (item) => `${item.confidence_grade} / ${item.risk_level}` },
    {
      label: "Signal",
      render: (item) => (
        <span className={signalClass(item.technical_indicators?.signal)}>{item.technical_indicators?.signal ?? "—"}</span>
      ),
    },
    { label: "RSI 14", render: (item) => item.technical_indicators?.rsi14 ?? "—" },
    { label: "Volume", render: (item) => item.volume?.toLocaleString() ?? "—" },
    { label: "Market cap", render: (item) => compact(item.fundamentals?.market_cap) },
    { label: "Revenue", render: (item) => compact(item.revenue) },
    {
      label: "Revenue growth",
      render: (item) => (item.revenue_growth_pct != null ? `${item.revenue_growth_pct.toFixed(1)}%` : "—"),
    },
    { label: "Net margin", render: (item) => (item.fundamentals?.margins?.net_pct != null ? `${item.fundamentals.margins.net_pct}%` : "—") },
    { label: "FCF", render: (item) => compact(item.free_cash_flow) },
    { label: "P/E", render: (item) => item.fundamentals?.ratios?.price_to_earnings ?? "—" },
    { label: "P/S", render: (item) => item.fundamentals?.ratios?.price_to_sales ?? "—" },
    { label: "P/B", render: (item) => item.fundamentals?.ratios?.price_to_book ?? "—" },
    { label: "Cash / Debt", render: (item) => `${compact(item.cash)} / ${compact(item.debt)}` },
  ];

  return (
    <main className="shell">
      <div className="pageHead">
        <div>
          <span className="eyebrow">Side by side</span>
          <h1>Compare securities</h1>
          <p>Line up to six analyzed securities against each other. Add tickers below or send your watchlist here.</p>
        </div>
      </div>

      <div className="compareControls">
        <input
          type="text"
          value={input}
          placeholder="Add tickers, e.g. AAPL, MSFT NVDA"
          onChange={(event) => setInput(event.target.value)}
          onKeyDown={(event) => event.key === "Enter" && addTickers()}
        />
        <button className="btn" onClick={addTickers}>Add</button>
        {currentTickers.length > 0 && (
          <button className="btn btn--ghost" onClick={() => updateTickers([])}>Clear all</button>
        )}
      </div>

      {loading && <p className="notice">Loading comparison…</p>}
      {error && !loading && <div className="notice notice--error">{error}</div>}
      {!currentTickers.length && !loading && (
        <div className="notice">No tickers selected. Add some above, or star securities and open Compare from the watchlist.</div>
      )}

      {results.length > 0 && (
        <div className="compareGrid" style={{ gridTemplateColumns: `repeat(${Math.min(results.length, 3)}, 1fr)` }}>
          {results.map((item) => (
            <div className="compareCard" key={item.company.ticker}>
              <header>
                <div>
                  <h3><Link href={`/stocks/${item.company.ticker}`} style={{ textDecoration: "none" }}>{item.company.ticker}</Link></h3>
                  <p>{item.company.name}</p>
                </div>
                <button
                  className="removeBtn"
                  title="Remove from comparison"
                  onClick={() => updateTickers(currentTickers.filter((ticker) => ticker !== item.company.ticker))}
                >
                  ✕
                </button>
              </header>
              {rows.map((row) => (
                <div className="kv" key={row.label}>
                  <span>{row.label}</span>
                  <b>{row.render(item)}</b>
                </div>
              ))}
            </div>
          ))}
        </div>
      )}

      <footer className="siteFooter">
        <span>Comparison uses each security&apos;s latest stored analysis</span>
        <span>Research support — not investment advice</span>
      </footer>
    </main>
  );
}

export default function ComparePage() {
  return (
    <>
      <TopNav online />
      <Suspense fallback={<main className="shell"><p className="notice">Loading…</p></main>}>
        <CompareContent />
      </Suspense>
    </>
  );
}
