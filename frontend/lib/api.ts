export type CompanyBrief = {
  ticker: string;
  name: string;
  exchange: string | null;
  asset_type: string;
};

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
};

export type Catalyst = { category?: string; title: string; detail: string; status: string };

export type ListItem = {
  company: CompanyBrief;
  as_of: string;
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
