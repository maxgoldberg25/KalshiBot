import { Check, X } from "lucide-react"
import { Reveal } from "@/components/fx/Reveal"
import { SectionEyebrow } from "./SectionEyebrow"

const PROS = [
  "One watch surface: large prints, market context, and execution links",
  "Month-long lookback catches slow-building insider flow",
  "Self-hosted, single-file SQLite — your keys, your machine",
  "Sports and parlay noise filtered before it reaches the feed",
]

const CONS = [
  "Raw tapes that only show the last few frantic hours",
  "Whale dashboards clogged with sports props and parlays",
  "Vibe-based alerts with no notional or open-interest context",
  "SaaS vaults holding your account keys on someone else's box",
]

export const WhyItLands = () => (
  <section className="relative">
    <div
      aria-hidden
      className="pointer-events-none absolute inset-x-0 top-0 -z-10 h-72 bg-gradient-to-b from-primary/5 via-transparent to-transparent"
    />
    <div className="mx-auto max-w-6xl px-4 py-24">
      <Reveal variant="up" className="mx-auto max-w-2xl text-center">
        <SectionEyebrow>Why it lands</SectionEyebrow>
        <h2 className="mt-4 text-balance font-display text-3xl font-bold uppercase tracking-tight md:text-5xl">
          Built like a <span className="text-gradient-emerald">surveillance terminal</span> for insider flow.
        </h2>
        <p className="mt-3 text-sm text-muted-foreground md:text-base">
          Not a broker clone. Not a dashboard maze. KalshiInsider turns prediction markets into a
          tape room with enough context to decide whether a large print is signal or noise.
        </p>
      </Reveal>

      <div className="mt-14 grid gap-5 md:grid-cols-2">
        <Reveal variant="left">
          <div className="relative h-full overflow-hidden rounded-2xl border border-primary/40 bg-card/60 p-7 shadow-2xl shadow-primary/10 backdrop-blur">
            <div
              aria-hidden
              className="pointer-events-none absolute -right-20 -top-20 size-56 rounded-full bg-primary/20 blur-3xl"
            />
            <div className="relative flex items-center gap-2">
              <span className="font-display text-[0.62rem] font-semibold uppercase tracking-[0.32em] text-emerald-300">
                KalshiInsider
              </span>
              <span className="h-px flex-1 bg-gradient-to-r from-emerald-400/50 to-transparent" />
            </div>
            <ul className="relative mt-5 space-y-3">
              {PROS.map((item) => (
                <li key={item} className="flex items-start gap-3 text-sm leading-relaxed">
                  <span className="mt-0.5 inline-flex size-5 shrink-0 items-center justify-center rounded-md bg-emerald-500/15 text-emerald-300 ring-1 ring-emerald-500/30">
                    <Check className="size-3" aria-hidden />
                  </span>
                  <span className="text-foreground/90">{item}</span>
                </li>
              ))}
            </ul>
          </div>
        </Reveal>

        <Reveal variant="right" delayMs={100}>
          <div className="relative h-full overflow-hidden rounded-2xl border border-border/60 bg-card/30 p-7 backdrop-blur">
            <div className="relative flex items-center gap-2">
              <span className="font-display text-[0.62rem] font-semibold uppercase tracking-[0.32em] text-muted-foreground">
                The rest of the pack
              </span>
              <span className="h-px flex-1 bg-gradient-to-r from-border to-transparent" />
            </div>
            <ul className="relative mt-5 space-y-3">
              {CONS.map((item) => (
                <li
                  key={item}
                  className="flex items-start gap-3 text-sm leading-relaxed text-muted-foreground"
                >
                  <span className="mt-0.5 inline-flex size-5 shrink-0 items-center justify-center rounded-md bg-muted/60 text-muted-foreground/80 ring-1 ring-border">
                    <X className="size-3" aria-hidden />
                  </span>
                  <span className="line-through decoration-muted-foreground/30">{item}</span>
                </li>
              ))}
            </ul>
          </div>
        </Reveal>
      </div>
    </div>
  </section>
)
