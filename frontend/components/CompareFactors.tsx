"use client";

import { type Detail, type FactorScores } from "../lib/api";

const AXES: Array<{ key: keyof FactorScores; label: string }> = [
  { key: "value", label: "Value" },
  { key: "quality", label: "Quality" },
  { key: "momentum", label: "Momentum" },
  { key: "growth", label: "Growth" },
  { key: "income", label: "Income" },
];

// Distinct, dark-theme-tuned categorical palette for up to six overlaid series.
// Ordered for maximum separation between adjacent picks.
const SERIES_COLORS = ["#5aa2ff", "#f0c05a", "#46d6a8", "#a99bff", "#ff6b7d", "#9ad46b"];

const CX = 130;
const CY = 122;
const R = 92;

const point = (index: number, fraction: number): [number, number] => {
  const angle = -Math.PI / 2 + (index / AXES.length) * Math.PI * 2;
  return [CX + Math.cos(angle) * R * fraction, CY + Math.sin(angle) * R * fraction];
};

type Series = { ticker: string; scores: FactorScores; color: string };

export default function CompareFactors({ items }: { items: Detail[] }) {
  const series: Series[] = items
    .filter(
      (item) =>
        item.factor_scores && AXES.some((axis) => typeof item.factor_scores?.[axis.key] === "number"),
    )
    .slice(0, 6)
    .map((item, index) => ({
      ticker: item.company.ticker,
      scores: item.factor_scores as FactorScores,
      color: SERIES_COLORS[index % SERIES_COLORS.length],
    }));

  // Nothing rated yet — leave the numeric table below as the sole view.
  if (series.length === 0) return null;

  const rows: Array<{ key: keyof FactorScores; label: string }> = [
    ...AXES,
    { key: "composite", label: "Composite" },
  ];

  // Best score per factor, so we can outline the leader in each row.
  const leaderByRow = new Map<keyof FactorScores, number>();
  rows.forEach((row) => {
    let best = -Infinity;
    series.forEach((s) => {
      const value = s.scores[row.key];
      if (typeof value === "number" && value > best) best = value;
    });
    leaderByRow.set(row.key, best);
  });

  const columns = `92px repeat(${series.length}, minmax(0, 1fr))`;

  return (
    <section className="panel compareFactors">
      <div className="panelTitle">
        <h2>Factor overlay</h2>
        <span className="eyebrow">Value · Quality · Momentum · Growth · Income</span>
      </div>
      <div className="compareFactorGrid">
        <svg className="factorRadar" viewBox="0 0 260 250" role="img" aria-label="Overlaid factor radar">
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
          {series.map((s) => {
            const polygon = AXES.map((axis, index) => {
              const [x, y] = point(index, ((s.scores[axis.key] as number) ?? 0) / 100);
              return `${x.toFixed(1)},${y.toFixed(1)}`;
            }).join(" ");
            return (
              <g key={s.ticker}>
                <polygon
                  points={polygon}
                  fill={s.color}
                  fillOpacity={0.1}
                  stroke={s.color}
                  strokeWidth="2"
                  strokeLinejoin="round"
                />
                {AXES.map((axis, index) => {
                  const [x, y] = point(index, ((s.scores[axis.key] as number) ?? 0) / 100);
                  return <circle key={axis.key} cx={x} cy={y} r="2.4" fill={s.color} />;
                })}
              </g>
            );
          })}
        </svg>

        <div className="compareFactorTable">
          <div className="compareFactorLegend">
            {series.map((s) => (
              <span key={s.ticker} className="compareFactorTag">
                <i style={{ background: s.color }} />
                {s.ticker}
              </span>
            ))}
          </div>
          {rows.map((row) => (
            <div className="compareFactorRow" key={row.key} style={{ gridTemplateColumns: columns }}>
              <span className="compareFactorLabel">{row.label}</span>
              {series.map((s) => {
                const value = s.scores[row.key];
                const isLeader =
                  typeof value === "number" && value === leaderByRow.get(row.key) && series.length > 1;
                return (
                  <div
                    className={`compareFactorCell${isLeader ? " compareFactorCell--lead" : ""}`}
                    key={s.ticker}
                    title={`${s.ticker} ${row.label}: ${typeof value === "number" ? value : "n/a"}`}
                  >
                    <div className="compareFactorMini">
                      <i style={{ width: `${typeof value === "number" ? value : 0}%`, background: s.color }} />
                    </div>
                    <b>{typeof value === "number" ? value : "—"}</b>
                  </div>
                );
              })}
            </div>
          ))}
        </div>
      </div>
      <p className="compareFactorNote">
        Scores are 0–100 (higher is stronger). The leader in each factor is outlined. Rules-based screen output — not investment advice.
      </p>
    </section>
  );
}
