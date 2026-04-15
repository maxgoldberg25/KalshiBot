export function fmtMoney(n: number | undefined): string {
  if (n === undefined || Number.isNaN(n)) return "—"
  const sign = n >= 0 ? "+$" : "-$"
  return sign + Math.abs(n).toFixed(2)
}

export function fmtTime(iso: string | undefined | null): string {
  if (!iso) return "—"
  return new Date(iso).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  })
}

export function fmtUptime(s: number | undefined): string {
  if (s === undefined) return "—"
  if (s < 60) return `${Math.floor(s)}s`
  if (s < 3600) return `${Math.floor(s / 60)}m`
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  return `${h}h ${m}m`
}
