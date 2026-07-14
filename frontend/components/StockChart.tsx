"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import type { PricePoint } from "../lib/api";

const W = 1100;
const PRICE_H = 340;
const VOL_H = 70;
const RSI_H = 90;
const MACD_H = 110;
const PAD_L = 56;
const PAD_R = 14;
const PAD_T = 12;

const COLORS = {
  price: "#5aa2ff",
  sma20: "#2fbf7f",
  sma50: "#f0c05a",
  sma100: "#a99bff",
  sma200: "#ff8fa3",
  bb: "#8a97a8",
  up: "#2fbf7f",
  down: "#e66767",
  neutral: "#5f6b7c",
  volume: "#2a3648",
};

const sma = (values: number[], period: number): Array<number | null> =>
  values.map((_, index) => {
    if (index + 1 < period) return null;
    let sum = 0;
    for (let cursor = index + 1 - period; cursor <= index; cursor += 1) sum += values[cursor];
    return sum / period;
  });

const ema = (values: number[], period: number): number[] => {
  const multiplier = 2 / (period + 1);
  const result: number[] = [];
  values.forEach((value, index) =>
    result.push(index === 0 ? value : (value - result[index - 1]) * multiplier + result[index - 1]),
  );
  return result;
};

const stdev = (values: number[]) => {
  const avg = values.reduce((sum, value) => sum + value, 0) / values.length;
  return Math.sqrt(values.reduce((sum, value) => sum + (value - avg) ** 2, 0) / values.length);
};

const wilderRsiSeries = (closes: number[], period = 14): Array<number | null> => {
  const result: Array<number | null> = closes.map(() => null);
  if (closes.length <= period) return result;
  let gain = 0;
  let loss = 0;
  for (let index = 1; index <= period; index += 1) {
    const change = closes[index] - closes[index - 1];
    gain += Math.max(change, 0);
    loss += Math.max(-change, 0);
  }
  gain /= period;
  loss /= period;
  result[period] = loss === 0 ? 100 : 100 - 100 / (1 + gain / loss);
  for (let index = period + 1; index < closes.length; index += 1) {
    const change = closes[index] - closes[index - 1];
    gain = (gain * (period - 1) + Math.max(change, 0)) / period;
    loss = (loss * (period - 1) + Math.max(-change, 0)) / period;
    result[index] = loss === 0 ? 100 : 100 - 100 / (1 + gain / loss);
  }
  return result;
};

type Overlay = "candles" | "sma20" | "sma50" | "sma100" | "sma200" | "bb" | "volume" | "rsi" | "macd";
const DEFAULT_SHOW: Record<Overlay, boolean> = {
  candles: true, sma20: true, sma50: true, sma100: false, sma200: true,
  bb: true, volume: true, rsi: true, macd: true,
};
const INDICATORS: Array<{ key: Overlay; label: string; color?: string }> = [
  { key: "candles", label: "Candles" },
  { key: "sma20", label: "SMA 20", color: COLORS.sma20 },
  { key: "sma50", label: "SMA 50", color: COLORS.sma50 },
  { key: "sma100", label: "SMA 100", color: COLORS.sma100 },
  { key: "sma200", label: "SMA 200", color: COLORS.sma200 },
  { key: "bb", label: "Bollinger", color: COLORS.bb },
  { key: "volume", label: "Volume", color: COLORS.volume },
  { key: "rsi", label: "RSI" },
  { key: "macd", label: "MACD" },
];

