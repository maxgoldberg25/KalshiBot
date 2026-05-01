import type { ReactNode } from "react"
import { cn } from "@/lib/utils"

type SectionEyebrowProps = {
  icon?: ReactNode
  children: ReactNode
  className?: string
}

export const SectionEyebrow = ({ icon, children, className }: SectionEyebrowProps) => (
  <span
    className={cn(
      "inline-flex items-center gap-2 rounded-full border border-border/60 bg-card/60 px-3 py-1 font-display text-[0.65rem] font-semibold uppercase tracking-[0.32em] text-muted-foreground backdrop-blur",
      className,
    )}
  >
    {icon ? <span className="text-primary">{icon}</span> : null}
    {children}
  </span>
)
