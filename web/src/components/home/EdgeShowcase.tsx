import { ArrowDownRight, ArrowUpRight, Sparkles, Zap } from "lucide-react"
import { Reveal } from "@/components/fx/Reveal"
import { useReveal } from "@/hooks/useReveal"
import { cn } from "@/lib/utils"
import { SectionEyebrow } from "./SectionEyebrow"

const ROWS = [
  {
    market: "Knicks ML vs Heat",
    side: "YES · 100",
    kalshi: 62,
    book: 68,
    edgeBps: 612,
  },
  {
    market: "Fed cuts in March",
    side: "YES · 250",
    kalshi: 41,
    book: 47,
    edgeBps: 593,
  },
  {
    market: "BTC > 110k by Friday",
    side: "NO · 150",
    kalshi: 38,
    book: 33,
    edgeBps: 503,
  },
]

const ProbBar = ({ value, color, delayMs }: { value: number; color: string; delayMs: number }) => {
  const { ref, visible } = useReveal<HTMLDivElement>({ threshold: 0.4 })
  return (
    <div
      ref={ref}
      className="relative h-1.5 overflow-hidden rounded-full bg-muted/50"
      aria-hidden
    >
      <div
        className={cn("absolute inset-y-0 left-0 origin-left rounded-full", color)}
        style={{
          width: `${value}%`,
          transform: visible ? "scaleX(1)" : "scaleX(0)",
          transition: `transform 1100ms cubic-bezier(0.22,1,0.36,1) ${delayMs}ms`,
        }}
      />
    </div>
  )
}

export const EdgeShowcase = () => (
  <section className="relative">
    <div className="mx-auto max-w-6xl px-4 py-24">
      <div className="grid items-start gap-10 lg:grid-cols-12">
        <Reveal variant="left" className="lg:col-span-5">
          <SectionEyebrow icon={<Sparkles className="size-3" aria-hidden />}>
            Live edge demo
          </SectionEyebrow>
          <h2 className="mt-4 text-balance text-3xl font-semibold tracking-tight md:text-4xl">
            See the gap. Take the gap.
          </h2>
          <p className="mt-3 text-sm leading-relaxed text-muted-foreground md:text-base">
            Each row is a real-style opportunity. The blue bar is the sportsbook implied
            probability, the green bar is Kalshi, and the chip is the Kelly-sized order ready to
            fire.
          </p>
          <ul className="mt-6 space-y-3 text-sm text-muted-foreground">
            <li className="flex items-start gap-3">
              <span className="mt-1 inline-flex size-5 items-center justify-center rounded-md bg-primary/15 text-primary ring-1 ring-primary/25">
                <Zap className="size-3" aria-hidden />
              </span>
              Sub-second refresh. Stale quotes are flagged, never executed.
            </li>
            <li className="flex items-start gap-3">
              <span className="mt-1 inline-flex size-5 items-center justify-center rounded-md bg-primary/15 text-primary ring-1 ring-primary/25">
                <ArrowUpRight className="size-3" aria-hidden />
              </span>
              Edge in basis points already nets out execution friction and slippage.
            </li>
            <li className="flex items-start gap-3">
              <span className="mt-1 inline-flex size-5 items-center justify-center rounded-md bg-primary/15 text-primary ring-1 ring-primary/25">
                <ArrowDownRight className="size-3" aria-hidden />
              </span>
              Position sizing follows fractional-Kelly with hard notional caps.
            </li>
          </ul>
        </Reveal>

        <Reveal variant="right" delayMs={120} className="lg:col-span-7">
          <div className="relative">
            <div
              aria-hidden
              className="absolute -inset-x-6 -top-12 -z-10 h-44 bg-aurora animate-aurora opacity-70 blur-3xl"
            />
            <div className="relative overflow-hidden rounded-2xl border border-border/60 bg-card/70 shadow-2xl shadow-primary/5 backdrop-blur">
              <div className="flex items-center justify-between border-b border-border/60 px-5 py-3">
                <div className="flex items-center gap-2">
                  <span className="size-2 animate-pulse-glow rounded-full bg-emerald-400" />
                  <span className="font-mono text-[0.65rem] uppercase tracking-widest text-muted-foreground">
                    scanner / live
                  </span>
                </div>
                <span className="font-mono text-[0.65rem] text-muted-foreground/70">
                  refreshed 1s ago
                </span>
              </div>

              <div className="grid grid-cols-12 gap-3 border-b border-border/40 px-5 py-2 text-[0.62rem] uppercase tracking-widest text-muted-foreground/70">
                <div className="col-span-5">Market</div>
                <div className="col-span-5">Kalshi vs Book</div>
                <div className="col-span-2 text-right">Edge</div>
              </div>

              <ul className="divide-y divide-border/40">
                {ROWS.map((r, idx) => (
                  <li
                    key={r.market}
                    className="grid grid-cols-12 items-center gap-3 px-5 py-4 transition-colors hover:bg-accent/40"
                  >
                    <div className="col-span-5 min-w-0">
                      <div className="truncate text-sm font-semibold">{r.market}</div>
                      <div className="mt-0.5 font-mono text-[0.65rem] uppercase tracking-wider text-muted-foreground">
                        {r.side}
                      </div>
                    </div>
                    <div className="col-span-5 space-y-2">
                      <div className="flex items-center gap-2">
                        <span className="w-12 shrink-0 font-mono text-[0.65rem] text-emerald-400">
                          K {r.kalshi}¢
                        </span>
                        <ProbBar
                          value={r.kalshi}
                          color="bg-emerald-400/80"
                          delayMs={idx * 120}
                        />
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="w-12 shrink-0 font-mono text-[0.65rem] text-sky-400">
                          B {r.book}¢
                        </span>
                        <ProbBar
                          value={r.book}
                          color="bg-sky-400/80"
                          delayMs={idx * 120 + 120}
                        />
                      </div>
                    </div>
                    <div className="col-span-2 text-right">
                      <span className="inline-flex items-center gap-1 rounded-full bg-emerald-500/15 px-2 py-0.5 font-mono text-[0.7rem] font-semibold text-emerald-300 ring-1 ring-emerald-500/30">
                        <ArrowUpRight className="size-3" aria-hidden />
                        {r.edgeBps} bps
                      </span>
                    </div>
                  </li>
                ))}
              </ul>

              <div className="flex items-center justify-between border-t border-border/60 bg-card/40 px-5 py-3 text-[0.7rem] text-muted-foreground">
                <span>3 active opportunities · auto-refresh 30s</span>
                <span className="font-mono text-emerald-400">+$1,284 expected EV</span>
              </div>
            </div>
          </div>
        </Reveal>
      </div>
    </div>
  </section>
)
