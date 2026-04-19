import { useMemo, type ReactNode } from "react"
import {
  Area,
  Bar,
  BarChart,
  Brush,
  CartesianGrid,
  Cell,
  ComposedChart,
  Legend,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"
import {
  Activity,
  ArrowDownRight,
  ArrowUpRight,
  BarChart3,
  Layers,
  PieChart,
  TrendingUp,
} from "lucide-react"
import type { TapeTradeRow, TopMarketRow } from "@/api/types"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { kalshiOpenHref } from "@/lib/kalshiLinks"
import { cn } from "@/lib/utils"

// ────────────────────────────────────────────────────────────────────────────
// Tokens
// ────────────────────────────────────────────────────────────────────────────

const COLOR = {
  major: "#10b981", // emerald-500
  large: "#38bdf8", // sky-400
  notable: "#a78bfa", // violet-400
  yes: "#10b981",
  no: "#f43f5e",
  cum: "hsl(var(--muted-foreground))",
  grid: "hsl(var(--border) / 0.5)",
  axis: "hsl(var(--muted-foreground))",
} as const

type Tier = "major" | "large" | "notable"

const TIER_LABEL: Record<Tier, string> = {
  major: "Major",
  large: "Large",
  notable: "Notable",
}

const PARETO_PALETTE = [
  COLOR.major,
  COLOR.large,
  COLOR.notable,
  "#f59e0b",
  "#fb7185",
  "#22d3ee",
  "#60a5fa",
  "#facc15",
]

// ────────────────────────────────────────────────────────────────────────────
// Formatters
// ────────────────────────────────────────────────────────────────────────────

const fmtUsd = (n: number, fractionDigits = 0) =>
  new Intl.NumberFormat(undefined, {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: fractionDigits,
    maximumFractionDigits: fractionDigits,
  }).format(n)

const fmtUsdCompact = (n: number) =>
  new Intl.NumberFormat(undefined, {
    style: "currency",
    currency: "USD",
    notation: "compact",
    maximumFractionDigits: 1,
  }).format(n)

const fmtNumber = (n: number) => new Intl.NumberFormat().format(Math.round(n))

const fmtPct = (n: number, digits = 0) =>
  `${n.toLocaleString(undefined, {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  })}%`

const fmtClock = (ts: number, withDay = false) =>
  new Date(ts).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    ...(withDay ? { month: "short", day: "numeric" } : {}),
  })

const median = (values: number[]): number => {
  if (!values.length) return 0
  const sorted = [...values].sort((a, b) => a - b)
  const mid = Math.floor(sorted.length / 2)
  return sorted.length % 2 === 0 ? (sorted[mid - 1] + sorted[mid]) / 2 : sorted[mid]
}

const percentile = (sortedAsc: number[], p: number): number => {
  if (!sortedAsc.length) return 0
  const rank = (sortedAsc.length - 1) * p
  const lo = Math.floor(rank)
  const hi = Math.ceil(rank)
  if (lo === hi) return sortedAsc[lo]
  return sortedAsc[lo] + (sortedAsc[hi] - sortedAsc[lo]) * (rank - lo)
}

// ────────────────────────────────────────────────────────────────────────────
// Bucketing
// ────────────────────────────────────────────────────────────────────────────

type FlowPoint = {
  bucket: number
  label: string
  major: number
  large: number
  notable: number
  total: number
  trades: number
  yes: number
  no: number
  net: number
  cumulative: number
  cumulativeNet: number
}

const pickBucketMs = (rows: TapeTradeRow[]): number => {
  const times = rows
    .map((r) => (r.created_time ? new Date(r.created_time).getTime() : Number.NaN))
    .filter((t) => Number.isFinite(t))
  if (times.length < 2) return 60_000
  const span = Math.max(...times) - Math.min(...times)
  if (span <= 30 * 60_000) return 60_000 // ≤ 30 min → 1 min buckets
  if (span <= 3 * 60 * 60_000) return 5 * 60_000 // ≤ 3 h → 5 min
  if (span <= 24 * 60 * 60_000) return 15 * 60_000 // ≤ 1 d → 15 min
  return 60 * 60_000 // hourly
}

const tierKey = (raw: TapeTradeRow["tier"]): Tier => {
  if (raw === "major" || raw === "large" || raw === "notable") return raw
  return "notable"
}

