"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import TopNav from "../components/TopNav";
import { useAuth } from "../lib/auth";
import {
  getJson,
  money,
  pct,
  ratingFor,
  timeAgo,
  type IdeasResponse,
  type ListItem,
  type RadarEvent,
  type RadarResponse,
  type Summary,
  type WatchlistRow,
} from "../lib/api";

const SESSION_LABEL: Record<string, string> = {
  pre: "Pre-market · live scanning",
  regular: "Market open · live scanning",
  after: "After-hours · live scanning",
  overnight: "Overnight · live scanning",
  closed: "Market closed · background scanning",
};

// Icon + tone per radar event category, so the feed reads at a glance.
const RADAR_META: Record<string, { icon: string; tone: "up" | "down" | "" }> = {
  golden_cross: { icon: "✦", tone: "up" },
  breakout: { icon: "▲", tone: "up" },
  gainers: { icon: "↗", tone: "up" },
  momentum: { icon: "➚", tone: "up" },
  value: { icon: "◈", tone: "" },
  unusual_volume: { icon: "⚡", tone: "" },
  oversold: { icon: "↺", tone: "" },
  overbought: { icon: "⚠", tone: "down" },
  decliners: { icon: "↘", tone: "down" },
  breakdown: { icon: "▽", tone: "down" },
  death_cross: { icon: "✕", tone: "down" },
};

type FeedItem = RadarEvent & { categoryKey: string; categoryLabel: string };

function greetingFor(date: Date): string {
  const hour = date.getHours();
  if (hour < 12) return "Good morning";
  if (hour < 18) return "Good afternoon";
  return "Good evening";
}

const LANDING_FEATURES: Array<{ icon: string; title: string; body: string }> = [
  {
    icon: "◈",
    title: "Fair value that shows its work",
    body: "Bear, base, and bull targets built from SEC filings and deterministic multiples — every number traces to a source, never a guess.",
  },
  {
    icon: "🔔",
    title: "Alerts that watch for you",
    body: "Set a price or upside threshold on any security and get notified the moment it crosses — evaluated continuously in the background.",
  },
  {
    icon: "◑",
    title: "Portfolio & watchlist",
    body: "Track holdings, factor exposure, and P&L in one place, with ratings and dividends followed over time.",
  },
];

function LandingHero({ summary }: { summary: Summary | null }) {
  return (
    <section className="landing">
      <div className="landingHero">
        <span className="landingEyebrow">
          <i className={`homePulse${summary && summary.market_session !== "closed" ? " open" : ""}`}>
            <i />
          </i>
          {summary
            ? `Live · ${summary.analysis_count.toLocaleString()} securities analyzed`
            : "Deterministic research terminal"}
        </span>
        <h1 className="landingTitle">
          Stock research that <span>shows its work.</span>
        </h1>
        <p className="landingLede">
          Rules-based valuation, trend, and risk signals on thousands of securities — traced back to
          filings and price data, not a black box. Built for long-term investors who want the
          reasoning behind every rating.
        </p>
        <div className="landingCtas">
          <Link href="/login?mode=signup&next=%2F" className="landingPrimary">
            Create a free account
          </Link>
          <Link href="/discover" className="landingSecondary">
            Browse the research →
          </Link>
        </div>
        <p className="landingNote">Free forever to start · Rules-based research, not investment advice</p>
      </div>
      <div className="landingFeatures">
        {LANDING_FEATURES.map((feature) => (
          <div className="landingFeature" key={feature.title}>
            <span className="landingFeatureIcon">{feature.icon}</span>
            <strong>{feature.title}</strong>
            <p>{feature.body}</p>
          </div>
        ))}
      </div>
      <div className="landingLiveHead">
        <h2>See it live</h2>
        <span>Real signals from the latest market scan — no account needed to look.</span>
      </div>
    </section>
  );
}

