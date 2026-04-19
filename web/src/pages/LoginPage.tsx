import { useEffect, useMemo, useState, type FormEvent, type ReactNode } from "react"
import { useNavigate, useSearchParams } from "react-router-dom"
import {
  CheckCircle2,
  KeyRound,
  Loader2,
  Lock,
  Mail,
  MessageSquare,
  ShieldCheck,
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
  const [searchParams] = useSearchParams()

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

  const [mode, setMode] = useState<Mode>(inviteToken ? "redeem" : "login")
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
    if (inviteToken) setMode("redeem")
  }, [inviteToken])

  const handleSwitchMode = (next: Mode) => {
    setMode(next)
    setError(null)
    setWaitlistSubmitted(false)
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
      ? "Sign in to KalshiBot"
      : mode === "redeem"
        ? "Activate your account"
        : "Request access"

  const headingSubtitle =
    mode === "login"
      ? "Access the live scanner, insider watch, and execution tools."
      : mode === "redeem"
        ? "You've been approved. Choose a password to finish setting up your account."
        : "KalshiBot is invite-only. Tell us a bit about yourself and we'll reach out when a spot opens."

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

      <div className="mx-auto flex max-w-md flex-col items-stretch gap-6 px-4 py-16">
        <div className="flex flex-col items-center gap-2 text-center">
          <div className="flex size-11 items-center justify-center rounded-xl bg-primary/15 ring-1 ring-primary/30">
            <ShieldCheck className="size-5 text-primary" aria-hidden />
          </div>
          <h1 className="text-balance text-2xl font-semibold tracking-tight">
            {headingTitle}
          </h1>
          <p className="max-w-sm text-sm text-muted-foreground">{headingSubtitle}</p>
        </div>

        <Card className="border-border/60 bg-card/80 shadow-xl backdrop-blur">
          <CardHeader className="pb-2">
            {mode !== "redeem" && (
              <div
                className="flex items-center gap-1 rounded-md bg-muted p-1"
                role="tablist"
                aria-label="Auth mode"
              >
                <ModeTab
                  active={mode === "login"}
                  label="Sign in"
                  onClick={() => handleSwitchMode("login")}
                />
                <ModeTab
                  active={mode === "waitlist"}
                  label="Request access"
                  onClick={() => handleSwitchMode("waitlist")}
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

          <CardContent className="pt-4">
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
                          : "Submitting…"}
                    </>
                  ) : (
                    <>
                      <KeyRound className="mr-2 size-4" aria-hidden />
                      {mode === "login"
                        ? "Sign in"
                        : mode === "redeem"
                          ? "Activate account"
                          : "Request access"}
                    </>
                  )}
                </Button>
              </form>
            )}

            {!waitlistSubmitted && mode !== "redeem" && (
              <p className="mt-4 text-center text-xs text-muted-foreground">
                {mode === "login" ? "No account? " : "Already approved? "}
                <button
                  type="button"
                  tabIndex={0}
                  onClick={() => handleSwitchMode(mode === "login" ? "waitlist" : "login")}
                  onKeyDown={(e) =>
                    e.key === "Enter" &&
                    handleSwitchMode(mode === "login" ? "waitlist" : "login")
                  }
                  className="font-medium text-primary underline-offset-4 hover:underline"
                >
                  {mode === "login" ? "Request access" : "Sign in instead"}
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
  onClick: () => void
}

const ModeTab = ({ active, label, onClick }: ModeTabProps) => (
  <button
    type="button"
    role="tab"
    aria-selected={active}
    tabIndex={0}
    onClick={onClick}
    onKeyDown={(e) => e.key === "Enter" && onClick()}
    className={cn(
      "flex-1 rounded px-3 py-1.5 text-xs font-medium transition-colors",
      active
        ? "bg-background text-foreground shadow-sm"
        : "text-muted-foreground hover:text-foreground",
    )}
  >
    {label}
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