const buildFlow = (rows: TapeTradeRow[], bucketMs: number): FlowPoint[] => {
  if (!rows.length) return []
  const map = new Map<number, FlowPoint>()
  for (const r of rows) {
    const iso = r.created_time
    if (!iso) continue
    const t = new Date(iso).getTime()
    if (Number.isNaN(t)) continue
    const bucket = Math.floor(t / bucketMs) * bucketMs
    const usd = r.notional_usd ?? 0
    const tier = tierKey(r.tier)
    const isYes = (r.taker_side ?? "yes") !== "no"

    let pt = map.get(bucket)
    if (!pt) {
      pt = {
        bucket,
        label: fmtClock(bucket),
        major: 0,
        large: 0,
        notable: 0,
        total: 0,
        trades: 0,
        yes: 0,
        no: 0,
        net: 0,
        cumulative: 0,
        cumulativeNet: 0,
      }
      map.set(bucket, pt)
    }
    pt[tier] += usd
    pt.total += usd
    pt.trades += 1
    if (isYes) pt.yes += usd
    else pt.no += usd
  }

  const sorted = [...map.values()].sort((a, b) => a.bucket - b.bucket)
  let cumTotal = 0
  let cumNet = 0
  for (const pt of sorted) {
    cumTotal += pt.total
    cumNet += pt.yes - pt.no
    pt.net = pt.yes - pt.no
    pt.cumulative = cumTotal
    pt.cumulativeNet = cumNet
  }
  return sorted
}

// ────────────────────────────────────────────────────────────────────────────
// Pareto + histogram + KPIs
// ────────────────────────────────────────────────────────────────────────────

type ParetoRow = {
  ticker: string
  name: string
  notional: number
  trades: number
  cumulativePct: number
  color: string
  href: string
}

const buildPareto = (markets: TopMarketRow[]): ParetoRow[] => {
  const filtered = markets.filter((m) => (m.notional ?? 0) > 0).slice(0, 8)
  if (!filtered.length) return []
  const grandTotal = filtered.reduce((s, m) => s + (m.notional ?? 0), 0)
  let running = 0
  return filtered.map((m, i) => {
    running += m.notional ?? 0
    return {
      ticker: m.ticker ?? `m-${i}`,
      name: (m.title ?? m.ticker ?? "—").slice(0, 32),
      notional: Math.round(m.notional ?? 0),
      trades: m.trades ?? 0,
      cumulativePct: grandTotal > 0 ? +((running / grandTotal) * 100).toFixed(1) : 0,
      color: PARETO_PALETTE[i % PARETO_PALETTE.length],
      href: kalshiOpenHref({ ticker: m.ticker, kalshi_url: m.kalshi_url }),
    }
  })
}

const HISTOGRAM_EDGES = [
  100, 250, 500, 1_000, 2_500, 5_000, 10_000, 25_000, 50_000, 100_000, Infinity,
]

type SizeBin = {
  label: string
  lo: number
  hi: number
  trades: number
  notional: number
  cumulativePct: number
}

const buildHistogram = (rows: TapeTradeRow[]): SizeBin[] => {
  const sizes = rows.map((r) => r.notional_usd ?? 0).filter((n) => n > 0)
  if (!sizes.length) return []

  const bins: SizeBin[] = []
  for (let i = 0; i < HISTOGRAM_EDGES.length - 1; i += 1) {
    const lo = HISTOGRAM_EDGES[i]
    const hi = HISTOGRAM_EDGES[i + 1]
    const label =
      hi === Infinity ? `${fmtUsdCompact(lo)}+` : `${fmtUsdCompact(lo)}–${fmtUsdCompact(hi)}`
    bins.push({ label, lo, hi, trades: 0, notional: 0, cumulativePct: 0 })
  }
  for (const s of sizes) {
    const idx = bins.findIndex((b) => s >= b.lo && s < b.hi)
    if (idx >= 0) {
      bins[idx].trades += 1
      bins[idx].notional += s
    }
  }
  // Trim leading/trailing empty bins for compactness, keep at least 4
  let start = 0
  let end = bins.length - 1
  while (start < end && bins[start].trades === 0) start += 1
  while (end > start && bins[end].trades === 0) end -= 1
  const trimmed = bins.slice(Math.max(0, start - 1), Math.min(bins.length, end + 2))

  const totalTrades = trimmed.reduce((s, b) => s + b.trades, 0)
  let running = 0
  for (const b of trimmed) {
    running += b.trades
    b.cumulativePct = totalTrades > 0 ? +((running / totalTrades) * 100).toFixed(1) : 0
  }
  return trimmed
}

