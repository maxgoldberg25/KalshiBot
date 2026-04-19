import type { ReactNode } from "react"
import { Navigate, useLocation } from "react-router-dom"
import { Loader2, ShieldAlert } from "lucide-react"
import { useAuth } from "@/context/AuthContext"

type RequireAdminProps = {
  children: ReactNode
}

export const RequireAdmin = ({ children }: RequireAdminProps) => {
  const { status, isAdmin } = useAuth()
  const location = useLocation()

  if (status === "loading") {
    return (
      <div className="flex min-h-[60vh] items-center justify-center text-muted-foreground">
        <Loader2 className="size-4 animate-spin" aria-hidden />
        <span className="sr-only">Loading session…</span>
      </div>
    )
  }

  if (status === "anon") {
    const redirect = encodeURIComponent(`${location.pathname}${location.search}`)
    return <Navigate to={`/login?next=${redirect}`} replace />
  }

  if (!isAdmin) {
    return (
      <div className="mx-auto flex min-h-[60vh] max-w-md flex-col items-center justify-center gap-3 px-4 text-center">
        <ShieldAlert className="size-8 text-destructive" aria-hidden />
        <h1 className="text-lg font-semibold">Admins only</h1>
        <p className="text-sm text-muted-foreground">
          You are signed in, but this area is reserved for administrators.
        </p>
      </div>
    )
  }

  return <>{children}</>
}
