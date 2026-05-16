import { ArrowDown, ArrowUp } from "lucide-react"
import { cn } from "@/lib/utils"

export type TickerItem = {
  label: string
  price: number
  change: number
}

const FAKE_TICKERS: TickerItem[] = [
  { label: "KXPRES-24 · D", price: 0.48, change: -0.02 },
  { label: "KXFED-JAN · 25bp", price: 0.71, change: 0.01 },
  { label: "KXCPI-MAR · >0.3%", price: 0.31, change: 0.02 },
  { label: "KXUSRECESSION", price: 0.22, change: -0.01 },
  { label: "KXBTCPRICE · >100K", price: 0.41, change: 0.06 },
  { label: "KXOSCAR · BEST PIC", price: 0.33, change: -0.03 },
  { label: "KXRATECUT · MARCH", price: 0.56, change: 0.04 },
  { label: "KXCLIMATE · HOTTEST", price: 0.64, change: 0.02 },
  { label: "KXSCOTUS · RULING", price: 0.37, change: -0.04 },
  { label: "KXBTCETF · INFLOW", price: 0.52, change: 0.05 },
  { label: "KXGOVSHUT · DEC", price: 0.28, change: -0.01 },
  { label: "KXREGULATE · APPROVAL", price: 0.44, change: 0.03 },
]

const TapeRow = ({ items, ariaHidden }: { items: TickerItem[]; ariaHidden?: boolean }) => (
  <div
    className="flex shrink-0 items-center gap-6 pr-6"
    aria-hidden={ariaHidden ? "true" : undefined}
  >
    {items.map((t, i) => {
      const up = t.change >= 0
      return (
        <div
          key={`${t.label}-${i}`}
          className="flex items-center gap-2 whitespace-nowrap text-xs tabular-nums"
        >
          <span className="font-mono text-muted-foreground">{t.label}</span>
          <span className="font-semibold text-foreground">{(t.price * 100).toFixed(0)}¢</span>
          <span
            className={cn(
              "flex items-center gap-0.5 font-medium",
              up ? "text-emerald-400" : "text-rose-400",
            )}
          >
            {up ? <ArrowUp className="size-3" /> : <ArrowDown className="size-3" />}
            {Math.abs(t.change * 100).toFixed(0)}¢
          </span>
          <span className="text-border">•</span>
        </div>
      )
    })}
  </div>
)

export const TickerTape = () => {
  return (
    <div
      className="mask-fade-x relative overflow-hidden border-y border-border/50 bg-card/40 py-2"
      role="marquee"
      aria-label="Example prediction market prices"
    >
      <div className="flex animate-marquee will-change-transform">
        <TapeRow items={FAKE_TICKERS} />
        <TapeRow items={FAKE_TICKERS} ariaHidden />
      </div>
    </div>
  )
}