type Kpis = {
  totalNotional: number
  totalTrades: number
  uniqueMarkets: number
  medianSize: number
  largestSize: number
  largestTicker: string
  netImbalance: number
  yesShare: number
  topMarketShare: number
  bucketLabel: string
}

const buildKpis = (
  rows: TapeTradeRow[],
  markets: ParetoRow[],
  bucketMs: number,
): Kpis => {
  const notionals = rows.map((r) => r.notional_usd ?? 0).filter((n) => n > 0)
  const total = notionals.reduce((s, n) => s + n, 0)
  const yesUsd = rows
    .filter((r) => (r.taker_side ?? "yes") !== "no")
    .reduce((s, r) => s + (r.notional_usd ?? 0), 0)
  const noUsd = rows
    .filter((r) => r.taker_side === "no")
    .reduce((s, r) => s + (r.notional_usd ?? 0), 0)

  const tickers = new Set(rows.map((r) => r.ticker).filter(Boolean) as string[])

  let largest = 0
  let largestTicker = "—"
  for (const r of rows) {
    const n = r.notional_usd ?? 0
    if (n > largest) {
      largest = n
      largestTicker = r.ticker ?? "—"
    }
  }

  const topMarketShare =
    total > 0 && markets.length > 0
      ? Math.min(100, (markets.reduce((s, m) => s + m.notional, 0) / total) * 100)
      : 0

  const bucketLabel =
    bucketMs >= 3_600_000
      ? `${bucketMs / 3_600_000}h`
      : `${bucketMs / 60_000}m`

  return {
    totalNotional: total,
    totalTrades: rows.length,
    uniqueMarkets: tickers.size,
    medianSize: median(notionals),
    largestSize: largest,
    largestTicker,
    netImbalance: yesUsd - noUsd,
    yesShare: yesUsd + noUsd > 0 ? (yesUsd / (yesUsd + noUsd)) * 100 : 0,
    topMarketShare,
    bucketLabel,
  }
}

// ────────────────────────────────────────────────────────────────────────────
// UI primitives
// ────────────────────────────────────────────────────────────────────────────

type SectionCardProps = {
  title: string
  hint?: string
  icon?: ReactNode
  children: ReactNode
  className?: string
  bodyClassName?: string
}

const SectionCard = ({
  title,
  hint,
  icon,
  children,
  className,
  bodyClassName,
}: SectionCardProps) => (
  <Card className={cn("border-border/60", className)}>
    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-1">
      <CardTitle className="flex items-center gap-1.5 text-sm font-medium">
        {icon ? <span className="text-primary/80">{icon}</span> : null}
        {title}
      </CardTitle>
      {hint ? (
        <span className="text-[0.65rem] text-muted-foreground">{hint}</span>
      ) : null}
    </CardHeader>
    <CardContent className={cn("pb-3", bodyClassName)}>{children}</CardContent>
  </Card>
)

const EmptyChart = ({ label }: { label: string }) => (
  <div className="flex h-full items-center justify-center text-xs text-muted-foreground">
    {label}
  </div>
)

const KpiTile = ({
  label,
  value,
  sub,
  tone,
  icon,
}: {
  label: string
  value: ReactNode
  sub?: ReactNode
  tone?: "positive" | "negative" | "neutral"
  icon?: ReactNode
}) => (
  <div className="rounded-lg border border-border/60 bg-card/60 px-3 py-2.5 backdrop-blur transition-colors hover:border-primary/40">
    <div className="flex items-center justify-between gap-2">
      <span className="text-[0.6rem] font-medium uppercase tracking-widest text-muted-foreground">
        {label}
      </span>
      {icon ? <span className="text-muted-foreground/70">{icon}</span> : null}
    </div>
    <div
      className={cn(
        "mt-1 text-base font-semibold tabular-nums tracking-tight",
        tone === "positive" && "text-emerald-400",
        tone === "negative" && "text-rose-400",
      )}
    >
      {value}
    </div>
    {sub ? (
      <div className="mt-0.5 truncate text-[0.65rem] text-muted-foreground">{sub}</div>
    ) : null}
  </div>
)

// ────────────────────────────────────────────────────────────────────────────
// Tooltips
// ────────────────────────────────────────────────────────────────────────────

const TooltipShell = ({ children }: { children: ReactNode }) => (
  <div className="min-w-[180px] rounded-md border border-border/70 bg-card/95 px-3 py-2 text-xs shadow-xl backdrop-blur">
    {children}
  </div>
)