export default function Home() {
  const { user, loading: authLoading } = useAuth();
  const [summary, setSummary] = useState<Summary | null>(null);
  const [radar, setRadar] = useState<RadarResponse | null>(null);
  const [ideas, setIdeas] = useState<IdeasResponse | null>(null);
  const [watchlist, setWatchlist] = useState<WatchlistRow[] | null>(null);
  const [nowMs, setNowMs] = useState(() => Date.now());
  const [online, setOnline] = useState<boolean | undefined>(undefined);

  useEffect(() => {
    let alive = true;
    Promise.all([
      getJson<Summary>("/api/research/opportunities/summary").catch(() => null),
      getJson<RadarResponse>("/api/research/opportunities/radar").catch(() => null),
      getJson<IdeasResponse>("/api/research/opportunities/ideas?limit=12").catch(() => null),
      getJson<WatchlistRow[]>("/api/research/watchlist").catch(() => null),
    ]).then(([s, r, i, w]) => {
      if (!alive) return;
      setSummary(s);
      setRadar(r);
      setIdeas(i);
      setWatchlist(w);
      setOnline(s ? true : false);
    });
    return () => {
      alive = false;
    };
  }, []);

  useEffect(() => {
    const timer = setInterval(() => setNowMs(Date.now()), 1000);
    return () => clearInterval(timer);
  }, []);

  // Flatten radar categories → the highest-significance events across all of them.
  const feed: FeedItem[] = useMemo(() => {
    if (!radar) return [];
    const all: FeedItem[] = [];
    for (const category of radar.categories) {
      for (const item of category.items) {
        all.push({ ...item, categoryKey: category.key, categoryLabel: category.label });
      }
    }
    return all.sort((a, b) => b.significance - a.significance).slice(0, 6);
  }, [radar]);

  // Real aggregate over the watchlist's latest analyses — a live "snapshot".
  const snapshot = useMemo(() => {
    const rows = (watchlist ?? []).map((row) => row.latest).filter((item): item is ListItem => !!item);
    if (!rows.length) return null;
    const composites = rows
      .map((item) => item.factor_scores?.composite)
      .filter((value): value is number => typeof value === "number");
    const upsides = rows
      .filter((item) => item.company.asset_type !== "ETF")
      .map((item) => item.upside_pct)
      .filter((value) => Number.isFinite(value));
    const avg = (values: number[]) =>
      values.length ? Math.round(values.reduce((sum, value) => sum + value, 0) / values.length) : null;
    return {
      count: rows.length,
      avgFactor: avg(composites),
      avgUpside: upsides.length
        ? upsides.reduce((sum, value) => sum + value, 0) / upsides.length
        : null,
    };
  }, [watchlist]);

  const ideaCards = useMemo(() => (ideas ? ideas.long_term.slice(0, 3) : []), [ideas]);
  const watchRows = useMemo(
    () => (watchlist ?? []).filter((row) => row.latest).slice(0, 6),
    [watchlist],
  );

  const greeting = greetingFor(new Date(nowMs));

  return (
    <>
      <TopNav online={online} />
      <main className="shell">
        {!authLoading && !user && <LandingHero summary={summary} />}
        {!authLoading && user && (
        <div className="homeGreet">
          <div>
            <h1>
              {greeting}
              {user?.display_name ? <>, <span>{user.display_name}</span></> : null}
            </h1>
            <p>
              {summary
                ? `${SESSION_LABEL[summary.market_session] ?? "Background scanning"} · ${summary.analysis_count.toLocaleString()} securities analyzed`
                : "Loading your research desk…"}
            </p>
          </div>
          {summary && (
            <div className="homeMkt">
              <span className={`homePulse${summary.market_session !== "closed" ? " open" : ""}`}>
                <i />
                {summary.market_session === "closed" ? "Market closed" : "Live"}
              </span>
              <span className="homeMktStat">
                <b>{summary.prices_updated_last_min.toLocaleString()}</b> prices / min
              </span>
              <span className="homeMktStat">
                <b>{summary.qualified_count.toLocaleString()}</b> high-upside ideas
              </span>
            </div>
          )}
        </div>
        )}

        <div className="homeGrid">
          <section className="card homeFeed">
            <div className="homeCardHead">
              <h2>What&apos;s moving</h2>
              <Link href="/radar" className="homeSeeAll">Live radar →</Link>
            </div>
            <div className="homeFeedList">
              {feed.length === 0 && (
                <p className="homeEmpty">
                  {radar ? "No standout events in the latest scan." : "Scanning the market…"}
                </p>
              )}
              {feed.map((item) => {
                const meta = RADAR_META[item.categoryKey] ?? { icon: "•", tone: "" as const };
                return (
                  <Link href={`/stocks/${item.ticker}`} className="homeFeedRow" key={`${item.categoryKey}-${item.ticker}`}>
                    <span className={`homeFeedIcon${meta.tone ? ` ${meta.tone}` : ""}`}>{meta.icon}</span>
                    <span className="homeFeedBody">
                      <span className="t"><b>{item.ticker}</b> {item.headline}</span>
                      <span className="s">{item.name} · {item.categoryLabel}</span>
                    </span>
                    {item.change_1d_pct != null && (
                      <span className={`homeFeedTag ${item.change_1d_pct >= 0 ? "up" : "down"}`}>
                        {pct(item.change_1d_pct)}
                      </span>
                    )}
                  </Link>
                );
              })}
            </div>
          </section>

          <section className="card homeSide">
            <div className="homeCardHead">
              <h2>Watchlist snapshot</h2>
              <span className="homeEye">{snapshot ? `${snapshot.count} tracked` : "—"}</span>
            </div>
            {snapshot ? (
              <div className="homeSnap">
                <div className="homeSnapStat">
                  <span>Avg factor</span>
                  <b>{snapshot.avgFactor ?? "—"}</b>
                </div>
                <div className="homeSnapStat">
                  <span>Avg upside</span>
                  <b className={snapshot.avgUpside != null && snapshot.avgUpside >= 0 ? "up" : ""}>
                    {snapshot.avgUpside != null ? `${snapshot.avgUpside.toFixed(1)}%` : "—"}
                  </b>
                </div>
              </div>
            ) : (
              <p className="homeEmpty" style={{ padding: "4px 18px 14px" }}>
                Star securities to build your watchlist.
              </p>
            )}
            <div className="homePortfolioCta">
              <div className="homeCtaTitle">Track your portfolio</div>
              <p>Add holdings to see P&amp;L and factor exposure across everything you own.</p>
              {user ? (
                <Link href="/portfolio" className="homeCtaBtn">Open portfolio →</Link>
              ) : (
                <Link href="/login?next=%2F" className="homeCtaBtn">Sign in to start</Link>
              )}
            </div>
          </section>
        </div>

        <div className="homeSectionRow">
          <h2 className="homeSectionTitle">Your watchlist</h2>
          <Link href="/watchlist" className="homeSeeAll">Manage →</Link>
        </div>
        <div className="card">
          {watchRows.length ? (
            <table className="homeTable">
              <thead>
                <tr>
                  <th>Company</th>
                  <th className="r">Price</th>
                  <th className="r">Fair value</th>
                  <th className="r">Upside</th>
                  <th className="r">Factor</th>
                  <th>Rating</th>
                  <th className="r">Updated</th>
                </tr>
              </thead>
              <tbody>
                {watchRows.map((row) => {
                  const item = row.latest as ListItem;
                  const technicalOnly =
                    item.company.asset_type === "ETF" || item.qualification === "Technical Screen Only";
                  const indicators = item.technical_indicators ?? {};
                  const rating = ratingFor({
                    upsidePct: item.upside_pct,
                    technicalOnly,
                    signal: indicators.signal,
                    rsi: indicators.rsi14,
                    risk: item.risk_level,
                    score: item.opportunity_score,
                    trendCross: indicators.trend_cross,
                  });
                  const composite = item.factor_scores?.composite;
                  return (
                    <tr key={row.ticker}>
                      <td>
                        <Link href={`/stocks/${row.ticker}`} className="homeTk">
                          <b>{row.ticker}</b> <span>{row.name}</span>
                        </Link>
                      </td>
                      <td className="r num">{money(item.current_price)}</td>
                      <td className="r num">{technicalOnly ? <span className="dim">n/a</span> : money(item.fair_value)}</td>
                      <td className={`r num ${technicalOnly ? "dim" : item.upside_pct >= 0 ? "up" : "down"}`}>
                        {technicalOnly ? "n/a" : `${item.upside_pct.toFixed(1)}%`}
                      </td>
                      <td className="r">
                        {composite != null ? (
                          <b className={`homeFc${composite >= 66 ? " hi" : ""}`}>{composite}</b>
                        ) : (
                          <span className="dim">—</span>
                        )}
                      </td>
                      <td><span className={`ratingBadge rating--${rating.slug}`}>{rating.label}</span></td>
                      <td className="r dim num">{timeAgo(item.price_as_of ?? item.as_of, nowMs)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          ) : (
            <p className="homeEmpty" style={{ padding: "22px 20px" }}>
              {user ? (
                <>Your watchlist is empty. Open <Link href="/discover" className="homeLink">Discover</Link> and star securities to track them here.</>
              ) : (
                <><Link href="/login?next=%2F" className="homeLink">Sign in</Link> to build a watchlist and follow ratings, fair values, and dividends over time.</>
              )}
            </p>
          )}
        </div>

        <div className="homeSectionRow">
          <h2 className="homeSectionTitle">
            Ideas that fit <span className="homeSectionSub">· quality &amp; value, long-term</span>
          </h2>
          <Link href="/ideas" className="homeSeeAll">All ideas →</Link>
        </div>
        <div className="homeIdeas">
          {ideaCards.length === 0 && (
            <p className="homeEmpty">{ideas ? "No long-term ideas in the latest run." : "Finding ideas…"}</p>
          )}
          {ideaCards.map((idea) => (
            <Link href={`/stocks/${idea.ticker}`} className="card homeIdea" key={idea.ticker}>
              <div className="homeIdeaHead">
                <div>
                  <div className="homeTk"><b>{idea.ticker}</b></div>
                  <div className="homeIdeaName">{idea.name}</div>
                </div>
                <span className="homeIdeaScore">{Math.round(idea.idea_score)}</span>
              </div>
              {idea.reasons[0] && <p className="homeIdeaWhy">{idea.reasons[0]}</p>}
              <div className="homeIdeaMetrics">
                <div>
                  <span>Upside</span>
                  <b className={idea.upside_pct != null && idea.upside_pct >= 0 ? "up" : ""}>
                    {idea.upside_pct != null ? `${idea.upside_pct.toFixed(0)}%` : "n/a"}
                  </b>
                </div>
                <div>
                  <span>Score</span>
                  <b>{idea.opportunity_score}</b>
                </div>
                <div>
                  <span>Risk</span>
                  <b>{idea.risk_level}</b>
                </div>
              </div>
            </Link>
          ))}
        </div>

        <footer className="siteFooter">
          <span>Stock Intelligence · deterministic research terminal</span>
          <span>Research support — not investment advice</span>
        </footer>
      </main>
    </>
  );
}
