import { useQuery, useQueryClient } from "@tanstack/react-query"
import { useMemo, useState, type ChangeEvent } from "react"
import { Loader2, RefreshCw, ShieldAlert } from "lucide-react"
import { fetchTradesWatch } from "@/api/fetch"
import type {
  MarketAggRow,
  TapeSummary,
  TapeTradeRow,
  TopMarketRow,
} from "@/api/types"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { InsiderCharts } from "@/components/insider/InsiderCharts"
import { InsiderNewsTicker } from "@/components/insider/InsiderNewsTicker"
import { TradeCard } from "@/components/insider/TradeCard"
import { Skeleton } from "@/components/ui/skeleton"
import { cn } from "@/lib/utils"

// Retail noise lives below $1k. Informed flow starts around $2.5k on illiquid
// markets and $10k+ on liquid ones; whales show up at $50k+. Defaults are
// calibrated to surface actionable signal, not volume.
const MIN_NOTIONAL_OPTIONS = [500, 1000, 2500, 5000, 10000, 25000, 50000] as const
const LOOKBACK_DAY_OPTIONS = [1, 7, 14, 30] as const
const DEFAULT_MIN_NOTIONAL = 2500
const DEFAULT_LOOKBACK_DAYS = 30

const fmtUsd = (n: number | null | undefined, fractionDigits = 2) => {
  if (n === null || n === undefined || Number.isNaN(n)) return "—"
  return new Intl.NumberFormat(undefined, {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: fractionDigits,
    maximumFractionDigits: fractionDigits,
  }).format(n)
}

const fmtNumber = (n: number | null | undefined) => {
  if (n === null || n === undefined || Number.isNaN(n)) return "—"
  return new Intl.NumberFormat().format(Math.round(n))
}

const fmtAbsTime = (iso: string | null | undefined) => {
  if (!iso) return "—"
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return "—"
  return d.toLocaleString([], {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  })
}

type StatCardProps = { label: string; value: string; sub?: string }

const StatCard = ({ label, value, sub }: StatCardProps) => (
  <Card className="border-border/60">
    <CardContent className="p-3">
      <div className="text-[0.65rem] font-medium uppercase tracking-wide text-muted-foreground">
        {label}
      </div>
      <div className="mt-1 text-xl font-semibold tabular-nums">{value}</div>
      {sub ? (
        <div className="mt-0.5 text-[0.65rem] text-muted-foreground">{sub}</div>
      ) : null}
    </CardContent>
  </Card>
)

const summaryStats = (s: TapeSummary | undefined) => {
  const tc = s?.tier_counts ?? {}
  return [
    {
      label: "Unique markets",
      value: fmtNumber(s?.unique_markets),
      sub: `${tc.whale ?? 0} whale · ${tc.major ?? 0} major · ${tc.large ?? 0} large`,
    },
    {
      label: "Total notional",
      value: fmtUsd(s?.total_notional_usd ?? undefined, 0),
      sub: `${fmtNumber(s?.total_contracts)} contracts · ${fmtNumber(
        s?.trades_shown,
      )} prints`,
    },
    {
      label: "Filtered out",
      value: fmtNumber(
        (s?.excluded_sports ?? 0) +
          (s?.excluded_unknown_market ?? 0) +
          (s?.excluded_untradeable_market ?? 0) +
          (s?.excluded_parlay_market ?? 0),
      ),
      sub: `${fmtNumber(s?.excluded_sports)} sports · ${fmtNumber(
        s?.excluded_parlay_market,
      )} parlays · ${fmtNumber(
        s?.excluded_unknown_market,
      )} unknown · ${fmtNumber(s?.excluded_untradeable_market)} not tradeable`,
    },
  ]
}

type QuickFilter = "all" | "whales" | "fresh" | "high"
type SortMode = "conviction" | "notional" | "recent"

const QUICK_FILTERS: { id: QuickFilter; label: string; title: string }[] = [
  { id: "all", label: "All", title: "Show every qualifying market" },
  {
    id: "high",
    label: "Conviction ≥ 75",
    title: "Only markets with a conviction score of 75 or higher",
  },
  {
    id: "whales",
    label: "Whales only",
    title: "Only markets where total notional cleared $50k (whale tier)",
  },
  {
    id: "fresh",
    label: "Fresh < 15m",
    title: "Only markets whose most recent print is under 15 minutes old",
  },
]

const SORT_MODES: { id: SortMode; label: string }[] = [
  { id: "conviction", label: "Conviction" },
  { id: "notional", label: "Notional" },
  { id: "recent", label: "Most recent" },
]

const applyQuickFilter = (
  rows: MarketAggRow[],
  mode: QuickFilter,
): MarketAggRow[] => {
  if (mode === "all") return rows
  if (mode === "whales") return rows.filter((r) => r.tier === "whale")
  if (mode === "high") return rows.filter((r) => (r.signal_score ?? 0) >= 75)
  if (mode === "fresh") {
    const cutoff = Date.now() - 15 * 60_000
    return rows.filter((r) => {
      if (!r.last_time) return false
      const t = new Date(r.last_time).getTime()
      return !Number.isNaN(t) && t >= cutoff
    })
  }
  return rows
}

