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
    title: "Month-long Kalshi tape",
    body:
      "Looks back 30 days by default and aggregates every qualifying print into notional, share-of-OI, and tier signals.",
  },
  {
    icon: GaugeCircle,
    title: "Conviction scoring",
    body:
      "Every market is ranked by size, directional imbalance, open-interest impact, concentration, and recency.",
  },
  {
    icon: ShieldAlert,
    title: "Insider watch",
    body:
      "Surveillance-style feed surfaces unusual prints across markets and ranks them by size and OI share.",
  },
  {
    icon: Bot,
    title: "Market hydration",
    body:
      "Ticker metadata, status, prices, and public Kalshi URLs are resolved before anything reaches the feed.",
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
        <SectionEyebrow>Inside the kit</SectionEyebrow>
        <h2 className="mt-4 text-balance font-display text-3xl font-bold uppercase tracking-tight md:text-5xl">
          Everything an <span className="text-gradient-emerald">tape-reader</span> needs, in one tab.
        </h2>
        <p className="mt-3 text-sm text-muted-foreground md:text-base">
          Built for traders who want to spot informed flow without digging through raw trade logs.
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
                <h3 className="mt-4 font-display text-base font-semibold uppercase tracking-tight">
                  {feature.title}
                </h3>
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
