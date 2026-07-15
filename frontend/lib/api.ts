export type CompanyBrief = {
  ticker: string;
  name: string;
  exchange: string | null;
  asset_type: string;
  sector?: string | null;
};

export type SectorCount = { sector: string; count: number };
export type SectorsResponse = { sectors: SectorCount[]; total: number };

export type TechnicalIndicators = {
  sma20?: number | null;
  sma50?: number | null;
  sma200?: number | null;
  rsi14?: number | null;
  high_52w?: number;
  low_52w?: number;
  range_position_pct?: number;
  bb_upper?: number | null;
  bb_lower?: number | null;
  bb_percent_b?: number | null;
  atr14?: number | null;
  atr_pct?: number | null;
  support?: number;
  resistance?: number;
  volume_avg20?: number | null;
  volume_avg50?: number | null;
  volume_trend?: string | null;
  trend_cross?: string | null;
  trend_cross_age_days?: number | null;
  change_1d_pct?: number | null;
  change_5d_pct?: number | null;
  change_20d_pct?: number | null;
  confirmations?: number;
  checks?: Array<{ name: string; passed: boolean }>;
  signal?: string;
  macd?: number;
  macd_signal?: number;
  macd_histogram?: number;
  impulse_macd?: string;
  spark?: number[];
};

export type Catalyst = { category?: string; title: string; detail: string; status: string };

export type FactorScores = {
  value?: number;
  quality?: number;
  momentum?: number;
  growth?: number;
  income?: number;
  composite?: number;
};

export type FactorsResponse = {
  ticker: string;
  sector: string;
  peer_count: number;
  scores: FactorScores;
  sector_percentiles: Partial<Record<keyof FactorScores, number>>;
};

export type ListItem = {
  company: CompanyBrief;
  as_of: string;
  price_as_of: string | null;
  factor_scores?: FactorScores;
  price_date: string;
  current_price: string;
  volume: number | null;
  fair_value: string;
  upside_pct: number;
  opportunity_score: number;
  confidence_grade: string;
  risk_level: string;
  qualification: string;
  technical_indicators: TechnicalIndicators;
  catalysts: Catalyst[];
};

export type PricePoint = {
  date: string;
  open?: number | null;
  high?: number | null;
  low?: number | null;
  close: number;
  volume: number | null;
};

export type Fundamentals = {
  revenue_history?: Array<{ fy_end: string; value: number }>;
  net_income_history?: Array<{ fy_end: string; value: number }>;
  operating_income?: number | null;
  gross_profit?: number | null;
  equity?: number | null;
  book_value_per_share?: number | null;
  market_cap?: number | null;
  revenue_cagr_pct?: number | null;
  dividend?: {
    pays?: boolean;
    source?: string | null;
    annual_amount_ttm?: number | null;
    forward_annual?: number | null;
    yield_pct?: number | null;
    forward_yield_pct?: number | null;
    frequency?: string | null;
    payments_per_year?: number | null;
    last_ex_date?: string | null;
    last_amount?: number | null;
    growth_1y_pct?: number | null;
    growth_streak_years?: number;
    payout_ratio_pct?: number | null;
    buyback_yield_pct?: number | null;
    shareholder_yield_pct?: number | null;
    payments?: Array<{ date: string; amount: number }>;
    annual?: Array<{ year: string; value: number }>;
  };
  margins?: {
    gross_pct?: number | null;
    operating_pct?: number | null;
    net_pct?: number | null;
    fcf_pct?: number | null;
  };
  ratios?: {
    price_to_sales?: number | null;
    price_to_earnings?: number | null;
    price_to_fcf?: number | null;
    price_to_book?: number | null;
  };
};