export default function StockChart({ history }: { history: PricePoint[] }) {
  const wrapRef = useRef<HTMLDivElement | null>(null);
  const priceSvgRef = useRef<SVGSVGElement | null>(null);
  const [hover, setHover] = useState<{ index: number; px: number; py: number } | null>(null);
  const [show, setShow] = useState<Record<Overlay, boolean>>(DEFAULT_SHOW);
  const [view, setView] = useState<{ s: number; e: number } | null>(null);
  const [brush, setBrush] = useState<{ start: number; cur: number } | null>(null);

  const wheelRef = useRef<((event: WheelEvent) => void) | null>(null);

  useEffect(() => {
    try {
      const saved = window.localStorage.getItem("si.chart.overlays");
      if (saved) setShow((current) => ({ ...current, ...JSON.parse(saved) }));
    } catch {
      /* ignore unavailable storage */
    }
  }, []);
  useEffect(() => {
    const svg = priceSvgRef.current;
    if (!svg) return;
    const handler = (event: WheelEvent) => {
      event.preventDefault();
      wheelRef.current?.(event);
    };
    svg.addEventListener("wheel", handler, { passive: false });
    return () => svg.removeEventListener("wheel", handler);
  }, []);
  const toggle = (key: Overlay) =>
    setShow((current) => {
      const next = { ...current, [key]: !current[key] };
      try {
        window.localStorage.setItem("si.chart.overlays", JSON.stringify(next));
      } catch {
        /* ignore */
      }
      return next;
    });

  const model = useMemo(() => {
    const closes = history.map((point) => Number(point.close));
    const hasOhlc = history.filter((point) => point.high != null && point.low != null && point.open != null).length > history.length * 0.8;
    const sma20 = sma(closes, 20);
    const sma50 = sma(closes, 50);
    const sma100 = sma(closes, 100);
    const sma200 = sma(closes, 200);
    const bbUpper: Array<number | null> = closes.map((_, index) => {
      if (index + 1 < 20) return null;
      const window = closes.slice(index - 19, index + 1);
      return window.reduce((sum, value) => sum + value, 0) / 20 + 2 * stdev(window);
    });
    const bbLower: Array<number | null> = closes.map((_, index) => {
      if (index + 1 < 20) return null;
      const window = closes.slice(index - 19, index + 1);
      return window.reduce((sum, value) => sum + value, 0) / 20 - 2 * stdev(window);
    });
    const ema12 = ema(closes, 12);
    const ema26 = ema(closes, 26);
    const ema13 = ema(closes, 13);
    const macd = ema12.map((value, index) => value - ema26[index]);
    const macdSignal = ema(macd, 9);
    const histogram = macd.map((value, index) => value - macdSignal[index]);
    const impulse = histogram.map((value, index) =>
      index === 0
        ? "neutral"
        : ema13[index] > ema13[index - 1] && value > histogram[index - 1]
          ? "up"
          : ema13[index] < ema13[index - 1] && value < histogram[index - 1]
            ? "down"
            : "neutral",
    );
    const rsi = wilderRsiSeries(closes);
    const highs = history.map((point, index) => Number(point.high ?? closes[index]));
    const lows = history.map((point, index) => Number(point.low ?? closes[index]));
    const plotted = [
      ...highs,
      ...lows,
      ...(bbUpper.filter((value): value is number => value !== null)),
      ...(bbLower.filter((value): value is number => value !== null)),
    ];
    return {
      closes,
      hasOhlc,
      sma20,
      sma50,
      sma100,
      sma200,
      bbUpper,
      bbLower,
      macd,
      macdSignal,
      histogram,
      impulse,
      rsi,
      highs,
      lows,
      min: Math.min(...plotted),
      max: Math.max(...plotted),
      maxVolume: Math.max(...history.map((point) => point.volume ?? 0), 1),
    };
  }, [history]);

  if (history.length < 2) {
    return <div className="notice">Chart data will appear after the continuous analyzer refreshes this security.</div>;
  }

  const count = history.length;
  // visible window (zoom). null → full range.
  const vs = view ? Math.max(0, Math.min(view.s, count - 2)) : 0;
  const ve = view ? Math.max(vs + 1, Math.min(view.e, count - 1)) : count - 1;
  const vspan = ve - vs;
  const inView = (index: number) => index >= vs && index <= ve;

  // y-range recomputed over just the visible window so zoom fills the frame
  const vis: number[] = [];
  for (let i = vs; i <= ve; i += 1) {
    vis.push(model.highs[i], model.lows[i]);
    if (show.bb) {
      if (model.bbUpper[i] != null) vis.push(model.bbUpper[i] as number);
      if (model.bbLower[i] != null) vis.push(model.bbLower[i] as number);
    }
    if (show.sma20 && model.sma20[i] != null) vis.push(model.sma20[i] as number);
    if (show.sma50 && model.sma50[i] != null) vis.push(model.sma50[i] as number);
    if (show.sma100 && model.sma100[i] != null) vis.push(model.sma100[i] as number);
    if (show.sma200 && model.sma200[i] != null) vis.push(model.sma200[i] as number);
  }
  const vmax = Math.max(...vis);
  const vmin = Math.min(...vis);
  const range = vmax - vmin || 1;
  const x = (index: number) => PAD_L + ((index - vs) / vspan) * (W - PAD_L - PAD_R);
  const y = (value: number) => PAD_T + ((vmax - value) / range) * (PRICE_H - PAD_T * 2);
  const bandWidth = Math.max(1.2, (W - PAD_L - PAD_R) / (vspan + 1) - 1.2);
  const maxVolume = Math.max(...history.slice(vs, ve + 1).map((p) => p.volume ?? 0), 1);

  const line = (values: Array<number | null>) =>
    values
      .map((value, index) => (value === null || !inView(index) ? null : `${x(index).toFixed(1)},${y(value).toFixed(1)}`))
      .filter(Boolean)
      .join(" ");

  const bandPath = (() => {
    const upper = model.bbUpper
      .map((value, index) => (value === null || !inView(index) ? null : `${x(index).toFixed(1)},${y(value).toFixed(1)}`))
      .filter(Boolean);
    const lower = model.bbLower
      .map((value, index) => (value === null || !inView(index) ? null : `${x(index).toFixed(1)},${y(value).toFixed(1)}`))
      .filter(Boolean)
      .reverse();
    if (!upper.length) return "";
    return `M${upper.join(" L")} L${lower.join(" L")} Z`;
  })();

  const rsiY = (value: number) => 10 + ((100 - value) / 100) * (RSI_H - 20);
  const macdRange = Math.max(
    ...model.macd.slice(vs, ve + 1).map(Math.abs),
    ...model.macdSignal.slice(vs, ve + 1).map(Math.abs),
    ...model.histogram.slice(vs, ve + 1).map(Math.abs),
    0.01,
  );
  const macdMid = MACD_H / 2;
  const macdY = (value: number) => macdMid - (value / macdRange) * (macdMid - 12);
  const macdLine = (values: number[]) =>
    values
      .map((value, index) => (inView(index) ? `${x(index).toFixed(1)},${macdY(value).toFixed(1)}` : null))
      .filter(Boolean)
      .join(" ");

  const priceTicks = [0, 0.25, 0.5, 0.75, 1].map((fraction) => vmin + range * fraction);
  const dateTickIndexes = [0, 0.25, 0.5, 0.75, 1].map((f) => Math.round(vs + f * vspan));

  const pointerIndex = (clientX: number, target: SVGSVGElement) => {
    const rect = target.getBoundingClientRect();
    const relative = ((clientX - rect.left) / rect.width) * W;
    const fraction = Math.min(1, Math.max(0, (relative - PAD_L) / (W - PAD_L - PAD_R)));
    return Math.round(vs + fraction * vspan);
  };

  const onMove = (event: React.MouseEvent<SVGSVGElement>) => {
    const index = pointerIndex(event.clientX, event.currentTarget);
    const wrapRect = wrapRef.current?.getBoundingClientRect();
    setHover({
      index,
      px: wrapRect ? event.clientX - wrapRect.left : 0,
      py: wrapRect ? event.clientY - wrapRect.top : 0,
    });
    if (brush) setBrush({ ...brush, cur: index });
  };

  const onDown = (event: React.MouseEvent<SVGSVGElement>) => {
    const index = pointerIndex(event.clientX, event.currentTarget);
    setBrush({ start: index, cur: index });
  };
  const onUp = () => {
    if (brush) {
      const s = Math.min(brush.start, brush.cur);
      const e = Math.max(brush.start, brush.cur);
      if (e - s >= 4) setView({ s, e });
      setBrush(null);
    }
  };

  const zoom = (factor: number, center: number) => {
    const newSpan = Math.max(10, Math.min(count - 1, Math.round(vspan * factor)));
    const ratio = (center - vs) / vspan || 0.5;
    let s = Math.round(center - ratio * newSpan);
    s = Math.max(0, Math.min(s, count - 1 - newSpan));
    setView(newSpan >= count - 1 ? null : { s, e: s + newSpan });
  };

  const presets: Array<{ label: string; days: number | null }> = [
    { label: "1M", days: 21 }, { label: "3M", days: 63 }, { label: "6M", days: 126 },
    { label: "1Y", days: 252 }, { label: "All", days: null },
  ];
  const applyPreset = (days: number | null) => {
    if (days === null || days >= count) setView(null);
    else setView({ s: count - 1 - days, e: count - 1 });
  };

  const hovered = hover ? history[hover.index] : null;
  const canCandles = model.hasOhlc && show.candles;
  wheelRef.current = (event: WheelEvent) => {
    const svg = priceSvgRef.current;
    if (!svg) return;
    zoom(event.deltaY < 0 ? 0.82 : 1.22, pointerIndex(event.clientX, svg));
  };
  const zoomed = view !== null;

  return (
    <div className="chartShell">
      <div className="chartTools">
        <div className="indicatorPicker">
          {INDICATORS.map((ind) => (
            <button
              key={ind.key}
              className={`indChip${show[ind.key] ? " on" : ""}`}
              onClick={() => toggle(ind.key)}
              aria-pressed={show[ind.key]}
            >
              {ind.color && <i style={{ background: ind.color }} />}
              {ind.label}
            </button>
          ))}
        </div>
        <div className="rangePicker">
          {presets.map((preset) => (
            <button key={preset.label} className="rangeBtn" onClick={() => applyPreset(preset.days)}>
              {preset.label}
            </button>
          ))}
          {zoomed && <button className="rangeBtn rangeBtn--reset" onClick={() => setView(null)}>Reset ✕</button>}
        </div>
      </div>
      <div className="chartWrap" ref={wrapRef}>
        <svg
          ref={priceSvgRef}
          className="stockChart"
          style={{ cursor: brush ? "ew-resize" : "crosshair", touchAction: "none" }}
          viewBox={`0 0 ${W} ${PRICE_H + VOL_H}`}
          role="img"
          aria-label="Zoomable price chart with selectable moving averages, Bollinger bands, and volume. Scroll to zoom, drag to select a range."
          onMouseMove={onMove}
          onMouseLeave={() => { setHover(null); setBrush(null); }}
          onMouseDown={onDown}
          onMouseUp={onUp}
        >
          {priceTicks.map((tick) => (
            <g key={tick}>
              <line x1={PAD_L} x2={W - PAD_R} y1={y(tick)} y2={y(tick)} className="gridLine" />
              <text x={PAD_L - 8} y={y(tick) + 3} textAnchor="end">${tick >= 100 ? tick.toFixed(0) : tick.toFixed(2)}</text>
            </g>
          ))}
          {show.bb && bandPath && <path d={bandPath} fill="#8a97a815" stroke="none" />}
          {show.bb && <polyline points={line(model.bbUpper)} fill="none" stroke={COLORS.bb} strokeWidth="1" strokeDasharray="3 4" opacity="0.7" />}
          {show.bb && <polyline points={line(model.bbLower)} fill="none" stroke={COLORS.bb} strokeWidth="1" strokeDasharray="3 4" opacity="0.7" />}
          {show.volume && history.map((point, index) => {
            if (!inView(index)) return null;
            const barHeight = ((point.volume ?? 0) / maxVolume) * (VOL_H - 8);
            const upDay = index > 0 && model.closes[index] >= model.closes[index - 1];
            return (
              <rect
                key={`volume-${point.date}`}
                x={x(index) - bandWidth / 2}
                y={PRICE_H + VOL_H - barHeight}
                width={bandWidth}
                height={Math.max(barHeight, 0.5)}
                fill={upDay ? "#2fbf7f3d" : "#e666673d"}
              />
            );
          })}
          {canCandles
            ? history.map((point, index) => {
                if (!inView(index)) return null;
                const open = Number(point.open ?? point.close);
                const close = model.closes[index];
                const upDay = close >= open;
                const color = upDay ? COLORS.up : COLORS.down;
                const bodyTop = y(Math.max(open, close));
                const bodyHeight = Math.max(Math.abs(y(open) - y(close)), 1);
                return (
                  <g key={`candle-${point.date}`}>
                    <line x1={x(index)} x2={x(index)} y1={y(model.highs[index])} y2={y(model.lows[index])} stroke={color} strokeWidth="1" />
                    <rect x={x(index) - bandWidth / 2} y={bodyTop} width={bandWidth} height={bodyHeight} fill={color} rx="0.5" />
                  </g>
                );
              })
            : <polyline points={line(model.closes.map((value) => value))} fill="none" stroke={COLORS.price} strokeWidth="2" strokeLinejoin="round" />}
          {show.sma200 && <polyline points={line(model.sma200)} fill="none" stroke={COLORS.sma200} strokeWidth="1.8" opacity="0.95" />}
          {show.sma100 && <polyline points={line(model.sma100)} fill="none" stroke={COLORS.sma100} strokeWidth="1.6" opacity="0.9" />}
          {show.sma50 && <polyline points={line(model.sma50)} fill="none" stroke={COLORS.sma50} strokeWidth="1.5" />}
          {show.sma20 && <polyline points={line(model.sma20)} fill="none" stroke={COLORS.sma20} strokeWidth="1.5" />}
          {dateTickIndexes.map((index) => (
            <text key={`date-${index}`} x={x(index)} y={PRICE_H + VOL_H - 2} textAnchor={index === 0 ? "start" : index === count - 1 ? "end" : "middle"} className="axisLabel">
              {history[index].date}
            </text>
          ))}
          {brush && Math.abs(brush.cur - brush.start) >= 1 && (
            <rect
              x={x(Math.min(brush.start, brush.cur))}
              y={PAD_T}
              width={Math.abs(x(brush.cur) - x(brush.start))}
              height={PRICE_H + VOL_H - PAD_T}
              fill="#5aa2ff22"
              stroke="#5aa2ff"
              strokeWidth="0.8"
              strokeDasharray="4 3"
            />
          )}
          {hover && (
            <line x1={x(hover.index)} x2={x(hover.index)} y1={PAD_T} y2={PRICE_H + VOL_H} stroke="#8a97a8" strokeWidth="0.7" strokeDasharray="3 3" />
          )}
        </svg>
        {hover && hovered && (
          <div
            className="chartTip"
            style={{
              left: Math.min(hover.px + 16, (wrapRef.current?.clientWidth ?? 600) - 190),
              top: Math.max(hover.py - 90, 4),
            }}
          >
            <b>{hovered.date}</b><br />
            {model.hasOhlc && hovered.open != null && (
              <>O {Number(hovered.open).toFixed(2)} · H {Number(hovered.high).toFixed(2)} · L {Number(hovered.low).toFixed(2)}<br /></>
            )}
            C <b>{Number(hovered.close).toFixed(2)}</b><br />
            Vol {hovered.volume ? hovered.volume.toLocaleString() : "—"}<br />
            {model.sma20[hover.index] != null && <>SMA20 {model.sma20[hover.index]!.toFixed(2)} </>}
            {model.sma50[hover.index] != null && <>· SMA50 {model.sma50[hover.index]!.toFixed(2)}</>}
          </div>
        )}
      </div>

      {show.rsi && (
      <>
      <div className="chartLegend" style={{ marginTop: 10 }}>
        <span><i style={{ background: COLORS.sma100 }} /> RSI 14 (Wilder)</span>
        <span className="dim">70 overbought · 30 oversold</span>
      </div>
      <svg className="stockChart" viewBox={`0 0 ${W} ${RSI_H}`} role="img" aria-label="RSI 14 oscillator">
        {[30, 50, 70].map((level) => (
          <g key={level}>
            <line x1={PAD_L} x2={W - PAD_R} y1={rsiY(level)} y2={rsiY(level)} className="gridLine" strokeDasharray={level === 50 ? "" : "4 4"} />
            <text x={PAD_L - 8} y={rsiY(level) + 3} textAnchor="end">{level}</text>
          </g>
        ))}
        <rect x={PAD_L} y={rsiY(70)} width={W - PAD_L - PAD_R} height={rsiY(30) - rsiY(70)} fill="#5aa2ff0f" />
        <polyline
          points={model.rsi.map((value, index) => (value === null || !inView(index) ? null : `${x(index).toFixed(1)},${rsiY(value).toFixed(1)}`)).filter(Boolean).join(" ")}
          fill="none"
          stroke={COLORS.sma100}
          strokeWidth="1.6"
        />
      </svg>
      </>
      )}

      {show.macd && (
      <>
      <div className="chartLegend" style={{ marginTop: 10 }}>
        <span>Impulse MACD (12, 26, 9)</span>
        <span style={{ color: COLORS.up }}>Bullish impulse</span>
        <span style={{ color: COLORS.down }}>Bearish impulse</span>
        <span className="dim">Mixed</span>
      </div>
      <svg className="stockChart" viewBox={`0 0 ${W} ${MACD_H}`} role="img" aria-label="Impulse MACD histogram with MACD and signal lines">
        <line x1={PAD_L} x2={W - PAD_R} y1={macdMid} y2={macdMid} className="gridLine" />
        {model.histogram.map((value, index) => {
          if (!inView(index)) return null;
          const barY = macdY(value);
          const color = model.impulse[index] === "up" ? COLORS.up : model.impulse[index] === "down" ? COLORS.down : COLORS.neutral;
          return (
            <rect
              key={`macd-${history[index].date}`}
              x={x(index) - bandWidth / 2}
              y={Math.min(macdMid, barY)}
              width={bandWidth}
              height={Math.max(1, Math.abs(macdMid - barY))}
              fill={color}
              opacity="0.85"
            />
          );
        })}
        <polyline points={macdLine(model.macd)} fill="none" stroke="#dfe7f1" strokeWidth="1.4" />
        <polyline points={macdLine(model.macdSignal)} fill="none" stroke={COLORS.sma50} strokeWidth="1.4" />
        <text x={PAD_L} y={12}>MACD {model.macd.at(-1)?.toFixed(3)}</text>
        <text x={W - PAD_R} y={12} textAnchor="end">Signal {model.macdSignal.at(-1)?.toFixed(3)}</text>
      </svg>
      </>
      )}
    </div>
  );
}
