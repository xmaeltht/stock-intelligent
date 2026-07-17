"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import TopNav from "../../components/TopNav";
import SignInPrompt from "../../components/SignInPrompt";
import { useAuth } from "../../lib/auth";
import { getJson, money, postJson, type PaperPortfolio } from "../../lib/api";

const n = (value: string | number) => Number(value);
const pnlClass = (value: string | number) => (n(value) >= 0 ? "up" : "down");
const signed = (value: string | number) => `${n(value) >= 0 ? "+" : ""}${money(value)}`;

export default function Portfolio() {
  const { user, loading: authLoading } = useAuth();
  const [pf, setPf] = useState<PaperPortfolio | null>(null);
  const [error, setError] = useState("");

  const [ticker, setTicker] = useState("");
  const [side, setSide] = useState<"BUY" | "SELL">("BUY");
  const [quantity, setQuantity] = useState("");
  const [price, setPrice] = useState("");
  const [thesis, setThesis] = useState("");
  const [formError, setFormError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const load = useCallback(() => {
    if (!user) return;
    getJson<PaperPortfolio>("/api/research/paper")
      .then((data) => {
        setPf(data);
        setError("");
      })
      .catch(() => setError("Your portfolio could not be loaded."));
  }, [user]);

  useEffect(load, [load]);

  const submitTrade = async (event: React.FormEvent) => {
    event.preventDefault();
    setFormError("");
    const qty = Number(quantity);
    if (!ticker.trim() || !(qty > 0)) {
      setFormError("Enter a ticker and a positive quantity.");
      return;
    }
    setSubmitting(true);
    try {
      const updated = await postJson<PaperPortfolio>("/api/research/paper/trades", {
        ticker: ticker.trim().toUpperCase(),
        side,
        quantity: qty,
        price: price ? Number(price) : null,
        thesis: thesis.trim() || null,
      });
      setPf(updated);
      setTicker("");
      setQuantity("");
      setPrice("");
      setThesis("");
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "Trade could not be recorded.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <>
      <TopNav online={pf ? true : error ? false : undefined} />
      <main className="shell">
        <div className="pageHead">
          <div>
            <span className="eyebrow">Paper portfolio</span>
            <h1>Portfolio</h1>
            <p>
              Track holdings, live P&amp;L, and every position scored on the same transparent
              factors. Paper trades — a disciplined journal, not brokerage execution.
            </p>
          </div>
          {pf && (
            <div className="pfHeadValue">
              <div className="pfHeadTotal">{money(pf.total_value)}</div>
              <div className={`pfHeadReturn ${pnlClass(pf.total_return)}`}>
                {signed(pf.total_return)} ({pf.total_return_pct.toFixed(2)}%)
              </div>
            </div>
          )}
        </div>

        {!authLoading && !user && (
          <SignInPrompt
            title="Sign in to track your portfolio"
            body="Add holdings once, then see live P&L, factor exposure, and a journaled record of every decision."
            icon="📊"
          />
        )}

        {error && user && <div className="notice notice--error">{error}</div>}

        {user && pf && (
          <>
            <div className="statRow">
              <div className="stat">
                <span>Total value</span>
                <strong>{money(pf.total_value)}</strong>
                <small>{money(pf.cash_balance)} cash</small>
              </div>
              <div className="stat">
                <span>Total return</span>
                <strong className={pnlClass(pf.total_return)}>{signed(pf.total_return)}</strong>
                <small>from {money(pf.starting_cash)} start</small>
              </div>
              <div className="stat">
                <span>Unrealized P&amp;L</span>
                <strong className={pnlClass(pf.unrealized_pnl)}>{signed(pf.unrealized_pnl)}</strong>
                <small>{money(pf.invested_value)} invested</small>
              </div>
              <div className="stat">
                <span>Realized P&amp;L</span>
                <strong className={pnlClass(pf.realized_pnl)}>{signed(pf.realized_pnl)}</strong>
                <small>{pf.trades.length} trades logged</small>
              </div>
            </div>

            <form className="pfTradeForm card" onSubmit={submitTrade}>
              <div className="pfFormTitle">Record a trade</div>
              <div className="pfFormRow">
                <label>
                  Ticker
                  <input
                    type="text"
                    value={ticker}
                    onChange={(e) => setTicker(e.target.value.toUpperCase())}
                    placeholder="AAPL"
                    maxLength={16}
                  />
                </label>
                <label>
                  Side
                  <select value={side} onChange={(e) => setSide(e.target.value as "BUY" | "SELL")}>
                    <option value="BUY">Buy</option>
                    <option value="SELL">Sell</option>
                  </select>
                </label>
                <label>
                  Quantity
                  <input
                    type="number"
                    value={quantity}
                    onChange={(e) => setQuantity(e.target.value)}
                    placeholder="10"
                    min="0"
                    step="any"
                  />
                </label>
                <label>
                  Price <span className="pfOpt">(optional)</span>
                  <input
                    type="number"
                    value={price}
                    onChange={(e) => setPrice(e.target.value)}
                    placeholder="market"
                    min="0"
                    step="any"
                  />
                </label>
                <button className="btn pfSubmit" type="submit" disabled={submitting}>
                  {submitting ? "…" : "Add trade"}
                </button>
              </div>
              <label className="pfThesis">
                Thesis <span className="pfOpt">(optional — why are you taking this position?)</span>
                <input
                  type="text"
                  value={thesis}
                  onChange={(e) => setThesis(e.target.value)}
                  placeholder="e.g. undervalued vs. base-case fair value, 21-yr dividend growth"
                  maxLength={2000}
                />
              </label>
              {formError && <div className="pfFormError">{formError}</div>}
            </form>

            <h2 className="pfSection">Positions</h2>
            {pf.positions.length ? (
              <div className="tableWrap">
                <table>
                  <thead>
                    <tr>
                      <th>Company</th>
                      <th className="r">Qty</th>
                      <th className="r">Avg cost</th>
                      <th className="r">Price</th>
                      <th className="r">Market value</th>
                      <th className="r">Unrealized</th>
                      <th className="r">Alloc.</th>
                    </tr>
                  </thead>
                  <tbody>
                    {pf.positions.map((pos) => (
                      <tr key={pos.ticker}>
                        <td className="tickerCell">
                          <Link href={`/stocks/${pos.ticker}`}>
                            <strong>{pos.ticker}</strong>
                            <span>{pos.name}</span>
                          </Link>
                        </td>
                        <td className="r num">{n(pos.quantity).toLocaleString()}</td>
                        <td className="r num">{money(pos.average_cost)}</td>
                        <td className="r num">{money(pos.current_price)}</td>
                        <td className="r num">{money(pos.market_value)}</td>
                        <td className={`r num ${pnlClass(pos.unrealized_pnl)}`}>
                          {signed(pos.unrealized_pnl)} ({pos.unrealized_pct.toFixed(1)}%)
                        </td>
                        <td className="r num">{pos.allocation_pct.toFixed(1)}%</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="notice">
                No open positions yet. Record a buy above, or find one in{" "}
                <Link href="/discover" className="homeLink">Discover</Link>.
              </div>
            )}

            {pf.trades.length > 0 && (
              <>
                <h2 className="pfSection">Trade journal</h2>
                <div className="tableWrap">
                  <table>
                    <thead>
                      <tr>
                        <th>Date</th>
                        <th>Company</th>
                        <th>Side</th>
                        <th className="r">Qty</th>
                        <th className="r">Price</th>
                        <th className="r">Realized</th>
                        <th>Thesis</th>
                      </tr>
                    </thead>
                    <tbody>
                      {pf.trades.map((trade) => (
                        <tr key={trade.id}>
                          <td className="dim num">{new Date(trade.executed_at).toLocaleDateString()}</td>
                          <td className="tickerCell">
                            <Link href={`/stocks/${trade.ticker}`}>
                              <strong>{trade.ticker}</strong>
                            </Link>
                          </td>
                          <td>
                            <span className={`pfSide pfSide--${trade.side.toLowerCase()}`}>{trade.side}</span>
                          </td>
                          <td className="r num">{n(trade.quantity).toLocaleString()}</td>
                          <td className="r num">{money(trade.price)}</td>
                          <td className={`r num ${trade.realized_pnl ? pnlClass(trade.realized_pnl) : "dim"}`}>
                            {trade.realized_pnl ? signed(trade.realized_pnl) : "—"}
                          </td>
                          <td className="pfThesisCell">{trade.thesis ?? <span className="dim">—</span>}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            )}
          </>
        )}

        <footer className="siteFooter">
          <span>Paper portfolio · disciplined journaling, not brokerage execution</span>
          <span>Research support — not investment advice</span>
        </footer>
      </main>
    </>
  );
}
