import {
  Activity,
  Bot,
  Database,
  GaugeCircle,
  Lock,
  ShieldAlert,
  type LucideIcon,
} from "lucide-react"
import { Reveal } from "@/components/fx/Reveal"
import { SectionEyebrow } from "./SectionEyebrow"

type Feature = {
  icon: LucideIcon
  title: string
  body: string
}

const FEATURES: Feature[] = [
  {
    icon: Activity,
    title: "Real-time Kalshi tape",
    body:
      "Sub-second tape ingest with smart back-off. Aggregates every print into notional, share-of-OI, and tier signals.",
  },
  {
    icon: GaugeCircle,
    title: "Edge in basis points",
    body:
      "Every opportunity is priced in bps after slippage and friction. No vibe-based percentages.",
  },
  {
    icon: ShieldAlert,
    title: "Insider watch",
    body:
      "Surveillance-style feed surfaces unusual prints across markets and ranks them by size and OI share.",
  },
  {
    icon: Bot,
    title: "Auto-mapping",
    body:
      "Fuzzy matcher links Kalshi contracts to sportsbook lines automatically — no spreadsheets to maintain.",
  },
  {
    icon: Database,
    title: "SQLite-native",
    body:
      "Every alert, position, and session lives in a single file. Bring your own backups, no infra to babysit.",
  },
  {
    icon: Lock,
    title: "Private by default",
    body:
      "PBKDF2 password hashing, HTTP-only session cookies, and protected APIs out of the box.",
  },
]

export const FeatureGrid = () => (
  <section className="relative">
    <div className="mx-auto max-w-6xl px-4 py-24">
      <Reveal variant="up" className="mx-auto max-w-2xl text-center">
        <SectionEyebrow>What's inside</SectionEyebrow>
        <h2 className="mt-4 text-balance text-3xl font-semibold tracking-tight md:text-4xl">
          Everything an edge-hunter needs, in one tab.
        </h2>
        <p className="mt-3 text-sm text-muted-foreground md:text-base">
          Built for traders who want institutional tooling without an institutional stack.
        </p>
      </Reveal>

      <div className="mt-12 grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {FEATURES.map((feature, idx) => {
          const Icon = feature.icon
          return (
            <Reveal
              key={feature.title}
              variant="up"
              delayMs={(idx % 3) * 90 + Math.floor(idx / 3) * 60}
            >
              <div className="group relative h-full overflow-hidden rounded-2xl border border-border/60 bg-card/50 p-5 transition-all duration-500 hover:-translate-y-0.5 hover:border-primary/40">
                <div
                  aria-hidden
                  className="pointer-events-none absolute -right-12 -top-12 size-32 rounded-full bg-primary/10 opacity-0 blur-2xl transition-opacity duration-500 group-hover:opacity-100"
                />
                <div className="flex size-9 items-center justify-center rounded-lg bg-primary/10 text-primary ring-1 ring-primary/25">
                  <Icon className="size-4" aria-hidden />
                </div>
                <h3 className="mt-4 text-base font-semibold tracking-tight">{feature.title}</h3>
                <p className="mt-1.5 text-sm leading-relaxed text-muted-foreground">
                  {feature.body}
                </p>
              </div>
            </Reveal>
          )
        })}
      </div>
    </div>
  </section>
)
