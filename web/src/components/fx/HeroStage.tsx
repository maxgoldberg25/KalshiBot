import { Activity, BarChart3, ShieldAlert, Sparkles, TrendingUp, Wallet, Zap } from "lucide-react"
import type { ReactNode } from "react"
import { NavLink } from "react-router-dom"
import { CountUp } from "./CountUp"
import { LiveEdgeChart } from "./LiveEdgeChart"
import { TickerTape } from "./TickerTape"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"

export type HeroMetrics = {
  liveOpps: number
  mappedMarkets: number
  totalScans: number
  realizedPnl: number
}

type HeroStageProps = {
  status?: string
  healthy?: boolean
  uptimeLabel?: string
  isScanning?: boolean
  metrics: HeroMetrics
  onScan?: () => void
  scanning?: boolean
}

const StatPill = ({
  label,
  icon,
  children,
  accent,
}: {
  label: string
  icon: ReactNode
  children: ReactNode
  accent?: "positive" | "negative"
}) => (
  <div className="group relative flex min-w-[150px] flex-col rounded-xl border border-border/60 bg-card/50 px-4 py-3 backdrop-blur-sm transition-colors hover:border-primary/40">
    <span className="mb-1 flex items-center gap-1.5 text-[0.62rem] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
      {icon}
      {label}
    </span>
    <span
      className={cn(
        "text-2xl font-bold tabular-nums tracking-tight",
        accent === "positive" && "text-emerald-400",
        accent === "negative" && "text-rose-400",
      )}
    >
      {children}
    </span>
  </div>
)

