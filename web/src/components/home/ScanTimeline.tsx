import { CheckCircle2, Cpu, Database, Radar, Send, Shuffle } from "lucide-react"
import { Reveal } from "@/components/fx/Reveal"
import { SectionEyebrow } from "./SectionEyebrow"

const STAGES = [
  {
    icon: Radar,
    time: "t = 0 ms",
    title: "Pull month tape",
    body: "Public Kalshi trades are requested from the last 30 days.",
  },
  {
    icon: Shuffle,
    time: "t = 80 ms",
    title: "Drop noise",
    body: "Sports, synthetic parlays, stale markets, and broken links are filtered out.",
  },
  {
    icon: Cpu,
    time: "t = 140 ms",
    title: "Score conviction",
    body: "Large trades are scored by size, imbalance, open-interest share, and concentration.",
  },
  {
    icon: Database,
    time: "t = 220 ms",
    title: "Aggregate markets",
    body: "Multiple prints roll up into one card with total notional and side balance.",
  },
  {
    icon: Send,
    time: "t = 300 ms",
    title: "Surface leads",
    body: "Insider watch refreshes with the highest-conviction markets first.",
  },
  {
    icon: CheckCircle2,
    time: "t = 320 ms",
    title: "Open Kalshi",
    body: "YES and NO buttons take you straight to the live market.",
  },
] as const

export const ScanTimeline = () => (
  <section className="relative">
    <div className="mx-auto max-w-5xl px-4 py-24">
      <Reveal variant="up" className="mx-auto max-w-2xl text-center">
        <SectionEyebrow>One tape cycle</SectionEyebrow>
        <h2 className="mt-4 text-balance font-display text-3xl font-bold uppercase tracking-tight md:text-5xl">
          From month of tape to <span className="text-gradient-emerald">ranked insider leads.</span>
        </h2>
        <p className="mt-3 text-sm text-muted-foreground md:text-base">
          A look at what runs every refresh so the feed stays focused on actionable large trades.
        </p>
      </Reveal>

      <ol className="relative mt-14 ml-4 border-l border-border/60 md:ml-6">
        {STAGES.map((stage, idx) => {
          const Icon = stage.icon
          return (
            <Reveal
              key={stage.title}
              as="li"
              variant="left"
              delayMs={idx * 90}
              className="relative pb-10 pl-8 md:pl-10 last:pb-0"
            >
              <span
                aria-hidden
                className="absolute -left-[13px] top-0 flex size-6 items-center justify-center rounded-full border border-primary/40 bg-card ring-4 ring-background"
              >
                <span className="size-2 animate-pulse-glow rounded-full bg-primary" />
              </span>
              <div className="flex flex-col gap-1.5 sm:flex-row sm:items-center sm:gap-4">
                <span className="font-mono text-[0.65rem] uppercase tracking-[0.28em] text-muted-foreground">
                  {stage.time}
                </span>
                <h3 className="flex items-center gap-2 font-display text-base font-semibold uppercase tracking-tight">
                  <Icon className="size-4 text-primary" aria-hidden />
                  {stage.title}
                </h3>
              </div>
              <p className="mt-1.5 text-sm leading-relaxed text-muted-foreground">{stage.body}</p>
            </Reveal>
          )
        })}
      </ol>
    </div>
  </section>
)
