import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import type { LucideIcon } from "lucide-react"
import { Activity, BarChart3, Loader2, TrendingUp, Wallet, Zap } from "lucide-react"
import { toast } from "sonner"
import { fetchHealth, fetchState, postScan } from "@/api/fetch"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { fmtMoney, fmtTime, fmtUptime } from "@/lib/format"
import { cn } from "@/lib/utils"
import { NavLink } from "react-router-dom"

export function HomePage() {
  const qc = useQueryClient()
  const stateQ = useQuery({ queryKey: ["state"], queryFn: fetchState, refetchInterval: 30_000 })
  const healthQ = useQuery({ queryKey: ["health"], queryFn: fetchHealth, refetchInterval: 30_000 })
  const scanM = useMutation({
    mutationFn: postScan,
    onSuccess: (j) => {
      if (j.ok) toast.success(`Scan complete — ${j.alerts ?? 0} new alerts`)
      else toast.error(j.error ?? "Scan failed")
      void qc.invalidateQueries({ queryKey: ["state"] })
      void qc.invalidateQueries({ queryKey: ["health"] })
    },
    onError: (e: Error) => toast.error(e.message),
  })

  const d = stateQ.data
  const h = healthQ.data
  const loading = stateQ.isPending || healthQ.isPending
  const err = stateQ.error ?? healthQ.error

  const healthy = h?.status === "healthy"
  const opps = d?.opportunities?.length ?? 0
  const pnl = d?.pnl?.total_realized_pnl ?? 0

  return (
    <>
      {/* ── Hero ───────────────────────────────────────────────────────── */}
      <section className="border-b border-border/40 bg-gradient-to-b from-card/70 to-background">
        <div className="mx-auto max-w-6xl px-4 pb-10 pt-12">

          {/* Brand row */}
          <div className="mb-2 flex flex-col gap-6 sm:flex-row sm:items-start sm:justify-between">
            <div className="flex items-center gap-4">
              <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl bg-primary/15 ring-1 ring-primary/25 shadow-[0_0_24px_0] shadow-primary/10">
                <TrendingUp className="h-7 w-7 text-primary" />
              </div>
              <div>
                <h1 className="text-4xl font-extrabold tracking-tight text-foreground">
                  KalshiBot
                </h1>
                <p className="mt-0.5 text-sm text-muted-foreground">
                  Kalshi vs sportsbook arbitrage scanner
                </p>
              </div>
            </div>

            {/* Status + scanning indicator */}
            <div className="flex items-center gap-2.5 sm:pt-1">
              {d?.is_scanning && (
                <span className="flex items-center gap-1.5 text-xs font-medium text-emerald-400">
                  <span className="size-2 animate-pulse rounded-full bg-emerald-400" />
                  Scanning
                </span>
              )}
              {!loading && (
                <Badge
                  className={cn(
                    "rounded px-2.5 py-0.5 text-[0.65rem] font-semibold uppercase tracking-widest",
                    healthy
                      ? "bg-emerald-500/15 text-emerald-400 ring-1 ring-emerald-500/30"
                      : "bg-amber-500/15 text-amber-400 ring-1 ring-amber-500/30"
                  )}
                >
                  {h?.status ?? "—"}
                </Badge>
              )}
            </div>
          </div>

          {/* Description */}
          <p className="mb-7 max-w-2xl text-sm leading-relaxed text-muted-foreground">
            Automatically maps Kalshi prediction markets to live sportsbook lines, detects mispricings,
            and surfaces actionable arbitrage opportunities in real time.
            Uptime: <span className="text-foreground">{fmtUptime(h?.uptime_seconds)}</span>.
          </p>

          {/* CTAs */}
          <div className="mb-10 flex flex-wrap gap-2.5">
            <Button asChild size="default" className="gap-2">
              <NavLink to="/scanner">
                <BarChart3 className="size-4" aria-hidden />
                Open Scanner
              </NavLink>
            </Button>
            <Button
              variant="outline"
              size="default"
              className="gap-2"
              disabled={scanM.isPending}
              onClick={() => scanM.mutate()}
              aria-busy={scanM.isPending}
            >
              {scanM.isPending ? (
                <Loader2 className="size-4 animate-spin" aria-hidden />
              ) : (
                <Zap className="size-4" aria-hidden />
              )}
              Scan now
            </Button>
          </div>

          {/* Live stat strip */}
          {loading ? (
            <div className="flex gap-8">
              {[...Array(4)].map((_, i) => (
                <Skeleton key={i} className="h-10 w-20 rounded" />
              ))}
            </div>
          ) : (
            <div className="flex flex-wrap items-end gap-0 divide-x divide-border/40">
              <HeroStat
                label="Live opps"
                value={String(opps)}
                icon={TrendingUp}
                accent={opps > 0}
              />
              <HeroStat
                label="Mapped markets"
                value={String(d?.mapped_count ?? 0)}
                icon={BarChart3}
              />
              <HeroStat
                label="Total scans"
                value={String(d?.scan_count ?? 0)}
                icon={Activity}
              />
              <HeroStat
                label="Realized P&L"
                value={fmtMoney(pnl)}
                icon={Wallet}
                accent={pnl > 0}
                negative={pnl < 0}
                mono
              />
            </div>
          )}
        </div>
      </section>

      {/* ── Body ───────────────────────────────────────────────────────── */}
      <div className="mx-auto max-w-6xl space-y-5 px-4 py-6">
        {err ? (
          <Alert variant="destructive">
            <AlertDescription>{String((err as Error).message)}</AlertDescription>
          </Alert>
        ) : null}

        {/* Health + Status */}
        <div className="grid gap-3 lg:grid-cols-5">
          <Card className="lg:col-span-3">
            <CardHeader className="pb-2 pt-4">
              <CardTitle className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                System health
              </CardTitle>
            </CardHeader>
            <CardContent className="pb-4 pt-0">
              {loading ? (
                <div className="space-y-2">
                  {[...Array(5)].map((_, i) => (
                    <Skeleton key={i} className="h-8 w-full rounded" />
                  ))}
                </div>
              ) : (
                <div className="divide-y divide-border/50">
                  <HealthRow
                    label="Kalshi API"
                    ok={!!h?.kalshi?.connected}
                    detail={h?.kalshi?.configured ? "Connected" : "Add keys in .env"}
                  />
                  <HealthRow
                    label="Odds — primary"
                    ok={!!h?.odds_primary?.connected}
                    detail={h?.odds_primary?.configured ? "Key present" : "Not configured"}
                  />
                  <HealthRow
                    label="Odds — fallback"
                    ok={!!h?.odds_fallback?.connected}
                    detail={h?.odds_fallback?.configured ? "Key present" : "Optional"}
                  />
                  <HealthRow label="Database" ok={!!h?.database?.connected} detail="SQLite" />
                  <HealthRow
                    label="Scanner"
                    ok={!!h?.scanner?.scan_count && !h?.scanner?.last_error}
                    detail={
                      h?.scanner?.last_error
                        ? String(h.scanner.last_error).slice(0, 60)
                        : `${h?.scanner?.scan_count ?? 0} scans run`
                    }
                  />
                </div>
              )}
            </CardContent>
          </Card>

          <Card className="lg:col-span-2">
            <CardHeader className="pb-2 pt-4">
              <CardTitle className="flex items-center justify-between text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                <span>Scan status</span>
                {!loading && d?.active_odds_provider && (
                  <span className="font-mono text-[0.62rem] normal-case text-muted-foreground/70">
                    {d.active_odds_provider}
                  </span>
                )}
              </CardTitle>
            </CardHeader>
            <CardContent className="pb-4 pt-0">
              {loading ? (
                <Skeleton className="h-28 w-full rounded" />
              ) : (
                <>
                  <div className="divide-y divide-border/50">
                    <StatusRow label="Last scan" value={fmtTime(d?.last_scan_iso ?? undefined)} />
                    <StatusRow label="Poll interval" value={`${d?.poll_interval_seconds ?? "—"} s`} mono />
                    <StatusRow label="Open positions" value={String(d?.pnl?.open_count ?? 0)} mono />
                    <StatusRow label="Settled" value={String(d?.pnl?.settled_count ?? 0)} mono />
                  </div>
                  <div className="flex flex-wrap gap-1.5 pt-3">
                    <ConfigPill label="Kalshi" ok={d?.kalshi_configured} />
                    <ConfigPill label="Odds API" ok={d?.odds_configured} />
                    <ConfigPill label="Execution" ok={d?.execution_enabled} />
                  </div>
                  {d?.last_error && !String(d.last_error).includes("Waiting") ? (
                    <p className="mt-2 text-[0.65rem] leading-relaxed text-amber-500">
                      {String(d.last_error).slice(0, 120)}
                    </p>
                  ) : null}
                </>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Active sports */}
        {!loading && !!d?.sports?.length && (
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs text-muted-foreground">Active sports:</span>
            {d.sports.map((s) => (
              <Badge
                key={s}
                variant="secondary"
                className="font-mono text-[0.62rem] uppercase tracking-wide"
              >
                {s.replaceAll("_", " ")}
              </Badge>
            ))}
          </div>
        )}
      </div>
    </>
  )
}

// ── Sub-components ────────────────────────────────────────────────────────────

function HeroStat({
  label,
  value,
  icon: Icon,
  accent,
  negative,
  mono,
}: {
  label: string
  value: string
  icon: LucideIcon
  accent?: boolean
  negative?: boolean
  mono?: boolean
}) {
  return (
    <div className="flex flex-col px-6 py-1 first:pl-0 last:pr-0">
      <span className="mb-1 flex items-center gap-1.5 text-[0.65rem] font-medium uppercase tracking-wider text-muted-foreground">
        <Icon className="size-3" aria-hidden />
        {label}
      </span>
      <span
        className={cn(
          "text-2xl font-bold tabular-nums tracking-tight",
          mono && "font-mono text-xl",
          accent && "text-emerald-400",
          negative && "text-red-400"
        )}
      >
        {value}
      </span>
    </div>
  )
}

function HealthRow({ label, ok, detail }: { label: string; ok: boolean; detail: string }) {
  return (
    <div className="flex items-center justify-between gap-3 py-2 text-sm">
      <div className="flex min-w-0 items-center gap-2">
        <span
          className={cn("size-1.5 shrink-0 rounded-full", ok ? "bg-emerald-500" : "bg-amber-500")}
          aria-hidden
        />
        <span className="font-medium">{label}</span>
      </div>
      <span className="shrink-0 text-xs text-muted-foreground">{detail}</span>
    </div>
  )
}

function StatusRow({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="flex items-center justify-between gap-4 py-2 text-xs">
      <span className="text-muted-foreground">{label}</span>
      <span className={cn("font-medium tabular-nums", mono && "font-mono")}>{value}</span>
    </div>
  )
}

function ConfigPill({ label, ok }: { label: string; ok?: boolean }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[0.62rem] font-semibold uppercase tracking-wider ring-1",
        ok
          ? "bg-emerald-500/10 text-emerald-400 ring-emerald-500/30"
          : "bg-muted/60 text-muted-foreground ring-border"
      )}
    >
      <span className={cn("size-1 rounded-full", ok ? "bg-emerald-400" : "bg-muted-foreground/40")} />
      {label}
    </span>
  )
}