export type Detail = ListItem & {
  price_as_of: string | null;
  price_history: PricePoint[];
  revenue: string | null;
  revenue_growth_pct: number | null;
  net_income: string | null;
  free_cash_flow: string | null;
  cash: string | null;
  debt: string | null;
  bear_value: string;
  bull_value: string;
  valuation_methods: Array<{ model: string; value: number; multiple: number }>;
  fundamentals: Fundamentals;
  risks: Array<{ title: string; severity: string }>;
  thesis_breakers: string[];
  sources: Array<{ name: string; url: string }>;
};

export type Summary = {
  company_count: number;
  eligible_count: number;
  analysis_count: number;
  attempted_count: number;
  failed_count: number;
  remaining_count: number;
  coverage_pct: number;
  qualified_count: number;
  last_analysis_at: string | null;
  market_open: boolean;
  market_session: string;
  prices_updated_last_min: number;
  analyses_last_5min: number;
  newest_price_at: string | null;
};

export type HistoryPoint = {
  as_of: string;
  price_date: string;
  current_price: string;
  fair_value: string;
  upside_pct: number;
  opportunity_score: number;
  confidence_grade: string;
};

export type Mover = {
  ticker: string;
  name: string;
  asset_type: string;
  current_price: string;
  change_1d_pct: number | null;
  upside_pct: number;
  opportunity_score: number;
  signal: string | null;
  volume: number | null;
};

export type Overview = {
  summary: Summary;
  signal_breadth: Record<string, number>;
  impulse_breadth: Record<string, number>;
  score_distribution: Array<{ label: string; count: number }>;
  upside_distribution: Array<{ label: string; count: number }>;
  exchange_counts: Record<string, number>;
  asset_type_counts: Record<string, number>;
  sector_counts: Record<string, number>;
  top_gainers: Mover[];
  top_losers: Mover[];
  most_active: Mover[];
  highest_scores: Mover[];
};

export type WatchlistRow = {
  ticker: string;
  name: string;
  exchange: string | null;
  asset_type: string;
  note: string | null;
  created_at: string;
  latest: ListItem | null;
};

export const money = (value: string | number | null | undefined) =>
  value === null || value === undefined
    ? "—"
    : new Intl.NumberFormat("en-US", {
        style: "currency",
        currency: "USD",
        maximumFractionDigits: 2,
      }).format(Number(value));

export const compact = (value: string | number | null | undefined) =>
  value === null || value === undefined
    ? "—"
    : new Intl.NumberFormat("en-US", { notation: "compact", maximumFractionDigits: 1 }).format(
        Number(value),
      );

export const pct = (value: number | null | undefined, digits = 1) =>
  value === null || value === undefined ? "—" : `${value >= 0 ? "+" : ""}${value.toFixed(digits)}%`;

export const signalClass = (signal?: string | null) =>
  `chip chip--${(signal ?? "neutral").toLowerCase()}`;

