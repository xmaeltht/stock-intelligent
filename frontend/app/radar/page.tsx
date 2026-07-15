"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import TopNav from "../../components/TopNav";
import { getJson, money, pct, timeAgo, type RadarEvent, type RadarResponse } from "../../lib/api";

const CATEGORY_TONE: Record<string, string> = {
  golden_cross: "up",
  breakout: "up",
  unusual_volume: "accent",
  gainers: "up",
  value: "accent",
  momentum: "up",
  oversold: "accent",
  overbought: "warn",
  decliners: "down",
  breakdown: "down",
  death_cross: "down",
};

function EventCard({ event, tone }: { event: RadarEvent; tone: string }) {
  const change = event.change_1d_pct;
  return (
    <Link href={`/stocks/${event.ticker}`} className="radarCard">
      <div className="radarCardTop">
        <div>
          <strong>{event.ticker}</strong>
          <span>{event.name}</span>
        </div>
        <div className="radarPrice">
          <b className="num">{money(event.price)}</b>
          <span className={change == null ? "dim" : change >= 0 ? "up" : "down"}>{pct(change)}</span>
        </div>
      </div>
      <div className="radarCardBot">
        <span className={`radarHeadline radarHeadline--${tone}`}>{event.headline}</span>
        <span className="sectorTag" style={{ pointerEvents: "none" }}>{event.sector}</span>
      </div>
    </Link>
  );
}

export default function RadarPage() {
  const [data, setData] = useState<RadarResponse | null>(null);
  const [error, setError] = useState("");
  const [active, setActive] = useState("all");
  const [nowMs, setNowMs] = useState(() => Date.now());

  useEffect(() => {
    const load = () =>
      getJson<RadarResponse>("/api/research/opportunities/radar")
        .then((payload) => {
          setData(payload);
          setError("");
        })
        .catch(() => setError("The radar needs the analyzer to finish a first pass before it can surface events."));
    load();
    const poll = setInterval(() => {
      if (!document.hidden) load();
    }, 15000);
    const clock = setInterval(() => setNowMs(Date.now()), 1000);
    return () => {
      clearInterval(poll);
      clearInterval(clock);
    };
  }, []);

  const categories = (data?.categories ?? []).filter((cat) => cat.count > 0);
  const shown = active === "all" ? categories : categories.filter((cat) => cat.key === active);

  return (
    <>
      <TopNav online={data ? true : error ? false : undefined} />
      <main className="shell">
        <div className="pageHead">
          <div>
            <span className="eyebrow">Only possible because we scan everything</span>
            <h1>Live market radar</h1>
            <p>
              What&apos;s moving across the entire analyzed universe right now — fresh crosses, 52-week breakouts,
              unusual volume, big movers, and new value setups, detected continuously so you see the shift as it
              happens instead of looking up one ticker at a time.
            </p>
          </div>
        </div>

        {error && <div className="notice notice--error">{error}</div>}
        {!data && !error && <p className="notice">Scanning the universe…</p>}

        {data && (
          <>
            <div className="liveStrip">
              <span className="livePulse open"><i />Live radar</span>
              <span className="liveMetric"><b className="num">{data.total_events.toLocaleString()}</b> active signals</span>
              <span className="liveMetric"><b className="num">{data.universe.toLocaleString()}</b> securities scanned</span>
              <span className="liveMetric dim">updated {timeAgo(data.generated_at, nowMs)} ago</span>
            </div>

            <div className="filterBar" style={{ gap: 8 }}>
              <button className={`toggleChip${active === "all" ? " on" : ""}`} onClick={() => setActive("all")}>
                All signals
              </button>
              {categories.map((cat) => (
                <button
                  key={cat.key}
                  className={`toggleChip${active === cat.key ? " on" : ""}`}
                  onClick={() => setActive(cat.key)}
                >
                  {cat.label} <b>{cat.count}</b>
                </button>
              ))}
            </div>

            {shown.length === 0 && (
              <div className="notice">No notable events in the current scan. The market is quiet — or coverage is still building.</div>
            )}

            {shown.map((cat) => (
              <section key={cat.key} className="radarSection">
                <div className="radarSectionHead">
                  <h2>{cat.label} <em>{cat.count}</em></h2>
                  <span>{cat.description}</span>
                </div>
                <div className="radarGrid">
                  {cat.items.slice(0, active === "all" ? 8 : 60).map((event) => (
                    <EventCard key={event.ticker} event={event} tone={CATEGORY_TONE[cat.key] ?? "accent"} />
                  ))}
                </div>
                {active === "all" && cat.count > 8 && (
                  <button className="radarMore" onClick={() => setActive(cat.key)}>
                    See all {cat.count} {cat.label.toLowerCase()} →
                  </button>
                )}
              </section>
            ))}
          </>
        )}

        <footer className="siteFooter">
          <span>Continuous market-wide event detection · updates live</span>
          <span>Research support — not investment advice</span>
        </footer>
      </main>
    </>
  );
}
