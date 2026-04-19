const KALSHI_BASE = "https://kalshi.com"

export type KalshiHrefInput = {
  ticker?: string | null
  kalshi_url?: string | null
}

/**
 * Returns a Kalshi URL that always opens a valid page.
 * Prefer the backend-provided `kalshi_url` when it looks like an absolute URL;
 * otherwise fall back to Kalshi search by ticker (guaranteed to resolve).
 */
export const kalshiOpenHref = ({
  ticker,
  kalshi_url: kalshiUrl,
}: KalshiHrefInput): string => {
  const url = (kalshiUrl ?? "").trim()
  if (url.startsWith("https://") || url.startsWith("http://")) {
    return url
  }
  const t = (ticker ?? "").trim()
  if (!t) {
    return `${KALSHI_BASE}/markets`
  }
  return `${KALSHI_BASE}/markets?search=${encodeURIComponent(t)}`
}
