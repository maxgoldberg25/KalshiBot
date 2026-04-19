import { useEffect } from "react"
import { HashRouter, NavLink, Navigate, Route, Routes } from "react-router-dom"
import { Home, ShieldAlert, ShieldCheck, TrendingUp } from "lucide-react"
import { AdminPage } from "@/pages/AdminPage"
import { HomePage } from "@/pages/HomePage"
import { InsiderWatchPage } from "@/pages/InsiderWatchPage"
import { LoginPage } from "@/pages/LoginPage"
import { RequireAdmin } from "@/components/auth/RequireAdmin"
import { RequireAuth } from "@/components/auth/RequireAuth"
import { UserMenu } from "@/components/auth/UserMenu"
import { useAuth } from "@/context/AuthContext"
import { cn } from "@/lib/utils"

const navLinkClass = ({ isActive }: { isActive: boolean }) =>
  cn(
    "flex items-center gap-1.5 rounded px-2.5 py-1.5 text-xs font-medium transition-colors",
    isActive
      ? "bg-accent text-foreground"
      : "text-muted-foreground hover:bg-accent/60 hover:text-foreground",
  )

export default function App() {
  useEffect(() => {
    document.documentElement.classList.add("dark")
    return () => document.documentElement.classList.remove("dark")
  }, [])

  return (
    <HashRouter>
      <AppShell />
    </HashRouter>
  )
}

const AppShell = () => {
  const { status, isAdmin } = useAuth()
  const isAuthed = status === "authed"

  return (
    <div className="min-h-screen bg-background text-foreground">
      <header className="sticky top-0 z-40 border-b border-border/60 bg-background/95 backdrop-blur-sm">
        <div className="mx-auto flex h-11 max-w-7xl items-center gap-5 px-4">
          <NavLink to="/" className="flex items-center gap-2" aria-label="MarketEdge home">
            <div className="flex h-6 w-6 items-center justify-center rounded bg-primary/15 ring-1 ring-primary/25">
              <TrendingUp className="h-3.5 w-3.5 text-primary" aria-hidden />
            </div>
            <span className="text-sm font-semibold tracking-tight">MarketEdge</span>
          </NavLink>

          <nav className="flex items-center gap-0.5" aria-label="Main navigation">
            <NavLink to="/" end className={navLinkClass}>
              <Home className="size-3.5" aria-hidden />
              Home
            </NavLink>
            {isAuthed && (
              <NavLink to="/insider" className={navLinkClass}>
                <ShieldAlert className="size-3.5" aria-hidden />
                Insider watch
              </NavLink>
            )}
            {isAuthed && isAdmin && (
              <NavLink to="/admin" className={navLinkClass}>
                <ShieldCheck className="size-3.5" aria-hidden />
                Admin
              </NavLink>
            )}
          </nav>

          <div className="ml-auto">
            <UserMenu />
          </div>
        </div>
      </header>

      <main>
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/login" element={<LoginPage />} />
          <Route
            path="/insider"
            element={
              <RequireAuth>
                <InsiderWatchPage />
              </RequireAuth>
            }
          />
          <Route
            path="/admin"
            element={
              <RequireAdmin>
                <AdminPage />
              </RequireAdmin>
            }
          />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </div>
  )
}
