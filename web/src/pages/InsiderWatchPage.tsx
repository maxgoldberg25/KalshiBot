import { useQuery, useQueryClient } from "@tanstack/react-query"
import { useState, type ChangeEvent } from "react"
import {
  ArrowDownRight,
  ArrowUpRight,
  ExternalLink,
  Loader2,
  RefreshCw,
  ShieldAlert,
} from "lucide-react"
import { fetchTradesWatch } from "@/api/fetch"
import type {
  KalshiMarketMeta,
  TapeSummary,
  TapeTradeRow,
  TopMarketRow,
} from "@/api/types"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { InsiderCharts } from "@/components/insider/InsiderCharts"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { cn } from "@/lib/utils"
import { NavLink } from "react-router-dom"

const MIN_NOTIONAL_OPTIONS = [100, 250, 500, 1000, 2500, 5000] as const
const FETCH_LIMIT_OPTIONS = [200, 500, 1000] as const

const KALSHI_SEARCH = (q: string) =>
  `https://kalshi.com/markets?search=${encodeURIComponent(q)}`

const safeKalshiHref = (row: TapeTradeRow) => {
  if (row.kalshi_url) return row.kalshi_url
  if (row.ticker) return KALSHI_SEARCH(row.ticker)
  return "https://kalshi.com/markets"
}

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

const fmtProb = (dollars: number | null | undefined) => {
  if (dollars === null || dollars === undefined || Number.isNaN(dollars)) return "—"
  return `${(dollars * 100).toFixed(0)}¢`
}

const fmtPct = (p: number | null | undefined) => {
  if (p === null || p === undefined || Number.isNaN(p)) return "—"
  return `${p.toFixed(p >= 10 ? 0 : 1)}%`
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

const fmtRelClose = (iso: string | null | undefined) => {
  if (!iso) return "—"
  const t = new Date(iso).getTime()
  if (Number.isNaN(t)) return "—"
  const diffMs = t - Date.now()
  const abs = Math.abs(diffMs)
  const mins = Math.round(abs / 60_000)
  const hrs = Math.round(abs / 3_600_000)
  const days = Math.round(abs / 86_400_000)
  const fmt =
    mins < 60 ? `${mins}m` : hrs < 48 ? `${hrs}h` : `${days}d`
  return diffMs >= 0 ? `in ${fmt}` : `${fmt} ago`
}

const TIER_CLASS: Record<string, string> = {
  major: "bg-rose-500/15 text-rose-300 ring-rose-500/35",
  large: "bg-amber-500/15 text-amber-300 ring-amber-500/35",
  notable: "bg-sky-500/15 text-sky-300 ring-sky-500/35",
}

const TierBadge = ({ tier }: { tier: string | undefined }) => {
  const t = tier ?? ""
  const tone = TIER_CLASS[t] ?? "bg-muted text-muted-foreground ring-border"
  return (
    <span
      className={cn(
        "inline-flex items-center rounded px-1.5 py-0.5 text-[0.6rem] font-semibold uppercase tracking-wide ring-1",
        tone,
      )}
    >
      {t || "—"}
    </span>
  )
}

const SideBadge = ({ side }: { side: string | undefined }) => {
  const isYes = side === "yes"
  const Icon = isYes ? ArrowUpRight : ArrowDownRight
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[0.65rem] font-semibold uppercase tracking-wide ring-1",
        isYes
          ? "bg-emerald-500/15 text-emerald-300 ring-emerald-500/30"
          : "bg-rose-500/15 text-rose-300 ring-rose-500/30",
      )}
    >
      <Icon className="size-3" aria-hidden />
      {side ?? "—"}
    </span>
  )
}

type StatCardProps = { label: string; value: string; sub?: string }

const StatCard = ({ label, value, sub }: StatCardProps) => (
  <Card className="border-border/60">
    <CardContent className="p-3">
      <div className="text-[0.65rem] font-medium uppercase tracking-wide text-muted-foreground">
        {label}
      </div>
      <div className="mt-1 text-xl font-semibold tabular-nums">{value}</div>
      {sub ? <div className="mt-0.5 text-[0.65rem] text-muted-foreground">{sub}</div> : null}
    </CardContent>
  </Card>
)

const takerDescription = (row: TapeTradeRow) => {
  const market = row.market
  const side = row.taker_side ?? "yes"
  const leg =
    side === "yes"
      ? market?.yes_sub_title || "YES"
      : market?.no_sub_title || "NO"
  const qty = row.count != null ? fmtNumber(row.count) : "?"
  const price = row.taker_price != null ? fmtProb(row.taker_price) : "—"
  const notional = fmtUsd(row.notional_usd ?? undefined)
  return `Taker bought ${qty} ${leg} at ${price} (${notional})`
}

const impliedProb = (row: TapeTradeRow) => {
  const p =
    row.taker_side === "yes" ? row.taker_price : row.taker_price != null ? 1 - row.taker_price : null
  return p != null ? `${Math.round(p * 100)}%` : "—"
}

