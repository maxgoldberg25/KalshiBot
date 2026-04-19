# KalshiBot deployment

The app is two pieces:

1. **Frontend** — a static React/Vite SPA (in `web/`). Deploys to Vercel.
2. **Backend** — a long-running FastAPI server with a SQLite database and a
   background scan loop. Cannot run on Vercel; deploy to any host that can run
   a persistent Python process (Fly.io, Railway, Render, Hetzner, a VPS, etc.).

```
                 ┌──────────────────────────┐         ┌───────────────────────────────┐
  browser ───▶   │  Vercel (static SPA)     │  HTTPS  │  Your backend host            │
                 │  web/ → built → CDN      │────────▶│  FastAPI + SQLite + scanner   │
                 └──────────────────────────┘         └───────────────────────────────┘
```

Sessions are HTTP-only cookies set by the backend. The SPA sends
`credentials: "include"` on every request and reads `VITE_API_BASE_URL`
to know where to go.

---

## 1. Deploy the frontend to Vercel

### One-time setup

```bash
cd web
npx vercel@latest link
```

Pick (or create) a project. Accept the defaults — Vercel detects Vite from
`web/vercel.json`.

### Environment variables (Vercel → Project Settings → Environment Variables)

| Key                   | Value                                                 | Notes                                                             |
| --------------------- | ----------------------------------------------------- | ----------------------------------------------------------------- |
| `VITE_API_BASE_URL`   | `https://api.your-domain.com` (no trailing slash)     | Origin of the backend. Set for *Production* and *Preview*.         |

### Deploy

```bash
# from inside web/
npx vercel@latest            # preview deploy
npx vercel@latest --prod     # production deploy
```

Vercel serves the SPA with the security headers declared in `web/vercel.json`
(HSTS, XFO, XCTO, Referrer-Policy, Permissions-Policy).

---

## 2. Deploy the backend

The backend uses SQLite on local disk and runs a background scan loop, so
**pick a host with a persistent filesystem and a single always-on process**.

### Required environment variables (all prefixed with `KALSHI_ODDS_`)

| Key                                    | Example                                           | Why it matters                                                                                                      |
| -------------------------------------- | ------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------- |
| `KALSHI_ODDS_KALSHI_API_KEY_ID`        | `abc123…`                                         | Kalshi API key.                                                                                                     |
| `KALSHI_ODDS_KALSHI_PRIVATE_KEY_PATH`  | `/data/kalshi.pem`                                | Path to Kalshi RSA private key inside the container.                                                                |
| `KALSHI_ODDS_ODDS_API_KEY`             | `…`                                               | Odds API key.                                                                                                       |
| `KALSHI_ODDS_DATABASE_URL`             | `sqlite+aiosqlite:///data/kalshi_odds.db`         | Persistent path (e.g. a Fly volume). **Do not** keep the default if your FS is ephemeral.                           |
| `KALSHI_ODDS_CORS_ORIGINS`             | `https://your-frontend.vercel.app`                | Comma-separated. Must exactly match the Vercel frontend origin(s).                                                  |
| `KALSHI_ODDS_SESSION_COOKIE_SECURE`    | `true`                                            | **Required in production.** Makes the session cookie HTTPS-only.                                                    |
| `KALSHI_ODDS_SESSION_COOKIE_SAMESITE`  | `none`                                            | Use `none` when the frontend and backend are on different origins (Vercel ↔ your backend). Requires `secure=true`. |
| `KALSHI_ODDS_PUBLIC_REGISTRATION_ENABLED` | `false`                                        | **Default false.** Keeps registration invite-only.                                                                  |
| `KALSHI_ODDS_ADMIN_BOOTSTRAP_USERNAMES`| `yourname`                                        | Comma-separated usernames auto-promoted to admin on startup (once the user exists).                                 |
| `KALSHI_ODDS_INVITE_TTL_HOURS`         | `168`                                             | Invite lifetime in hours. 168 = 7 days.                                                                             |
| `KALSHI_ODDS_IP_HASH_SECRET`           | `openssl rand -hex 32`                            | Salt used to hash client IPs in the waitlist table. Rotate = resets rate-limit memory.                              |
| `KALSHI_ODDS_DASHBOARD_PORT`           | `8080`                                            | Port the server listens on.                                                                                         |

The server exposes:

- `python -m kalshi_odds.dashboard.server` (uses `main()`), or
- `uvicorn kalshi_odds.dashboard.server:create_app --factory --host 0.0.0.0 --port 8080`

### Minimal Fly.io example

```toml
# fly.toml
app = "kalshibot-api"
primary_region = "iad"

[build]
  dockerfile = "Dockerfile"

[[mounts]]
  source = "kalshibot_data"
  destination = "/data"

[http_service]
  internal_port = 8080
  force_https = true
  auto_stop_machines = false
  auto_start_machines = true
  min_machines_running = 1
```

```dockerfile
# Dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir .
ENV KALSHI_ODDS_DATABASE_URL=sqlite+aiosqlite:///data/kalshi_odds.db
EXPOSE 8080
CMD ["uvicorn", "kalshi_odds.dashboard.server:create_app", "--factory", "--host", "0.0.0.0", "--port", "8080"]
```

---

## 3. First admin account

Registration is invite-only by default. To bootstrap the first admin:

1. Set `KALSHI_ODDS_ADMIN_BOOTSTRAP_USERNAMES=yourname` in the backend env.
2. Temporarily set `KALSHI_ODDS_PUBLIC_REGISTRATION_ENABLED=true`, deploy,
   and create the account named `yourname` from the SPA.
3. Set `KALSHI_ODDS_PUBLIC_REGISTRATION_ENABLED=false` and redeploy.
4. On startup, the bootstrap list auto-promotes `yourname` to admin. Log in
   and you'll see the **Admin** nav link.

From then on:

- Visitors go to **/login → Request access** and fill the waitlist form.
- You approve them on **/admin**, copy the invite link, and send it over.
- The invited user clicks the link and sets a password. Their account is
  bound to the exact username the admin approved.

---

## 4. Security posture (what's already done)

Backend:

- Passwords hashed with PBKDF2-SHA256 + per-user salt, 240k iterations.
- Session tokens: 256-bit `secrets.token_urlsafe`, stored server-side, sent
  via HTTP-only cookie. Configurable `Secure` + `SameSite`.
- Deactivated users can't log in and existing sessions are purged.
- Rate limits on `/api/auth/login`, `/api/auth/register`, `/api/waitlist`
  (per-IP, plus a per-username limiter on failed logins).
- CORS is an explicit allow-list (no `*`), credentials-aware.
- Security headers middleware: HSTS, `X-Frame-Options: DENY`,
  `X-Content-Type-Options: nosniff`, Referrer-Policy, Permissions-Policy,
  COOP/CORP, and a restrictive CSP.
- `/api/execute` and all `/api/admin/*` endpoints require `is_admin`.
- Waitlist IPs are stored hashed, never raw.
- Invite tokens are single-use (atomic consume) and time-limited.

Frontend:

- `credentials: "include"` on all fetches.
- Admin UI is gated by `RequireAdmin`, which re-checks server-side `is_admin`
  via `/api/auth/me`.
- `vercel.json` ships the same hardening headers at the edge.

Operational recommendations:

- Rotate `KALSHI_ODDS_IP_HASH_SECRET` if you suspect it's been leaked.
- Run the backend on HTTPS only (`SESSION_COOKIE_SECURE=true`).
- Periodically review `/admin` and disable accounts you don't recognize.
- Take regular snapshots of the SQLite volume.
