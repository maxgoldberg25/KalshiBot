import { useEffect, useId, useMemo, useRef, useState, type ReactNode } from "react"
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"
import type { DashboardState } from "@/api/types"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { fmtTime } from "@/lib/format"
import { cn } from "@/lib/utils"

const SCAN_HIST_MAX = 72

type ScanPoint = { label: string; opps: number }

const TOOLTIP_STYLE = {
  background: "hsl(var(--card))",
  border: "1px solid hsl(var(--border))",
  borderRadius: "6px",
  fontSize: "11px",
  color: "hsl(var(--foreground))",
  boxShadow: "0 4px 12px rgba(0,0,0,0.4)",
} as const

const AXIS_PROPS = {
  tick: { fontSize: 9, fill: "hsl(var(--muted-foreground))" },
  tickLine: false,
  axisLine: false,
} as const

export type ScanAnalyticsChartsProps = {
  state: DashboardState | undefined
  loading: boolean
  className?: string
}

export const ScanAnalyticsCharts = ({ state, loading, className }: ScanAnalyticsChartsProps) => {
  const oppsGradId = useId().replace(/:/g, "")
  const [scanHist, setScanHist] = useState<ScanPoint[]>([])
  const prevScan = useRef(-1)

  useEffect(() => {
    const d = state
    if (!d) return
    const sc = d.scan_count ?? 0
    if (sc <= 0 || sc === prevScan.current) return
    prevScan.current = sc
    const pt: ScanPoint = {
      label: fmtTime(d.last_scan_iso ?? undefined),
      opps: d.opportunities?.length ?? 0,
    }
    setScanHist((h) => [...h, pt].slice(-SCAN_HIST_MAX))
  }, [state])

  const edgeBuckets = useMemo(() => {
    const opps = state?.opportunities ?? []
    const b = [0, 0, 0, 0, 0]
    for (const o of opps) {
      const e = Number(o.edge_cents) || 0
      if (e < 1) b[0]++
      else if (e < 2) b[1]++
      else if (e < 3) b[2]++
      else if (e < 5) b[3]++
      else b[4]++
    }
    return [
      { name: "0–1¢", v: b[0] },
      { name: "1–2¢", v: b[1] },
      { name: "2–3¢", v: b[2] },
      { name: "3–5¢", v: b[3] },
      { name: "5¢+", v: b[4] },
    ]
  }, [state?.opportunities])

  return (
    <div className={cn("grid gap-4 lg:grid-cols-2", className)}>
      <ChartCard title="Opportunities per scan">
        {loading ? (
          <Skeleton className="h-[150px] w-full rounded-md" />
        ) : scanHist.length < 2 ? (
          <EmptyChart />
        ) : (
          <ResponsiveContainer width="100%" height={150}>
            <AreaChart data={scanHist} margin={{ left: -12, right: 4, top: 6, bottom: 0 }}>
              <defs>
                <linearGradient id={oppsGradId} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="hsl(var(--primary))" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="hsl(var(--primary))" stopOpacity={0.02} />
                </linearGradient>
              </defs>
              <XAxis dataKey="label" {...AXIS_PROPS} />
              <YAxis {...AXIS_PROPS} allowDecimals={false} width={26} />
              <Tooltip contentStyle={TOOLTIP_STYLE} cursor={{ stroke: "hsl(var(--border))" }} />
              <Area
                type="monotone"
                dataKey="opps"
                name="Opportunities"
                stroke="hsl(var(--primary))"
                strokeWidth={1.5}
                fill={`url(#${oppsGradId})`}
                dot={false}
                activeDot={{ r: 3, fill: "hsl(var(--primary))" }}
              />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </ChartCard>

      <ChartCard title="Edge spread (¢)">
        {loading ? (
          <Skeleton className="h-[150px] w-full rounded-md" />
        ) : !state?.opportunities?.length ? (
          <EmptyChart />
        ) : (
          <ResponsiveContainer width="100%" height={150}>
            <BarChart data={edgeBuckets} margin={{ left: -12, right: 4, top: 6, bottom: 0 }}>
              <XAxis dataKey="name" {...AXIS_PROPS} />
              <YAxis {...AXIS_PROPS} allowDecimals={false} width={26} />
              <Tooltip
                contentStyle={TOOLTIP_STYLE}
                cursor={{ fill: "hsl(var(--accent))", opacity: 0.6 }}
              />
              <Bar
                dataKey="v"
                name="Count"
                fill="hsl(var(--primary))"
                fillOpacity={0.8}
                radius={[3, 3, 0, 0]}
              />
            </BarChart>
          </ResponsiveContainer>
        )}
      </ChartCard>
    </div>
  )
}

function ChartCard({ title, children }: { title: string; children: ReactNode }) {
  return (
    <Card>
      <CardHeader className="pb-1 pt-4">
        <CardTitle className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          {title}
        </CardTitle>
      </CardHeader>
      <CardContent className="pb-3 pt-1">{children}</CardContent>
    </Card>
  )
}

function EmptyChart() {
  return (
    <div className="flex h-[150px] items-center justify-center text-xs text-muted-foreground/60">
      No data yet
    </div>
  )
}
