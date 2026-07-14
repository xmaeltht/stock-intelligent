"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import {
  createChart,
  CandlestickSeries,
  HistogramSeries,
  LineSeries,
  AreaSeries,
  ColorType,
  CrosshairMode,
  LineStyle,
  type IChartApi,
  type ISeriesApi,
  type UTCTimestamp,
} from "lightweight-charts";
import type { PricePoint } from "../lib/api";

const COLORS = {
  price: "#5aa2ff",
  sma20: "#38d39f",
  sma50: "#f4c95d",
  sma100: "#b3a4ff",
  sma200: "#ff8fa3",
  bb: "#8a97a8",
  up: "#2fbf7f",
  down: "#e66767",
  signal: "#f4c95d",
  grid: "rgba(255,255,255,0.045)",
  text: "#8a97a8",
  border: "rgba(255,255,255,0.08)",
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
  { key: "volume", label: "Volume", color: COLORS.up },
  { key: "rsi", label: "RSI", color: COLORS.sma100 },
  { key: "macd", label: "MACD", color: COLORS.price },
];

const PRESETS: Array<{ label: string; bars: number | null }> = [
  { label: "1M", bars: 21 }, { label: "3M", bars: 63 }, { label: "6M", bars: 126 },
  { label: "1Y", bars: 252 }, { label: "All", bars: null },
];

// dates arrive as YYYY-MM-DD; convert to a UTC timestamp so the axis is stable & unique
const toTime = (iso: string): UTCTimestamp =>
  (Date.parse(`${iso}T00:00:00Z`) / 1000) as UTCTimestamp;

