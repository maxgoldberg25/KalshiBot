import { Flame, Radar, Trophy } from "lucide-react"
import type { ReactNode } from "react"
import { Reveal } from "@/components/fx/Reveal"

type Pillar = {
  kicker: string
  headline: string
  body: string
  icon: ReactNode
  tint: string
}

const PILLARS: Pillar[] = [
  {
    kicker: "Scope",
    headline: "30D",
    body: "Large Kalshi prints stay under watch for a full month, not just the last burst of tape activity.",
    icon: <Radar className="size-4" aria-hidden />,
    tint: "from-emerald-400/25 to-emerald-500/0",
  },
  {
    kicker: "Signal",
    headline: "Size",
    body: "Whale and major orders are grouped by market with direction, concentration, and share-of-open-interest context.",
    icon: <Flame className="size-4" aria-hidden />,
    tint: "from-amber-400/25 to-rose-500/0",
  },
  {
    kicker: "Goal",
    headline: "Lead",
    body: "Sports noise is filtered away so politics, economics, crypto, regulatory, and climate markets rise to the top.",
    icon: <Trophy className="size-4" aria-hidden />,
    tint: "from-sky-400/25 to-indigo-500/0",
  },
]

export const PillarTriad = () => (
  <section className="relative" aria-label="Why KalshiInsider lands">
    <div className="mx-auto max-w-6xl px-4 py-16 md:py-20">
      <div className="grid gap-4 md:grid-cols-3">
        {PILLARS.map((pillar, idx) => (
          <Reveal key={pillar.kicker} variant="up" delayMs={idx * 110}>
            <article className="group relative h-full overflow-hidden rounded-2xl border border-border/60 bg-card/50 p-6 backdrop-blur transition-all duration-500 hover:-translate-y-0.5 hover:border-primary/40">
              <div
                aria-hidden
                className={`pointer-events-none absolute inset-0 bg-gradient-to-br ${pillar.tint} opacity-0 transition-opacity duration-500 group-hover:opacity-100`}
              />
              <div className="relative flex items-center justify-between">
                <span className="font-display text-[0.62rem] font-semibold uppercase tracking-[0.32em] text-muted-foreground">
                  {pillar.kicker}
                </span>
                <span className="flex size-8 items-center justify-center rounded-lg bg-primary/10 text-primary ring-1 ring-primary/25">
                  {pillar.icon}
                </span>
              </div>
              <h3 className="relative mt-4 font-display text-5xl font-bold uppercase tracking-tight text-foreground md:text-6xl">
                {pillar.headline}
              </h3>
              <p className="relative mt-3 text-sm leading-relaxed text-muted-foreground">
                {pillar.body}
              </p>
            </article>
          </Reveal>
        ))}
      </div>
    </div>
  </section>
)
