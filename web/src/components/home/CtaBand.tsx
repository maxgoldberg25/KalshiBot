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
              className="pointer-events-none absolute inset-0 -z-10 bg-aurora animate-aurora opacity-70"
            />
            <div
              aria-hidden
              className="pointer-events-none absolute inset-0 -z-10 bg-grid-sm opacity-[0.08]"
            />
            <div
              aria-hidden
              className="pointer-events-none absolute -left-24 top-1/2 -z-10 size-[420px] -translate-y-1/2 rounded-full bg-primary/10 blur-3xl animate-float-slow"
            />
            <div
              aria-hidden
              className="pointer-events-none absolute -right-24 top-1/3 -z-10 size-[360px] rounded-full bg-sky-500/10 blur-3xl animate-float"
            />

            <div className="mx-auto inline-flex items-center gap-2 rounded-full border border-primary/30 bg-primary/10 px-3 py-1 text-[0.7rem] font-semibold uppercase tracking-widest text-primary">
              <span className="size-1.5 animate-pulse-glow rounded-full bg-primary" />
              Live now
            </div>

            <h2 className="mt-5 text-balance text-4xl font-semibold tracking-tight md:text-5xl">
              Trade the spread between{" "}
              <span className="text-gradient-emerald">truth and price.</span>
            </h2>
            <p className="mx-auto mt-4 max-w-xl text-sm text-muted-foreground md:text-base">
              The scanner is already running. Sign in to see what it's catching right now.
            </p>

            <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
              {isAuthed ? (
                <>
                  <Button asChild size="lg" className="gap-2 shadow-lg shadow-primary/20">
                    <NavLink to="/insider">
                      <ShieldCheck className="size-4" aria-hidden />
                      Open Insider watch
                      <ArrowRight className="size-4" aria-hidden />
                    </NavLink>
                  </Button>
                </>
              ) : (
                <>
                  <Button asChild size="lg" className="gap-2 shadow-lg shadow-primary/20">
                    <NavLink to="/login">
                      Create your account
                      <ArrowRight className="size-4" aria-hidden />
                    </NavLink>
                  </Button>
                  <Button asChild size="lg" variant="outline" className="gap-2">
                    <NavLink to="/login">
                      <ShieldCheck className="size-4" aria-hidden />
                      I already have one
                    </NavLink>
                  </Button>
                </>
              )}
            </div>

            <p className="mt-6 text-[11px] text-muted-foreground">
              Self-hosted · single-file SQLite · sessions never leave your machine.
            </p>
          </div>
        </Reveal>
      </div>
    </section>
  )
}