type TradeRowProps = { row: TapeTradeRow }

const TradeRow = ({ row }: TradeRowProps) => {
  const href = safeKalshiHref(row)
  const m: KalshiMarketMeta = row.market ?? {}
  const title = m.title || row.ticker || "Unknown market"
  const subtitle = m.subtitle || m.event_ticker || ""
  const change = m.price_change_24h
  const changeTone =
    change == null
      ? "text-muted-foreground"
      : change >= 0
      ? "text-emerald-400"
      : "text-rose-400"

  return (
    <TableRow className="align-top">
      <TableCell className="w-[72px] whitespace-nowrap py-3">
        <div className="flex flex-col gap-1">
          <TierBadge tier={row.tier} />
          <span className="text-[0.6rem] text-muted-foreground" title={row.created_time ?? ""}>
            {fmtAbsTime(row.created_time)}
          </span>
        </div>
      </TableCell>

      <TableCell className="py-3">
        <a
          href={href}
          target="_blank"
          rel="noopener noreferrer"
          className="group flex flex-col gap-0.5"
          aria-label={`Open ${row.ticker ?? "market"} on Kalshi`}
        >
          <span className="line-clamp-2 text-sm font-medium text-foreground group-hover:underline">
            {title}
          </span>
          {subtitle ? (
            <span className="line-clamp-1 text-xs text-muted-foreground">{subtitle}</span>
          ) : null}
          <span className="font-mono text-[0.65rem] text-muted-foreground/80">
            {row.ticker}
            {m.event_ticker && m.event_ticker !== row.ticker ? ` · ${m.event_ticker}` : ""}
          </span>
          <span className="text-[0.65rem] text-muted-foreground">{takerDescription(row)}</span>
        </a>
      </TableCell>

      <TableCell className="py-3">
        <div className="flex flex-col items-start gap-1">
          <SideBadge side={row.taker_side} />
          <span className="text-[0.65rem] text-muted-foreground">
            implied {impliedProb(row)}
          </span>
        </div>
      </TableCell>

      <TableCell className="py-3 text-right">
        <div className="text-sm font-medium tabular-nums">{fmtProb(row.taker_price)}</div>
        <div className="text-[0.65rem] text-muted-foreground tabular-nums">
          YES {fmtProb(row.yes_price)} · NO {fmtProb(row.no_price)}
        </div>
        {m.last_price != null ? (
          <div className={cn("text-[0.65rem] tabular-nums", changeTone)}>
            last {fmtProb(m.last_price)}
            {change != null ? ` (${change >= 0 ? "+" : ""}${Math.round(change * 100)}¢ 24h)` : ""}
          </div>
        ) : null}
      </TableCell>

      <TableCell className="py-3 text-right">
        <div className="text-sm font-semibold tabular-nums">{fmtNumber(row.count)}</div>
        <div className="text-[0.65rem] text-muted-foreground tabular-nums">contracts</div>
        {row.share_of_oi_pct != null ? (
          <div className="text-[0.65rem] text-muted-foreground tabular-nums">
            {fmtPct(row.share_of_oi_pct)} of OI
          </div>
        ) : null}
      </TableCell>

      <TableCell className="py-3 text-right">
        <div className="text-sm font-semibold tabular-nums">
          {fmtUsd(row.notional_usd ?? undefined, 0)}
        </div>
        <div className="text-[0.65rem] text-muted-foreground tabular-nums">taker notional</div>
      </TableCell>

      <TableCell className="py-3 text-right">
        <div className="text-xs tabular-nums">24h {fmtNumber(m.volume_24h)}</div>
        <div className="text-[0.65rem] text-muted-foreground tabular-nums">
          total {fmtNumber(m.volume_total)}
        </div>
        <div className="text-[0.65rem] text-muted-foreground tabular-nums">
          OI {fmtNumber(m.open_interest)}
        </div>
      </TableCell>

      <TableCell className="py-3 text-right">
        <div className="text-xs tabular-nums" title={m.close_time ?? ""}>
          {fmtRelClose(m.close_time)}
        </div>
        <div className="text-[0.65rem] text-muted-foreground">{m.status ?? "—"}</div>
      </TableCell>

      <TableCell className="w-[52px] p-1 align-middle">
        <Button variant="ghost" size="icon" className="size-8" asChild>
          <a
            href={href}
            target="_blank"
            rel="noopener noreferrer"
            aria-label={`Open ${row.ticker ?? "market"} on kalshi.com`}
          >
            <ExternalLink className="size-3.5" aria-hidden />
          </a>
        </Button>
      </TableCell>
    </TableRow>
  )
}

const summaryStats = (s: TapeSummary | undefined) => {
  const tc = s?.tier_counts ?? {}
  return [
    {
      label: "Trades shown",
      value: fmtNumber(s?.trades_shown),
      sub: s?.scored_count != null ? `${s.scored_count} above filter` : undefined,
    },
    {
      label: "Total notional",
      value: fmtUsd(s?.total_notional_usd ?? undefined, 0),
      sub: `${fmtNumber(s?.total_contracts)} contracts`,
    },
    {
      label: "Unique markets",
      value: fmtNumber(s?.unique_markets),
      sub: `${tc.major ?? 0} major · ${tc.large ?? 0} large · ${tc.notable ?? 0} notable`,
    },
  ]
}