// Short "updated Xs ago" style label from an ISO timestamp.
export const timeAgo = (iso: string | null | undefined, nowMs = Date.now()): string => {
  if (!iso) return "—";
  const seconds = Math.max(0, Math.round((nowMs - Date.parse(iso)) / 1000));
  if (seconds < 5) return "now";
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours}h`;
  return `${Math.round(hours / 24)}d`;
};

// A quote refreshed within the last few minutes is considered "live".
export const isFresh = (iso: string | null | undefined, nowMs = Date.now(), windowSec = 180) =>
  !!iso && nowMs - Date.parse(iso) <= windowSec * 1000;

export type Rating = "Strong Buy" | "Buy" | "Accumulate" | "Hold" | "Reduce" | "Sell";

const clamp = (value: number, low: number, high: number) => Math.max(low, Math.min(high, value));

/**
 * Deterministic, transparent action rating blending modeled upside (when a
 * fundamental fair value exists), the technical signal, trend cross, RSI, risk,
 * and opportunity score. This is a rules-based screen output, not personalized
 * investment advice.
 */
export function ratingFor(opts: {
  upsidePct?: number | null;
  technicalOnly: boolean;
  signal?: string | null;
  rsi?: number | null;
  risk?: string | null;
  score?: number | null;
  trendCross?: string | null;
}): { label: Rating; slug: string } {
  let points = 0;
  const signal = (opts.signal ?? "").toLowerCase();
  if (signal === "bullish") points += 2;
  else if (signal === "bearish") points -= 2;

  if (!opts.technicalOnly && opts.upsidePct != null) {
    points += clamp(opts.upsidePct / 20, -3, 4);
  }
  if (opts.trendCross === "Golden cross") points += 1;
  else if (opts.trendCross === "Death cross") points -= 1;

  if (opts.rsi != null) {
    if (opts.rsi >= 78) points -= 1; // overbought — accumulate on pullbacks, not chase
    else if (opts.rsi <= 30) points += 1; // oversold bounce potential
    else if (opts.rsi >= 45 && opts.rsi <= 68) points += 0.5;
  }
  if (opts.risk === "Low") points += 0.5;
  else if (opts.risk === "High") points -= 0.5;
  if (opts.score != null) points += clamp((opts.score - 50) / 25, -2, 2);

  const label: Rating =
    points >= 4 ? "Strong Buy"
    : points >= 2 ? "Buy"
    : points >= 0.75 ? "Accumulate"
    : points > -0.75 ? "Hold"
    : points > -2.25 ? "Reduce"
    : "Sell";
  return { label, slug: label.toLowerCase().replace(/\s+/g, "") };
}

export async function getJson<T>(url: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(url, { signal });
  if (!response.ok) throw new Error(`Request failed: ${response.status}`);
  return response.json() as Promise<T>;
}

export async function fetchWatchlistTickers(): Promise<Set<string>> {
  const tickers = await getJson<string[]>("/api/research/watchlist/tickers");
  return new Set(tickers);
}

export async function toggleWatch(ticker: string, watched: boolean): Promise<void> {
  await fetch(`/api/research/watchlist/${ticker}`, { method: watched ? "DELETE" : "POST" });
}

export type IdeaItem = {
  ticker: string;
  name: string;
  asset_type: string;
  current_price: string;
  change_1d_pct: number | null;
  change_5d_pct: number | null;
  upside_pct: number | null;
  opportunity_score: number;
  signal: string | null;
  rsi14: number | null;
  confidence_grade: string;
  risk_level: string;
  idea_score: number;
  reasons: string[];
};

export type IdeasResponse = { swing: IdeaItem[]; long_term: IdeaItem[] };

export type BacktestBucket = {
  n: number;
  avg_return_pct: number | null;
  median_return_pct: number | null;
  hit_rate_pct: number | null;
};
export type BacktestRating = { rating: string; by_horizon: Record<string, BacktestBucket> };
export type BacktestResponse = {
  sample_size: number;
  since: string | null;
  universe: number;
  horizons: Array<{ days: number; label: string }>;
  benchmark: Record<string, BacktestBucket>;
  ratings: BacktestRating[];
};

export type RadarEvent = {
  ticker: string;
  name: string;
  sector: string;
  asset_type: string;
  price: number;
  change_1d_pct: number | null;
  as_of: string | null;
  headline: string;
  significance: number;
};
export type RadarCategory = {
  key: string;
  label: string;
  description: string;
  count: number;
  items: RadarEvent[];
};
export type RadarResponse = {
  generated_at: string | null;
  universe: number;
  total_events: number;
  categories: RadarCategory[];
};

export type ScreenResponse = {
  query: string;
  interpretation: Array<{ label: string }>;
  filters: Record<string, unknown>;
  count: number;
  results: ListItem[];
};

export type SectorFactorRow = {
  sector: string;
  count: number;
  value: number | null;
  quality: number | null;
  momentum: number | null;
  growth: number | null;
  income: number | null;
  composite: number | null;
};
export type SectorFactorMatrix = { factors: string[]; sectors: SectorFactorRow[] };
