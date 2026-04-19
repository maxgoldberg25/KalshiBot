import { useEffect, useRef, useState } from "react"

type CountUpProps = {
  value: number
  durationMs?: number
  prefix?: string
  suffix?: string
  decimals?: number
  className?: string
}

const easeOutCubic = (t: number) => 1 - Math.pow(1 - t, 3)

export const CountUp = ({
  value,
  durationMs = 900,
  prefix = "",
  suffix = "",
  decimals = 0,
  className,
}: CountUpProps) => {
  const [display, setDisplay] = useState<number>(value)
  const fromRef = useRef<number>(value)
  const startRef = useRef<number | null>(null)
  const rafRef = useRef<number | null>(null)

  useEffect(() => {
    const from = fromRef.current
    const delta = value - from
    if (delta === 0) {
      setDisplay(value)
      return
    }
    startRef.current = null

    const step = (ts: number) => {
      if (startRef.current === null) startRef.current = ts
      const elapsed = ts - startRef.current
      const t = Math.min(1, elapsed / durationMs)
      const eased = easeOutCubic(t)
      setDisplay(from + delta * eased)
      if (t < 1) {
        rafRef.current = requestAnimationFrame(step)
      } else {
        fromRef.current = value
      }
    }

    rafRef.current = requestAnimationFrame(step)
    return () => {
      if (rafRef.current !== null) cancelAnimationFrame(rafRef.current)
    }
  }, [value, durationMs])

  const formatted = new Intl.NumberFormat(undefined, {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(display)

  return (
    <span className={className}>
      {prefix}
      {formatted}
      {suffix}
    </span>
  )
}
