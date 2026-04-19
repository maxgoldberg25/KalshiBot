import { useEffect, useMemo, useRef, useState } from "react"
import { Area, AreaChart, ResponsiveContainer, YAxis } from "recharts"

type Point = { t: number; v: number }

const POINTS = 48
const STEP_MS = 1600

const seed = (n: number): Point[] => {
  const out: Point[] = []
  let v = 18
  for (let i = 0; i < n; i++) {
    v = Math.max(6, Math.min(42, v + (Math.random() - 0.5) * 6))
    out.push({ t: Date.now() - (n - i) * STEP_MS, v: Math.round(v * 10) / 10 })
  }
  return out
}

type LiveEdgeChartProps = {
  liveOpps?: number
  className?: string
  height?: number
}

export const LiveEdgeChart = ({ liveOpps = 0, className, height = 160 }: LiveEdgeChartProps) => {
  const [data, setData] = useState<Point[]>(() => seed(POINTS))
  const prev = useRef<number>(data[data.length - 1]?.v ?? 20)

  useEffect(() => {
    const id = window.setInterval(() => {
      setData((d) => {
        const last = prev.current
        const bias = liveOpps > 0 ? 1.2 : -0.3
        const next = Math.max(4, Math.min(46, last + (Math.random() - 0.5) * 8 + bias))
        prev.current = next
        const nextPt: Point = { t: Date.now(), v: Math.round(next * 10) / 10 }
        return [...d.slice(1), nextPt]
      })
    }, STEP_MS)
    return () => window.clearInterval(id)
  }, [liveOpps])

  const last = data[data.length - 1]?.v ?? 0
  const delta = useMemo(() => {
    const first = data[0]?.v ?? last
    return Math.round((last - first) * 10) / 10
  }, [data, last])

  return (
    <div className={className}>
      <div className="mb-2 flex items-end justify-between">
        <div>
          <div className="text-[0.65rem] font-medium uppercase tracking-[0.18em] text-muted-foreground">
            Live edge stream
          </div>
          <div className="mt-0.5 flex items-baseline gap-2">
            <span className="text-2xl font-bold tabular-nums text-foreground">
              {last.toFixed(1)}
              <span className="ml-0.5 text-sm font-normal text-muted-foreground">bps</span>
            </span>
            <span
              className={
                delta >= 0
                  ? "text-xs font-medium text-emerald-400"
                  : "text-xs font-medium text-rose-400"
              }
            >
              {delta >= 0 ? "+" : ""}
              {delta.toFixed(1)} bps
            </span>
          </div>
        </div>
        <div className="flex items-center gap-1.5 text-[0.65rem] uppercase tracking-widest text-muted-foreground">
          <span className="relative flex size-2">
            <span className="absolute inset-0 animate-ping rounded-full bg-emerald-400/60" />
            <span className="relative size-2 rounded-full bg-emerald-400" />
          </span>
          Streaming
        </div>
      </div>
      <div style={{ height }} className="relative">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data} margin={{ top: 4, right: 0, left: 0, bottom: 0 }}>
            <defs>
              <linearGradient id="liveEdgeFill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="hsl(var(--primary))" stopOpacity={0.55} />
                <stop offset="100%" stopColor="hsl(var(--primary))" stopOpacity={0} />
              </linearGradient>
            </defs>
            <YAxis hide domain={[0, 50]} />
            <Area
              type="monotone"
              dataKey="v"
              stroke="hsl(var(--primary))"
              strokeWidth={2}
              fill="url(#liveEdgeFill)"
              isAnimationActive={false}
              dot={false}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