export const HeroStage = ({
  status,
  healthy,
  uptimeLabel,
  isScanning,
  metrics,
  onScan,
  scanning,
}: HeroStageProps) => {
  const { liveOpps, mappedMarkets, totalScans, realizedPnl } = metrics
  const pnlAccent = realizedPnl > 0 ? "positive" : realizedPnl < 0 ? "negative" : undefined

  return (
    <section className="relative overflow-hidden border-b border-border/40 bg-gradient-to-b from-card/40 to-background">
      <div
        className="bg-grid absolute inset-0 opacity-[0.18] mask-fade-b"
        aria-hidden
      />
      <div
        className="absolute -left-32 -top-32 size-[520px] rounded-full bg-primary/20 blur-3xl animate-float-slow"
        aria-hidden
      />
      <div
        className="absolute -right-40 top-20 size-[420px] rounded-full bg-sky-500/15 blur-3xl animate-pulse-glow"
        aria-hidden
      />
      <div
        className="absolute bottom-[-10rem] left-1/3 size-[360px] rounded-full bg-emerald-500/10 blur-3xl animate-float"
        aria-hidden
      />

      <div className="relative mx-auto grid max-w-6xl gap-10 px-4 pb-12 pt-14 lg:grid-cols-[1.1fr_1fr] lg:pt-16">
        <div className="flex flex-col gap-6 animate-fade-up">
          <div className="flex items-center gap-2">
            <span className="inline-flex items-center gap-1.5 rounded-full border border-primary/30 bg-primary/10 px-3 py-1 text-[0.65rem] font-semibold uppercase tracking-[0.2em] text-primary">
              <Sparkles className="size-3" aria-hidden />
              Real-time arbitrage engine
            </span>
            {!!status && (
              <Badge
                className={cn(
                  "rounded-full border-0 px-2.5 py-0.5 text-[0.6rem] font-semibold uppercase tracking-[0.18em]",
                  healthy
                    ? "bg-emerald-500/15 text-emerald-300 ring-1 ring-emerald-500/30"
                    : "bg-amber-500/15 text-amber-300 ring-1 ring-amber-500/30",
                )}
              >
                {status}
              </Badge>
            )}
          </div>

          <div className="space-y-3">
            <h1 className="text-balance text-5xl font-extrabold leading-[1.05] tracking-tight text-foreground sm:text-6xl">
              Turn prediction markets into{" "}
              <span className="bg-gradient-to-br from-emerald-300 via-primary to-teal-500 bg-clip-text text-transparent">
                a trading desk.
              </span>
            </h1>
            <p className="max-w-xl text-balance text-base leading-relaxed text-muted-foreground">
              KalshiBot continuously maps Kalshi contracts to live sportsbook lines, detects
              mispricings with slippage-aware math, and surfaces the edge before it disappears.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
              <span className="relative flex size-2">
                <span
                  className={cn(
                    "absolute inset-0 rounded-full",
                    isScanning ? "animate-ping bg-emerald-400/60" : "bg-transparent",
                  )}
                />
                <span
                  className={cn(
                    "relative size-2 rounded-full",
                    isScanning ? "bg-emerald-400" : "bg-muted-foreground/40",
                  )}
                />
              </span>
              {isScanning ? "Scanning markets" : "Idle"}
            </div>
            {uptimeLabel ? (
              <div className="text-xs text-muted-foreground">
                Uptime <span className="text-foreground">{uptimeLabel}</span>
              </div>
            ) : null}
          </div>

          <div className="flex flex-wrap gap-2.5">
            <Button asChild size="lg" className="gap-2 shadow-lg shadow-primary/20">
              <NavLink to="/scanner">
                <BarChart3 className="size-4" aria-hidden />
                Open Scanner
              </NavLink>
            </Button>
            <Button asChild size="lg" variant="outline" className="gap-2">
              <NavLink to="/insider">
                <ShieldAlert className="size-4" aria-hidden />
                Insider watch
              </NavLink>
            </Button>
            {onScan ? (
              <Button
                size="lg"
                variant="ghost"
                className="gap-2"
                onClick={onScan}
                disabled={scanning}
                aria-busy={scanning}
              >
                <Zap className={cn("size-4", scanning && "animate-pulse")} aria-hidden />
                Scan now
              </Button>
            ) : null}
          </div>

          <div className="mt-2 grid grid-cols-2 gap-2.5 sm:grid-cols-4">
            <StatPill
              label="Live opps"
              icon={<TrendingUp className="size-3" aria-hidden />}
              accent={liveOpps > 0 ? "positive" : undefined}
            >
              <CountUp value={liveOpps} />
            </StatPill>
            <StatPill label="Mapped" icon={<BarChart3 className="size-3" aria-hidden />}>
              <CountUp value={mappedMarkets} />
            </StatPill>
            <StatPill label="Scans" icon={<Activity className="size-3" aria-hidden />}>
              <CountUp value={totalScans} />
            </StatPill>
            <StatPill
              label="P&L"
              icon={<Wallet className="size-3" aria-hidden />}
              accent={pnlAccent}
            >
              <CountUp
                value={Math.abs(realizedPnl)}
                prefix={realizedPnl >= 0 ? "+$" : "-$"}
                decimals={2}
              />
            </StatPill>
          </div>
        </div>

        <div
          className="relative animate-fade-up"
          style={{ animationDelay: "120ms" }}
        >
          <div className="relative rounded-2xl border border-border/60 bg-card/70 p-5 shadow-2xl shadow-primary/5 backdrop-blur-md">
            <div
              aria-hidden
              className="pointer-events-none absolute inset-0 rounded-2xl bg-gradient-to-br from-primary/10 via-transparent to-sky-500/10 opacity-60"
            />
            <LiveEdgeChart liveOpps={liveOpps} />
            <div className="relative mt-4 grid grid-cols-3 gap-3 border-t border-border/50 pt-4 text-center">
              <div>
                <div className="text-[0.6rem] uppercase tracking-widest text-muted-foreground">
                  Avg latency
                </div>
                <div className="mt-0.5 text-sm font-semibold tabular-nums">
                  <CountUp value={142} suffix="ms" />
                </div>
              </div>
              <div>
                <div className="text-[0.6rem] uppercase tracking-widest text-muted-foreground">
                  Markets
                </div>
                <div className="mt-0.5 text-sm font-semibold tabular-nums">
                  <CountUp value={mappedMarkets} />
                </div>
              </div>
              <div>
                <div className="text-[0.6rem] uppercase tracking-widest text-muted-foreground">
                  Cycles
                </div>
                <div className="mt-0.5 text-sm font-semibold tabular-nums">
                  <CountUp value={totalScans} />
                </div>
              </div>
            </div>
          </div>

          <div
            aria-hidden
            className="pointer-events-none absolute -inset-6 -z-10 rounded-3xl bg-gradient-to-br from-primary/25 via-transparent to-sky-500/15 blur-2xl animate-pulse-glow"
          />
        </div>
      </div>

      <div className="relative">
        <TickerTape />
      </div>
    </section>
  )
}
