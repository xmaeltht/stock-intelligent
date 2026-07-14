"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import TopNav from "../../components/TopNav";
import { getJson, money, pct, signalClass, type IdeaItem, type IdeasResponse } from "../../lib/api";

function IdeaCard({ item, rank }: { item: IdeaItem; rank: number }) {
  const change = item.change_1d_pct;
  return (
    <Link href={`/stocks/${item.ticker}`} className="ideaCard">
      <div className="ideaRank">{rank}</div>
      <div className="ideaMain">
        <div className="ideaHead">
          <div>
            <strong>{item.ticker}</strong>
            <span>{item.name}</span>
          </div>
          <div className="ideaPrice">
            <b className="num">{money(item.current_price)}</b>
            <span className={change == null ? "dim" : change >= 0 ? "up" : "down"}>{pct(change)}</span>
          </div>
        </div>
        <div className="ideaReasons">
          {item.reasons.map((reason) => (
            <span key={reason} className="reasonChip">{reason}</span>
          ))}
        </div>
        <div className="ideaMeta">
          <span className={signalClass(item.signal ?? "neutral")}>{item.signal ?? "—"}</span>
          <span className="dim">Score {item.opportunity_score}</span>
          <span className="dim">Conf {item.confidence_grade}</span>
          <span className={item.risk_level === "Low" ? "up" : item.risk_level === "High" ? "down" : "dim"}>
            {item.risk_level} risk
          </span>
          {item.upside_pct != null && item.upside_pct > 0 && (
            <span className="up">{item.upside_pct.toFixed(0)}% upside</span>
          )}
        </div>
      </div>
    </Link>
  );
}

export default function IdeasPage() {
  const [data, setData] = useState<IdeasResponse | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    getJson<IdeasResponse>("/api/research/opportunities/ideas?limit=15")
      .then(setData)
      .catch(() => setError("Ideas are not available yet. The analyzer is still building coverage."));
  }, []);

  return (
    <>
      <TopNav online={data ? true : error ? false : undefined} />
      <main className="shell">
        <div className="pageHead">
          <div>
            <span className="eyebrow">Rules-based idea lists</span>
            <h1>Ideas</h1>
            <p>
              Two transparent, deterministic screens over the analyzed universe — a momentum screen for
              swing setups and a quality screen for long-term buy &amp; hold. Every pick lists exactly why
              it qualified. These are rule outputs, not personalized recommendations or investment advice.
            </p>
          </div>
        </div>

        {error && <div className="notice notice--error">{error}</div>}
        {!data && !error && <p className="notice">Building idea lists…</p>}

        {data && (
          <div className="ideasGrid">
            <section>
              <div className="ideasColHead">
                <div>
                  <span className="eyebrow">Momentum</span>
                  <h2>Swing ideas</h2>
                </div>
                <p>Bullish trend, above rising moving averages, healthy RSI, positive 5-day drift, liquid.</p>
              </div>
              {data.swing.length ? (
                data.swing.map((item, index) => <IdeaCard key={item.ticker} item={item} rank={index + 1} />)
              ) : (
                <div className="notice">No securities currently pass the swing screen.</div>
              )}
            </section>

            <section>
              <div className="ideasColHead">
                <div>
                  <span className="eyebrow">Quality</span>
                  <h2>Long-term buy &amp; hold</h2>
                </div>
                <p>Profitable with positive free cash flow, above the 200-day average, higher confidence grade.</p>
              </div>
              {data.long_term.length ? (
                data.long_term.map((item, index) => <IdeaCard key={item.ticker} item={item} rank={index + 1} />)
              ) : (
                <div className="notice">No securities currently pass the long-term screen.</div>
              )}
            </section>
          </div>
        )}

        <footer className="siteFooter">
          <span>Deterministic rule screens · re-computed from each security&apos;s latest analysis</span>
          <span>Research support — not investment advice</span>
        </footer>
      </main>
    </>
  );
}
