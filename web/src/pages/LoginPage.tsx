import {
  useEffect,
  useMemo,
  useState,
  type FormEvent,
  type KeyboardEvent,
  type ReactNode,
} from "react"
import { useNavigate, useSearchParams } from "react-router-dom"
import {
  Check,
  CheckCircle2,
  ClipboardList,
  KeyRound,
  Loader2,
  Lock,
  LogIn,
  Mail,
  MessageSquare,
  ShieldCheck,
  Sparkles,
  Ticket,
  UserRound,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { postWaitlist } from "@/api/fetch"
import { useAuth } from "@/context/AuthContext"
import { cn } from "@/lib/utils"

type Mode = "login" | "waitlist" | "redeem"

const MIN_PASSWORD_LEN = 8
const USERNAME_RE = /^[a-zA-Z0-9_.-]{3,32}$/

export const LoginPage = () => {
  const { status, login, register } = useAuth()
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()

  const inviteToken = useMemo(() => {
    return (searchParams.get("invite") || "").trim().slice(0, 128)
  }, [searchParams])

  const redirectTarget = useMemo(() => {
    const raw = searchParams.get("next")
    if (!raw) return "/insider"
    try {
      const decoded = decodeURIComponent(raw)
      return decoded.startsWith("/") ? decoded : "/insider"
    } catch {
      return "/insider"
    }
  }, [searchParams])

  const [mode, setMode] = useState<Mode>(() => {
    const inv = (searchParams.get("invite") || "").trim().slice(0, 128)
    if (inv) return "redeem"
    return searchParams.get("mode") === "waitlist" ? "waitlist" : "login"
  })
  const [username, setUsername] = useState("")
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [reason, setReason] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [waitlistSubmitted, setWaitlistSubmitted] = useState(false)

  useEffect(() => {
    if (status === "authed") {
      navigate(redirectTarget, { replace: true })
    }
  }, [status, navigate, redirectTarget])

  useEffect(() => {
    if (inviteToken) {
      setMode("redeem")
      return
    }
    const m = searchParams.get("mode")
    setMode(m === "waitlist" ? "waitlist" : "login")
  }, [inviteToken, searchParams])

  const handleSwitchMode = (next: Mode) => {
    setMode(next)
    setError(null)
    setWaitlistSubmitted(false)
    if (!inviteToken) {
      setSearchParams(
        (prev) => {
          const p = new URLSearchParams(prev)
          if (next === "waitlist") p.set("mode", "waitlist")
          else p.delete("mode")
          return p
        },
        { replace: true },
      )
    }
  }

  const handleSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    setError(null)

    const u = username.trim()
    if (!USERNAME_RE.test(u)) {
      setError("Username must be 3-32 chars: letters, numbers, '.', '_' or '-'.")
      return
    }

    if (mode === "waitlist") {
      setSubmitting(true)
      try {
        await postWaitlist({
          username: u,
          email: email.trim() || undefined,
          reason: reason.trim() || undefined,
        })
        setWaitlistSubmitted(true)
      } catch (err) {
        setError(err instanceof Error ? err.message : "Could not submit request.")
      } finally {
        setSubmitting(false)
      }
      return
    }

    if (password.length < MIN_PASSWORD_LEN) {
      setError(`Password must be at least ${MIN_PASSWORD_LEN} characters.`)
      return
    }

    setSubmitting(true)
    try {
      if (mode === "login") {
        await login(u, password)
      } else {
        if (!inviteToken) {
          setError("Missing invite token.")
          return
        }
        await register({
          username: u,
          password,
          email: email.trim() || undefined,
          inviteToken,
        })
      }
      navigate(redirectTarget, { replace: true })
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.")
    } finally {
      setSubmitting(false)
    }
  }

  const headingTitle =
    mode === "login"
      ? "Sign in to KalshiInsider"
      : mode === "redeem"
        ? "Activate your account"
        : "Join the waitlist"

  const headingSubtitle =
    mode === "login"
      ? "Access the live scanner, insider watch, and execution tools."
      : mode === "redeem"
        ? "You've been approved. Choose a password to finish setting up your account."
        : "Invite-only access. Tell us who you are — we'll email you if a seat opens."

  return (
    <div className="relative min-h-[calc(100vh-2.75rem)] overflow-hidden">
      <div className="pointer-events-none absolute inset-0 -z-10">
        <div className="absolute inset-0 bg-grid-sm opacity-[0.15]" aria-hidden />
        <div
          className="absolute left-1/2 top-[-10%] h-[480px] w-[720px] -translate-x-1/2 rounded-full bg-primary/20 blur-3xl"
          aria-hidden
        />
        <div
          className="absolute bottom-[-20%] right-[-10%] h-[420px] w-[560px] rounded-full bg-emerald-500/15 blur-3xl"
          aria-hidden
        />
      </div>

      <div className="mx-auto flex max-w-md flex-col items-stretch gap-8 px-4 py-16 sm:py-20">
        <div className="flex flex-col items-center gap-3 text-center">
          <div
            className={cn(
              "relative flex size-14 items-center justify-center rounded-2xl bg-gradient-to-br shadow-lg ring-1 transition-colors duration-300",
              mode === "waitlist"
                ? "from-emerald-500/25 via-primary/15 to-sky-500/20 ring-emerald-500/25"
                : "from-primary/25 via-primary/10 to-sky-500/15 ring-primary/30",
            )}
          >
            <span
              className="absolute inset-0 rounded-2xl bg-[radial-gradient(ellipse_at_30%_20%,rgba(255,255,255,0.12),transparent_55%)]"
              aria-hidden
            />
            {mode === "waitlist" ? (
              <ClipboardList className="relative size-6 text-emerald-300" aria-hidden />
            ) : mode === "redeem" ? (
              <Ticket className="relative size-6 text-primary" aria-hidden />
            ) : (
              <ShieldCheck className="relative size-6 text-primary" aria-hidden />
            )}
          </div>
          <div className="space-y-2">
            <p className="text-[0.65rem] font-semibold uppercase tracking-[0.22em] text-muted-foreground">
              {mode === "waitlist" ? "Early access" : mode === "redeem" ? "Invite" : "Secure access"}
            </p>
            <h1 className="text-balance text-2xl font-semibold tracking-tight sm:text-3xl">
              {headingTitle}
            </h1>
            <p className="mx-auto max-w-sm text-pretty text-sm leading-relaxed text-muted-foreground">
              {headingSubtitle}
            </p>
          </div>
        </div>

        <Card className="overflow-hidden rounded-2xl border-border/50 bg-card/85 shadow-2xl shadow-primary/5 ring-1 ring-white/[0.04] backdrop-blur-md dark:ring-white/[0.06]">
          <CardHeader className="space-y-4 pb-2 pt-6">
            {mode === "waitlist" && !waitlistSubmitted && (
              <div className="flex flex-col gap-2 rounded-xl border border-border/50 bg-muted/25 px-3 py-3 sm:flex-row sm:items-center sm:justify-between">
                <p className="text-xs leading-snug text-muted-foreground">
                  Already have an account? Sign in with your username and password.
                </p>
                <Button
                  type="button"
                  variant="secondary"
                  size="sm"
                  className="h-8 shrink-0 cursor-pointer gap-1.5 self-start sm:self-auto"
                  onClick={() => handleSwitchMode("login")}
                >
                  <LogIn className="size-3.5" aria-hidden />
                  Sign in
                </Button>
              </div>
            )}
            {mode !== "redeem" && (
              <div
                className="grid grid-cols-1 gap-2 rounded-xl bg-gradient-to-b from-muted/90 to-muted/50 p-1.5 ring-1 ring-border/40 sm:grid-cols-2"
                role="tablist"
                aria-label="Sign in or join the waitlist"
              >
                <ModeTab
                  active={mode === "login"}
                  label="Sign in"
                  icon={<LogIn className="size-4 shrink-0" aria-hidden />}
                  onClick={() => handleSwitchMode("login")}
                  onKeyDown={(e) => {
                    if (e.key === "ArrowRight" || e.key === "ArrowDown") {
                      e.preventDefault()
                      handleSwitchMode("waitlist")
                    }
                  }}
                />
                <ModeTab
                  active={mode === "waitlist"}
                  label="Join the waitlist"
                  icon={<Sparkles className="size-4 shrink-0" aria-hidden />}
                  onClick={() => handleSwitchMode("waitlist")}
                  onKeyDown={(e) => {
                    if (e.key === "ArrowLeft" || e.key === "ArrowUp") {
                      e.preventDefault()
                      handleSwitchMode("login")
                    }
                  }}
                />
              </div>
            )}
            {mode === "redeem" && (
              <div className="flex items-center gap-2 rounded-md border border-emerald-500/30 bg-emerald-500/10 px-3 py-2 text-xs text-emerald-400">
                <Ticket className="size-3.5" aria-hidden />
                <span className="truncate">Invite verified — set your credentials below.</span>
              </div>
            )}
            <CardTitle className="sr-only">{headingTitle}</CardTitle>
          </CardHeader>

          <CardContent className="px-5 pb-6 pt-2 sm:px-6">
            {mode === "waitlist" && !waitlistSubmitted && (
              <ul className="mb-5 space-y-2.5 rounded-xl border border-primary/15 bg-gradient-to-br from-primary/[0.07] to-transparent px-4 py-3.5 text-left">
                <li className="flex gap-2.5 text-xs leading-snug text-muted-foreground">
                  <span className="mt-0.5 flex size-5 shrink-0 items-center justify-center rounded-md bg-emerald-500/15 text-emerald-400 ring-1 ring-emerald-500/25">
                    <Check className="size-3" aria-hidden />
                  </span>
                  Live scanner, insider tape, and execution tooling once approved.
                </li>
                <li className="flex gap-2.5 text-xs leading-snug text-muted-foreground">
                  <span className="mt-0.5 flex size-5 shrink-0 items-center justify-center rounded-md bg-sky-500/15 text-sky-300 ring-1 ring-sky-500/25">
                    <Check className="size-3" aria-hidden />
                  </span>
                  We review every request — no spam, no auto-approved bots.
                </li>
                <li className="flex gap-2.5 text-xs leading-snug text-muted-foreground">
                  <span className="mt-0.5 flex size-5 shrink-0 items-center justify-center rounded-md bg-amber-500/10 text-amber-400/90 ring-1 ring-amber-500/20">
                    <Check className="size-3" aria-hidden />
                  </span>
                  Typical reply time is a few business days if it’s a fit.
                </li>
              </ul>
            )}

            {waitlistSubmitted ? (
              <WaitlistSuccess
                onReset={() => {
                  setWaitlistSubmitted(false)
                  setUsername("")
                  setEmail("")
                  setReason("")
                  handleSwitchMode("login")
                }}
              />
            ) : (
              <form onSubmit={handleSubmit} className="flex flex-col gap-3" noValidate>
                <FormField
                  id="username"
                  label="Username"
                  icon={<UserRound className="size-3.5" aria-hidden />}
                >
                  <input
                    id="username"
                    name="username"
                    type="text"
                    autoComplete="username"
                    required
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    placeholder="ada.lovelace"
                    className="w-full bg-transparent text-sm outline-none placeholder:text-muted-foreground/60"
                  />
                </FormField>

                {mode !== "login" && (
                  <FormField
                    id="email"
                    label={mode === "waitlist" ? "Email" : "Email (optional)"}
                    icon={<Mail className="size-3.5" aria-hidden />}
                  >
                    <input
                      id="email"
                      name="email"
                      type="email"
                      autoComplete="email"
                      required={mode === "waitlist"}
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      placeholder="you@example.com"
                      className="w-full bg-transparent text-sm outline-none placeholder:text-muted-foreground/60"
                    />
                  </FormField>
                )}

                {mode === "waitlist" && (
                  <FormField
                    id="reason"
                    label="Why do you want access? (optional)"
                    icon={<MessageSquare className="size-3.5" aria-hidden />}
                  >
                    <textarea
                      id="reason"
                      name="reason"
                      value={reason}
                      onChange={(e) => setReason(e.target.value)}
                      rows={3}
                      maxLength={1000}
                      placeholder="Quant at a hedge fund, researcher, personal trader…"
                      className="w-full resize-y bg-transparent text-sm outline-none placeholder:text-muted-foreground/60"
                    />
                  </FormField>
                )}

                {mode !== "waitlist" && (
                  <FormField
                    id="password"
                    label="Password"
                    icon={<Lock className="size-3.5" aria-hidden />}
                  >
                    <input
                      id="password"
                      name="password"
                      type="password"
                      autoComplete={mode === "login" ? "current-password" : "new-password"}
                      required
                      minLength={MIN_PASSWORD_LEN}
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      placeholder="••••••••"
                      className="w-full bg-transparent text-sm outline-none placeholder:text-muted-foreground/60"
                    />
                  </FormField>
                )}

                {error && (
                  <div
                    role="alert"
                    aria-live="polite"
                    className="rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-xs text-destructive"
                  >
                    {error}
                  </div>
                )}

                <Button
                  type="submit"
                  disabled={submitting}
                  className="mt-1 w-full"
                >
                  {submitting ? (
                    <>
                      <Loader2 className="mr-2 size-4 animate-spin" aria-hidden />
                      {mode === "login"
                        ? "Signing in…"
                        : mode === "redeem"
                          ? "Activating…"
                          : "Sending request…"}
                    </>
                  ) : (
                    <>
                      <KeyRound className="mr-2 size-4" aria-hidden />
                      {mode === "login"
                        ? "Sign in"
                        : mode === "redeem"
                          ? "Activate account"
                          : "Join the waitlist"}
                    </>
                  )}
                </Button>
              </form>
            )}

            {!waitlistSubmitted && mode === "login" && (
              <p className="mt-5 text-center text-xs text-muted-foreground">
                Need an invite?{" "}
                <button
                  type="button"
                  tabIndex={0}
                  onClick={() => handleSwitchMode("waitlist")}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") handleSwitchMode("waitlist")
                  }}
                  className="cursor-pointer font-medium text-primary underline-offset-4 transition-colors hover:text-primary/90 hover:underline"
                >
                  Join the waitlist
                </button>
              </p>
            )}
          </CardContent>
        </Card>

        <p className="text-center text-[11px] text-muted-foreground">
          Sessions are stored in an HTTP-only cookie and last 14 days.
          Accounts are invite-only and manually approved.
        </p>
      </div>
    </div>
  )
}

