import type { DashboardState, HealthResponse } from "./types"

export async function fetchState(): Promise<DashboardState> {
  const r = await fetch("/api/state")
  if (!r.ok) throw new Error(`state ${r.status}`)
  return r.json() as Promise<DashboardState>
}

export async function fetchHealth(): Promise<HealthResponse> {
  const r = await fetch("/api/health")
  if (!r.ok) throw new Error(`health ${r.status}`)
  return r.json() as Promise<HealthResponse>
}

export async function postScan(): Promise<{ ok: boolean; alerts?: number; error?: string }> {
  const r = await fetch("/api/scan", { method: "POST" })
  return r.json() as Promise<{ ok: boolean; alerts?: number; error?: string }>
}
