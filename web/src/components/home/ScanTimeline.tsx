import { CheckCircle2, Cpu, Database, Radar, Send, Shuffle } from "lucide-react"
import { Reveal } from "@/components/fx/Reveal"
import { SectionEyebrow } from "./SectionEyebrow"

const STAGES = [
  {
    icon: Radar,
    time: "t = 0 ms",
    title: "Pull tape",
    body: "Public Kalshi tape + sportsbook quotes ingested in parallel.",
  },
  {
    icon: Shuffle,
    time: "t = 80 ms",
    title: "Auto-map",
    body: "Fuzzy matcher links contracts to bookmaker selections by score.",
  },
  {
    icon: Cpu,
    time: "t = 140 ms",
    title: "Price the edge",
    body: "Convert to true probabilities, net out friction, compute bps.",
  },
  {
    icon: Database,
    time: "t = 220 ms",
    title: "Persist",
    body: "Alerts upserted with dedupe; sessions and positions stored locally.",
  },
  {
    icon: Send,
    time: "t = 300 ms",
    title: "Notify",
    body: "Insider watch + scanner views update; toast pings on new opps.",
  },
  {
    icon: CheckCircle2,
    time: "t = 320 ms",
    title: "Ready to execute",
    body: "Kelly-sized order suggested. One click sends; dry-run by default.",
  },
] as const

export const ScanTimeline = () => (
  <section className="relative">
    <div className="mx-auto max-w-5xl px-4 py-24">
      <Reveal variant="up" className="mx-auto max-w-2xl text-center">
        <SectionEyebrow>Inside one scan cycle</SectionEyebrow>
        <h2 className="mt-4 text-balance text-3xl font-semibold tracking-tight md:text-4xl">
          From quote to ticket in under a third of a second.
        </h2>
        <p className="mt-3 text-sm text-muted-foreground md:text-base">
          A look at what runs every 30 seconds (and what you don't have to think about).
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
                <span className="font-mono text-[0.65rem] uppercase tracking-widest text-muted-foreground">
                  {stage.time}
                </span>
                <h3 className="flex items-center gap-2 text-base font-semibold tracking-tight">
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