const applySort = (rows: MarketAggRow[], mode: SortMode): MarketAggRow[] => {
  const copy = [...rows]
  if (mode === "notional") {
    copy.sort((a, b) => (b.total_notional ?? 0) - (a.total_notional ?? 0))
  } else if (mode === "recent") {
    copy.sort((a, b) => {
      const ta = a.last_time ? new Date(a.last_time).getTime() : 0
      const tb = b.last_time ? new Date(b.last_time).getTime() : 0
      return tb - ta
    })
  } else {
    copy.sort((a, b) => {
      const score = (b.signal_score ?? 0) - (a.signal_score ?? 0)
      if (score !== 0) return score
      return (b.total_notional ?? 0) - (a.total_notional ?? 0)
    })
  }
  return copy
}

export function InsiderWatchPage() {
  const qc = useQueryClient()
  const [minNotional, setMinNotional] = useState<number>(DEFAULT_MIN_NOTIONAL)
  const [lookbackDays, setLookbackDays] = useState<number>(DEFAULT_LOOKBACK_DAYS)
  const [quickFilter, setQuickFilter] = useState<QuickFilter>("all")
  const [sortMode, setSortMode] = useState<SortMode>("conviction")

  const q = useQuery({
    queryKey: ["trades-watch", minNotional, lookbackDays],
    queryFn: () => fetchTradesWatch(minNotional, lookbackDays),
    refetchInterval: 30_000,
  })

  const handleRefresh = () => {
    void qc.invalidateQueries({ queryKey: ["trades-watch"] })
  }

  const handleMinNotionalChange = (e: ChangeEvent<HTMLSelectElement>) => {
    setMinNotional(Number(e.target.value))
  }

  const handleLookbackDaysChange = (e: ChangeEvent<HTMLSelectElement>) => {
    setLookbackDays(Number(e.target.value))
  }

  const d = q.data
  const trades: TapeTradeRow[] = d?.trades ?? []
  const markets: MarketAggRow[] = useMemo(() => d?.markets ?? [], [d?.markets])
  const top: TopMarketRow[] = d?.top_markets ?? []
  const loading = q.isPending
  const stats = summaryStats(d?.summary)

  const visibleMarkets = useMemo(
    () => applySort(applyQuickFilter(markets, quickFilter), sortMode),
    [markets, quickFilter, sortMode],
  )

  const handleSortChange = (e: ChangeEvent<HTMLSelectElement>) => {
    setSortMode(e.target.value as SortMode)
  }

  return (
    <div className="mx-auto max-w-7xl px-4 py-8">
      <InsiderNewsTicker markets={markets} loading={loading} />

      <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <div className="mb-1 flex items-center gap-2">
            <ShieldAlert className="size-5 text-primary" aria-hidden />
            <h1 className="text-xl font-bold tracking-tight">Insider watch</h1>
          </div>
          <p className="max-w-2xl text-sm text-muted-foreground">
            Unusual size on Kalshi markets where information asymmetry can
            exist — politics, economics, regulatory, corporate events, crypto,
            and climate. Ranked by a 0-100 conviction score combining print
            size, directional imbalance, share of open interest, concentration
            and recency. Sports and synthetic parlays are excluded; the default
            view scans large trades from the last 30 days.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <label className="flex items-center gap-2 text-xs text-muted-foreground">
            <span className="whitespace-nowrap">Min notional</span>
            <select
              value={minNotional}
              onChange={handleMinNotionalChange}
              className="h-9 rounded-md border border-border bg-background px-2 text-xs text-foreground"
              aria-label="Minimum trade notional filter in US dollars"
            >
              {MIN_NOTIONAL_OPTIONS.map((n) => (
                <option key={n} value={n}>
                  {fmtUsd(n, 0)}
                </option>
              ))}
            </select>
          </label>
          <label className="flex items-center gap-2 text-xs text-muted-foreground">
            <span className="whitespace-nowrap">Lookback</span>
            <select
              value={lookbackDays}
              onChange={handleLookbackDaysChange}
              className="h-9 rounded-md border border-border bg-background px-2 text-xs text-foreground"
              aria-label="Trade lookback window in days"
            >
              {LOOKBACK_DAY_OPTIONS.map((n) => (
                <option key={n} value={n}>
                  Last {n === 1 ? "24 hours" : `${n} days`}
                </option>
              ))}
            </select>
          </label>
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="gap-1.5"
            onClick={handleRefresh}
            disabled={q.isFetching}
            aria-label="Refresh trade tape"
          >
            {q.isFetching ? (
              <Loader2 className="size-3.5 animate-spin" aria-hidden />
            ) : (
              <RefreshCw className="size-3.5" aria-hidden />
            )}
            Refresh
          </Button>
        </div>
      </div>

      <div className="mb-6 grid gap-3 sm:grid-cols-3">
        {stats.map((s) => (
          <StatCard key={s.label} label={s.label} value={s.value} sub={s.sub} />
        ))}
      </div>

      {d?.kalshi_configured === false && (
        <Alert variant="destructive" className="mb-6">
          <AlertTitle className="text-sm">Kalshi not configured</AlertTitle>
          <AlertDescription className="text-xs">
            Add API credentials in <code className="rounded bg-muted px-1">.env</code> to load the tape.
          </AlertDescription>
        </Alert>
      )}

      {d?.ok === false && d?.error ? (
        <Alert variant="destructive" className="mb-6">
          <AlertTitle className="text-sm">Tape request failed</AlertTitle>
          <AlertDescription className="text-xs">{d.error}</AlertDescription>
        </Alert>
      ) : null}

      <div className="mb-6">
        <InsiderCharts rows={trades} topMarkets={top} loading={loading} />
      </div>

      <section aria-label="Markets ranked by conviction score">
        <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
          <div>
            <h2 className="text-sm font-semibold text-foreground">
              Tap a price to execute on Kalshi
            </h2>
            <p className="text-xs text-muted-foreground">
              One tap opens the market — the button you pick tells you the
              exact side and ask you&apos;re targeting.
            </p>
          </div>
          <span className="text-[0.65rem] text-muted-foreground">
            {d?.fetched_at
              ? `Updated ${fmtAbsTime(d.fetched_at)}`
              : loading
              ? "Loading…"
              : "—"}
            {d?.lookback_days ? ` · last ${d.lookback_days}d` : ""}
            {d?.raw_count != null ? ` · ${d.raw_count} raw rows scanned` : ""}
            {d?.filter_version ? ` · ${d.filter_version}` : ""}
          </span>
        </div>

        <div className="mb-3 flex flex-wrap items-center justify-between gap-2 rounded-lg border border-border/60 bg-card/60 px-2 py-1.5">
          <div
            className="flex flex-wrap items-center gap-1"
            role="group"
            aria-label="Quick filter"
          >
            {QUICK_FILTERS.map((f) => {
              const isActive = quickFilter === f.id
              return (
                <button
                  key={f.id}
                  type="button"
                  onClick={() => setQuickFilter(f.id)}
                  title={f.title}
                  aria-pressed={isActive}
                  className={cn(
                    "inline-flex items-center rounded px-2.5 py-1 text-[0.7rem] font-semibold uppercase tracking-wider ring-1 transition-colors",
                    isActive
                      ? "bg-primary/15 text-primary ring-primary/40"
                      : "bg-transparent text-muted-foreground ring-border/60 hover:bg-muted hover:text-foreground",
                  )}
                >
                  {f.label}
                </button>
              )
            })}
          </div>
          <div className="flex items-center gap-2">
            <span className="text-[0.7rem] tabular-nums text-muted-foreground">
              {loading
                ? "—"
                : `${fmtNumber(visibleMarkets.length)} of ${fmtNumber(
                    markets.length,
                  )} markets`}
            </span>
            <label className="flex items-center gap-1.5 text-[0.7rem] text-muted-foreground">
              <span className="whitespace-nowrap uppercase tracking-wider">
                Sort
              </span>
              <select
                value={sortMode}
                onChange={handleSortChange}
                className="h-8 rounded-md border border-border bg-background px-2 text-[0.7rem] text-foreground"
                aria-label="Sort markets by"
              >
                {SORT_MODES.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.label}
                  </option>
                ))}
              </select>
            </label>
          </div>
        </div>

        {loading ? (
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            {Array.from({ length: 9 }).map((_, i) => (
              <Card key={`sk-${i}`} className="border-border/60">
                <CardContent className="space-y-3 p-4">
                  <Skeleton className="h-4 w-24" />
                  <Skeleton className="h-5 w-full" />
                  <Skeleton className="h-5 w-3/4" />
                  <Skeleton className="h-8 w-full" />
                  <Skeleton className="h-6 w-1/2" />
                </CardContent>
              </Card>
            ))}
          </div>
        ) : markets.length === 0 ? (
          <Card className="border-border/60">
            <CardContent className="py-10 text-center text-sm text-muted-foreground">
              No non-sports markets above this notional in the selected lookback.
              Lower the minimum or expand the window.
            </CardContent>
          </Card>
        ) : visibleMarkets.length === 0 ? (
          <Card className="border-border/60">
            <CardContent className="py-10 text-center text-sm text-muted-foreground">
              No markets match this quick filter. Try
              {" "}
              <button
                type="button"
                onClick={() => setQuickFilter("all")}
                className="text-primary underline-offset-4 hover:underline"
              >
                clearing it
              </button>
              .
            </CardContent>
          </Card>
        ) : (
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            {visibleMarkets.map((row) => (
              <TradeCard key={row.ticker} row={row} />
            ))}
          </div>
        )}
      </section>
    </div>
  )
}
