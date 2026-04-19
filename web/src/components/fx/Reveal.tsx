import type { ElementType, ReactNode } from "react"
import { useReveal } from "@/hooks/useReveal"
import { cn } from "@/lib/utils"

type Variant = "up" | "left" | "right" | "scale" | "blur"

type RevealProps = {
  as?: ElementType
  variant?: Variant
  delayMs?: number
  durationMs?: number
  className?: string
  children: ReactNode
}

const initialClass: Record<Variant, string> = {
  up: "opacity-0 translate-y-8",
  left: "opacity-0 -translate-x-8",
  right: "opacity-0 translate-x-8",
  scale: "opacity-0 scale-95",
  blur: "opacity-0 blur-md",
}

const visibleClass: Record<Variant, string> = {
  up: "opacity-100 translate-y-0",
  left: "opacity-100 translate-x-0",
  right: "opacity-100 translate-x-0",
  scale: "opacity-100 scale-100",
  blur: "opacity-100 blur-0",
}

export const Reveal = ({
  as,
  variant = "up",
  delayMs = 0,
  durationMs = 700,
  className,
  children,
}: RevealProps) => {
  const Tag = (as ?? "div") as ElementType
  const { ref, visible } = useReveal<HTMLDivElement>()

  return (
    <Tag
      ref={ref}
      style={{
        transitionDelay: `${delayMs}ms`,
        transitionDuration: `${durationMs}ms`,
      }}
      className={cn(
        "will-change-transform transition-all ease-out motion-reduce:transition-none motion-reduce:transform-none",
        visible ? visibleClass[variant] : initialClass[variant],
        className,
      )}
    >
      {children}
    </Tag>
  )
}
