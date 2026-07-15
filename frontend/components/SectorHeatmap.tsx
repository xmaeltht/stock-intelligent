"use client";

import { useEffect, useState } from "react";
import { getJson, type SectorFactorMatrix } from "../lib/api";

const FACTOR_LABELS: Record<string, string> = {
  value: "Value",
  quality: "Quality",
  momentum: "Momentum",
  growth: "Growth",
  income: "Income",
  composite: "Composite",
};

function cellStyle(value: number | null): React.CSSProperties {
  if (value == null) return { color: "var(--faint)" };
  const t = (value - 50) / 50; // -1 (weak) .. +1 (strong)
  const alpha = 0.08 + Math.min(Math.abs(t), 1) * 0.42;
  const bg = t >= 0 ? `rgba(56,224,160,${alpha})` : `rgba(255,122,122,${alpha})`;
  return { background: bg, color: "var(--text)" };
}

export default function SectorHeatmap() {
  const [data, setData] = useState<SectorFactorMatrix | null>(null);

  useEffect(() => {
    getJson<SectorFactorMatrix>("/api/research/opportunities/sector-factors")
      .then(setData)
      .catch(() => setData(null));
  }, []);

  if (!data || data.sectors.length === 0) {
    return (
      <section className="panel">
        <div className="panelTitle"><h2>Sector factor map</h2><span className="eyebrow">Value · Quality · Momentum · Growth · Income</span></div>
        <p className="dim" style={{ fontSize: 12.5 }}>The heatmap fills in once the analyzer has scored each sector.</p>
      </section>
    );
  }

  return (
    <section className="panel">
      <div className="panelTitle">
        <h2>Sector factor map</h2>
        <span className="eyebrow">Average factor score by sector · green = strong, red = weak</span>
      </div>
      <div className="heatWrap">
        <table className="heatTable">
          <thead>
            <tr>
              <th className="heatSector">Sector</th>
              {data.factors.map((factor) => (
                <th key={factor} className="r">{FACTOR_LABELS[factor] ?? factor}</th>
              ))}
              <th className="r heatCount">Names</th>
            </tr>
          </thead>
          <tbody>
            {data.sectors.map((row) => (
              <tr key={row.sector}>
                <td className="heatSector">{row.sector}</td>
                {data.factors.map((factor) => {
                  const value = row[factor as keyof typeof row] as number | null;
                  return (
                    <td key={factor} className="heatCell" style={cellStyle(value)}>
                      {value == null ? "—" : value.toFixed(0)}
                    </td>
                  );
                })}
                <td className="r heatCount">{row.count.toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
