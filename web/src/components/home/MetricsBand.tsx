import { RevealStat } from "@/components/fx/RevealStat"
import { Reveal } from "@/components/fx/Reveal"
import { SectionEyebrow } from "./SectionEyebrow"

type Metric = {
  label: string
  value: number
  prefix?: string
  suffix?: string
  decimals?: number
}

const METRICS: Metric[] = [
  { label: "Tape lookback", value: 30, suffix: " days" },
  { label: "Large-trade floor", value: 2.5, prefix: "$", suffix: "K", decimals: 1 },
  { label: "Whale threshold", value: 50, prefix: "$", suffix: "K" },
  { label: "Notional under watch", value: 12.6, prefix: "$", suffix: "M", decimals: 1 },
]

export const MetricsBand = () => (
  <section className="relative">
    <div
      aria-hidden
      className="absolute inset-0 -z-10 bg-aurora animate-aurora opacity-50"
    />
    <div
      aria-hidden
      className="absolute inset-0 -z-10 bg-noise opacity-[0.04]"
    />

    <div className="mx-auto max-w-6xl px-4 py-24">
      <Reveal variant="up" className="mx-auto max-w-2xl text-center">
        <SectionEyebrow>The month-long tape</SectionEyebrow>
        <h2 className="mt-4 text-balance font-display text-3xl font-bold uppercase tracking-tight md:text-5xl">
          Built for <span className="text-gradient-emerald">big prints</span>, tuned for signal.
        </h2>
      </Reveal>

      <div className="mt-12 grid grid-cols-2 gap-4 md:grid-cols-4">
        {METRICS.map((m, idx) => (
          <Reveal key={m.label} variant="scale" delayMs={idx * 90}>
            <div className="group relative h-full overflow-hidden rounded-2xl border border-border/60 bg-card/60 p-6 text-center backdrop-blur transition-all duration-500 hover:border-primary/40">
              <div
                aria-hidden
                className="pointer-events-none absolute inset-0 bg-gradient-to-b from-primary/5 to-transparent opacity-0 transition-opacity duration-500 group-hover:opacity-100"
              />
              <div className="font-display text-3xl font-bold tracking-tight tabular-nums md:text-5xl">
                <RevealStat
                  value={m.value}
                  prefix={m.prefix}
                  suffix={m.suffix}
                  decimals={m.decimals ?? 0}
                  className="text-gradient-emerald"
                />
              </div>
              <div className="mt-2 font-display text-[0.7rem] font-medium uppercase tracking-[0.28em] text-muted-foreground">
                {m.label}
              </div>
            </div>
          </Reveal>
        ))}
      </div>
    </div>
  </section>
)