type ModeTabProps = {
  active: boolean
  label: string
  icon: ReactNode
  onClick: () => void
  onKeyDown?: (e: KeyboardEvent<HTMLButtonElement>) => void
}

const ModeTab = ({ active, label, icon, onClick, onKeyDown }: ModeTabProps) => (
  <button
    type="button"
    role="tab"
    aria-selected={active}
    tabIndex={0}
    onClick={onClick}
    onKeyDown={(e) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault()
        onClick()
      }
      onKeyDown?.(e)
    }}
    className={cn(
      "flex cursor-pointer items-center justify-center gap-2 rounded-lg px-3 py-2.5 text-sm font-medium transition-all duration-200",
      active
        ? "bg-background text-foreground shadow-md ring-1 ring-border/50"
        : "text-muted-foreground hover:bg-background/50 hover:text-foreground",
      "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/35 focus-visible:ring-offset-2 focus-visible:ring-offset-background",
    )}
  >
    <span
      className={cn(
        "transition-colors duration-200",
        active ? "text-primary" : "text-muted-foreground",
      )}
    >
      {icon}
    </span>
    <span className="text-balance leading-tight">{label}</span>
  </button>
)

type FormFieldProps = {
  id: string
  label: string
  icon: ReactNode
  children: ReactNode
}