const FlowTooltip = ({
  active,
  payload,
  bucketMs,
}: {
  active?: boolean
  payload?: Array<{ payload: FlowPoint }>
  bucketMs: number
}) => {
  if (!active || !payload?.length) return null
  const p = payload[0].payload
  const end = p.bucket + bucketMs
  return (
    <TooltipShell>
      <div className="font-mono text-[0.65rem] uppercase tracking-widest text-muted-foreground">
        {fmtClock(p.bucket)} – {fmtClock(end)}
      </div>
      <div className="mt-1.5 flex items-baseline justify-between gap-3">
        <span className="text-muted-foreground">Notional</span>
        <span className="font-semibold tabular-nums">{fmtUsd(p.total)}</span>
      </div>
      <div className="flex items-baseline justify-between gap-3">
        <span className="text-muted-foreground">Trades</span>
        <span className="tabular-nums">{fmtNumber(p.trades)}</span>
      </div>
      <div className="my-1.5 h-px bg-border/60" />
      {(["major", "large", "notable"] as Tier[]).map((t) => (
        <div key={t} className="flex items-center justify-between gap-3">
          <span className="flex items-center gap-1.5 text-muted-foreground">
            <span className="size-2 rounded-sm" style={{ backgroundColor: COLOR[t] }} />
            {TIER_LABEL[t]}
          </span>
          <span className="tabular-nums">{fmtUsd(p[t])}</span>
        </div>
      ))}
      <div className="my-1.5 h-px bg-border/60" />
      <div className="flex items-baseline justify-between gap-3">
        <span className="text-muted-foreground">Cumulative</span>
        <span className="tabular-nums">{fmtUsd(p.cumulative)}</span>
      </div>
    </TooltipShell>
  )
}

const ImbalanceTooltip = ({
  active,
  payload,
}: {
  active?: boolean
  payload?: Array<{ payload: FlowPoint }>
}) => {
  if (!active || !payload?.length) return null
  const p = payload[0].payload
  const tone = p.net >= 0 ? "text-emerald-400" : "text-rose-400"
  return (
    <TooltipShell>
      <div className="font-mono text-[0.65rem] uppercase tracking-widest text-muted-foreground">
        {p.label}
      </div>
      <div className="mt-1.5 flex items-baseline justify-between gap-3">
        <span className="flex items-center gap-1.5 text-muted-foreground">
          <span className="size-2 rounded-sm" style={{ backgroundColor: COLOR.yes }} />
          YES taker
        </span>
        <span className="tabular-nums">{fmtUsd(p.yes)}</span>
      </div>
      <div className="flex items-baseline justify-between gap-3">
        <span className="flex items-center gap-1.5 text-muted-foreground">
          <span className="size-2 rounded-sm" style={{ backgroundColor: COLOR.no }} />
          NO taker
        </span>
        <span className="tabular-nums">{fmtUsd(p.no)}</span>
      </div>
      <div className="my-1.5 h-px bg-border/60" />
      <div className="flex items-baseline justify-between gap-3">
        <span className="text-muted-foreground">Net (YES − NO)</span>
        <span className={cn("font-semibold tabular-nums", tone)}>
          {p.net >= 0 ? "+" : ""}
          {fmtUsd(p.net)}
        </span>
      </div>
      <div className="flex items-baseline justify-between gap-3">
        <span className="text-muted-foreground">Cumulative net</span>
        <span className={cn("tabular-nums", tone)}>
          {p.cumulativeNet >= 0 ? "+" : ""}
          {fmtUsd(p.cumulativeNet)}
        </span>
      </div>
    </TooltipShell>
  )
}

const ParetoTooltip = ({
  active,
  payload,
}: {
  active?: boolean
  payload?: Array<{ payload: ParetoRow }>
}) => {
  if (!active || !payload?.length) return null
  const p = payload[0].payload
  return (
    <TooltipShell>
      <div className="font-medium text-foreground">{p.name}</div>
      <div className="mt-0.5 font-mono text-[0.65rem] text-muted-foreground">{p.ticker}</div>
      <div className="my-1.5 h-px bg-border/60" />
      <div className="flex items-baseline justify-between gap-3">
        <span className="text-muted-foreground">Notional</span>
        <span className="font-semibold tabular-nums">{fmtUsd(p.notional)}</span>
      </div>
      <div className="flex items-baseline justify-between gap-3">
        <span className="text-muted-foreground">Trades</span>
        <span className="tabular-nums">{fmtNumber(p.trades)}</span>
      </div>
      <div className="flex items-baseline justify-between gap-3">
        <span className="text-muted-foreground">Cumulative share</span>
        <span className="tabular-nums">{fmtPct(p.cumulativePct, 1)}</span>
      </div>
    </TooltipShell>
  )
}

