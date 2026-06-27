import { ArrowRight, ShieldCheck } from "lucide-react"
import { NavLink } from "react-router-dom"
import { Reveal } from "@/components/fx/Reveal"
import { Button } from "@/components/ui/button"
import { useAuth } from "@/context/AuthContext"

export const CtaBand = () => {
  const { status } = useAuth()
  const isAuthed = status === "authed"

  return (
    <section className="relative">
      <div className="mx-auto max-w-5xl px-4 pb-28 pt-12">
        <Reveal variant="up">
          <div className="relative overflow-hidden rounded-3xl border border-border/60 bg-card/60 p-10 text-center shadow-2xl shadow-primary/10 backdrop-blur md:p-14">
            <div
              aria-hidden
              className="pointer-events-none absolute inset-0 -z-10 bg-grid-sm opacity-[0.06]"
            />
            <div
              aria-hidden
              className="pointer-events-none absolute left-1/2 top-1/2 -z-10 size-[480px] -translate-x-1/2 -translate-y-1/2 rounded-full bg-primary/[0.08] blur-3xl"
            />

            <div className="mx-auto inline-flex items-center gap-2 rounded-full border border-primary/40 bg-primary/10 px-3 py-1 font-display text-[0.7rem] font-semibold uppercase tracking-[0.32em] text-primary">
              <span className="size-1.5 animate-pulse-glow rounded-full bg-primary" />
              Start watching
            </div>

            <h2 className="mt-5 text-balance font-display text-4xl font-bold uppercase tracking-tight md:text-6xl">
              Follow the flow.
              <br />
              <span className="text-gradient-emerald">
                Catch the move.
              </span>
            </h2>
            <p className="mx-auto mt-5 max-w-xl text-sm text-muted-foreground md:text-base">
              Insider Watch is scanning the last month of large Kalshi prints.
              Open the feed and see which markets are attracting serious size.
            </p>

            <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
              {isAuthed ? (
                <Button
                  asChild
                  size="lg"
                  className="gap-2 font-display uppercase tracking-wider shadow-lg shadow-primary/25"
                >
                  <NavLink to="/insider">
                    <ShieldCheck className="size-4" aria-hidden />
                    Open insider watch
                    <ArrowRight className="size-4" aria-hidden />
                  </NavLink>
                </Button>
              ) : (
                <>
                  <Button
                    asChild
                    size="lg"
                    className="gap-2 font-display uppercase tracking-wider shadow-lg shadow-primary/25"
                  >
                    <NavLink to="/login">
                      Claim your seat
                      <ArrowRight className="size-4" aria-hidden />
                    </NavLink>
                  </Button>
                  <Button
                    asChild
                    size="lg"
                    variant="outline"
                    className="gap-2 font-display uppercase tracking-wider"
                  >
                    <NavLink to="/login">
                      <ShieldCheck className="size-4" aria-hidden />
                      I already have one
                    </NavLink>
                  </Button>
                </>
              )}
            </div>

            <p className="mt-6 font-display text-[11px] uppercase tracking-[0.28em] text-muted-foreground">
              30-day tape · Large-trade filter · Sessions never leave your machine
            </p>
          </div>
        </Reveal>
      </div>
    </section>
  )
}
