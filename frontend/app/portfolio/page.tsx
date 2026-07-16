"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useState } from "react";

import TopNav from "../../components/TopNav";
import {
  getJson,
  money,
  pct,
  sendJson,
  type PaperPortfolio,
  type RiskPlan,
} from "../../lib/api";

const emptyTrade = {
  ticker: "",
  side: "BUY" as "BUY" | "SELL",
  quantity: "",
  price: "",
  invalidation: "",
  target: "",
  fees: "0",
  thesis: "",
  catalyst: "",
  notes: "",
};

export default function PortfolioPage() {
  const [portfolio, setPortfolio] = useState<PaperPortfolio | null>(null);
  const [trade, setTrade] = useState(emptyTrade);
  const [plan, setPlan] = useState<RiskPlan | null>(null);
  const [riskPct, setRiskPct] = useState("");
  const [maxPosition, setMaxPosition] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const next = await getJson<PaperPortfolio>("/api/research/paper");
      setPortfolio(next);
      setRiskPct(String(next.max_risk_per_trade_pct));
      setMaxPosition(String(next.max_position_pct));
      setError("");
    } catch {
      setError("The paper portfolio could not be loaded.");
    }
  }, []);

  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const ticker = params.get("ticker");
    if (!ticker) return;
    setTrade((current) => ({
      ...current,
      ticker,
      price: params.get("price") ?? current.price,
      target: params.get("target") ?? current.target,
      invalidation: params.get("stop") ?? current.invalidation,
    }));
  }, []);

  const calculate = async () => {
    if (!trade.ticker || !trade.invalidation) {
      setError("Ticker and invalidation price are required for risk sizing.");
      return;
    }
    setBusy(true);
    try {
      const result = await sendJson<RiskPlan>("/api/research/paper/plan", "POST", {
        ticker: trade.ticker,
        entry_price: trade.price ? Number(trade.price) : null,
        invalidation_price: Number(trade.invalidation),
        target_price: trade.target ? Number(trade.target) : null,
        risk_pct: riskPct ? Number(riskPct) : null,
      });
      setPlan(result);
      setTrade((current) => ({
        ...current,
        ticker: result.ticker,
        price: result.entry_price,
        quantity: result.suggested_shares,
      }));
      setError("");
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Risk plan failed.");
    } finally {
      setBusy(false);
    }
  };

  const execute = async (event: FormEvent) => {
    event.preventDefault();
    if (!trade.ticker || !trade.quantity) return;
    setBusy(true);
    try {
      const next = await sendJson<PaperPortfolio>("/api/research/paper/trades", "POST", {
        ticker: trade.ticker,
        side: trade.side,
        quantity: Number(trade.quantity),
        price: trade.price ? Number(trade.price) : null,
        fees: Number(trade.fees || 0),
        invalidation_price: trade.invalidation ? Number(trade.invalidation) : null,
        target_price: trade.target ? Number(trade.target) : null,
        thesis: trade.thesis || null,
        catalyst: trade.catalyst || null,
        notes: trade.notes || null,
      });
      setPortfolio(next);
      setTrade(emptyTrade);
      setPlan(null);
      setError("");
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Paper trade failed.");
    } finally {
      setBusy(false);
    }
  };

  const saveRisk = async () => {
    if (!portfolio) return;
    setBusy(true);
    try {
      const next = await sendJson<PaperPortfolio>("/api/research/paper/settings", "PUT", {
        max_risk_per_trade_pct: Number(riskPct),
        max_position_pct: Number(maxPosition),
      });
      setPortfolio(next);
      setError("");
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Settings update failed.");
    } finally {
      setBusy(false);
    }
  };

  const prepareSell = (ticker: string, quantity: string, price: string) => {
    setTrade({ ...emptyTrade, ticker, quantity, price, side: "SELL" });
    setPlan(null);
    window.scrollTo({ top: 360, behavior: "smooth" });
  };

  return (
    <>
      <TopNav online={portfolio ? true : error ? false : undefined} />
      <main className="shell">
        <div className="pageHead">
          <div>
            <span className="eyebrow">Decision system · simulated capital</span>
            <h1>Paper portfolio</h1>
            <p>Test entries, position sizing, targets, and thesis discipline before risking real money. No brokerage orders are sent.</p>
          </div>
        </div>

        {error && <div className="notice notice--error">{error}</div>}
        {portfolio && (
          <>
            <div className="statRow portfolioStats">
              <div className="stat"><span>Total value</span><strong>{money(portfolio.total_value)}</strong></div>
              <div className="stat"><span>Available cash</span><strong>{money(portfolio.cash_balance)}</strong></div>
              <div className="stat"><span>Invested</span><strong>{money(portfolio.invested_value)}</strong></div>
              <div className={`stat ${portfolio.total_return_pct >= 0 ? "stat--accent" : "stat--danger"}`}>
                <span>Total return</span>
                <strong>{money(portfolio.total_return)}</strong>
                <small>{pct(portfolio.total_return_pct)}</small>
              </div>
            </div>

            <div className="portfolioGrid">
              <form className="panel tradeTicket" onSubmit={execute}>
                <div className="panelTitle"><h2>Paper trade ticket</h2><span className="eyebrow">No real order</span></div>
                <div className="tradeSide">
                  {(["BUY", "SELL"] as const).map((side) => (
                    <button key={side} type="button" className={`sideBtn ${side.toLowerCase()}${trade.side === side ? " on" : ""}`} onClick={() => setTrade({ ...trade, side })}>{side}</button>
                  ))}
                </div>
                <div className="formGrid">
                  <label>Ticker<input value={trade.ticker} onChange={(event) => setTrade({ ...trade, ticker: event.target.value.toUpperCase() })} placeholder="AAPL" required /></label>
                  <label>Quantity<input type="number" min="0.000001" step="0.000001" value={trade.quantity} onChange={(event) => setTrade({ ...trade, quantity: event.target.value })} required /></label>
                  <label>Entry price<input type="number" min="0" step="0.0001" value={trade.price} onChange={(event) => setTrade({ ...trade, price: event.target.value })} placeholder="Use live price" /></label>
                  <label>Fees<input type="number" min="0" step="0.01" value={trade.fees} onChange={(event) => setTrade({ ...trade, fees: event.target.value })} /></label>
                  <label>Invalidation price<input type="number" min="0" step="0.0001" value={trade.invalidation} onChange={(event) => setTrade({ ...trade, invalidation: event.target.value })} placeholder="Where thesis is wrong" /></label>
                  <label>Target price<input type="number" min="0" step="0.0001" value={trade.target} onChange={(event) => setTrade({ ...trade, target: event.target.value })} /></label>
                </div>
                <label>Thesis<textarea value={trade.thesis} onChange={(event) => setTrade({ ...trade, thesis: event.target.value })} placeholder="Why this trade should work" /></label>
                <label>Catalyst<textarea value={trade.catalyst} onChange={(event) => setTrade({ ...trade, catalyst: event.target.value })} placeholder="What may unlock the value, and when" /></label>
                <label>Journal notes<textarea value={trade.notes} onChange={(event) => setTrade({ ...trade, notes: event.target.value })} placeholder="Entry context, concerns, or exit reason" /></label>
                <div className="ticketActions">
                  {trade.side === "BUY" && <button type="button" className="btn" onClick={calculate} disabled={busy}>Calculate safe size</button>}
                  <button type="submit" className="btn btn--primary" disabled={busy}>{busy ? "Working…" : `Record ${trade.side}`}</button>
                </div>
              </form>

              <aside className="panel riskPanel">
                <div className="panelTitle"><h2>Risk manager</h2><span className="eyebrow">Portfolio rules</span></div>
                <div className="formGrid">
                  <label>Risk per trade %<input type="number" min="0.1" max="10" step="0.1" value={riskPct} onChange={(event) => setRiskPct(event.target.value)} /></label>
                  <label>Max position %<input type="number" min="1" max="100" step="1" value={maxPosition} onChange={(event) => setMaxPosition(event.target.value)} /></label>
                </div>
                <button className="btn" type="button" onClick={saveRisk} disabled={busy}>Save risk limits</button>
                {plan ? (
                  <div className="planResult">
                    <span className="eyebrow">Suggested position</span>
                    <strong>{Number(plan.suggested_shares).toLocaleString()} shares</strong>
                    <dl className="facts">
                      <div><dt>Risk budget</dt><dd>{money(plan.risk_budget)}</dd></div>
                      <div><dt>Position value</dt><dd>{money(plan.suggested_position_value)}</dd></div>
                      <div><dt>Portfolio allocation</dt><dd>{plan.position_pct}%</dd></div>
                      <div><dt>Reward / risk</dt><dd>{plan.reward_risk_ratio ? `${plan.reward_risk_ratio}:1` : "—"}</dd></div>
                    </dl>
                    {plan.warnings.map((warning) => <p className="riskWarning" key={warning}>{warning}</p>)}
                  </div>
                ) : (
                  <p className="dim riskExplainer">Enter a ticker and an invalidation price, then calculate. Suggested size is capped by your risk budget, cash, and maximum allocation.</p>
                )}
              </aside>
            </div>

            <section className="portfolioSection">
              <div className="panelTitle"><h2>Open positions</h2><span className="eyebrow">Marked to latest analyzed price</span></div>
              {portfolio.positions.length === 0 ? <div className="notice">No positions yet. Use the paper ticket to test your first idea.</div> : (
                <div className="tableWrap"><table><thead><tr><th>Company</th><th className="r">Shares</th><th className="r">Avg cost</th><th className="r">Current</th><th className="r">Market value</th><th className="r">P&amp;L</th><th className="r">Allocation</th><th>Plan</th><th /></tr></thead><tbody>
                  {portfolio.positions.map((position) => <tr key={position.ticker}>
                    <td className="tickerCell"><Link href={`/stocks/${position.ticker}`}><strong>{position.ticker}</strong><span>{position.name}</span></Link></td>
                    <td className="r num">{Number(position.quantity).toLocaleString()}</td><td className="r num">{money(position.average_cost)}</td><td className="r num">{money(position.current_price)}</td><td className="r num">{money(position.market_value)}</td>
                    <td className={`r num ${Number(position.unrealized_pnl) >= 0 ? "up" : "down"}`}>{money(position.unrealized_pnl)}<br /><small>{pct(position.unrealized_pct)}</small></td>
                    <td className="r num">{position.allocation_pct}%</td><td className="num"><span className="dim">Stop</span> {money(position.invalidation_price)}<br /><span className="dim">Target</span> {money(position.target_price)}</td>
                    <td><button className="btn btn--small" onClick={() => prepareSell(position.ticker, position.quantity, position.current_price)}>Sell</button></td>
                  </tr>)}
                </tbody></table></div>
              )}
            </section>

            <section className="portfolioSection">
              <div className="panelTitle"><h2>Trade journal</h2><span className="eyebrow">Append-only decision record</span></div>
              {portfolio.trades.length === 0 ? <div className="notice">Your entries, exits, thesis, catalyst, and realized results will appear here.</div> : (
                <div className="tableWrap"><table><thead><tr><th>Date</th><th>Trade</th><th className="r">Quantity</th><th className="r">Price</th><th className="r">Realized P&amp;L</th><th>Decision record</th></tr></thead><tbody>
                  {portfolio.trades.map((item) => <tr key={item.id}><td className="dim num">{new Date(item.executed_at).toLocaleString()}</td><td><span className={`tradeBadge ${item.side.toLowerCase()}`}>{item.side}</span> <Link href={`/stocks/${item.ticker}`}><b className="mono">{item.ticker}</b></Link></td><td className="r num">{Number(item.quantity).toLocaleString()}</td><td className="r num">{money(item.price)}</td><td className={`r num ${item.realized_pnl == null ? "dim" : Number(item.realized_pnl) >= 0 ? "up" : "down"}`}>{item.realized_pnl == null ? "Open" : money(item.realized_pnl)}</td><td className="journalCell">{item.thesis && <span><b>Thesis:</b> {item.thesis}</span>}{item.catalyst && <span><b>Catalyst:</b> {item.catalyst}</span>}{item.notes && <span><b>Notes:</b> {item.notes}</span>}</td></tr>)}
                </tbody></table></div>
              )}
            </section>
          </>
        )}
        <footer className="siteFooter"><span>Simulation only · no brokerage connection</span><span>Research support — not investment advice</span></footer>
      </main>
    </>
  );
}
