import { useEffect, useState } from "react"

export const ScrollProgress = () => {
  const [progress, setProgress] = useState(0)

  useEffect(() => {
    const handleScroll = () => {
      const doc = document.documentElement
      const max = doc.scrollHeight - doc.clientHeight
      const next = max > 0 ? doc.scrollTop / max : 0
      setProgress(Math.min(1, Math.max(0, next)))
    }
    handleScroll()
    window.addEventListener("scroll", handleScroll, { passive: true })
    window.addEventListener("resize", handleScroll)
    return () => {
      window.removeEventListener("scroll", handleScroll)
      window.removeEventListener("resize", handleScroll)
    }
  }, [])

  return (
    <div
      aria-hidden
      className="pointer-events-none fixed inset-x-0 top-11 z-50 h-[2px] bg-transparent"
    >
      <div
        className="h-full origin-left bg-gradient-to-r from-primary via-emerald-400 to-sky-400 shadow-[0_0_18px_rgba(16,185,129,0.65)] transition-[transform] duration-150 ease-out"
        style={{ transform: `scaleX(${progress})` }}
      />
    </div>
  )
}