const HistogramTooltip = ({
  active,
  payload,
}: {
  active?: boolean
  payload?: Array<{ payload: SizeBin }>
}) => {
  if (!active || !payload?.length) return null
  const p = payload[0].payload
  return (
    <TooltipShell>
      <div className="font-mono text-[0.65rem] uppercase tracking-widest text-muted-foreground">
        Bucket
      </div>
      <div className="mt-0.5 font-medium">{p.label}</div>
      <div className="my-1.5 h-px bg-border/60" />
      <div className="flex items-baseline justify-between gap-3">
        <span className="text-muted-foreground">Trades</span>
        <span className="font-semibold tabular-nums">{fmtNumber(p.trades)}</span>
      </div>
      <div className="flex items-baseline justify-between gap-3">
        <span className="text-muted-foreground">Notional</span>
        <span className="tabular-nums">{fmtUsd(p.notional)}</span>
      </div>
      <div className="flex items-baseline justify-between gap-3">
        <span className="text-muted-foreground">Cumulative trades</span>
        <span className="tabular-nums">{fmtPct(p.cumulativePct, 1)}</span>
      </div>
    </TooltipShell>
  )
}

// ────────────────────────────────────────────────────────────────────────────
// Main component
// ────────────────────────────────────────────────────────────────────────────

type InsiderChartsProps = {
  rows: TapeTradeRow[]
  topMarkets: TopMarketRow[]
  loading?: boolean
}

