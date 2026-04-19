import { useCallback, useEffect, useMemo, useState } from "react"
import {
  Check,
  Copy,
  Loader2,
  RefreshCw,
  ShieldCheck,
  UserCog,
  UserX,
  X,
} from "lucide-react"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import {
  approveWaitlistEntry,
  fetchAdminUsers,
  fetchAdminWaitlist,
  rejectWaitlistEntry,
  setUserActive,
  setUserAdmin,
  type AuthUser,
  type WaitlistEntry,
} from "@/api/fetch"
import { useAuth } from "@/context/AuthContext"

const formatDate = (iso: string | null): string => {
  if (!iso) return "—"
  const d = new Date(iso)
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString()
}

const statusTone = (status: WaitlistEntry["status"]): string => {
  if (status === "pending") return "border-amber-500/30 bg-amber-500/10 text-amber-400"
  if (status === "approved") return "border-emerald-500/30 bg-emerald-500/10 text-emerald-400"
  if (status === "consumed") return "border-sky-500/30 bg-sky-500/10 text-sky-400"
  return "border-destructive/30 bg-destructive/10 text-destructive"
}

const buildInviteLink = (token: string): string => {
  const base = window.location.origin + window.location.pathname
  // HashRouter url: `#/login?invite=TOKEN`
  return `${base}#/login?invite=${encodeURIComponent(token)}`
}

