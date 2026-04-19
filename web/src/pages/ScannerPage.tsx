import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useMemo, useState } from "react"
import { ChevronDown, ChevronUp, ChevronsUpDown, ExternalLink, Loader2, RefreshCw, Zap } from "lucide-react"
import { toast } from "sonner"
import { fetchState, postScan } from "@/api/fetch"
import type { OpportunityRow } from "@/api/types"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
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
import { fmtMoney, fmtTime } from "@/lib/format"
import { cn } from "@/lib/utils"
import { NavLink } from "react-router-dom"
import { ScanAnalyticsCharts } from "@/components/scan/ScanAnalyticsCharts"

function aggregateOpps(opps: OpportunityRow[]) {
  const n = opps.length
  if (!n) return { meanEdge: 0, maxEdge: 0, meanBps: 0, est: 0 }
  let sum = 0
  let sumB = 0
  let maxE = 0
  let est = 0
  for (const o of opps) {
    const ec = Number(o.edge_cents) || 0
    let eb = Number(o.edge_bps)
    if (Number.isNaN(eb)) eb = ec * 100
    sum += ec
    sumB += eb
    maxE = Math.max(maxE, ec)
    if (o.is_estimated) est += 1
  }
  return { meanEdge: sum / n, maxEdge: maxE, meanBps: sumB / n, est }
}

