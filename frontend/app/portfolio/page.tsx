"use client";

import Link from "next/link";
import TopNav from "../../components/TopNav";

export default function Portfolio() {
  return (
    <>
      <TopNav online />
      <main className="shell">
        <div className="pageHead">
          <div>
            <span className="eyebrow">Coming soon</span>
            <h1>Portfolio</h1>
            <p>
              Add your holdings to track gains and losses and see your whole portfolio scored on the
              same transparent factors — quality, value, income, and concentration.
            </p>
          </div>
        </div>

        <div className="card portfolioTease">
          <div className="portfolioTeaseInner">
            <div className="portfolioTeaseIcon">📊</div>
            <h2>Your portfolio, scored like everything else</h2>
            <p>
              Portfolio tracking arrives with accounts. You&apos;ll add holdings once, then see live
              P&amp;L, estimated dividends, factor exposure versus the market, and alerts when a
              holding&apos;s rating or fair value changes.
            </p>
            <div className="portfolioTeaseActions">
              <button className="btn" type="button" disabled title="Accounts are coming soon">
                Sign in to start · coming soon
              </button>
              <Link href="/discover" className="btn btn--ghost">Explore the screener</Link>
            </div>
          </div>
        </div>

        <footer className="siteFooter">
          <span>Stock Intelligence · deterministic research terminal</span>
          <span>Research support — not investment advice</span>
        </footer>
      </main>
    </>
  );
}