export const AdminPage = () => {
  const { user } = useAuth()
  const [waitlist, setWaitlist] = useState<WaitlistEntry[]>([])
  const [users, setUsers] = useState<AuthUser[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [busyId, setBusyId] = useState<string | null>(null)
  const [copiedToken, setCopiedToken] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [w, u] = await Promise.all([fetchAdminWaitlist(), fetchAdminUsers()])
      setWaitlist(w)
      setUsers(u)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load admin data.")
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  const pending = useMemo(
    () => waitlist.filter((w) => w.status === "pending"),
    [waitlist],
  )
  const decided = useMemo(
    () => waitlist.filter((w) => w.status !== "pending"),
    [waitlist],
  )

  const handleApprove = async (entry: WaitlistEntry) => {
    const key = `wl:${entry.id}`
    setBusyId(key)
    setError(null)
    try {
      const updated = await approveWaitlistEntry(entry.id)
      setWaitlist((prev) => prev.map((w) => (w.id === entry.id ? updated : w)))
    } catch (err) {
      setError(err instanceof Error ? err.message : "Approval failed.")
    } finally {
      setBusyId(null)
    }
  }

  const handleReject = async (entry: WaitlistEntry) => {
    const key = `wl:${entry.id}`
    setBusyId(key)
    setError(null)
    try {
      const updated = await rejectWaitlistEntry(entry.id)
      setWaitlist((prev) => prev.map((w) => (w.id === entry.id ? updated : w)))
    } catch (err) {
      setError(err instanceof Error ? err.message : "Rejection failed.")
    } finally {
      setBusyId(null)
    }
  }

  const handleToggleActive = async (target: AuthUser) => {
    const key = `u-active:${target.id}`
    setBusyId(key)
    setError(null)
    try {
      await setUserActive(target.id, !target.is_active)
      setUsers((prev) =>
        prev.map((u) => (u.id === target.id ? { ...u, is_active: !target.is_active } : u)),
      )
    } catch (err) {
      setError(err instanceof Error ? err.message : "Update failed.")
    } finally {
      setBusyId(null)
    }
  }

  const handleToggleAdmin = async (target: AuthUser) => {
    const key = `u-admin:${target.id}`
    setBusyId(key)
    setError(null)
    try {
      await setUserAdmin(target.id, !target.is_admin)
      setUsers((prev) =>
        prev.map((u) => (u.id === target.id ? { ...u, is_admin: !target.is_admin } : u)),
      )
    } catch (err) {
      setError(err instanceof Error ? err.message : "Update failed.")
    } finally {
      setBusyId(null)
    }
  }

  const handleCopy = async (token: string) => {
    const link = buildInviteLink(token)
    try {
      await navigator.clipboard.writeText(link)
      setCopiedToken(token)
      setTimeout(() => setCopiedToken((t) => (t === token ? null : t)), 2000)
    } catch {
      setError("Could not copy invite link to clipboard.")
    }
  }

  return (
    <div className="mx-auto max-w-6xl px-4 py-8">
      <div className="mb-6 flex items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Admin</h1>
          <p className="text-sm text-muted-foreground">
            Review waitlist applications, issue invite links, and manage user access.
          </p>
        </div>
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={() => void load()}
          disabled={loading}
          className="gap-1.5"
        >
          {loading ? (
            <Loader2 className="size-3.5 animate-spin" aria-hidden />
          ) : (
            <RefreshCw className="size-3.5" aria-hidden />
          )}
          Refresh
        </Button>
      </div>

      {error && (
        <Alert variant="destructive" className="mb-6">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <div className="grid gap-6">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              Pending waitlist
              <Badge variant="secondary" className="font-mono">
                {pending.length}
              </Badge>
            </CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            {pending.length === 0 ? (
              <EmptyRow label={loading ? "Loading…" : "No pending applications."} />
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Username</TableHead>
                    <TableHead>Email</TableHead>
                    <TableHead>Reason</TableHead>
                    <TableHead>Submitted</TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {pending.map((entry) => {
                    const key = `wl:${entry.id}`
                    const busy = busyId === key
                    return (
                      <TableRow key={entry.id}>
                        <TableCell className="font-mono text-xs">
                          {entry.username}
                        </TableCell>
                        <TableCell className="text-xs">
                          {entry.email || "—"}
                        </TableCell>
                        <TableCell className="max-w-[320px] truncate text-xs text-muted-foreground">
                          {entry.reason || "—"}
                        </TableCell>
                        <TableCell className="text-xs text-muted-foreground">
                          {formatDate(entry.created_at)}
                        </TableCell>
                        <TableCell className="text-right">
                          <div className="flex justify-end gap-1.5">
                            <Button
                              type="button"
                              size="sm"
                              variant="default"
                              disabled={busy}
                              onClick={() => void handleApprove(entry)}
                              className="h-7 gap-1 px-2 text-xs"
                            >
                              {busy ? (
                                <Loader2 className="size-3 animate-spin" aria-hidden />
                              ) : (
                                <Check className="size-3" aria-hidden />
                              )}
                              Approve
                            </Button>
                            <Button
                              type="button"
                              size="sm"
                              variant="ghost"
                              disabled={busy}
                              onClick={() => void handleReject(entry)}
                              className="h-7 gap-1 px-2 text-xs text-muted-foreground hover:text-destructive"
                            >
                              <X className="size-3" aria-hidden />
                              Reject
                            </Button>
                          </div>
                        </TableCell>
                      </TableRow>
                    )
                  })}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Decided applications</CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            {decided.length === 0 ? (
              <EmptyRow label="No decided applications yet." />
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Username</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Invite link</TableHead>
                    <TableHead>Expires</TableHead>
                    <TableHead>Decided</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {decided.map((entry) => {
                    const token = entry.invite_token
                    const expired =
                      entry.invite_expires_at &&
                      new Date(entry.invite_expires_at).getTime() < Date.now()
                    const canCopy = entry.status === "approved" && token && !expired
                    return (
                      <TableRow key={entry.id}>
                        <TableCell className="font-mono text-xs">
                          {entry.username}
                        </TableCell>
                        <TableCell>
                          <span
                            className={`rounded border px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide ${statusTone(
                              entry.status,
                            )}`}
                          >
                            {entry.status}
                          </span>
                        </TableCell>
                        <TableCell className="text-xs">
                          {canCopy ? (
                            <Button
                              type="button"
                              size="sm"
                              variant="ghost"
                              onClick={() => void handleCopy(token!)}
                              className="h-7 gap-1 px-2 text-xs"
                            >
                              {copiedToken === token ? (
                                <Check className="size-3 text-emerald-400" aria-hidden />
                              ) : (
                                <Copy className="size-3" aria-hidden />
                              )}
                              {copiedToken === token ? "Copied" : "Copy invite link"}
                            </Button>
                          ) : entry.status === "consumed" ? (
                            <span className="text-muted-foreground">Used</span>
                          ) : expired ? (
                            <span className="text-muted-foreground">Expired</span>
                          ) : (
                            <span className="text-muted-foreground">—</span>
                          )}
                        </TableCell>
                        <TableCell className="text-xs text-muted-foreground">
                          {formatDate(entry.invite_expires_at)}
                        </TableCell>
                        <TableCell className="text-xs text-muted-foreground">
                          {formatDate(entry.decided_at)}
                        </TableCell>
                      </TableRow>
                    )
                  })}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              Users
              <Badge variant="secondary" className="font-mono">
                {users.length}
              </Badge>
            </CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            {users.length === 0 ? (
              <EmptyRow label={loading ? "Loading…" : "No users yet."} />
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Username</TableHead>
                    <TableHead>Email</TableHead>
                    <TableHead>Created</TableHead>
                    <TableHead>Last login</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {users.map((target) => {
                    const isSelf = user?.id === target.id
                    const activeKey = `u-active:${target.id}`
                    const adminKey = `u-admin:${target.id}`
                    return (
                      <TableRow key={target.id}>
                        <TableCell className="font-mono text-xs">
                          {target.username}
                          {target.is_admin && (
                            <Badge
                              variant="outline"
                              className="ml-1.5 border-primary/40 px-1 py-0 text-[9px] uppercase text-primary"
                            >
                              admin
                            </Badge>
                          )}
                          {isSelf && (
                            <span className="ml-1.5 text-[9px] uppercase text-muted-foreground">
                              you
                            </span>
                          )}
                        </TableCell>
                        <TableCell className="text-xs">
                          {target.email || "—"}
                        </TableCell>
                        <TableCell className="text-xs text-muted-foreground">
                          {formatDate(target.created_at)}
                        </TableCell>
                        <TableCell className="text-xs text-muted-foreground">
                          {formatDate(target.last_login_at)}
                        </TableCell>
                        <TableCell>
                          <span
                            className={`rounded border px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide ${
                              target.is_active
                                ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-400"
                                : "border-destructive/30 bg-destructive/10 text-destructive"
                            }`}
                          >
                            {target.is_active ? "active" : "disabled"}
                          </span>
                        </TableCell>
                        <TableCell className="text-right">
                          <div className="flex justify-end gap-1.5">
                            <Button
                              type="button"
                              size="sm"
                              variant="ghost"
                              disabled={busyId === adminKey || isSelf}
                              onClick={() => void handleToggleAdmin(target)}
                              className="h-7 gap-1 px-2 text-xs"
                              aria-label={
                                target.is_admin ? "Revoke admin" : "Grant admin"
                              }
                            >
                              {busyId === adminKey ? (
                                <Loader2 className="size-3 animate-spin" aria-hidden />
                              ) : target.is_admin ? (
                                <UserCog className="size-3" aria-hidden />
                              ) : (
                                <ShieldCheck className="size-3" aria-hidden />
                              )}
                              {target.is_admin ? "Revoke admin" : "Make admin"}
                            </Button>
                            <Button
                              type="button"
                              size="sm"
                              variant="ghost"
                              disabled={busyId === activeKey || isSelf}
                              onClick={() => void handleToggleActive(target)}
                              className="h-7 gap-1 px-2 text-xs text-muted-foreground hover:text-destructive"
                              aria-label={
                                target.is_active ? "Disable user" : "Re-enable user"
                              }
                            >
                              {busyId === activeKey ? (
                                <Loader2 className="size-3 animate-spin" aria-hidden />
                              ) : target.is_active ? (
                                <UserX className="size-3" aria-hidden />
                              ) : (
                                <Check className="size-3" aria-hidden />
                              )}
                              {target.is_active ? "Disable" : "Enable"}
                            </Button>
                          </div>
                        </TableCell>
                      </TableRow>
                    )
                  })}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

const EmptyRow = ({ label }: { label: string }) => (
  <div className="flex items-center justify-center px-4 py-10 text-sm text-muted-foreground">
    {label}
  </div>
)

export default AdminPage
