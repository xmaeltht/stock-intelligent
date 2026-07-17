"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import TopNav from "../../components/TopNav";
import SignInPrompt from "../../components/SignInPrompt";
import { useAuth } from "../../lib/auth";
import {
  ALERT_KIND_LABEL,
  deleteJson,
  getJson,
  postJson,
  timeAgo,
  type AlertEvent,
  type AlertKind,
  type AlertRule,
} from "../../lib/api";

const KINDS: AlertKind[] = ["price_below", "price_above", "upside_above"];

export default function AlertsPage() {
  const { user, loading: authLoading } = useAuth();
  const [rules, setRules] = useState<AlertRule[] | null>(null);
  const [events, setEvents] = useState<AlertEvent[] | null>(null);
  const [ticker, setTicker] = useState("");
  const [kind, setKind] = useState<AlertKind>("price_below");
  const [threshold, setThreshold] = useState("");
  const [formError, setFormError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [nowMs, setNowMs] = useState(() => Date.now());

  const load = useCallback(() => {
    if (!user) return;
    getJson<AlertRule[]>("/api/research/alerts").then(setRules).catch(() => setRules([]));
    getJson<AlertEvent[]>("/api/research/alerts/events")
      .then(async (list) => {
        setEvents(list);
        if (list.some((event) => !event.read_at)) {
          try {
            await postJson("/api/research/alerts/read", {});
          } catch {
            /* best-effort — the badge will clear on next visit */
          }
        }
      })
      .catch(() => setEvents([]));
  }, [user]);

  useEffect(load, [load]);

  useEffect(() => {
    const timer = setInterval(() => setNowMs(Date.now()), 1000);
    return () => clearInterval(timer);
  }, []);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setFormError("");
    const value = Number(threshold);
    if (!ticker.trim() || !Number.isFinite(value)) {
      setFormError("Enter a ticker and a numeric value.");
      return;
    }
    setSubmitting(true);
    try {
      await postJson<AlertRule>("/api/research/alerts", {
        ticker: ticker.trim().toUpperCase(),
        kind,
        threshold: value,
      });
      setTicker("");
      setThreshold("");
      load();
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "Could not create the alert.");
    } finally {
      setSubmitting(false);
    }
  };

  const remove = async (id: string) => {
    setRules((current) => current?.filter((rule) => rule.id !== id) ?? null);
    try {
      await deleteJson(`/api/research/alerts/${id}`);
    } catch {
      load();
    }
  };

  const unit = kind === "upside_above" ? "%" : "$";

  return (
    <>
      <TopNav online={rules ? true : undefined} />
      <main className="shell">
        <div className="pageHead">
          <div>
            <span className="eyebrow">Stay ahead</span>
            <h1>Alerts</h1>
            <p>
              Get notified when a security crosses a price you care about or its modeled upside
              opens up. Evaluated continuously against the latest analysis.
            </p>
          </div>
        </div>

        {!authLoading && !user && (
          <SignInPrompt
            title="Sign in to set alerts"
            body="Create price and upside alerts on any security and see them fire the moment a threshold is crossed."
            icon="🔔"
          />
        )}

        {user && (
          <>
            <form className="pfTradeForm card" onSubmit={submit}>
              <div className="pfFormTitle">New alert</div>
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
                  Condition
                  <select value={kind} onChange={(e) => setKind(e.target.value as AlertKind)}>
                    {KINDS.map((k) => (
                      <option key={k} value={k}>{ALERT_KIND_LABEL[k]}</option>
                    ))}
                  </select>
                </label>
                <label>
                  Value ({unit})
                  <input
                    type="number"
                    value={threshold}
                    onChange={(e) => setThreshold(e.target.value)}
                    placeholder={kind === "upside_above" ? "20" : "180"}
                    step="any"
                  />
                </label>
                <button className="btn pfSubmit" type="submit" disabled={submitting}>
                  {submitting ? "…" : "Add alert"}
                </button>
              </div>
              {formError && <div className="pfFormError">{formError}</div>}
            </form>

            <h2 className="pfSection">Recent alerts</h2>
            {events && events.length > 0 ? (
              <div className="card alertFeed">
                {events.map((event) => (
                  <Link href={`/stocks/${event.ticker}`} className="alertRow" key={event.id}>
                    <span className={`alertDot alert--${event.kind}`}>
                      {event.kind === "price_below" ? "▼" : event.kind === "price_above" ? "▲" : "◆"}
                    </span>
                    <span className="alertBody">
                      <span className="alertMsg">{event.message}</span>
                      <span className="alertTime">{timeAgo(event.created_at, nowMs)} ago</span>
                    </span>
                  </Link>
                ))}
              </div>
            ) : (
              <div className="notice">
                No alerts have fired yet. Add a rule above — you&apos;ll see crossings here.
              </div>
            )}

            <h2 className="pfSection">Your alert rules</h2>
            {rules && rules.length > 0 ? (
              <div className="tableWrap">
                <table>
                  <thead>
                    <tr>
                      <th>Company</th>
                      <th>Condition</th>
                      <th className="r">Value</th>
                      <th />
                    </tr>
                  </thead>
                  <tbody>
                    {rules.map((rule) => (
                      <tr key={rule.id}>
                        <td className="tickerCell">
                          <Link href={`/stocks/${rule.ticker}`}>
                            <strong>{rule.ticker}</strong>
                            <span>{rule.name}</span>
                          </Link>
                        </td>
                        <td>{ALERT_KIND_LABEL[rule.kind]}</td>
                        <td className="r num">
                          {rule.kind === "upside_above"
                            ? `${Number(rule.threshold).toFixed(0)}%`
                            : `$${Number(rule.threshold).toFixed(2)}`}
                        </td>
                        <td className="r">
                          <button className="alertDelete" title="Delete alert" onClick={() => remove(rule.id)}>
                            ✕
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="notice">No alert rules yet.</div>
            )}
          </>
        )}

        <footer className="siteFooter">
          <span>Alerts evaluate against the latest analysis while you&apos;re signed in</span>
          <span>Research support — not investment advice</span>
        </footer>
      </main>
    </>
  );
}