export function ScannerPage() {
  const qc = useQueryClient()
  const stateQ = useQuery({
    queryKey: ["state"],
    queryFn: fetchState,
    refetchInterval: 15_000,
  })
  const [sortCol, setSortCol] = useState<"edge" | "game" | "conf">("edge")
  const [sortAsc, setSortAsc] = useState(false)

  const d = stateQ.data
  const loading = stateQ.isPending

  const scanM = useMutation({
    mutationFn: postScan,
    onSuccess: (j) => {
      if (j.ok) toast.success(`Scan complete — ${j.alerts ?? 0} alerts`)
      else toast.error(j.error ?? "Scan failed")
      void qc.invalidateQueries({ queryKey: ["state"] })
    },
    onError: (e: Error) => toast.error(e.message),
  })

  const oppsSorted = useMemo(() => {
    // Deduplicate: same game + action + edge = same opportunity from multiple books
    const seen = new Set<string>()
    const unique = (d?.opportunities ?? []).filter((o) => {
      const key = `${o.game_label}|${o.kalshi_action}|${o.hedge_action}|${o.edge_cents}`
      if (seen.has(key)) return false
      seen.add(key)
      return true
    })
    const dir = sortAsc ? 1 : -1
    unique.sort((a, b) => {
      if (sortCol === "game")
        return dir * String(a.game_label ?? "").localeCompare(String(b.game_label ?? ""))
      if (sortCol === "conf") {
        const rank = (c: string | undefined) =>
          c === "high" ? 3 : c === "med" || c === "medium" ? 2 : 1
        return dir * (rank(a.confidence) - rank(b.confidence))
      }
      return dir * ((Number(a.edge_cents) || 0) - (Number(b.edge_cents) || 0))
    })
    return unique
  }, [d?.opportunities, sortCol, sortAsc])

  const agg = aggregateOpps(d?.opportunities ?? [])
  const hasErr = d?.last_error && !String(d.last_error).includes("Waiting")

  function handleSort(col: typeof sortCol) {
    if (sortCol === col) setSortAsc((a) => !a)
    else {
      setSortCol(col)
      setSortAsc(col === "game")
    }
  }

  return (
    <div className="mx-auto max-w-7xl space-y-5 px-4 py-6">
      {/* ── Header ─────────────────────────────────────── */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-baseline gap-3">
          <h1 className="text-xl font-bold tracking-tight">Scanner</h1>
          <NavLink
            to="/"
            className="text-xs text-muted-foreground underline-offset-4 hover:text-foreground hover:underline"
          >
            Home
          </NavLink>
        </div>
        <div className="flex gap-2">
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => void stateQ.refetch()}
          >
            <RefreshCw className="size-3.5" aria-hidden />
            Refresh
          </Button>
          <Button
            type="button"
            size="sm"
            disabled={scanM.isPending}
            onClick={() => scanM.mutate()}
          >
            {scanM.isPending ? (
              <Loader2 className="size-3.5 animate-spin" aria-hidden />
            ) : (
              <Zap className="size-3.5" aria-hidden />
            )}
            Scan now
          </Button>
        </div>
      </div>

      {hasErr ? (
        <Alert variant="destructive">
          <AlertDescription>{String(d?.last_error)}</AlertDescription>
        </Alert>
      ) : null}

      {/* ── Overview card ──────────────────────────────── */}
      <Card>
        <CardContent className="pt-5 pb-5">
          {loading ? (
            <Skeleton className="h-24 w-full rounded" />
          ) : (
            <>
              {/* Headline numbers */}
              <div className="grid grid-cols-2 gap-5 sm:grid-cols-5">
                <StatCell label="Last scan"      value={fmtTime(d?.last_scan_iso ?? undefined)} />
                <StatCell label="Opportunities"  value={String(oppsSorted.length)} highlight={oppsSorted.length > 0} />
                <StatCell label="Mean edge"      value={`${agg.meanEdge.toFixed(1)}¢`} mono />
                <StatCell label="~EST rows"      value={String(agg.est)} />
                <StatCell
                  label="Status"
                  value={d?.is_scanning ? "Scanning" : "Idle"}
                  live={d?.is_scanning}
                />
              </div>

              {/* Secondary metadata */}
              <div className="mt-4 grid gap-x-8 gap-y-0 border-t border-border/50 pt-4 text-xs sm:grid-cols-3">
                <MetaRow label="Mapped"   value={String(d?.mapped_count ?? 0)} mono />
                <MetaRow label="Credits"  value={d?.odds_requests_remaining != null ? String(d.odds_requests_remaining) : "—"} mono />
                <MetaRow label="Provider" value={d?.active_odds_provider || "—"} mono />
                <MetaRow label="Poll"     value={`${d?.poll_interval_seconds ?? "—"}s`} mono />
                <MetaRow
                  label="Positions"
                  value={`${d?.pnl?.open_count ?? 0} open · ${d?.pnl?.settled_count ?? 0} settled`}
                />
                <MetaRow label="P&L"     value={fmtMoney(d?.pnl?.total_realized_pnl)} mono />
              </div>
            </>
          )}
        </CardContent>
      </Card>

      {/* ── Charts ──────────────────────────────────────── */}
      <ScanAnalyticsCharts state={d} loading={loading} />

      {/* ── Opportunities table ─────────────────────────── */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between pb-2 pt-4">
          <CardTitle className="text-sm font-semibold">Opportunities</CardTitle>
          {!loading && oppsSorted.length > 0 && (
            <Badge variant="secondary" className="font-mono text-xs">
              {oppsSorted.length}
            </Badge>
          )}
        </CardHeader>
        <CardContent className="p-0 pb-1">
          <ScrollArea className="h-[min(520px,58vh)] w-full">
            <Table aria-label="Scanner opportunities">
              <TableHeader className="sticky top-0 z-10 bg-card">
                <TableRow className="border-b border-border/60 hover:bg-transparent">
                  <SortHead label="Game"  col="game" sortCol={sortCol} sortAsc={sortAsc} onSort={handleSort} />
                  <SortHead label="Edge"  col="edge" sortCol={sortCol} sortAsc={sortAsc} onSort={handleSort} />
                  <TableHead className="text-xs">Kalshi</TableHead>
                  <TableHead className="text-xs">Hedge</TableHead>
                  <TableHead className="text-center text-xs">Books</TableHead>
                  <SortHead label="Conf"  col="conf" sortCol={sortCol} sortAsc={sortAsc} onSort={handleSort} />
                  <TableHead className="text-right text-xs">Liq</TableHead>
                  <TableHead className="text-right text-xs">Kelly</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {loading ? (
                  <TableRow>
                    <TableCell colSpan={8}>
                      <div className="space-y-2 py-2">
                        {[...Array(4)].map((_, i) => (
                          <Skeleton key={i} className="h-8 w-full rounded" />
                        ))}
                      </div>
                    </TableCell>
                  </TableRow>
                ) : oppsSorted.length ? (
                  oppsSorted.map((o, i) => <OppRow key={`${o.kalshi_ticker ?? i}-${i}`} o={o} />)
                ) : (
                  <TableRow>
                    <TableCell colSpan={8} className="py-10 text-center text-sm text-muted-foreground">
                      No opportunities — configure APIs and mappings, then run a scan.
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </ScrollArea>
        </CardContent>
      </Card>
    </div>
  )
}

// ── Row component ─────────────────────────────────────────────────────────────

function kalshiHref(o: OpportunityRow): string | null {
  if (o.kalshi_url) return o.kalshi_url
  if (o.kalshi_ticker) return `https://kalshi.com/markets/${o.kalshi_ticker}`
  return null
}

function OppRow({ o }: { o: OpportunityRow }) {
  const conf = (o.confidence ?? "").toLowerCase()
  const edgeCents = Number(o.edge_cents) || 0
  const href = kalshiHref(o)

  const confBorder =
    conf === "high" ? "border-l-emerald-500/55" :
    conf === "med" || conf === "medium" ? "border-l-amber-500/55" :
    "border-l-transparent"

  const edgeClass =
    edgeCents >= 3 ? "text-emerald-400" :
    edgeCents >= 1 ? "text-foreground" :
    "text-muted-foreground"

  return (
    <TableRow
      className={cn(
        "border-l-2 transition-colors hover:bg-muted/20",
        confBorder,
        o.is_estimated && "opacity-70"
      )}
    >
      <TableCell>
        <div className="flex flex-wrap items-center gap-1">
          {o.is_estimated && (
            <Badge
              variant="outline"
              className="h-4 border-amber-500/40 px-1 font-mono text-[0.58rem] text-amber-500"
            >
              ~EST
            </Badge>
          )}
          {o.odds_source && (
            <Badge
              variant="secondary"
              className="h-4 px-1 font-mono text-[0.58rem] uppercase"
            >
              {o.odds_source}
            </Badge>
          )}
          {href ? (
            <a
              href={href}
              target="_blank"
              rel="noopener noreferrer"
              className="group inline-flex items-center gap-0.5 font-mono text-xs text-foreground underline-offset-4 hover:text-primary hover:underline"
              aria-label={`Open ${o.game_label ?? "market"} on Kalshi`}
            >
              {trunc(o.game_label, 32)}
              <ExternalLink className="size-2.5 opacity-40" aria-hidden />
            </a>
          ) : (
            <span className="font-mono text-xs">{trunc(o.game_label, 32)}</span>
          )}
        </div>
      </TableCell>
      <TableCell className={cn("font-mono text-sm font-semibold tabular-nums", edgeClass)}>
        {edgeCents.toFixed(1)}¢
      </TableCell>
      <TableCell className="max-w-[190px] truncate text-xs" title={o.kalshi_action}>
        {o.kalshi_action}
      </TableCell>
      <TableCell
        className="max-w-[170px] truncate text-xs text-muted-foreground"
        title={o.hedge_action}
      >
        {o.hedge_action}
      </TableCell>
      <TableCell className="text-center text-xs text-muted-foreground">
        {o.book_count ?? "—"}
      </TableCell>
      <TableCell>
        <ConfDot conf={conf} />
      </TableCell>
      <TableCell className="text-right font-mono text-xs text-muted-foreground">
        {o.kalshi_liquidity ?? "—"}
      </TableCell>
      <TableCell className="text-right font-mono text-xs text-muted-foreground">
        {o.kelly_shares ?? "—"}
      </TableCell>
    </TableRow>
  )
}

function ConfDot({ conf }: { conf: string }) {
  const map: Record<string, { dot: string; label: string }> = {
    high:   { dot: "bg-emerald-500", label: "HIGH" },
    med:    { dot: "bg-amber-400",   label: "MED" },
    medium: { dot: "bg-amber-400",   label: "MED" },
  }
  const entry = map[conf] ?? { dot: "bg-muted-foreground/40", label: conf.toUpperCase() || "—" }
  return (
    <div className="flex items-center gap-1.5">
      <span className={cn("size-1.5 rounded-full", entry.dot)} aria-hidden />
      <span className="text-[0.65rem] font-medium text-muted-foreground">{entry.label}</span>
    </div>
  )
}

// ── Helper sub-components ─────────────────────────────────────────────────────

function StatCell({
  label,
  value,
  mono,
  highlight,
  live,
}: {
  label: string
  value: string
  mono?: boolean
  highlight?: boolean
  live?: boolean
}) {
  return (
    <div>
      <p className="text-[0.65rem] font-medium uppercase tracking-wider text-muted-foreground">
        {label}
      </p>
      <div className="mt-0.5 flex items-center gap-1.5">
        {live && (
          <span className="size-1.5 animate-pulse rounded-full bg-emerald-400" aria-hidden />
        )}
        <p
          className={cn(
            "text-lg font-bold tabular-nums tracking-tight",
            mono && "font-mono text-base",
            highlight && "text-emerald-400"
          )}
        >
          {value}
        </p>
      </div>
    </div>
  )
}

function MetaRow({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="flex items-center justify-between gap-4 py-1.5">
      <span className="text-muted-foreground">{label}</span>
      <span className={cn("font-medium tabular-nums", mono && "font-mono text-[0.78rem]")}>
        {value}
      </span>
    </div>
  )
}

function SortHead({
  label,
  col,
  sortCol,
  sortAsc,
  onSort,
}: {
  label: string
  col: "edge" | "game" | "conf"
  sortCol: "edge" | "game" | "conf"
  sortAsc: boolean
  onSort: (col: "edge" | "game" | "conf") => void
}) {
  const active = sortCol === col
  return (
    <TableHead
      className="cursor-pointer select-none"
      onClick={() => onSort(col)}
      aria-sort={active ? (sortAsc ? "ascending" : "descending") : undefined}
    >
      <div className="flex items-center gap-0.5 text-xs">
        <span className={cn(active && "text-foreground")}>{label}</span>
        {active ? (
          sortAsc ? (
            <ChevronUp className="size-3" aria-hidden />
          ) : (
            <ChevronDown className="size-3" aria-hidden />
          )
        ) : (
          <ChevronsUpDown className="size-3 opacity-30" aria-hidden />
        )}
      </div>
    </TableHead>
  )
}

function trunc(s: string | undefined, n: number) {
  if (!s) return ""
  return s.length <= n ? s : `${s.slice(0, n - 1)}…`
}