export default function StockChart({ history }: { history: PricePoint[] }) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const legendRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<Record<string, ISeriesApi<"Candlestick" | "Line" | "Histogram" | "Area">>>({});
  const [show, setShow] = useState<Record<Overlay, boolean>>(DEFAULT_SHOW);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    try {
      const saved = window.localStorage.getItem("si.chart.overlays");
      if (saved) setShow((current) => ({ ...current, ...JSON.parse(saved) }));
    } catch {
      /* ignore unavailable storage */
    }
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

  // deterministic derived series
  const data = useMemo(() => {
    const seen = new Set<string>();
    const rows = history
      .filter((point) => point.date && !seen.has(point.date) && seen.add(point.date))
      .map((point) => ({ ...point, close: Number(point.close) }))
      .sort((a, b) => (a.date < b.date ? -1 : 1));
    const closes = rows.map((row) => row.close);
    const hasOhlc =
      rows.filter((row) => row.high != null && row.low != null && row.open != null).length >
      rows.length * 0.8;
    const sma20 = sma(closes, 20);
    const sma50 = sma(closes, 50);
    const sma100 = sma(closes, 100);
    const sma200 = sma(closes, 200);
    const bbUpper = closes.map((_, index) => {
      if (index + 1 < 20) return null;
      const window = closes.slice(index - 19, index + 1);
      return window.reduce((sum, value) => sum + value, 0) / 20 + 2 * stdev(window);
    });
    const bbLower = closes.map((_, index) => {
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

    const time = rows.map((row) => toTime(row.date));
    const lineData = (values: Array<number | null>) =>
      values
        .map((value, index) => (value == null ? null : { time: time[index], value }))
        .filter((point): point is { time: UTCTimestamp; value: number } => point !== null);

    return {
      rows,
      closes,
      hasOhlc,
      time,
      candles: rows.map((row, index) => ({
        time: time[index],
        open: Number(row.open ?? row.close),
        high: Number(row.high ?? row.close),
        low: Number(row.low ?? row.close),
        close: row.close,
      })),
      area: rows.map((row, index) => ({ time: time[index], value: row.close })),
      volume: rows.map((row, index) => ({
        time: time[index],
        value: row.volume ?? 0,
        color:
          index > 0 && closes[index] >= closes[index - 1]
            ? "rgba(47,191,127,0.34)"
            : "rgba(230,103,103,0.34)",
      })),
      sma20: lineData(sma20),
      sma50: lineData(sma50),
      sma100: lineData(sma100),
      sma200: lineData(sma200),
      bbUpper: lineData(bbUpper),
      bbLower: lineData(bbLower),
      rsi: lineData(rsi),
      macd: lineData(macd),
      macdSignal: lineData(macdSignal),
      histogram: rows.map((row, index) => ({
        time: time[index],
        value: histogram[index],
        color:
          impulse[index] === "up"
            ? "rgba(47,191,127,0.85)"
            : impulse[index] === "down"
              ? "rgba(230,103,103,0.85)"
              : "rgba(95,107,124,0.7)",
      })),
    };
  }, [history]);

  // build the chart; rebuild only when data or the pane layout (rsi/macd) changes
  useEffect(() => {
    const container = containerRef.current;
    if (!container || data.rows.length < 2) return;

    const priceH = 400;
    const rsiH = show.rsi ? 108 : 0;
    const macdH = show.macd ? 128 : 0;

    const chart = createChart(container, {
      width: container.clientWidth,
      height: priceH + rsiH + macdH,
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: COLORS.text,
        fontFamily: "var(--mono, ui-monospace), monospace",
        fontSize: 11,
        attributionLogo: false,
        panes: { separatorColor: COLORS.border, separatorHoverColor: "rgba(90,162,255,0.35)" },
      },
      grid: { vertLines: { color: COLORS.grid }, horzLines: { color: COLORS.grid } },
      rightPriceScale: { borderColor: COLORS.border, scaleMargins: { top: 0.06, bottom: 0.06 } },
      timeScale: { borderColor: COLORS.border, rightOffset: 4, barSpacing: 8, minBarSpacing: 1 },
      crosshair: {
        mode: CrosshairMode.Normal,
        vertLine: { color: "rgba(138,151,168,0.55)", width: 1, style: LineStyle.Dashed, labelBackgroundColor: "#1a2233" },
        horzLine: { color: "rgba(138,151,168,0.55)", labelBackgroundColor: "#1a2233" },
      },
      handleScroll: true,
      handleScale: true,
      autoSize: false,
    });
    chartRef.current = chart;
    const series: typeof seriesRef.current = {};

    // ── price pane (0)
    const candle = chart.addSeries(CandlestickSeries, {
      upColor: COLORS.up, downColor: COLORS.down,
      borderUpColor: COLORS.up, borderDownColor: COLORS.down,
      wickUpColor: "rgba(47,191,127,0.9)", wickDownColor: "rgba(230,103,103,0.9)",
      priceLineVisible: true, priceLineColor: "rgba(90,162,255,0.5)", priceLineStyle: LineStyle.Dotted,
      lastValueVisible: true,
      visible: show.candles && data.hasOhlc,
    }, 0);
    candle.setData(data.candles);
    series.candle = candle;

    const area = chart.addSeries(AreaSeries, {
      lineColor: COLORS.price, lineWidth: 2,
      topColor: "rgba(90,162,255,0.28)", bottomColor: "rgba(90,162,255,0.01)",
      priceLineVisible: false, lastValueVisible: !(show.candles && data.hasOhlc),
      crosshairMarkerVisible: true,
      visible: !(show.candles && data.hasOhlc),
    }, 0);
    area.setData(data.area);
    series.area = area;

    const addLine = (key: string, points: typeof data.sma20, color: string, width: number, dashed = false) => {
      const line = chart.addSeries(LineSeries, {
        color, lineWidth: width as 1 | 2 | 3 | 4,
        lineStyle: dashed ? LineStyle.Dashed : LineStyle.Solid,
        priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false,
      }, 0);
      line.setData(points);
      series[key] = line;
      return line;
    };
    addLine("sma20", data.sma20, COLORS.sma20, 1.5).applyOptions({ visible: show.sma20 });
    addLine("sma50", data.sma50, COLORS.sma50, 1.5).applyOptions({ visible: show.sma50 });
    addLine("sma100", data.sma100, COLORS.sma100, 1.5).applyOptions({ visible: show.sma100 });
    addLine("sma200", data.sma200, COLORS.sma200, 2).applyOptions({ visible: show.sma200 });
    addLine("bbUpper", data.bbUpper, "rgba(138,151,168,0.7)", 1, true).applyOptions({ visible: show.bb });
    addLine("bbLower", data.bbLower, "rgba(138,151,168,0.7)", 1, true).applyOptions({ visible: show.bb });

    // volume overlay at the bottom of the price pane
    const volume = chart.addSeries(HistogramSeries, {
      priceFormat: { type: "volume" },
      priceScaleId: "vol",
      priceLineVisible: false, lastValueVisible: false,
      visible: show.volume,
    }, 0);
    volume.setData(data.volume);
    chart.priceScale("vol", 0).applyOptions({ scaleMargins: { top: 0.82, bottom: 0 } });
    series.volume = volume;

    // ── RSI pane (1)
    if (show.rsi) {
      const rsi = chart.addSeries(LineSeries, {
        color: COLORS.sma100, lineWidth: 2,
        priceLineVisible: false, lastValueVisible: true,
        priceFormat: { type: "custom", formatter: (v: number) => v.toFixed(0), minMove: 1 },
      }, 1);
      rsi.setData(data.rsi);
      [{ p: 70, c: "rgba(230,103,103,0.6)" }, { p: 50, c: "rgba(138,151,168,0.35)" }, { p: 30, c: "rgba(47,191,127,0.6)" }].forEach(({ p, c }) =>
        rsi.createPriceLine({ price: p, color: c, lineWidth: 1, lineStyle: LineStyle.Dashed, axisLabelVisible: true, title: "" }),
      );
      series.rsi = rsi;
    }

    // ── MACD pane (2 or 1 if rsi hidden)
    if (show.macd) {
      const macdPane = show.rsi ? 2 : 1;
      const hist = chart.addSeries(HistogramSeries, {
        priceLineVisible: false, lastValueVisible: false,
      }, macdPane);
      hist.setData(data.histogram);
      series.histogram = hist;
      const macdLine = chart.addSeries(LineSeries, {
        color: "#dfe7f1", lineWidth: 1, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false,
      }, macdPane);
      macdLine.setData(data.macd);
      series.macd = macdLine;
      const signalLine = chart.addSeries(LineSeries, {
        color: COLORS.signal, lineWidth: 1, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false,
      }, macdPane);
      signalLine.setData(data.macdSignal);
      series.macdSignal = signalLine;
    }

    seriesRef.current = series;

    // pane heights
    const panes = chart.panes();
    if (panes[0]) panes[0].setHeight(priceH);
    let paneCursor = 1;
    if (show.rsi && panes[paneCursor]) panes[paneCursor++].setHeight(rsiH);
    if (show.macd && panes[paneCursor]) panes[paneCursor].setHeight(macdH);

    chart.timeScale().fitContent();
    setReady(true);

    // crosshair legend
    const legend = legendRef.current;
    const fmt = (v: number | undefined) => (v == null ? "—" : v.toFixed(2));
    const updateLegend = (index: number) => {
      if (!legend) return;
      const row = data.rows[index];
      if (!row) return;
      const dChange = index > 0 ? ((row.close - data.closes[index - 1]) / data.closes[index - 1]) * 100 : 0;
      const cls = dChange >= 0 ? "up" : "down";
      legend.innerHTML =
        `<b>${row.date}</b>` +
        (data.hasOhlc
          ? `<span>O <em>${fmt(Number(row.open))}</em> H <em>${fmt(Number(row.high))}</em> L <em>${fmt(Number(row.low))}</em> C <em>${fmt(row.close)}</em></span>`
          : `<span>C <em>${fmt(row.close)}</em></span>`) +
        `<span class="${cls}">${dChange >= 0 ? "+" : ""}${dChange.toFixed(2)}%</span>` +
        `<span>Vol <em>${row.volume ? row.volume.toLocaleString() : "—"}</em></span>`;
    };
    updateLegend(data.rows.length - 1);
    chart.subscribeCrosshairMove((param) => {
      if (param.time == null) {
        updateLegend(data.rows.length - 1);
        return;
      }
      const index = data.time.findIndex((t) => t === param.time);
      if (index >= 0) updateLegend(index);
    });

    const observer = new ResizeObserver(() => {
      if (containerRef.current) chart.applyOptions({ width: containerRef.current.clientWidth });
    });
    observer.observe(container);

    return () => {
      observer.disconnect();
      chart.remove();
      chartRef.current = null;
      seriesRef.current = {};
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data, show.rsi, show.macd]);

  // live overlay visibility (no rebuild) for price-pane indicators
  useEffect(() => {
    const s = seriesRef.current;
    if (!chartRef.current || !s.candle) return;
    const candlesOn = show.candles && data.hasOhlc;
    s.candle?.applyOptions({ visible: candlesOn, lastValueVisible: candlesOn });
    s.area?.applyOptions({ visible: !candlesOn, lastValueVisible: !candlesOn });
    s.sma20?.applyOptions({ visible: show.sma20 });
    s.sma50?.applyOptions({ visible: show.sma50 });
    s.sma100?.applyOptions({ visible: show.sma100 });
    s.sma200?.applyOptions({ visible: show.sma200 });
    s.bbUpper?.applyOptions({ visible: show.bb });
    s.bbLower?.applyOptions({ visible: show.bb });
    s.volume?.applyOptions({ visible: show.volume });
  }, [show.candles, show.sma20, show.sma50, show.sma100, show.sma200, show.bb, show.volume, data.hasOhlc]);

  const applyPreset = (bars: number | null) => {
    const chart = chartRef.current;
    if (!chart) return;
    if (bars == null) {
      chart.timeScale().fitContent();
      return;
    }
    const n = data.rows.length;
    chart.timeScale().setVisibleLogicalRange({ from: Math.max(0, n - bars), to: n - 1 + 4 });
  };

  if (history.length < 2) {
    return <div className="notice">Chart data will appear after the continuous analyzer refreshes this security.</div>;
  }

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
          {PRESETS.map((preset) => (
            <button key={preset.label} className="rangeBtn" onClick={() => applyPreset(preset.bars)}>
              {preset.label}
            </button>
          ))}
        </div>
      </div>
      <div className="proChartWrap">
        <div ref={legendRef} className="proLegend" />
        <div ref={containerRef} className="proChart" style={{ opacity: ready ? 1 : 0 }} />
      </div>
      <div className="chartHint">
        Scroll to zoom · drag to pan · drag the pane dividers to resize · hover for the crosshair readout
      </div>
    </div>
  );
}