export const InsiderCharts = ({ rows, topMarkets, loading }: InsiderChartsProps) => {
  const bucketMs = useMemo(() => pickBucketMs(rows), [rows])
  const flow = useMemo(() => buildFlow(rows, bucketMs), [rows, bucketMs])
  const pareto = useMemo(() => buildPareto(topMarkets), [topMarkets])
  const histogram = useMemo(() => buildHistogram(rows), [rows])
  const kpis = useMemo(() => buildKpis(rows, pareto, bucketMs), [rows, pareto, bucketMs])

  const sortedSizes = useMemo(
    () =>
      rows
        .map((r) => r.notional_usd ?? 0)
        .filter((n) => n > 0)
        .sort((a, b) => a - b),
    [rows],
  )
  const p50 = percentile(sortedSizes, 0.5)
  const p95 = percentile(sortedSizes, 0.95)

  const meanPerBucket = flow.length > 0 ? kpis.totalNotional / flow.length : 0

  const hasFlow = flow.length > 0
  const hasPareto = pareto.length > 0
  const hasHistogram = histogram.length > 0

  const netTone = kpis.netImbalance >= 0 ? "positive" : "negative"
  const netSign = kpis.netImbalance >= 0 ? "+" : "−"

  return (
    <div className="space-y-4">
      {/* KPI strip */}
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 lg:grid-cols-7">
        <KpiTile
          label="Total notional"
          value={fmtUsdCompact(kpis.totalNotional)}
          sub={`${fmtNumber(kpis.totalTrades)} trades`}
          icon={<Activity className="size-3" aria-hidden />}
        />
        <KpiTile
          label="Unique markets"
          value={fmtNumber(kpis.uniqueMarkets)}
          sub={`bucket ${kpis.bucketLabel}`}
          icon={<Layers className="size-3" aria-hidden />}
        />
        <KpiTile
          label="Median trade"
          value={fmtUsdCompact(kpis.medianSize)}
          sub={p95 > 0 ? `p95 ${fmtUsdCompact(p95)}` : undefined}
        />
        <KpiTile
          label="Largest trade"
          value={fmtUsdCompact(kpis.largestSize)}
          sub={kpis.largestTicker !== "—" ? kpis.largestTicker : undefined}
          icon={<TrendingUp className="size-3" aria-hidden />}
        />
        <KpiTile
          label="YES taker share"
          value={fmtPct(kpis.yesShare)}
          sub={`${fmtPct(100 - kpis.yesShare)} NO`}
        />
        <KpiTile
          label="Net YES − NO"
          tone={netTone}
          value={
            <span className="inline-flex items-center gap-1">
              {kpis.netImbalance >= 0 ? (
                <ArrowUpRight className="size-3.5" aria-hidden />
              ) : (
                <ArrowDownRight className="size-3.5" aria-hidden />
              )}
              {netSign}
              {fmtUsdCompact(Math.abs(kpis.netImbalance))}
            </span>
          }
          sub="directional pressure"
        />
        <KpiTile
          label="Top-10 share"
          value={fmtPct(kpis.topMarketShare)}
          sub="market concentration"
          icon={<PieChart className="size-3" aria-hidden />}
        />
      </div>

      {/* Row 1: notional flow + pareto */}
      <div className="grid gap-4 lg:grid-cols-5">
        <SectionCard
          className="lg:col-span-3"
          title="Notional flow over time"
          hint={`stacked by tier · ${kpis.bucketLabel} buckets · cumulative line`}
          icon={<Activity className="size-3.5" aria-hidden />}
        >
          <div className="h-[260px]">
            {loading || !hasFlow ? (
              <EmptyChart label={loading ? "Loading…" : "No trade flow yet"} />
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <ComposedChart
                  data={flow}
                  margin={{ top: 8, right: 12, left: -8, bottom: 0 }}
                >
                  <defs>
                    <linearGradient id="majorFill" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor={COLOR.major} stopOpacity={0.55} />
                      <stop offset="100%" stopColor={COLOR.major} stopOpacity={0} />
                    </linearGradient>
                    <linearGradient id="largeFill" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor={COLOR.large} stopOpacity={0.5} />
                      <stop offset="100%" stopColor={COLOR.large} stopOpacity={0} />
                    </linearGradient>
                    <linearGradient id="notableFill" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor={COLOR.notable} stopOpacity={0.45} />
                      <stop offset="100%" stopColor={COLOR.notable} stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid stroke={COLOR.grid} strokeDasharray="2 4" vertical={false} />
                  <XAxis
                    dataKey="label"
                    tick={{ fontSize: 10, fill: COLOR.axis }}
                    tickLine={false}
                    axisLine={{ stroke: COLOR.grid }}
                    minTickGap={28}
                  />
                  <YAxis
                    yAxisId="left"
                    tickFormatter={fmtUsdCompact}
                    tick={{ fontSize: 10, fill: COLOR.axis }}
                    tickLine={false}
                    axisLine={false}
                    width={52}
                  />
                  <YAxis
                    yAxisId="right"
                    orientation="right"
                    tickFormatter={fmtUsdCompact}
                    tick={{ fontSize: 10, fill: COLOR.axis }}
                    tickLine={false}
                    axisLine={false}
                    width={48}
                  />
                  {meanPerBucket > 0 && (
                    <ReferenceLine
                      yAxisId="left"
                      y={meanPerBucket}
                      stroke={COLOR.grid}
                      strokeDasharray="3 3"
                      label={{
                        value: `mean ${fmtUsdCompact(meanPerBucket)}`,
                        position: "insideTopRight",
                        fill: COLOR.axis,
                        fontSize: 9,
                      }}
                    />
                  )}
                  <Tooltip content={<FlowTooltip bucketMs={bucketMs} />} />
                  <Legend
                    verticalAlign="top"
                    height={20}
                    wrapperStyle={{ fontSize: 10, color: COLOR.axis }}
                    iconType="square"
                  />
                  <Area
                    yAxisId="left"
                    type="monotone"
                    name="Major"
                    dataKey="major"
                    stackId="tier"
                    stroke={COLOR.major}
                    strokeWidth={1.25}
                    fill="url(#majorFill)"
                    isAnimationActive={false}
                  />
                  <Area
                    yAxisId="left"
                    type="monotone"
                    name="Large"
                    dataKey="large"
                    stackId="tier"
                    stroke={COLOR.large}
                    strokeWidth={1.25}
                    fill="url(#largeFill)"
                    isAnimationActive={false}
                  />
                  <Area
                    yAxisId="left"
                    type="monotone"
                    name="Notable"
                    dataKey="notable"
                    stackId="tier"
                    stroke={COLOR.notable}
                    strokeWidth={1.25}
                    fill="url(#notableFill)"
                    isAnimationActive={false}
                  />
                  <Line
                    yAxisId="right"
                    type="monotone"
                    name="Cumulative"
                    dataKey="cumulative"
                    stroke={COLOR.cum}
                    strokeWidth={1.25}
                    strokeDasharray="4 4"
                    dot={false}
                    isAnimationActive={false}
                  />
                  {flow.length > 12 && (
                    <Brush
                      dataKey="label"
                      height={18}
                      travellerWidth={8}
                      stroke={COLOR.grid}
                      fill="hsl(var(--card))"
                      tickFormatter={() => ""}
                    />
                  )}
                </ComposedChart>
              </ResponsiveContainer>
            )}
          </div>
        </SectionCard>

        <SectionCard
          className="lg:col-span-2"
          title="Top markets · Pareto"
          hint="bars = notional · line = cumulative %"
          icon={<BarChart3 className="size-3.5" aria-hidden />}
        >
          <div className="h-[260px]">
            {loading || !hasPareto ? (
              <EmptyChart label={loading ? "Loading…" : "No markets in sample"} />
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <ComposedChart
                  data={pareto}
                  layout="vertical"
                  margin={{ top: 8, right: 32, bottom: 0, left: 8 }}
                  barCategoryGap={6}
                >
                  <CartesianGrid stroke={COLOR.grid} strokeDasharray="2 4" horizontal={false} />
                  <XAxis
                    type="number"
                    xAxisId="bottom"
                    tickFormatter={fmtUsdCompact}
                    tick={{ fontSize: 10, fill: COLOR.axis }}
                    tickLine={false}
                    axisLine={false}
                  />
                  <XAxis
                    type="number"
                    xAxisId="top"
                    orientation="top"
                    domain={[0, 100]}
                    tickFormatter={(v) => `${v}%`}
                    tick={{ fontSize: 9, fill: COLOR.axis }}
                    tickLine={false}
                    axisLine={false}
                    hide
                  />
                  <YAxis
                    type="category"
                    dataKey="ticker"
                    width={0}
                    tick={false}
                    axisLine={false}
                    tickLine={false}
                  />
                  <Tooltip content={<ParetoTooltip />} cursor={{ fill: "hsl(var(--muted) / 0.3)" }} />
                  <Bar
                    xAxisId="bottom"
                    dataKey="notional"
                    radius={[4, 4, 4, 4]}
                    isAnimationActive={false}
                  >
                    {pareto.map((b) => (
                      <Cell key={b.ticker} fill={b.color} />
                    ))}
                  </Bar>
                  <Line
                    xAxisId="top"
                    type="monotone"
                    dataKey="cumulativePct"
                    stroke={COLOR.cum}
                    strokeWidth={1.25}
                    dot={{ r: 2.5, fill: COLOR.cum }}
                    isAnimationActive={false}
                  />
                </ComposedChart>
              </ResponsiveContainer>
            )}
          </div>
          <ul className="mt-2 space-y-1">
            {pareto.map((b) => {
              const content = (
                <>
                  <span
                    className="size-2 shrink-0 rounded-sm"
                    style={{ backgroundColor: b.color }}
                    aria-hidden
                  />
                  <span className="line-clamp-1 flex-1 text-foreground/90">{b.name}</span>
                  <span className="font-mono text-[0.6rem] text-muted-foreground/70">
                    {fmtPct(b.cumulativePct, 0)}
                  </span>
                  <span className="w-14 text-right tabular-nums">
                    {fmtUsdCompact(b.notional)}
                  </span>
                </>
              )
              return (
                <li
                  key={b.ticker}
                  className="flex items-center gap-2 text-[0.7rem] text-muted-foreground"
                >
                  <a
                    href={b.href}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex w-full items-center gap-2 rounded px-1 py-0.5 hover:bg-accent/40 hover:text-foreground"
                    aria-label={`Open ${b.name} on Kalshi`}
                  >
                    {content}
                  </a>
                </li>
              )
            })}
          </ul>
        </SectionCard>
      </div>

      {/* Row 2: imbalance + size distribution */}
      <div className="grid gap-4 lg:grid-cols-5">
        <SectionCard
          className="lg:col-span-3"
          title="Side imbalance · YES vs NO"
          hint="bars = per-bucket signed notional · line = cumulative net"
          icon={<TrendingUp className="size-3.5" aria-hidden />}
        >
          <div className="h-[240px]">
            {loading || !hasFlow ? (
              <EmptyChart label={loading ? "Loading…" : "No directional flow yet"} />
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <ComposedChart
                  data={flow.map((p) => ({
                    ...p,
                    yesSigned: p.yes,
                    noSigned: -p.no,
                  }))}
                  margin={{ top: 8, right: 12, left: -8, bottom: 0 }}
                  stackOffset="sign"
                >
                  <CartesianGrid stroke={COLOR.grid} strokeDasharray="2 4" vertical={false} />
                  <XAxis
                    dataKey="label"
                    tick={{ fontSize: 10, fill: COLOR.axis }}
                    tickLine={false}
                    axisLine={{ stroke: COLOR.grid }}
                    minTickGap={28}
                  />
                  <YAxis
                    yAxisId="left"
                    tickFormatter={(v: number) => fmtUsdCompact(Math.abs(v))}
                    tick={{ fontSize: 10, fill: COLOR.axis }}
                    tickLine={false}
                    axisLine={false}
                    width={52}
                  />
                  <YAxis
                    yAxisId="right"
                    orientation="right"
                    tickFormatter={fmtUsdCompact}
                    tick={{ fontSize: 10, fill: COLOR.axis }}
                    tickLine={false}
                    axisLine={false}
                    width={48}
                  />
                  <ReferenceLine yAxisId="left" y={0} stroke={COLOR.grid} />
                  <Tooltip content={<ImbalanceTooltip />} cursor={{ fill: "hsl(var(--muted) / 0.3)" }} />
                  <Legend
                    verticalAlign="top"
                    height={20}
                    wrapperStyle={{ fontSize: 10, color: COLOR.axis }}
                    iconType="square"
                  />
                  <Bar
                    yAxisId="left"
                    dataKey="yesSigned"
                    name="YES taker"
                    stackId="side"
                    fill={COLOR.yes}
                    fillOpacity={0.7}
                    radius={[2, 2, 0, 0]}
                    isAnimationActive={false}
                  />
                  <Bar
                    yAxisId="left"
                    dataKey="noSigned"
                    name="NO taker"
                    stackId="side"
                    fill={COLOR.no}
                    fillOpacity={0.7}
                    radius={[0, 0, 2, 2]}
                    isAnimationActive={false}
                  />
                  <Line
                    yAxisId="right"
                    type="monotone"
                    name="Cumulative net"
                    dataKey="cumulativeNet"
                    stroke={COLOR.cum}
                    strokeWidth={1.5}
                    strokeDasharray="4 4"
                    dot={false}
                    isAnimationActive={false}
                  />
                </ComposedChart>
              </ResponsiveContainer>
            )}
          </div>
        </SectionCard>

        <SectionCard
          className="lg:col-span-2"
          title="Trade size distribution"
          hint="log-scaled bins · p50 / p95 markers"
          icon={<BarChart3 className="size-3.5" aria-hidden />}
        >
          <div className="h-[240px]">
            {loading || !hasHistogram ? (
              <EmptyChart label={loading ? "Loading…" : "No size data"} />
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart
                  data={histogram}
                  margin={{ top: 8, right: 8, bottom: 0, left: -12 }}
                >
                  <CartesianGrid stroke={COLOR.grid} strokeDasharray="2 4" vertical={false} />
                  <XAxis
                    dataKey="label"
                    tick={{ fontSize: 9, fill: COLOR.axis }}
                    tickLine={false}
                    axisLine={{ stroke: COLOR.grid }}
                    interval={0}
                    angle={-25}
                    textAnchor="end"
                    height={48}
                  />
                  <YAxis
                    yAxisId="left"
                    allowDecimals={false}
                    tick={{ fontSize: 10, fill: COLOR.axis }}
                    tickLine={false}
                    axisLine={false}
                    width={32}
                  />
                  <Tooltip
                    content={<HistogramTooltip />}
                    cursor={{ fill: "hsl(var(--muted) / 0.3)" }}
                  />
                  <Bar
                    yAxisId="left"
                    dataKey="trades"
                    fill={COLOR.major}
                    fillOpacity={0.55}
                    radius={[3, 3, 0, 0]}
                    isAnimationActive={false}
                  />
                </BarChart>
              </ResponsiveContainer>
            )}
          </div>
          <div className="mt-2 flex flex-wrap items-center justify-between gap-2 text-[0.65rem] text-muted-foreground">
            <div className="flex items-center gap-3">
              <span className="flex items-center gap-1">
                <span className="size-2 rounded-sm" style={{ backgroundColor: COLOR.major }} />
                trade count
              </span>
              <span className="tabular-nums">
                p50 <span className="text-foreground">{fmtUsdCompact(p50)}</span>
              </span>
              <span className="tabular-nums">
                p95 <span className="text-foreground">{fmtUsdCompact(p95)}</span>
              </span>
            </div>
            <span className="font-mono">{fmtNumber(sortedSizes.length)} sized prints</span>
          </div>
        </SectionCard>
      </div>
    </div>
  )
}