const FormField = ({ id, label, icon, children }: FormFieldProps) => (
  <label htmlFor={id} className="flex flex-col gap-1.5">
    <span className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
      {label}
    </span>
    <span className="flex items-start gap-2 rounded-md border border-border/70 bg-background/60 px-3 py-2 transition-colors focus-within:border-primary/60 focus-within:ring-2 focus-within:ring-primary/25">
      <span className="pt-[2px] text-muted-foreground">{icon}</span>
      {children}
    </span>
  </label>
)

const WaitlistSuccess = ({ onReset }: { onReset: () => void }) => (
  <div
    role="status"
    aria-live="polite"
    className="flex flex-col items-center gap-3 rounded-md border border-emerald-500/30 bg-emerald-500/10 px-4 py-6 text-center"
  >
    <CheckCircle2 className="size-7 text-emerald-400" aria-hidden />
    <div>
      <h2 className="text-sm font-semibold text-foreground">Request received</h2>
      <p className="mt-1 text-xs text-muted-foreground">
        We'll email you if your application is approved. Invites are sent manually,
        so sit tight — it may take a few days.
      </p>
    </div>
    <Button
      type="button"
      variant="ghost"
      size="sm"
      onClick={onReset}
      className="text-xs"
    >
      Back to sign in
    </Button>
  </div>
)

export default LoginPage
