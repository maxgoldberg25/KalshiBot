import { useState } from "react"
import {
  ArrowDownRight,
  ArrowUpRight,
  Check,
  Copy,
  ExternalLink,
} from "lucide-react"
import type { MarketAggRow } from "@/api/types"
import { Card, CardContent } from "@/components/ui/card"
import { kalshiOpenHref } from "@/lib/kalshiLinks"
import { cn } from "@/lib/utils"

const fmtUsd = (n: number | null | undefined, fractionDigits = 0) => {
  if (n == null || Number.isNaN(n)) return "—"
  return new Intl.NumberFormat(undefined, {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: fractionDigits,
    maximumFractionDigits: fractionDigits,
  }).format(n)
}

const fmtCompactUsd = (n: number | null | undefined) => {
  if (n == null || Number.isNaN(n)) return "—"
  if (n >= 1_000_000) return `$${(n / 1_000_000).toFixed(2)}M`
  if (n >= 1_000) return `$${(n / 1_000).toFixed(n >= 10_000 ? 1 : 2)}K`
  return fmtUsd(n, 0)
}

const fmtNumber = (n: number | null | undefined) => {
  if (n == null || Number.isNaN(n)) return "—"
  return new Intl.NumberFormat().format(Math.round(n))
}

const fmtCents = (dollars: number | null | undefined) => {
  if (dollars == null || Number.isNaN(dollars)) return null
  return Math.round(dollars * 100)
}

const fmtRelTime = (iso: string | null | undefined) => {
  if (!iso) return "—"
  const t = new Date(iso).getTime()
  if (Number.isNaN(t)) return "—"
  const diff = t - Date.now()
  const abs = Math.abs(diff)
  const mins = Math.round(abs / 60_000)
  const hrs = Math.round(abs / 3_600_000)
  const days = Math.round(abs / 86_400_000)
  const s = mins < 60 ? `${mins}m` : hrs < 48 ? `${hrs}h` : `${days}d`
  return diff >= 0 ? `in ${s}` : `${s} ago`
}

const fmtCloseTime = (iso: string | null | undefined) => {
  if (!iso) return "—"
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return "—"
  return d.toLocaleString([], {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  })
}

const shortTicker = (t: string | undefined) => {
  if (!t) return "—"
  if (t.length <= 22) return t
  return `${t.slice(0, 12)}…${t.slice(-8)}`
}

type ImpactLevel = "high" | "medium" | "low"

const impactFromScore = (score: number | undefined, tier?: string): ImpactLevel => {
  if (tier === "whale" || (score ?? 0) >= 75) return "high"
  if ((score ?? 0) >= 55) return "medium"
  return "low"
}

const IMPACT_META: Record<ImpactLevel, { label: string; cls: string }> = {
  high: {
    label: "High Impact",
    cls: "bg-rose-500/15 text-rose-300 ring-rose-500/40",
  },
  medium: {
    label: "Medium Impact",
    cls: "bg-amber-500/15 text-amber-300 ring-amber-500/40",
  },
  low: {
    label: "Low Impact",
    cls: "bg-sky-500/15 text-sky-300 ring-sky-400/30",
  },
}

type PriceChipProps = {
  side: "YES" | "NO"
  ask: number | null | undefined
  bid: number | null | undefined
  emphasized: boolean
}

