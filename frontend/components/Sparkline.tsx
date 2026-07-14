"use client";

// Tiny inline trend line for table rows. Colored by net direction over the window.
export default function Sparkline({
  values,
  width = 68,
  height = 22,
}: {
  values?: number[] | null;
  width?: number;
  height?: number;
}) {
  if (!values || values.length < 3) {
    return <span className="dim sparkEmpty">—</span>;
  }
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const step = width / (values.length - 1);
  const points = values
    .map((value, index) => {
      const x = index * step;
      const y = height - 2 - ((value - min) / range) * (height - 4);
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
  const up = values[values.length - 1] >= values[0];
  const stroke = up ? "var(--bull-bright, #38e0a0)" : "var(--bear-bright, #ff7a7a)";
  const lastX = (values.length - 1) * step;
  const lastY = height - 2 - ((values[values.length - 1] - min) / range) * (height - 4);
  return (
    <svg className="spark" width={width} height={height} viewBox={`0 0 ${width} ${height}`} aria-hidden="true">
      <polyline points={points} fill="none" stroke={stroke} strokeWidth="1.5" strokeLinejoin="round" strokeLinecap="round" />
      <circle cx={lastX} cy={lastY} r="1.6" fill={stroke} />
    </svg>
  );
}
