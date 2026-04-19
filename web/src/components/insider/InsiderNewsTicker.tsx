import { useMemo } from "react"
import { Radio } from "lucide-react"
import type { MarketAggRow } from "@/api/types"
import { kalshiOpenHref } from "@/lib/kalshiLinks"
import { cn } from "@/lib/utils"

const usd = (n: number | undefined | null) => {
  if (n == null || Number.isNaN(n)) return "$0"
  if (n >= 1_000_000) return `$${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `$${(n / 1_000).toFixed(n >= 10_000 ? 0 : 1)}K`
  return `$${Math.round(n)}`
}

const headlineFor = (m: MarketAggRow) => {
  const score = m.signal_score ?? 0
  const prefix =
    score >= 75 || m.tier === "whale"
      ? "BREAKING"
      : score >= 55
      ? "JUST IN"
      : "WATCH"

  const yes = m.yes_notional ?? 0
  const no = m.no_notional ?? 0
  const side = yes >= no ? "YES" : "NO"
  const title = (m.title || m.ticker || "market").replace(/\s+/g, " ").trim()
  const shortTitle = title.length > 90 ? `${title.slice(0, 87)}…` : title

  return {
    prefix,
    body: `${usd(m.total_notional)} swept ${side} on "${shortTitle}"`,
    tail: `${score} conviction${m.category ? ` · ${m.category}` : ""}`,
    side,
  }
}

type TickerProps = {
  markets: MarketAggRow[]
  loading?: boolean
}

const prefixTone: Record<string, string> = {
  BREAKING: "bg-rose-500/20 text-rose-200 ring-rose-500/40",
  "JUST IN": "bg-amber-500/20 text-amber-200 ring-amber-500/40",
  WATCH: "bg-sky-500/15 text-sky-200 ring-sky-400/30",
}

export function InsiderNewsTicker({ markets, loading = false }: TickerProps) {
  const items = useMemo(
    () =>
      markets
        .filter((m) => (m.signal_score ?? 0) > 0)
        .slice(0, 24)
        .map((m) => ({ row: m, head: headlineFor(m) })),
    [markets],
  )

  if (loading) {
    return (
      <div
        className="mb-4 flex items-center gap-3 overflow-hidden rounded-lg border border-border/60 bg-card/60 px-3 py-2 text-xs text-muted-foreground"
        role="status"
        aria-live="polite"
      >
        <Radio className="size-3.5 animate-pulse text-primary" aria-hidden />
        <span>Scanning the tape for unusual flow…</span>
      </div>
    )
  }

  if (items.length === 0) {
    return (
      <div className="mb-4 flex items-center gap-3 overflow-hidden rounded-lg border border-border/60 bg-card/60 px-3 py-2 text-xs text-muted-foreground">
        <Radio className="size-3.5 text-primary" aria-hidden />
        <span>No qualifying flow in the current window.</span>
      </div>
    )
  }

  // Render the list twice so the -50% marquee loop is seamless.
  const loop = [...items, ...items]

  return (
    <div
      className="group relative mb-4 flex items-center gap-3 overflow-hidden rounded-lg border border-border/60 bg-card/70 py-2 pl-3 pr-2"
      aria-label="Live insider flow headlines"
    >
      <div className="flex shrink-0 items-center gap-2 border-r border-border/60 pr-3 text-[0.65rem] font-semibold uppercase tracking-wider text-primary">
        <span className="relative flex size-2">
          <span className="absolute inline-flex size-full animate-ping rounded-full bg-primary opacity-60" />
          <span className="relative inline-flex size-2 rounded-full bg-primary" />
        </span>
        Live tape
      </div>

      <div className="relative flex-1 overflow-hidden mask-fade-x">
        <div className="flex w-max animate-marquee-slow items-center gap-6 pr-6 group-hover:[animation-play-state:paused]">
          {loop.map((it, idx) => {
            const href = kalshiOpenHref({
              ticker: it.row.ticker,
              kalshi_url: it.row.kalshi_url,
            })
            const tone = prefixTone[it.head.prefix] ?? prefixTone.WATCH
            const sideTone =
              it.head.side === "YES" ? "text-emerald-300" : "text-rose-300"
            return (
              <a
                key={`${it.row.ticker}-${idx}`}
                href={href}
                target="_blank"
                rel="noopener noreferrer"
                className="flex shrink-0 items-center gap-2 text-xs"
                aria-label={`Open ${it.row.ticker ?? "market"} on kalshi.com`}
              >
                <span
                  className={cn(
                    "inline-flex items-center rounded px-1.5 py-0.5 text-[0.58rem] font-bold uppercase tracking-wider ring-1",
                    tone,
                  )}
                >
                  {it.head.prefix}
                </span>
                <span className="text-foreground/90">
                  <span className={cn("font-semibold", sideTone)}>
                    {it.head.body.split(" swept ")[0]}
                  </span>
                  <span className="text-muted-foreground"> swept </span>
                  <span className={cn("font-semibold", sideTone)}>
                    {it.head.side}
                  </span>
                  <span className="text-muted-foreground">
                    {" on "}
                    <span className="text-foreground/90">
                      {it.head.body.split(" on ").slice(1).join(" on ")}
                    </span>
                  </span>
                </span>
                <span className="text-[0.65rem] text-muted-foreground">
                  · {it.head.tail}
                </span>
                <span className="text-muted-foreground/60">•</span>
              </a>
            )
          })}
        </div>
      </div>
    </div>
  )
}
