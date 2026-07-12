"use client";

import { useEffect, useState } from "react";

type HealthState =
  | { phase: "checking" }
  | { phase: "healthy"; version: string; environment: string }
  | { phase: "unavailable" };

const researchSteps = [
  ["01", "Collect", "Prices, filings, and financial statements"],
  ["02", "Value", "Bear, base, and bull scenarios"],
  ["03", "Explain", "Catalysts, risks, and thesis breakers"],
];

export default function Dashboard() {
  const [health, setHealth] = useState<HealthState>({ phase: "checking" });

  useEffect(() => {
    const controller = new AbortController();

    async function checkBackend() {
      try {
        const response = await fetch("/api/health", { signal: controller.signal });
        if (!response.ok) throw new Error("backend unavailable");
        const payload = (await response.json()) as { version: string; environment: string };
        setHealth({ phase: "healthy", version: payload.version, environment: payload.environment });
      } catch (error) {
        if ((error as Error).name !== "AbortError") setHealth({ phase: "unavailable" });
      }
    }

    void checkBackend();
    return () => controller.abort();
  }, []);

  return (
    <main>
      <nav className="nav shell">
        <a className="brand" href="#top" aria-label="Stock Intelligence home">
          <span className="brandMark">SI</span>
          <span>Stock Intelligence</span>
        </a>
        <div className="navMeta">
          <span className={`statusDot statusDot--${health.phase}`} aria-hidden="true" />
          {health.phase === "checking" && "Checking API"}
          {health.phase === "healthy" && `API ${health.version}`}
          {health.phase === "unavailable" && "API unavailable"}
        </div>
      </nav>

      <section className="hero shell" id="top">
        <div className="eyebrow">Local research workspace</div>
        <div className="heroGrid">
          <div>
            <h1>Find the upside.<br />Interrogate the thesis.</h1>
            <p className="heroCopy">
              An evidence-first workspace for discovering stocks with 90%+ modeled upside—then
              understanding the valuation, catalyst, and risk behind every result.
            </p>
            <div className="heroActions">
              <button type="button" disabled>Run first screen</button>
              <span>Company data provider is the next milestone.</span>
            </div>
          </div>

          <aside className="systemCard" aria-label="Foundation status">
            <div className="systemCardHeader">
              <span>Foundation status</span>
              <span className="kicker">MVP 0.1</span>
            </div>
            <dl>
              <div><dt>Frontend</dt><dd className="good">Online</dd></div>
              <div><dt>Backend API</dt><dd className={health.phase === "healthy" ? "good" : "muted"}>{health.phase}</dd></div>
              <div><dt>Universe</dt><dd className="muted">Not loaded</dd></div>
              <div><dt>Last pipeline</dt><dd className="muted">Waiting</dd></div>
            </dl>
            <p>
              {health.phase === "healthy"
                ? `FastAPI is responding from the ${health.environment} environment.`
                : "Start the backend to complete the application health check."}
            </p>
          </aside>
        </div>
      </section>

      <section className="workflow shell" aria-labelledby="workflow-title">
        <div className="sectionHeading">
          <div>
            <span className="eyebrow">Research pipeline</span>
            <h2 id="workflow-title">From raw evidence to a qualified opportunity</h2>
          </div>
          <span className="sectionNote">Nightly · Point-in-time · Auditable</span>
        </div>
        <div className="steps">
          {researchSteps.map(([number, title, copy]) => (
            <article key={number} className="step">
              <span className="stepNumber">{number}</span>
              <h3>{title}</h3>
              <p>{copy}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="emptyState shell">
        <div>
          <span className="eyebrow">Opportunity dashboard</span>
          <h2>No claims without evidence.</h2>
        </div>
        <p>
          The dashboard will populate after the company universe and first data provider are
          connected. Every future opportunity will show its model, assumptions, source dates,
          catalyst confidence, and thesis breakers.
        </p>
      </section>

      <footer className="shell">
        <span>Stock Intelligence</span>
        <span>Research support—not investment advice.</span>
      </footer>
    </main>
  );
}

