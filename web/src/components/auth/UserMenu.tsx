import { useState } from "react"
import { Link, useNavigate } from "react-router-dom"
import { LogIn, LogOut, Loader2, Sparkles, UserRound } from "lucide-react"
import { Button } from "@/components/ui/button"
import { useAuth } from "@/context/AuthContext"

export const UserMenu = () => {
  const { status, user, logout } = useAuth()
  const navigate = useNavigate()
  const [busy, setBusy] = useState(false)

  const handleLogout = async () => {
    setBusy(true)
    try {
      await logout()
      navigate("/", { replace: true })
    } finally {
      setBusy(false)
    }
  }

  if (status === "loading") {
    return (
      <div
        className="flex items-center gap-1.5 text-xs text-muted-foreground"
        aria-label="Loading session"
      >
        <Loader2 className="size-3.5 animate-spin" aria-hidden />
      </div>
    )
  }

  if (status === "anon") {
    return (
      <div
        className="flex h-7 max-w-[200px] items-stretch overflow-hidden rounded-md border border-border/60 bg-background text-xs shadow-sm ring-1 ring-border/30 sm:max-w-none"
        role="group"
        aria-label="Sign in or join the waitlist"
      >
        <Link
          to="/login?mode=waitlist"
          className="flex min-w-0 flex-1 cursor-pointer items-center justify-center gap-1 border-r border-border/60 px-2 font-medium text-muted-foreground transition-colors duration-200 hover:bg-muted/70 hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-primary/40"
        >
          <Sparkles className="size-3 shrink-0 opacity-80" aria-hidden />
          <span className="truncate sm:max-w-[7.5rem]">Join waitlist</span>
        </Link>
        <Link
          to="/login?mode=login"
          className="flex min-w-0 flex-1 cursor-pointer items-center justify-center gap-1 bg-primary px-2.5 font-medium text-primary-foreground transition-colors duration-200 hover:bg-primary/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-primary-foreground/30"
        >
          <LogIn className="size-3.5 shrink-0" aria-hidden />
          <span className="shrink-0">Sign in</span>
        </Link>
      </div>
    )
  }

  return (
    <div className="flex items-center gap-2">
      <div
        className="flex items-center gap-1.5 rounded-full border border-border/60 bg-accent/40 px-2 py-1 text-xs"
        aria-label={`Signed in as ${user?.username}`}
      >
        <span className="flex size-4 items-center justify-center rounded-full bg-primary/15 ring-1 ring-primary/30">
          <UserRound className="size-2.5 text-primary" aria-hidden />
        </span>
        <span className="max-w-[140px] truncate font-medium">
          {user?.username ?? "user"}
        </span>
      </div>
      <Button
        type="button"
        size="sm"
        variant="ghost"
        tabIndex={0}
        aria-label="Sign out"
        onClick={handleLogout}
        onKeyDown={(e) => e.key === "Enter" && void handleLogout()}
        disabled={busy}
        className="h-7 gap-1.5 px-2 text-xs text-muted-foreground hover:text-foreground"
      >
        {busy ? (
          <Loader2 className="size-3.5 animate-spin" aria-hidden />
        ) : (
          <LogOut className="size-3.5" aria-hidden />
        )}
        Sign out
      </Button>
    </div>
  )
}
