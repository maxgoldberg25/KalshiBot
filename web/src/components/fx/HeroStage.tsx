import {
  Activity,
  BarChart3,
  ChevronDown,
  Flame,
  ShieldAlert,
  TrendingUp,
  Wallet,
  Zap,
} from "lucide-react"
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
  <div className="group relative flex min-w-0 w-full flex-col rounded-xl border border-border/60 bg-card/50 px-3 py-3 backdrop-blur-sm transition-colors hover:border-primary/40 sm:px-4">
    <span className="mb-1 flex items-center gap-1.5 font-display text-[0.62rem] font-semibold uppercase tracking-[0.22em] text-muted-foreground">
      {icon}
      {label}
    </span>
    <span
      className={cn(
        "font-display text-2xl font-bold tabular-nums tracking-tight",
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
        className="pointer-events-none bg-grid absolute inset-0 opacity-[0.12] mask-fade-b"
        aria-hidden
      />
      <div
        className="pointer-events-none absolute -right-32 -top-24 size-[460px] rounded-full bg-primary/10 blur-3xl"
        aria-hidden
      />

      <div className="relative mx-auto grid max-w-6xl gap-10 px-4 pb-12 pt-14 lg:grid-cols-[1.1fr_1fr] lg:pt-16">
        <div className="relative z-10 flex min-w-0 flex-col gap-6 animate-fade-up">
          <div className="flex flex-wrap items-center gap-2 gap-y-2">
            <span className="inline-flex items-center gap-1.5 rounded-full border border-primary/40 bg-primary/10 px-3 py-1 font-display text-[0.65rem] font-semibold uppercase tracking-[0.28em] text-primary">
              <Flame className="size-3" aria-hidden />
              Insider-flow radar
            </span>
            {!!status && (
              <Badge
                className={cn(
                  "rounded-full border-0 px-2.5 py-0.5 font-display text-[0.6rem] font-semibold uppercase tracking-[0.22em]",
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
            <h1 className="font-display text-balance text-5xl font-bold uppercase leading-[1.02] tracking-tight text-foreground sm:text-6xl lg:text-[4.25rem]">
              Track the tape.
              <br />
              <span className="bg-gradient-to-br from-emerald-300 via-primary to-teal-400 bg-clip-text text-transparent">
                Catch the insiders.
              </span>
            </h1>
            <p className="max-w-xl text-balance text-base leading-relaxed text-muted-foreground">
              KalshiInsider watches the public trade tape for unusually large
              non-sports orders, clusters them by market, and ranks the flow by
              conviction so you can see where informed money is moving first.
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
            <Button
              asChild
              size="lg"
              className="gap-2 font-display uppercase tracking-wider shadow-lg shadow-primary/25"
            >
              <NavLink to="/insider">
                <ShieldAlert className="size-4" aria-hidden />
                Open insider watch
              </NavLink>
            </Button>
            {onScan ? (
              <Button
                size="lg"
                variant="ghost"
                className="gap-2 font-display uppercase tracking-wider"
                onClick={onScan}
                disabled={scanning}
                aria-busy={scanning}
              >
                <Zap className={cn("size-4", scanning && "animate-pulse")} aria-hidden />
                Scan now
              </Button>
            ) : null}
          </div>

          <div className="mt-2 grid grid-cols-2 gap-2.5 sm:grid-cols-4 sm:gap-3 [&>*]:min-w-0">
            <StatPill
              label="Live signals"
              icon={<TrendingUp className="size-3" aria-hidden />}
              accent={liveOpps > 0 ? "positive" : undefined}
            >
              <CountUp value={liveOpps} />
            </StatPill>
            <StatPill label="Mapped" icon={<BarChart3 className="size-3" aria-hidden />}>
              <CountUp value={mappedMarkets} />
            </StatPill>
            <StatPill label="Tape scans" icon={<Activity className="size-3" aria-hidden />}>
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
          className="relative z-0 mt-4 min-w-0 animate-fade-up lg:mt-0"
          style={{ animationDelay: "120ms" }}
        >
          <div className="relative z-10 rounded-2xl border border-border/60 bg-card/70 p-5 shadow-xl shadow-primary/5 backdrop-blur-md">
            <LiveEdgeChart liveOpps={liveOpps} />
          </div>

          <div
            aria-hidden
            className="pointer-events-none absolute -inset-4 -z-10 rounded-3xl bg-primary/10 blur-2xl"
          />
        </div>

        <div className="pointer-events-none col-span-full flex flex-col items-center gap-1 pb-3 pt-8 text-muted-foreground sm:pt-10">
          <span className="sr-only">More on this page below.</span>
          <span
            className="font-display text-[0.6rem] uppercase tracking-[0.35em]"
            aria-hidden
          >
            Follow the flow
          </span>
          <ChevronDown className="size-4 animate-scroll-hint" aria-hidden />
        </div>
      </div>

      <div className="relative z-20 border-t border-border/30 bg-background/80">
        <TickerTape />
      </div>
    </section>
  )
}
