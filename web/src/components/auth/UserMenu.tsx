import { useState } from "react"
import { Link, useNavigate } from "react-router-dom"
import { LogIn, LogOut, Loader2, UserRound } from "lucide-react"
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
      <Button
        asChild
        size="sm"
        variant="default"
        className="h-7 gap-1.5 px-2.5 text-xs"
      >
        <Link to="/login" aria-label="Sign in">
          <LogIn className="size-3.5" aria-hidden />
          Sign in
        </Link>
      </Button>
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