const PriceChip = ({ side, ask, bid, emphasized }: PriceChipProps) => {
  const askCents = fmtCents(ask)
  const bidCents = fmtCents(bid)
  const spread =
    askCents != null && bidCents != null ? Math.max(0, askCents - bidCents) : null

  const tone =
    side === "YES"
      ? emphasized
        ? "border-emerald-400/60 bg-emerald-500/15 text-emerald-200"
        : "border-border/60 bg-card text-foreground/90"
      : emphasized
      ? "border-rose-400/60 bg-rose-500/15 text-rose-200"
      : "border-border/60 bg-card text-foreground/90"

  return (
    <div
      className={cn(
        "flex flex-1 flex-col items-start justify-between gap-0.5 rounded-md border px-2.5 py-2 transition-colors",
        tone,
      )}
      aria-label={`${side} side: ask ${askCents ?? "—"} cents, bid ${bidCents ?? "—"} cents`}
    >
      <div className="flex w-full items-center justify-between gap-2">
        <span className="text-[0.6rem] font-semibold uppercase tracking-wider text-muted-foreground">
          {side}
        </span>
        <span className="text-[0.55rem] font-medium uppercase tracking-wider text-muted-foreground">
          ask
        </span>
      </div>
      <div className="flex items-baseline gap-1">
        <span className="text-xl font-bold tabular-nums">
          {askCents != null ? `${askCents}` : "—"}
        </span>
        <span className="text-xs text-muted-foreground">¢</span>
      </div>
      <div className="flex w-full items-center justify-between text-[0.58rem] tabular-nums text-muted-foreground">
        <span>bid {bidCents != null ? `${bidCents}¢` : "—"}</span>
        {spread != null ? (
          <span
            className={cn(
              "font-medium",
              spread <= 2
                ? "text-emerald-300/80"
                : spread <= 5
                ? "text-amber-300/80"
                : "text-rose-300/80",
            )}
          >
            spread {spread}¢
          </span>
        ) : null}
      </div>
    </div>
  )
}

type Props = { row: MarketAggRow }

