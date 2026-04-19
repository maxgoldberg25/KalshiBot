import { ArrowRight, Radar, Scale, Zap } from "lucide-react"
import { Reveal } from "@/components/fx/Reveal"
import { SectionEyebrow } from "./SectionEyebrow"

const STEPS = [
  {
    icon: <Radar className="size-5" aria-hidden />,
    title: "Pull every market",
    body:
      "Stream Kalshi event contracts and sportsbook lines side by side, normalized to true probabilities — no manual mapping required.",
    gradient: "from-emerald-400/20 to-teal-500/0",
  },
  {
    icon: <Scale className="size-5" aria-hidden />,
    title: "Compare in basis points",
    body:
      "We weight by liquidity, stale-quote risk, and execution friction so the edge you see is the edge you can actually capture.",
    gradient: "from-sky-400/20 to-indigo-500/0",
  },
  {
    icon: <Zap className="size-5" aria-hidden />,
    title: "Act before it closes",
    body:
      "Get an alert the moment an opportunity opens, with a Kelly-sized order ready to send and a one-click execution flow.",
    gradient: "from-fuchsia-400/20 to-violet-500/0",
  },
]

export const HowItWorks = () => (
  <section className="relative">
    <div className="mx-auto max-w-6xl px-4 py-24">
      <Reveal variant="up" className="mx-auto max-w-2xl text-center">
        <SectionEyebrow>How it works</SectionEyebrow>
        <h2 className="mt-4 text-balance text-3xl font-semibold tracking-tight md:text-4xl">
          A scanner that thinks like a <span className="text-gradient-emerald">market maker</span>.
        </h2>
        <p className="mt-3 text-sm text-muted-foreground md:text-base">
          Three stages run on a 30-second loop. By the time the screen refreshes, the edge has been
          priced, sized, and queued for execution.
        </p>
      </Reveal>

      <ol className="mt-14 grid gap-5 md:grid-cols-3">
        {STEPS.map((step, idx) => (
          <Reveal
            key={step.title}
            variant="up"
            delayMs={idx * 120}
            as="li"
            className="group relative"
          >
            <div className="relative h-full overflow-hidden rounded-2xl border border-border/60 bg-card/60 p-6 backdrop-blur transition-all duration-500 hover:-translate-y-1 hover:border-primary/40 hover:shadow-2xl hover:shadow-primary/10">
              <div
                className={`pointer-events-none absolute inset-0 bg-gradient-to-br ${step.gradient} opacity-0 transition-opacity duration-500 group-hover:opacity-100`}
                aria-hidden
              />
              <div className="relative flex items-center justify-between">
                <span className="flex size-10 items-center justify-center rounded-xl bg-primary/15 text-primary ring-1 ring-primary/30 transition-transform duration-500 group-hover:scale-110">
                  {step.icon}
                </span>
                <span className="font-mono text-xs uppercase tracking-widest text-muted-foreground/70">
                  Step {String(idx + 1).padStart(2, "0")}
                </span>
              </div>
              <h3 className="relative mt-5 text-lg font-semibold tracking-tight">{step.title}</h3>
              <p className="relative mt-2 text-sm leading-relaxed text-muted-foreground">
                {step.body}
              </p>
              <div className="relative mt-6 flex items-center gap-1.5 text-xs font-medium text-primary opacity-0 transition-opacity duration-500 group-hover:opacity-100">
                Live in production
                <ArrowRight className="size-3.5" aria-hidden />
              </div>
            </div>

            {idx < STEPS.length - 1 && (
              <div
                aria-hidden
                className="pointer-events-none absolute left-full top-1/2 hidden h-px w-6 -translate-y-1/2 bg-gradient-to-r from-primary/60 to-transparent md:block"
              />
            )}
          </Reveal>
        ))}
      </ol>
    </div>
  </section>
)