export function InsiderWatchPage() {
  const qc = useQueryClient()
  const [minNotional, setMinNotional] = useState<number>(250)
  const [fetchLimit, setFetchLimit] = useState<number>(500)

  const q = useQuery({
    queryKey: ["trades-watch", minNotional, fetchLimit],
    queryFn: () => fetchTradesWatch(minNotional, fetchLimit),
    refetchInterval: 30_000,
  })

  const handleRefresh = () => {
    void qc.invalidateQueries({ queryKey: ["trades-watch"] })
  }

  const handleMinNotionalChange = (e: ChangeEvent<HTMLSelectElement>) => {
    setMinNotional(Number(e.target.value))
  }

  const handleFetchLimitChange = (e: ChangeEvent<HTMLSelectElement>) => {
    setFetchLimit(Number(e.target.value))
  }

  const d = q.data
  const rows: TapeTradeRow[] = d?.trades ?? []
  const top: TopMarketRow[] = d?.top_markets ?? []
  const loading = q.isPending
  const stats = summaryStats(d?.summary)

  return (
    <div className="mx-auto max-w-7xl px-4 py-8">
      <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <div className="mb-1 flex items-center gap-2">
            <ShieldAlert className="size-5 text-primary" aria-hidden />
            <h1 className="text-xl font-bold tracking-tight">Insider watch</h1>
          </div>
          <p className="max-w-2xl text-sm text-muted-foreground">
            Large prints on Kalshi&apos;s public trade tape, enriched with live market metadata.
            Counterparties are never disclosed — this surfaces unusual size for your own review.
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
            <span className="whitespace-nowrap">Sample size</span>
            <select
              value={fetchLimit}
              onChange={handleFetchLimitChange}
              className="h-9 rounded-md border border-border bg-background px-2 text-xs text-foreground"
              aria-label="Number of recent trades to pull from the API"
            >
              {FETCH_LIMIT_OPTIONS.map((n) => (
                <option key={n} value={n}>
                  {n} trades
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
        <InsiderCharts rows={rows} topMarkets={top} loading={loading} />
      </div>

      <Card className="border-border/60">
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-sm font-medium">Trade tape (ranked by notional)</CardTitle>
          <span className="text-[0.65rem] text-muted-foreground">
            {d?.fetched_at ? `Updated ${fmtAbsTime(d.fetched_at)}` : loading ? "Loading…" : "—"}
            {d?.raw_count != null ? ` · ${d.raw_count} raw rows sampled` : ""}
          </span>
        </CardHeader>
        <CardContent className="p-0">
          <ScrollArea className="h-[min(640px,calc(100vh-260px))]">
            <Table>
              <caption className="sr-only">
                Kalshi public trades ranked by approximate taker notional
              </caption>
              <TableHeader className="sticky top-0 z-10 bg-card">
                <TableRow className="hover:bg-transparent">
                  <TableHead className="w-[96px] text-xs">Tier / Time</TableHead>
                  <TableHead className="text-xs">Market</TableHead>
                  <TableHead className="w-[90px] text-xs">Taker</TableHead>
                  <TableHead className="w-[120px] text-right text-xs">Price</TableHead>
                  <TableHead className="w-[96px] text-right text-xs">Size</TableHead>
                  <TableHead className="w-[96px] text-right text-xs">Notional</TableHead>
                  <TableHead className="w-[110px] text-right text-xs">Volume / OI</TableHead>
                  <TableHead className="w-[100px] text-right text-xs">Closes</TableHead>
                  <TableHead className="w-[52px] text-xs" />
                </TableRow>
              </TableHeader>
              <TableBody>
                {loading &&
                  Array.from({ length: 8 }).map((_, i) => (
                    <TableRow key={`sk-${i}`}>
                      <TableCell colSpan={9}>
                        <Skeleton className="h-10 w-full" />
                      </TableCell>
                    </TableRow>
                  ))}
                {!loading && rows.length === 0 && (
                  <TableRow>
                    <TableCell
                      colSpan={9}
                      className="py-10 text-center text-sm text-muted-foreground"
                    >
                      No trades above this notional in the sample. Lower the minimum or increase
                      the sample size.
                    </TableCell>
                  </TableRow>
                )}
                {!loading &&
                  rows.map((row) => (
                    <TradeRow
                      key={row.trade_id ?? `${row.ticker}-${row.created_time}`}
                      row={row}
                    />
                  ))}
              </TableBody>
            </Table>
          </ScrollArea>
        </CardContent>
      </Card>

      <p className="mt-6 text-center text-xs text-muted-foreground">
        <NavLink to="/scanner" className="text-primary underline-offset-4 hover:underline">
          Back to scanner
        </NavLink>
      </p>
    </div>
  )
}
