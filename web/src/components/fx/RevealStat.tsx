import { useEffect, useState } from "react"
import { CountUp } from "./CountUp"
import { useReveal } from "@/hooks/useReveal"

type RevealStatProps = {
  value: number
  prefix?: string
  suffix?: string
  decimals?: number
  durationMs?: number
  className?: string
}

export const RevealStat = ({
  value,
  prefix,
  suffix,
  decimals,
  durationMs = 1400,
  className,
}: RevealStatProps) => {
  const { ref, visible } = useReveal<HTMLSpanElement>({ threshold: 0.4 })
  const [target, setTarget] = useState(0)

  useEffect(() => {
    if (visible) setTarget(value)
  }, [visible, value])

  return (
    <span ref={ref} className={className}>
      <CountUp
        value={target}
        prefix={prefix}
        suffix={suffix}
        decimals={decimals}
        durationMs={durationMs}
      />
    </span>
  )
}
