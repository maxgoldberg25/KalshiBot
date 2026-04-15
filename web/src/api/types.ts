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
