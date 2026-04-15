import { useEffect } from "react"
import { HashRouter, NavLink, Navigate, Route, Routes } from "react-router-dom"
import { BarChart3, Home, TrendingUp } from "lucide-react"
import { HomePage } from "@/pages/HomePage"
import { ScannerPage } from "@/pages/ScannerPage"
import { cn } from "@/lib/utils"

export default function App() {
  useEffect(() => {
    document.documentElement.classList.add("dark")
    return () => document.documentElement.classList.remove("dark")
  }, [])

  return (
    <HashRouter>
      <div className="min-h-screen bg-background text-foreground">
        <header className="sticky top-0 z-40 border-b border-border/60 bg-background/95 backdrop-blur-sm">
          <div className="mx-auto flex h-11 max-w-7xl items-center gap-5 px-4">
            {/* Brand */}
            <div className="flex items-center gap-2">
              <div className="flex h-6 w-6 items-center justify-center rounded bg-primary/15 ring-1 ring-primary/25">
                <TrendingUp className="h-3.5 w-3.5 text-primary" aria-hidden />
              </div>
              <span className="text-sm font-semibold tracking-tight">KalshiBot</span>
            </div>

            {/* Nav */}
            <nav className="flex items-center gap-0.5" aria-label="Main navigation">
              <NavLink
                to="/"
                end
                className={({ isActive }) =>
                  cn(
                    "flex items-center gap-1.5 rounded px-2.5 py-1.5 text-xs font-medium transition-colors",
                    isActive
                      ? "bg-accent text-foreground"
                      : "text-muted-foreground hover:bg-accent/60 hover:text-foreground"
                  )
                }
              >
                <Home className="size-3.5" aria-hidden />
                Home
              </NavLink>
              <NavLink
                to="/scanner"
                className={({ isActive }) =>
                  cn(
                    "flex items-center gap-1.5 rounded px-2.5 py-1.5 text-xs font-medium transition-colors",
                    isActive
                      ? "bg-accent text-foreground"
                      : "text-muted-foreground hover:bg-accent/60 hover:text-foreground"
                  )
                }
              >
                <BarChart3 className="size-3.5" aria-hidden />
                Scanner
              </NavLink>
            </nav>
          </div>
        </header>

        <main>
          <Routes>
            <Route path="/" element={<HomePage />} />
            <Route path="/scanner" element={<ScannerPage />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </main>
      </div>
    </HashRouter>
  )
}
