/** Loose types for KalshiBot dashboard JSON APIs */

export type PnlSummary = {
  total_realized_pnl?: number
  open_count?: number
  settled_count?: number
  winning_count?: number
  losing_count?: number
}

export type OpportunityRow = {
  game_label?: string
  edge_cents?: number
  edge_bps?: number
  kalshi_action?: string
  hedge_action?: string
  book_count?: number
  confidence?: string
  kalshi_liquidity?: number
  /** Present when enriched by dashboard API */
  kelly_shares?: number
  is_estimated?: boolean
  odds_source?: string
  kalshi_ticker?: string
  kalshi_url?: string
}

export type DashboardState = {
  last_scan_iso?: string | null
  scan_count?: number
  last_error?: string | null
  opportunities?: OpportunityRow[]
  odds_requests_remaining?: number | string | null
  is_scanning?: boolean
  sports?: string[]
  mapped_count?: number
  active_odds_provider?: string
  poll_interval_seconds?: number
  kalshi_configured?: boolean
  odds_configured?: boolean
  execution_enabled?: boolean
  positions?: unknown[]
  settled?: unknown[]
  pnl?: PnlSummary
}

export type KalshiMarketMeta = {
  ticker?: string
  event_ticker?: string
  title?: string
  subtitle?: string
  yes_sub_title?: string
  no_sub_title?: string
  status?: string
  close_time?: string
  expected_expiration_time?: string | null
  yes_bid?: number | null
  yes_ask?: number | null
  no_bid?: number | null
  no_ask?: number | null
  last_price?: number | null
  previous_price?: number | null
  price_change_24h?: number | null
  volume_total?: number | null
  volume_24h?: number | null
  open_interest?: number | null
  notional_value?: number | null
}

export type TapeTradeRow = {
  trade_id?: string
  ticker?: string
  taker_side?: "yes" | "no" | string
  taker_price?: number
  count?: number
  yes_price?: number
  no_price?: number
  notional_usd?: number
  tier?: "major" | "large" | "notable" | string
  created_time?: string
  share_of_oi_pct?: number | null
  kalshi_url?: string
  market?: KalshiMarketMeta
}

export type TapeSummary = {
  trades_shown?: number
  scored_count?: number
  total_notional_usd?: number
  total_contracts?: number
  unique_markets?: number
  tier_counts?: { major?: number; large?: number; notable?: number }
}

export type TopMarketRow = {
  ticker?: string
  title?: string
  notional?: number
  contracts?: number
  trades?: number
  kalshi_url?: string
}

export type TradesWatchResponse = {
  ok?: boolean
  error?: string
  trades?: TapeTradeRow[]
  summary?: TapeSummary
  top_markets?: TopMarketRow[]
  kalshi_configured?: boolean
  raw_count?: number
  fetched_at?: string
  min_notional?: number
  fetch_limit?: number
}

export type HealthResponse = {
  status?: string
  uptime_seconds?: number
  kalshi?: { connected?: boolean; configured?: boolean }
  odds_primary?: { connected?: boolean; configured?: boolean }
  odds_fallback?: { connected?: boolean; configured?: boolean }
  active_provider?: string
  database?: { connected?: boolean }
  scanner?: {
    running?: boolean
    scan_count?: number
    last_scan?: string | null
    last_error?: string | null
    mapped_count?: number
  }
}
