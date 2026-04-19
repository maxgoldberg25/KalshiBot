import type { DashboardState, HealthResponse, TradesWatchResponse } from "./types"

const JSON_HEADERS = { "Content-Type": "application/json" } as const

// Base URL for the API. Empty string = same origin (dev proxy or combined deploy).
// In production on Vercel, set VITE_API_BASE_URL to the full backend origin
// (e.g. https://api.yourdomain.com). No trailing slash.
const RAW_BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? ""
export const API_BASE_URL = RAW_BASE.replace(/\/+$/, "")

const api = (path: string) => `${API_BASE_URL}${path}`

const BASE_INIT: RequestInit = { credentials: "include" }

const asApiError = async (r: Response, fallback: string): Promise<never> => {
  let detail = fallback
  try {
    const body = (await r.json()) as { detail?: string }
    if (body && typeof body.detail === "string") detail = body.detail
  } catch {
    // non-JSON body; keep fallback
  }
  throw new Error(detail)
}

export async function fetchState(): Promise<DashboardState> {
  const r = await fetch(api("/api/state"), BASE_INIT)
  if (!r.ok) throw new Error(`state ${r.status}`)
  return r.json() as Promise<DashboardState>
}

export async function fetchHealth(): Promise<HealthResponse> {
  const r = await fetch(api("/api/health"), BASE_INIT)
  if (!r.ok) throw new Error(`health ${r.status}`)
  return r.json() as Promise<HealthResponse>
}

export async function postScan(): Promise<{ ok: boolean; alerts?: number; error?: string }> {
  const r = await fetch(api("/api/scan"), { method: "POST", ...BASE_INIT })
  return r.json() as Promise<{ ok: boolean; alerts?: number; error?: string }>
}

export async function fetchTradesWatch(
  minNotional: number,
  fetchLimit: number,
): Promise<TradesWatchResponse> {
  const sp = new URLSearchParams({
    min_notional: String(minNotional),
    fetch_limit: String(fetchLimit),
  })
  const r = await fetch(api(`/api/trades/watch?${sp}`), BASE_INIT)
  if (!r.ok) throw new Error(`trades watch ${r.status}`)
  return r.json() as Promise<TradesWatchResponse>
}

// ── Auth ───────────────────────────────────────────────────────────────────

export type AuthUser = {
  id: number
  username: string
  email: string | null
  created_at: string | null
  last_login_at: string | null
  is_admin: boolean
  is_active: boolean
}

export type MeResponse = {
  authenticated: boolean
  user: AuthUser | null
}

export const fetchMe = async (): Promise<MeResponse> => {
  const r = await fetch(api("/api/auth/me"), BASE_INIT)
  if (!r.ok) throw new Error(`me ${r.status}`)
  return (await r.json()) as MeResponse
}

export const postLogin = async (
  username: string,
  password: string,
): Promise<AuthUser> => {
  const r = await fetch(api("/api/auth/login"), {
    method: "POST",
    ...BASE_INIT,
    headers: JSON_HEADERS,
    body: JSON.stringify({ username, password }),
  })
  if (!r.ok) return asApiError(r, "Login failed")
  const body = (await r.json()) as { user: AuthUser }
  return body.user
}

export type RegisterInput = {
  username: string
  password: string
  email?: string
  inviteToken: string
}

export const postRegister = async (input: RegisterInput): Promise<AuthUser> => {
  const r = await fetch(api("/api/auth/register"), {
    method: "POST",
    ...BASE_INIT,
    headers: JSON_HEADERS,
    body: JSON.stringify({
      username: input.username,
      password: input.password,
      invite_token: input.inviteToken,
      ...(input.email ? { email: input.email } : {}),
    }),
  })
  if (!r.ok) return asApiError(r, "Registration failed")
  const body = (await r.json()) as { user: AuthUser }
  return body.user
}

export const postLogout = async (): Promise<void> => {
  await fetch(api("/api/auth/logout"), { method: "POST", ...BASE_INIT })
}

// ── Waitlist ───────────────────────────────────────────────────────────────

export type WaitlistApplication = {
  username: string
  email?: string
  reason?: string
}

export type WaitlistEntry = {
  id: number
  username: string
  email: string | null
  reason: string | null
  status: "pending" | "approved" | "rejected" | "consumed"
  created_at: string
  decided_at: string | null
  decided_by_user_id: number | null
  invite_token: string | null
  invite_expires_at: string | null
}

export const postWaitlist = async (
  input: WaitlistApplication,
): Promise<{ ok: true; status: string; id?: number }> => {
  const r = await fetch(api("/api/waitlist"), {
    method: "POST",
    ...BASE_INIT,
    headers: JSON_HEADERS,
    body: JSON.stringify({
      username: input.username,
      ...(input.email ? { email: input.email } : {}),
      ...(input.reason ? { reason: input.reason } : {}),
    }),
  })
  if (!r.ok) return asApiError(r, "Could not submit request")
  return (await r.json()) as { ok: true; status: string; id?: number }
}

// ── Admin ──────────────────────────────────────────────────────────────────

export const fetchAdminWaitlist = async (
  statusFilter?: string,
): Promise<WaitlistEntry[]> => {
  const qs = statusFilter ? `?status_filter=${encodeURIComponent(statusFilter)}` : ""
  const r = await fetch(api(`/api/admin/waitlist${qs}`), BASE_INIT)
  if (!r.ok) return asApiError(r, "Could not load waitlist")
  return (await r.json()) as WaitlistEntry[]
}

export const approveWaitlistEntry = async (
  id: number,
): Promise<WaitlistEntry> => {
  const r = await fetch(api(`/api/admin/waitlist/${id}/approve`), {
    method: "POST",
    ...BASE_INIT,
  })
  if (!r.ok) return asApiError(r, "Could not approve entry")
  const body = (await r.json()) as { entry: WaitlistEntry }
  return body.entry
}

export const rejectWaitlistEntry = async (
  id: number,
): Promise<WaitlistEntry> => {
  const r = await fetch(api(`/api/admin/waitlist/${id}/reject`), {
    method: "POST",
    ...BASE_INIT,
  })
  if (!r.ok) return asApiError(r, "Could not reject entry")
  const body = (await r.json()) as { entry: WaitlistEntry }
  return body.entry
}

export const fetchAdminUsers = async (): Promise<AuthUser[]> => {
  const r = await fetch(api("/api/admin/users"), BASE_INIT)
  if (!r.ok) return asApiError(r, "Could not load users")
  return (await r.json()) as AuthUser[]
}

export const setUserActive = async (id: number, active: boolean): Promise<void> => {
  const r = await fetch(api(`/api/admin/users/${id}/active`), {
    method: "POST",
    ...BASE_INIT,
    headers: JSON_HEADERS,
    body: JSON.stringify({ value: active }),
  })
  if (!r.ok) return asApiError(r, "Could not update user")
}

export const setUserAdmin = async (id: number, isAdmin: boolean): Promise<void> => {
  const r = await fetch(api(`/api/admin/users/${id}/admin`), {
    method: "POST",
    ...BASE_INIT,
    headers: JSON_HEADERS,
    body: JSON.stringify({ value: isAdmin }),
  })
  if (!r.ok) return asApiError(r, "Could not update user")
}
