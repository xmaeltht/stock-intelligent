"use client";

import { Suspense, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import TopNav from "../../components/TopNav";
import { useAuth } from "../../lib/auth";
import { getJson, postJson } from "../../lib/api";

type BillingStatus = { plan: string; is_pro: boolean; billing_enabled: boolean };

const FREE_FEATURES = [
  "Full screener & company deep-dives",
  "Factor scores & fair values",
  "One personal watchlist",
  "Paper portfolio & journal",
  "Up to 3 alerts",
];

const PRO_FEATURES = [
  "Everything in Free, plus:",
  "Unlimited alerts & watchlists",
  "Background + email alert delivery",
  "Priority data refresh",
  "Full snapshot history",
];

function PricingContent() {
  const pathname = usePathname();
  const params = useSearchParams();
  const upgraded = params.get("upgraded") === "1";
  const { user, loading: authLoading } = useAuth();
  const [status, setStatus] = useState<BillingStatus | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const loadStatus = useCallback(() => {
    if (!user) return;
    getJson<BillingStatus>("/api/research/billing/status").then(setStatus).catch(() => setStatus(null));
  }, [user]);

  useEffect(loadStatus, [loadStatus]);

  const upgrade = async () => {
    setError("");
    setBusy(true);
    try {
      const { url } = await postJson<{ url: string }>("/api/research/billing/checkout", {});
      window.location.href = url;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not start checkout.");
      setBusy(false);
    }
  };

  const isPro = status?.is_pro;
  const billingEnabled = status?.billing_enabled ?? false;

  const proCta = () => {
    if (!user) {
      return (
        <Link href={`/login?next=${encodeURIComponent(pathname)}`} className="btn btn--primary priceBtn">
          Sign in to upgrade
        </Link>
      );
    }
    if (isPro) return <div className="priceCurrent">✓ You&apos;re on Pro</div>;
    if (!billingEnabled) {
      return (
        <button className="btn priceBtn" type="button" disabled title="Billing is being set up">
          Coming soon
        </button>
      );
    }
    return (
      <button className="btn btn--primary priceBtn" type="button" onClick={upgrade} disabled={busy}>
        {busy ? "…" : "Upgrade to Pro"}
      </button>
    );
  };

  return (
    <main className="shell">
      <div className="pageHead" style={{ justifyContent: "center", textAlign: "center" }}>
        <div>
          <span className="eyebrow">Pricing</span>
          <h1>Simple pricing. Free to start.</h1>
          <p style={{ margin: "0 auto" }}>
            Use the core research tools free forever. Upgrade for unlimited alerts, background
            delivery, and priority data.
          </p>
        </div>
      </div>

      {upgraded && (
        <div className="notice notice--ok" style={{ marginBottom: 16 }}>
          🎉 Welcome to Pro — your upgrade is being confirmed. It may take a moment to reflect.
        </div>
      )}
      {error && <div className="notice notice--error" style={{ marginBottom: 16 }}>{error}</div>}

      <div className="priceGrid">
        <div className="card price">
          <div className="plan">Free</div>
          <div className="priceTag">$0<small> / forever</small></div>
          <ul className="plist">
            {FREE_FEATURES.map((feature) => (
              <li key={feature}><span className="ck">✓</span> {feature}</li>
            ))}
          </ul>
          {!authLoading && (user ? (
            !isPro ? <div className="priceCurrent">Your current plan</div> : <span />
          ) : (
            <Link href="/login?next=%2Fpricing" className="btn priceBtn">Start free</Link>
          ))}
        </div>

        <div className="card price price--pro">
          <div className="plan">Pro</div>
          <div className="priceTag">$12<small> / month</small></div>
          <ul className="plist">
            {PRO_FEATURES.map((feature) => (
              <li key={feature}><span className="ck">✓</span> {feature}</li>
            ))}
          </ul>
          {proCta()}
        </div>
      </div>

      <p className="pricingNote">
        Cancel anytime. Rules-based research — not investment advice.
      </p>

      <footer className="siteFooter">
        <span>Stock Intelligence · deterministic research terminal</span>
        <span>Research support — not investment advice</span>
      </footer>
    </main>
  );
}

export default function PricingPage() {
  return (
    <>
      <TopNav online />
      <Suspense fallback={<main className="shell"><p className="notice">Loading…</p></main>}>
        <PricingContent />
      </Suspense>
    </>
  );
}
