"use client";

import { useEffect, useState } from "react";
import { getJson, type FactorScores, type FactorsResponse } from "../lib/api";

const AXES: Array<{ key: keyof FactorScores; label: string }> = [
  { key: "value", label: "Value" },
  { key: "quality", label: "Quality" },
  { key: "momentum", label: "Momentum" },
  { key: "growth", label: "Growth" },
  { key: "income", label: "Income" },
];

const CX = 130;
const CY = 122;
const R = 92;

const point = (index: number, fraction: number): [number, number] => {
  const angle = -Math.PI / 2 + (index / AXES.length) * Math.PI * 2;
  return [CX + Math.cos(angle) * R * fraction, CY + Math.sin(angle) * R * fraction];
};

function scoreTone(score?: number) {
  if (score == null) return "dim";
  if (score >= 66) return "up";
  if (score <= 34) return "down";
  return "";
}

export default function FactorRadar({ ticker, fallback }: { ticker: string; fallback?: FactorScores }) {
  const [data, setData] = useState<FactorsResponse | null>(null);

  useEffect(() => {
    if (!ticker) return;
    getJson<FactorsResponse>(`/api/research/opportunities/stocks/${ticker}/factors`)
      .then(setData)
      .catch(() => setData(null));
  }, [ticker]);

  const scores = data?.scores ?? fallback ?? {};
  const percentiles = data?.sector_percentiles ?? {};
  const hasAny = AXES.some((axis) => typeof scores[axis.key] === "number");

  if (!hasAny) {
    return (
      <section className="panel" style={{ gridColumn: "1 / -1" }}>
        <div className="panelTitle"><h2>Factor profile</h2><span className="eyebrow">Value · Quality · Momentum · Growth · Income</span></div>
        <p style={{ color: "var(--muted)" }}>Factor scores will appear after the analyzer next rates this security.</p>
      </section>
    );
  }

  const polygon = AXES.map((axis, index) => {
    const [x, y] = point(index, ((scores[axis.key] as number) ?? 0) / 100);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(" ");

  return (
    <section className="panel" style={{ gridColumn: "1 / -1" }}>
      <div className="panelTitle">
        <h2>Factor profile</h2>
        <span className="eyebrow">
          {data ? `Percentiles vs ${data.peer_count} ${data.sector} peers` : "Value · Quality · Momentum · Growth · Income"}
        </span>
      </div>
      <div className="factorGrid">
        <svg className="factorRadar" viewBox="0 0 260 250" role="img" aria-label="Factor radar chart">
          {[0.25, 0.5, 0.75, 1].map((ring) => (
            <polygon
              key={ring}
              points={AXES.map((_, index) => point(index, ring).map((n) => n.toFixed(1)).join(",")).join(" ")}
              fill="none"
              stroke="rgba(255,255,255,0.07)"
              strokeWidth="1"
            />
          ))}
          {AXES.map((axis, index) => {
            const [x, y] = point(index, 1);
            const [lx, ly] = point(index, 1.22);
            return (
              <g key={axis.key}>
                <line x1={CX} y1={CY} x2={x} y2={y} stroke="rgba(255,255,255,0.07)" strokeWidth="1" />
                <text x={lx} y={ly} textAnchor="middle" className="factorAxisLabel">{axis.label}</text>
              </g>
            );
          })}
          <polygon points={polygon} fill="rgba(90,162,255,0.22)" stroke="#5aa2ff" strokeWidth="2" strokeLinejoin="round" />
          {AXES.map((axis, index) => {
            const [x, y] = point(index, ((scores[axis.key] as number) ?? 0) / 100);
            return <circle key={axis.key} cx={x} cy={y} r="2.6" fill="#5aa2ff" />;
          })}
        </svg>
        <div className="factorLegend">
          <div className="factorComposite">
            <span>Composite</span>
            <strong className={scoreTone(scores.composite)}>{scores.composite ?? "—"}</strong>
            <small>0–100 · higher is stronger</small>
          </div>
          {AXES.map((axis) => (
            <div key={axis.key} className="factorRow">
              <span>{axis.label}</span>
              <div className="factorBar">
                <i style={{ width: `${scores[axis.key] ?? 0}%` }} className={scoreTone(scores[axis.key] as number)} />
              </div>
              <b className={scoreTone(scores[axis.key] as number)}>{scores[axis.key] ?? "—"}</b>
              {percentiles[axis.key] != null && (
                <em className="factorPct">{percentiles[axis.key]}th</em>
              )}
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