export function TradeCard({ row }: Props) {
  const [copied, setCopied] = useState(false)

  const href = kalshiOpenHref({ ticker: row.ticker, kalshi_url: row.kalshi_url })
  const m = row.market ?? {}
  const title = row.title || row.ticker || "—"
  const subtitle = row.subtitle || m.subtitle || ""
  const yes = row.yes_notional ?? 0
  const no = row.no_notional ?? 0
  const total = yes + no
  const yesPct = total > 0 ? (yes / total) * 100 : 50
  const leaning: "yes" | "no" | "mixed" =
    yesPct >= 55 ? "yes" : yesPct <= 45 ? "no" : "mixed"

  const impact = impactFromScore(row.signal_score, row.tier)
  const impactMeta = IMPACT_META[impact]

  const yesAskCents = fmtCents(m.yes_ask)
  const noAskCents = fmtCents(m.no_ask)

  const handleCopyTicker = async (e: React.MouseEvent<HTMLButtonElement>) => {
    e.preventDefault()
    e.stopPropagation()
    if (!row.ticker) return
    try {
      await navigator.clipboard.writeText(row.ticker)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1_500)
    } catch {
      setCopied(false)
    }
  }

  const SideIcon =
    leaning === "yes" ? ArrowUpRight : leaning === "no" ? ArrowDownRight : null

  return (
    <Card className="group relative flex flex-col border-border/60 transition-colors hover:border-primary/40 hover:bg-card/80">
      <CardContent className="flex flex-1 flex-col gap-3 p-4">
        <div className="flex items-start justify-between gap-2">
          <div className="flex min-w-0 items-center gap-1.5">
            <button
              type="button"
              onClick={handleCopyTicker}
              className="group/copy inline-flex max-w-full items-center gap-1 rounded px-1 py-0.5 font-mono text-[0.65rem] text-muted-foreground hover:bg-muted hover:text-foreground"
              aria-label={
                copied
                  ? `Copied ${row.ticker ?? "ticker"} to clipboard`
                  : `Copy ticker ${row.ticker ?? ""} to clipboard`
              }
              title={row.ticker}
            >
              <span className="truncate">{shortTicker(row.ticker)}</span>
              {copied ? (
                <Check className="size-3 text-emerald-400" aria-hidden />
              ) : (
                <Copy
                  className="size-3 text-muted-foreground/70 group-hover/copy:text-foreground"
                  aria-hidden
                />
              )}
            </button>
            <span aria-hidden className="text-[0.65rem] text-muted-foreground">
              ·
            </span>
            <span
              className="whitespace-nowrap text-[0.65rem] text-muted-foreground"
              title={row.last_time ?? ""}
            >
              {fmtRelTime(row.last_time)}
            </span>
          </div>
          <span
            className={cn(
              "inline-flex shrink-0 items-center rounded px-1.5 py-0.5 text-[0.58rem] font-semibold uppercase tracking-wider ring-1",
              impactMeta.cls,
            )}
          >
            {impactMeta.label}
          </span>
        </div>

        <a
          href={href}
          target="_blank"
          rel="noopener noreferrer"
          className="space-y-1"
          aria-label={`Open market "${title}" on Kalshi`}
        >
          <div className="line-clamp-2 text-sm font-semibold leading-snug text-foreground group-hover:text-primary">
            {title}
          </div>
          {subtitle ? (
            <div className="line-clamp-1 text-xs text-muted-foreground">
              {subtitle}
            </div>
          ) : null}
        </a>

        <div className="flex items-stretch gap-2">
          <PriceChip
            side="YES"
            ask={m.yes_ask}
            bid={m.yes_bid}
            emphasized={leaning === "yes"}
          />
          <PriceChip
            side="NO"
            ask={m.no_ask}
            bid={m.no_bid}
            emphasized={leaning === "no"}
          />
        </div>

        <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1 text-[0.7rem] text-muted-foreground">
          <span
            className="inline-flex items-center gap-1 font-semibold text-emerald-300"
            title="Conviction score 0–100: size × imbalance × OI share × concentration × recency"
          >
            Signal: {row.signal_score ?? 0}
          </span>
          {SideIcon ? (
            <span
              className={cn(
                "inline-flex items-center gap-1 tabular-nums",
                leaning === "yes" ? "text-emerald-300" : "text-rose-300",
              )}
            >
              <SideIcon className="size-3" aria-hidden />
              {leaning === "yes" ? "YES bias" : "NO bias"}
            </span>
          ) : (
            <span className="text-muted-foreground">Balanced flow</span>
          )}
          <span className="tabular-nums">
            {row.trades} {row.trades === 1 ? "print" : "prints"}
          </span>
          <span className="font-semibold tabular-nums text-foreground">
            {fmtCompactUsd(row.total_notional)}
          </span>
        </div>

        <div>
          <div
            className="h-1.5 w-full overflow-hidden rounded-full bg-rose-500/20"
            aria-hidden
          >
            <div
              className="h-full bg-emerald-500/70"
              style={{ width: `${yesPct}%` }}
            />
          </div>
          <div className="mt-1 flex items-center justify-between text-[0.6rem] text-muted-foreground tabular-nums">
            <span className="text-emerald-300/90">
              YES {fmtCompactUsd(yes)}
            </span>
            <span className="text-rose-300/90">NO {fmtCompactUsd(no)}</span>
          </div>
        </div>

        <div className="flex items-center justify-between gap-3 text-[0.65rem] text-muted-foreground">
          <span className="tabular-nums" title={row.close_time ?? ""}>
            Closes {fmtCloseTime(row.close_time)}
          </span>
          <span className="tabular-nums">
            Largest {fmtUsd(row.largest_notional, 0)} · {fmtNumber(row.largest_count)}{" "}
            sh
          </span>
        </div>

        <div className="mt-auto grid grid-cols-2 gap-2 pt-1">
          <a
            href={href}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center justify-center gap-1.5 rounded-md bg-emerald-500/20 px-3 py-2 text-xs font-bold uppercase tracking-wider text-emerald-200 ring-1 ring-emerald-400/40 transition-colors hover:bg-emerald-500/30 hover:text-emerald-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-300"
            aria-label={`Buy YES on Kalshi${
              yesAskCents != null ? ` at ${yesAskCents} cents` : ""
            } for market ${title}`}
          >
            Buy YES
            <span className="font-mono text-[0.75rem] font-semibold tabular-nums">
              {yesAskCents != null ? `${yesAskCents}¢` : "—"}
            </span>
            <ExternalLink className="size-3" aria-hidden />
          </a>
          <a
            href={href}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center justify-center gap-1.5 rounded-md bg-rose-500/20 px-3 py-2 text-xs font-bold uppercase tracking-wider text-rose-200 ring-1 ring-rose-400/40 transition-colors hover:bg-rose-500/30 hover:text-rose-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rose-300"
            aria-label={`Buy NO on Kalshi${
              noAskCents != null ? ` at ${noAskCents} cents` : ""
            } for market ${title}`}
          >
            Buy NO
            <span className="font-mono text-[0.75rem] font-semibold tabular-nums">
              {noAskCents != null ? `${noAskCents}¢` : "—"}
            </span>
            <ExternalLink className="size-3" aria-hidden />
          </a>
        </div>
      </CardContent>
    </Card>
  )
}
