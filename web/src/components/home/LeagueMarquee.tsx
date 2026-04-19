import { Trophy } from "lucide-react"

const TAGS = [
  "NFL",
  "NBA",
  "MLB",
  "NHL",
  "NCAAF",
  "NCAAB",
  "Soccer · EPL",
  "Soccer · UCL",
  "Tennis · ATP",
  "Politics",
  "Macro · CPI",
  "Macro · Fed",
  "Crypto · BTC",
  "Crypto · ETH",
  "Box Office",
  "Weather",
]

const Strip = () => (
  <div className="flex shrink-0 items-center gap-3 pr-3">
    {TAGS.map((t) => (
      <span
        key={t}
        className="inline-flex items-center gap-1.5 rounded-full border border-border/50 bg-card/60 px-3 py-1 text-[0.7rem] font-medium text-muted-foreground"
      >
        <Trophy className="size-3 text-primary/80" aria-hidden />
        {t}
      </span>
    ))}
  </div>
)

export const LeagueMarquee = () => (
  <div
    className="relative w-full overflow-hidden border-y border-border/50 bg-card/30 py-3"
    aria-label="Markets we cover"
  >
    <div className="mask-fade-x flex w-max animate-marquee-slow">
      <Strip />
      <Strip />
    </div>
  </div>
)
