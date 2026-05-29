export interface Quote {
  symbol: string
  name: string
  latest_price: number
  pct_change: number
  turnover_rate: number
  amount: number
  volume_ratio: number
  pe_ttm: number | null
  pb: number | null
  market_cap: number | null
  sector: string | null
}

export interface Factors {
  strategy_id: string
  strategy_name: string
  momentum_20d: number
  trend_strength: number
  liquidity_score: number
  valuation_score: number
  risk_score: number
  total_score: number
  eligible: boolean
  entry_signal: string
  exit_signal: string
  failed_filters: string[]
  risk_flags: string[]
  explanations: string[]
  profitability_index: number | null
}

export interface ProviderMeta {
  operation: string
  resolved_provider: string
  source_provider: string
  from_cache: boolean
  used_stale_cache: boolean
  cache_age_seconds: number | null
  cache_backend: string | null
  attempted_providers: string[]
  note: string | null
}

export interface DiagnosisResult {
  quote: Quote
  factors: Factors
  quote_meta: ProviderMeta | null
  bars_meta: ProviderMeta | null
}

export interface Strategy {
  id: string
  name: string
  description: string | null
}

export interface RankingRow {
  rank: number
  symbol: string
  name: string
  sector: string
  score: number
  eligible: string
  pct_change: number
  entry_signal: string
  risk_flags: string
}

export interface Summary {
  total: number
  eligible_count: number
  avg_score: number
  top_score: number
}

export interface RankingsTableResponse {
  summary: Summary
  rows: RankingRow[]
  universe_meta: ProviderMeta | null
}

export interface WatchlistRow {
  symbol: string
  name: string
  score: number
  eligible: string
  latest_price: string | number
  pct_change: string | number
  entry_signal: string
  failed_filters: string
}

export interface WatchlistResponse {
  rows: WatchlistRow[]
}

export interface WatchlistListResponse {
  symbols: string[]
}

export interface WatchlistAddResponse {
  symbol: string
  row: WatchlistRow
}

export interface WatchlistRemoveResponse {
  symbol: string
  removed: boolean
}

export interface BarDataPoint {
  date: string
  open: number
  high: number
  low: number
  close: number
  volume: number
}

export interface BarsResponse {
  symbol: string
  bars: BarDataPoint[]
  bars_meta: ProviderMeta | null
}

export interface StatusResponse {
  status: string
  configured_provider: string
  active_provider: string
  active_provider_chain: string | null
  persistent_cache_enabled: boolean
  cache: any
  provider_routes: Record<string, string> | null
  provider_diagnostics: any[] | null
  strategies: Strategy[]
}
