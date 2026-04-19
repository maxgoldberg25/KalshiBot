import { ChevronDown } from "lucide-react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"
import { fetchHealth, fetchState, postScan } from "@/api/fetch"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { HeroStage } from "@/components/fx/HeroStage"
import { ScrollProgress } from "@/components/fx/ScrollProgress"
import { CtaBand } from "@/components/home/CtaBand"
import { EdgeShowcase } from "@/components/home/EdgeShowcase"
import { FeatureGrid } from "@/components/home/FeatureGrid"
import { HowItWorks } from "@/components/home/HowItWorks"
import { LeagueMarquee } from "@/components/home/LeagueMarquee"
import { MetricsBand } from "@/components/home/MetricsBand"
import { ScanTimeline } from "@/components/home/ScanTimeline"
import { useAuth } from "@/context/AuthContext"
import { fmtTime, fmtUptime } from "@/lib/format"
import { cn } from "@/lib/utils"

export function HomePage() {
  const qc = useQueryClient()
  const { status: authStatus } = useAuth()
  const isAuthed = authStatus === "authed"

  const stateQ = useQuery({
    queryKey: ["state"],
    queryFn: fetchState,
    refetchInterval: 30_000,
    enabled: isAuthed,
  })
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
  const loading = (isAuthed && stateQ.isPending) || healthQ.isPending
  const err = (isAuthed ? stateQ.error : null) ?? healthQ.error

  const healthy = h?.status === "healthy"
  const opps = d?.opportunities?.length ?? 0
  const pnl = d?.pnl?.total_realized_pnl ?? 0

  return (
    <div className="relative isolate">
      <ScrollProgress />

      {/* Ambient page-wide background */}
      <div aria-hidden className="pointer-events-none fixed inset-0 -z-10 overflow-hidden">
        <div className="absolute inset-0 bg-aurora animate-aurora opacity-60" />
        <div className="absolute inset-0 bg-noise opacity-[0.03]" />
        <div className="absolute inset-x-0 bottom-0 h-96 bg-gradient-to-t from-background via-background/80 to-transparent" />
      </div>

      <div className="relative">
        <HeroStage
          status={h?.status ?? undefined}
          healthy={healthy}
          uptimeLabel={fmtUptime(h?.uptime_seconds)}
          isScanning={!!d?.is_scanning}
          metrics={{
            liveOpps: opps,
            mappedMarkets: d?.mapped_count ?? 0,
            totalScans: d?.scan_count ?? 0,
            realizedPnl: pnl,
          }}
          onScan={isAuthed ? () => scanM.mutate() : undefined}
          scanning={scanM.isPending}
        />

        {/* Scroll hint */}
        <div className="pointer-events-none -mt-2 flex flex-col items-center gap-1 text-muted-foreground">
          <span className="font-mono text-[0.6rem] uppercase tracking-[0.3em]">scroll</span>
          <ChevronDown className="size-4 animate-scroll-hint" aria-hidden />
        </div>
      </div>

      <div className="relative z-10 mx-auto max-w-6xl space-y-5 px-4 py-6">
        {err ? (
          <Alert variant="destructive">
            <AlertDescription>{String((err as Error).message)}</AlertDescription>
          </Alert>
        ) : null}

        {!isAuthed && (
          <Alert>
            <AlertDescription>
              Sign in to unlock the live scanner, insider watch, and execution tools.
            </AlertDescription>
          </Alert>
        )}

        {/* Health + Status */}
        <div className="grid min-w-0 gap-3 lg:grid-cols-5">
          <Card className="min-w-0 lg:col-span-3">
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

          <Card className={cn("min-w-0 lg:col-span-2", !isAuthed && "opacity-60")}>
            <CardHeader className="space-y-0 pb-2 pt-4">
              <CardTitle className="flex flex-wrap items-baseline justify-between gap-x-2 gap-y-1 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                <span className="shrink-0">Scan status</span>
                {!loading && d?.active_odds_provider ? (
                  <span
                    className="min-w-0 max-w-full break-words text-end font-mono text-[0.62rem] font-medium normal-case leading-snug text-muted-foreground/70 sm:max-w-[65%]"
                    title={d.active_odds_provider}
                  >
                    {d.active_odds_provider}
                  </span>
                ) : null}
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
        {isAuthed && !loading && !!d?.sports?.length && (
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

      <LeagueMarquee />

      <HowItWorks />
      <EdgeShowcase />
      <MetricsBand />
      <FeatureGrid />
      <ScanTimeline />

      <CtaBand />
    </div>
  )
}

// ── Sub-components ────────────────────────────────────────────────────────────

function HealthRow({ label, ok, detail }: { label: string; ok: boolean; detail: string }) {
  return (
    <div className="flex items-start justify-between gap-3 py-2 text-sm">
      <div className="flex min-w-0 items-center gap-2">
        <span
          className={cn("size-1.5 shrink-0 rounded-full", ok ? "bg-emerald-500" : "bg-amber-500")}
          aria-hidden
        />
        <span className="font-medium leading-snug">{label}</span>
      </div>
      <span className="max-w-[55%] shrink-0 break-words text-right text-xs leading-snug text-muted-foreground">
        {detail}
      </span>
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
