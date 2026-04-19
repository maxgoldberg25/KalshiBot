# KalshiBot — Kalshi vs Sportsbook Odds Scanner

Automated edge detection between Kalshi prediction markets and traditional sportsbooks. Finds price discrepancies, ranks them by edge, and surfaces them in a real-time web dashboard. Ships with an **invite-only waitlist**, an **admin console**, a **live public-tape "Insider Watch"** feed, and a ready-to-deploy **Vercel frontend + standalone FastAPI backend** architecture. Optional Kalshi-side execution with manual sportsbook hedging.

> **Disclaimer:** This tool detects *theoretical* price discrepancies. Sportsbook execution is manual. No guarantees of profit. Use for research and informational purposes only.

---

## Quick Start

```bash
# 1. Create and activate virtual environment
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

# 2. Install
pip install -e ".[dev]"

# 3. Configure credentials
cp .env.example .env
# Edit .env — add Kalshi API keys and at least one odds API key

# 4. (Optional) Build the shadcn/React dashboard UI
cd web && npm install && npm run build && cd ..

# 5. Launch the dashboard
kalshi-odds dashboard
# Open http://127.0.0.1:8080
```

If `web/dist/` exists (after step 4), the server serves the **React + shadcn/ui** app (Hash routes: `/#/` home, `/#/scanner`, `/#/insider`, `/#/admin`, `/#/login`). Otherwise it falls back to the legacy single-file template at `src/kalshi_odds/dashboard/templates/index.html`.

**Dev (hot reload):** with the API on port 8080, run `cd web && npm run dev` (Vite proxies `/api` to `http://127.0.0.1:8080`). Open the URL Vite prints (usually `http://127.0.0.1:5173`).

The dashboard auto-maps Kalshi game contracts to sportsbook events on startup and begins scanning immediately.

> **First run, invite-only:** accounts are invite-only by default. To create the first admin, temporarily set `KALSHI_ODDS_PUBLIC_REGISTRATION_ENABLED=true`, register yourself, and set `KALSHI_ODDS_ADMIN_BOOTSTRAP_USERNAMES=<yourname>` — you'll be auto-promoted to admin on register/login. Then flip registration back to `false`. See [Accounts, waitlist & admin](#accounts-waitlist--admin).

---

## Architecture

```
src/kalshi_odds/
├── adapters/                  # External API integrations
│   ├── kalshi.py              # Kalshi REST API (RSA-PSS auth)
│   ├── odds_api.py            # The Odds API (primary, 500 req/month free)
│   ├── oddspapi.py            # OddsPapi (fallback, 250 req/month free)
│   ├── espn.py                # ESPN unofficial API (free, no key needed)
│   └── odds_provider.py       # FallbackOddsProvider — auto-routes across tiers
├── core/                      # Business logic
│   ├── automapper.py          # Auto-match Kalshi contracts to sportsbook events
│   ├── matcher.py             # Load & query mappings.yaml
│   ├── odds_math.py           # Odds conversion & vig removal
│   ├── scan_runner.py         # Scan cycle: fetch → match → compare
│   ├── scanner.py             # Edge detection, confidence scoring, alert generation
│   ├── sizing.py              # Kelly Criterion position sizing
│   └── portfolio.py           # Portfolio-level risk management
├── models/                    # Pydantic data models
│   ├── kalshi.py              # KalshiContract, KalshiTopOfBook
│   ├── odds.py                # OddsQuote, MarketType, OddsFormat
│   ├── probability.py         # NormalizedProb, VigMethod
│   └── comparison.py         # Alert, Opportunity, Direction, Confidence
├── dashboard/
│   ├── server.py              # FastAPI app — REST API + SPA serving + auth/admin/waitlist
│   └── templates/index.html   # Legacy SPA (Tabler + ApexCharts) if web/dist missing
├── web/                       # React + shadcn/ui dashboard (Vite) — deployable to Vercel
│   ├── src/pages/             # Home, Scanner, InsiderWatch, Login, Admin
│   ├── src/context/           # AuthContext (invite-only register, login, logout, refresh)
│   ├── src/components/auth/   # RequireAuth, RequireAdmin, UserMenu
│   ├── src/api/fetch.ts       # API client (uses VITE_API_BASE_URL for split deploys)
│   ├── vercel.json            # SPA rewrites + security headers
│   └── package.json
├── auth.py                    # PBKDF2 hashing, session tokens, cookies, rate limiters, IP hashing
├── config.py                  # Pydantic-settings (env-based config)
├── db.py                      # SQLite persistence via aiosqlite (users, sessions, waitlist, ...)
├── execution.py               # Kalshi order placement
└── cli.py                     # Typer CLI
```

Deployment docs live at [`DEPLOY.md`](./DEPLOY.md).

---

## Odds Provider Tiers

The system cascades automatically across three tiers — no manual intervention required:

| Tier | Provider | Cost | Notes |
|------|----------|------|-------|
| 1 | **The Odds API** | 500 req/month free | Primary. `list_events` (free endpoint) always tried first even when credits are exhausted |
| 2 | **OddsPapi** | 250 req/month free | Fallback when Odds API `get_odds` credits run out |
| 3 | **ESPN (unofficial)** | Free, no key | Final fallback. Real DraftKings moneyline odds. No rate limits |

`FallbackOddsProvider` handles routing transparently. `list_events` (used for auto-mapping) is always served from The Odds API since it's a free endpoint. `get_odds` (used for scanning) escalates through the tiers until one succeeds.

---

## Setup

### 1. Credentials

```bash
cp .env.example .env
```

**Required:**

```dotenv
KALSHI_ODDS_KALSHI_API_KEY_ID=your-kalshi-key-id
KALSHI_ODDS_KALSHI_PRIVATE_KEY_PATH=/path/to/kalshi_private.pem
```

**Odds API (at least one):**

```dotenv
# Tier 1 — https://the-odds-api.com/  (500 req/month free)
KALSHI_ODDS_ODDS_API_KEY=your-odds-api-key

# Tier 2 — https://oddspapi.io/  (250 req/month free, optional)
KALSHI_ODDS_ODDSPAPI_API_KEY=your-oddspapi-key
```

ESPN (Tier 3) requires no configuration — it is always available as a final fallback.

### 2. Generate Kalshi RSA Key

In your Kalshi account settings, generate an RSA key pair. Download the private key (`.pem`) and note the Key ID. Set both in `.env`.

### 3. Keep secrets out of git

`.env` and `*.pem` are already in `.gitignore`. Never commit them.

---

## Accounts, waitlist & admin

KalshiBot ships as a **closed platform**: no one can create an account without an admin-issued invite.

### Flow

1. A visitor opens `/login`, switches to the **Request access** tab, submits a username + email + optional reason.
2. The entry lands in the `waitlist` table (status `pending`). Per-IP rate limits and per-day caps apply.
3. An admin opens `/admin`, reviews the entry, and clicks **Approve** — the server generates a single-use, time-limited invite token (`KALSHI_ODDS_INVITE_TTL_HOURS`, default 7 days) and binds it to the approved username.
4. Admin clicks **Copy invite link** (e.g. `https://yoursite.com/#/login?invite=<TOKEN>`) and sends it to the user through whatever channel they prefer (email, Slack, DM).
5. The user clicks the link, lands in **Redeem invite** mode, picks a password, and their account is created and immediately logged in.
6. Invite tokens are atomically consumed — a link can only be used once and only for the exact username approved.

### Admin console (`/admin`)

Available only when `is_admin = true` on your user. The page shows three tables:

- **Pending waitlist** — approve or reject. Approve immediately generates an invite link.
- **Decided applications** — copy an existing invite link (only if still valid), see whether tokens are used/expired.
- **Users** — toggle `is_active` (disables login and kills existing sessions) and `is_admin`. You cannot disable or demote yourself.

### Bootstrapping the first admin

The first admin has to be created carefully because nothing grants admin by default.

1. In `.env` (or your deployment env), set:
   ```dotenv
   KALSHI_ODDS_PUBLIC_REGISTRATION_ENABLED=true
   KALSHI_ODDS_ADMIN_BOOTSTRAP_USERNAMES=yourname
   ```
2. Start the server and register the account named `yourname` from the SPA.
3. `yourname` is auto-promoted to admin on register (and re-checked on every login for safety).
4. Flip `KALSHI_ODDS_PUBLIC_REGISTRATION_ENABLED` back to `false` and redeploy.

From that point on, every new account goes through the waitlist.

### Security posture

Backend:

- **Passwords** — PBKDF2-SHA256, per-user 16-byte random salt, 240 000 iterations. Constant-time comparison.
- **Sessions** — 256-bit `secrets.token_urlsafe` tokens stored server-side, delivered via HTTP-only cookies. 14-day TTL, expired sessions purged on startup and on access.
- **Cookie flags** — configurable `Secure` and `SameSite` (`lax` by default; set `none` + `secure=true` for cross-origin Vercel / backend deployments).
- **Rate limiting** — in-process sliding-window limiters on `/api/auth/login` (per-IP + per-username on failures), `/api/auth/register`, and `/api/waitlist`.
- **CORS** — explicit allow-list only (never `*`), credentials-aware, only active when `KALSHI_ODDS_CORS_ORIGINS` is set.
- **Security headers middleware** on every response: HSTS (when `SESSION_COOKIE_SECURE=true`), `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: strict-origin-when-cross-origin`, `Permissions-Policy`, `Cross-Origin-Opener-Policy`, `Cross-Origin-Resource-Policy`, and a restrictive `Content-Security-Policy`.
- **Invite tokens** — 256-bit, time-limited, single-use (atomic `UPDATE … WHERE status='approved'`), bound to the approved username (and email if provided).
- **Disabled accounts** — cannot log in; existing sessions are invalidated on deactivation.
- **`/api/execute`** and all `/api/admin/*` endpoints require `is_admin`, not just authentication.
- **PII handling** — client IPs are hashed with an HMAC secret (`KALSHI_ODDS_IP_HASH_SECRET`) for the waitlist; raw IPs are never stored.
- **Response hygiene** — login errors are generic (`Invalid username or password`); waitlist submissions for already-existing usernames return success to avoid user enumeration.

Frontend:

- All fetches use `credentials: "include"`.
- `RequireAuth` / `RequireAdmin` wrappers re-check server-side state via `/api/auth/me` and redirect to `/login?next=…` when needed.
- `web/vercel.json` mirrors the same security headers at the CDN edge.
- No tokens are ever stored in `localStorage`; the only auth state the browser keeps is the HTTP-only cookie.

---

## Insider Watch (`/#/insider`)

A real-time, authenticated view of **unusually large prints on the public Kalshi tape**, designed as a surveillance-style feed. The page combines:

- **KPI strip** — total notional shown, unique markets, median / largest trade, net side imbalance, top-10 concentration share.
- **Notional flow over time** — adaptive time buckets (1 min → 1 h depending on span), stacked by tier (`major ≥ $10k`, `large ≥ $2.5k`, `notable`) with a cumulative line and a zoom brush.
- **Top markets Pareto** — notional by ticker with a cumulative concentration line.
- **Side imbalance** — diverging bars (YES vs NO) per ticker so you can spot one-sided flow.
- **Trade size distribution** — log-scaled histogram of trade notionals with cumulative density.
- **Trade rows** — each row shows ticker, market title, subtitle, tier badge, side, price, contracts, notional, % of open interest, plus a deep link to the Kalshi market.

Backend details:

- Pulls `GET /markets/trades` (public tape, no counterparty identification — this is not "insider" in the legal sense; it surfaces *sized* activity).
- Enriches each trade with market metadata (`/markets/{ticker}`) using an in-process TTL cache (120 s) and a per-request fetch cap to stay inside Kalshi rate limits.
- Endpoint: `GET /api/trades/watch?min_notional=250&fetch_limit=500` (auth required).

---

## Deployment

The app is **two pieces** and should be deployed as such:

| Piece | Where | Why |
|-------|-------|-----|
| **Frontend** — static React/Vite SPA (`web/`) | **Vercel** (CDN, preview URLs, instant rollbacks) | Perfect fit for a static SPA |
| **Backend** — FastAPI + SQLite + background scan loop | **Fly.io / Railway / Render / VPS** | Requires a persistent filesystem and an always-on process — **cannot** run on Vercel |

> **Important:** the backend maintains a long-running scan loop and writes to a local SQLite file. Vercel functions are short-lived and stateless, so the scanner would never run and every login/waitlist entry would vanish on the next cold start. Keep the backend on real infrastructure.

### Frontend on Vercel

```bash
cd web
npx vercel@latest link            # one-time
npx vercel@latest --prod          # deploy
```

Set these Vercel project env vars:

| Key | Example | Notes |
|-----|---------|-------|
| `VITE_API_BASE_URL` | `https://api.your-domain.com` | Origin of your backend (no trailing slash). Leave empty to use same-origin (e.g. when the Python server serves `web/dist`). |

`web/vercel.json` handles SPA rewrites and CDN-edge security headers (HSTS, XFO, XCTO, Referrer-Policy, Permissions-Policy, immutable caching for `/assets/*`).

### Backend (Fly.io / Railway / VPS)

Required env vars — all prefixed with `KALSHI_ODDS_`:

| Key | Example | Why |
|-----|---------|-----|
| `KALSHI_API_KEY_ID` / `KALSHI_PRIVATE_KEY_PATH` | `abc…` / `/data/kalshi.pem` | Kalshi API credentials. |
| `ODDS_API_KEY` | `…` | Odds API key. |
| `DATABASE_URL` | `sqlite+aiosqlite:///data/kalshi_odds.db` | **Must point at a persistent volume.** |
| `CORS_ORIGINS` | `https://your-frontend.vercel.app` | Comma-separated, exact origin match. Required when frontend and backend are on different domains. |
| `SESSION_COOKIE_SECURE` | `true` | Required in production (HTTPS-only cookie). |
| `SESSION_COOKIE_SAMESITE` | `none` | Use `none` for cross-origin Vercel ↔ backend. Requires `secure=true`. Use `lax` for same-origin. |
| `PUBLIC_REGISTRATION_ENABLED` | `false` | **Default false** — keeps signups invite-only. |
| `ADMIN_BOOTSTRAP_USERNAMES` | `yourname` | Comma-separated usernames auto-promoted to admin on startup and on their next login. |
| `INVITE_TTL_HOURS` | `168` | Invite link lifetime (default 7 days). |
| `IP_HASH_SECRET` | `openssl rand -hex 32` | Salt used to hash waitlist client IPs. |
| `DASHBOARD_PORT` | `8080` | Listen port. |

Start the server with:

```bash
uvicorn kalshi_odds.dashboard.server:create_app --factory --host 0.0.0.0 --port 8080
```

A Fly.io/Dockerfile template and a full walkthrough (including a worked first-admin bootstrap) live in [`DEPLOY.md`](./DEPLOY.md).

---

## Usage

### Dashboard (recommended)

```bash
kalshi-odds dashboard
```

Opens `http://127.0.0.1:8080`. The dashboard:
- Auto-maps Kalshi game contracts to sportsbook events on startup
- Runs continuous scans on `poll_interval_seconds` cadence (default: 60s)
- Displays ranked opportunities with edge bars, confidence badges, and Kelly sizing
- Supports inline dry-run and live execution (requires `KALSHI_ODDS_EXECUTION_ENABLED=true`)

### CLI

```bash
# One-shot scan — display ranked opportunities and exit
kalshi-odds scan --sport basketball_nba

# Continuous scanner loop (alerts only, no dashboard)
kalshi-odds run --sport basketball_nba,baseball_mlb

# Show recent alerts from the database
kalshi-odds show --last 50

# Manual execution of Kalshi leg
kalshi-odds execute --index 1 --shares 100 --dry-run

# Detailed breakdown for one opportunity
kalshi-odds detail --index 1

# Re-build mappings.yaml from Kalshi + Odds API
kalshi-odds sync-kalshi
kalshi-odds sync-odds --sport basketball_nba

# Show fuzzy-match candidates for manual review
kalshi-odds match-candidates --fuzzy
```

Multiple sports: pass a comma-separated list to `--sport`:

```bash
kalshi-odds scan --sport basketball_nba,baseball_mlb
```

Or set a default in `.env`:

```dotenv
KALSHI_ODDS_DEFAULT_SPORT=basketball_nba,baseball_mlb
```

---

## Auto-Mapping

The auto-mapper (`core/automapper.py`) connects Kalshi game contracts to sportsbook events automatically:

1. Fetches active Kalshi markets for a sport series (e.g., `KXNBAGAME`)
2. Fetches upcoming events from the odds provider
3. Parses team codes from Kalshi tickers (e.g., `KXNBAGAME-26APR10CLEATL-CLE` → teams `CLE`, `ATL`)
4. Matches by team name keywords (configurable in `automapper.py`)
5. Writes or merges into `mappings.yaml`

The dashboard re-maps automatically every 360 scans (~6 hours at default interval) and on startup. You can also trigger it manually from the dashboard UI or CLI.

### mappings.yaml format

```yaml
markets:
  - market_key: nba_20260410_cleatl_cle
    kalshi:
      contract_id: KXNBAGAME-26APR10CLEATL-CLE
      side: YES
    odds:
      event_id: 3fe42fd427985fed1fee7c2e58935a67
      market_type: h2h
      selection: Cleveland Cavaliers
```

---

## Edge Detection

Edge is computed in both directions for each (Kalshi contract, sportsbook quote) pair:

### Kalshi Cheap (buy YES on Kalshi, hedge on sportsbook)

```
edge = sportsbook_p_no_vig × (1 − friction) − (kalshi_yes_ask + slippage)
```

If positive, Kalshi is pricing the contract below the sportsbook's fair probability.

### Kalshi Rich (sell YES on Kalshi, bet on sportsbook)

```
edge = (kalshi_yes_bid − slippage) − sportsbook_p_no_vig × (1 − friction)
```

If positive, Kalshi is pricing the contract above the sportsbook's fair probability.

### Default buffers

| Parameter | Default | Description |
|-----------|---------|-------------|
| `kalshi_slippage_buffer` | 0.5% | Applied to Kalshi bid/ask prices |
| `sportsbook_execution_friction` | 1.0% | Accounts for sportsbook execution difficulty |
| `min_edge_bps` | 50 bps | Minimum edge to surface an alert |
| `min_liquidity` | 10 shares | Minimum Kalshi orderbook size |

### Signal mode

When Kalshi has no active market makers (empty orderbook), the scanner enters **signal mode**: it synthesizes a Kalshi price at ~90% of the sportsbook's no-vig probability — a common discount in thin markets to attract initial buyers. These opportunities are marked `~EST` in the dashboard with a full explanation. They are watchlist items only; do not execute them.

---

## Dashboard: How to read an opportunity row

The **Opportunities** table compares **Kalshi** prices to **sportsbook consensus** (after removing vig where applicable). Each row is one actionable *view* of a game side (for example, one team’s moneyline on Kalshi vs books).

### Badges before the game name

| Badge | Meaning |
|--------|--------|
| **`~EST`** | **Estimated / signal mode.** Kalshi’s order book for this contract was **empty** (no live YES/NO bids and asks). The scanner **did not** use a real Kalshi market price. It **simulated** a Kalshi YES price at about **90%** of the sportsbook’s fair (no-vig) probability so you can still see *where* the market might be mispriced **if** Kalshi opened near that level. **Do not treat this as tradable on Kalshi** until there is a real book — use it as a **watchlist / research** signal only. |
| **`THEODDSAPI`**, **`ODDSPAPI`**, **`ESPN`** | **Which feed supplied the sportsbook odds** used in this row’s math (after the app’s provider fallback chain). It does **not** mean “execute on that website”; it tells you **data provenance** for the fair-probability side. |

Rows **without** `~EST` use a **live Kalshi top-of-book** (real bid/ask). Those are the only rows where **Execute** is available (and only if execution is enabled in `.env`).

### Example row (decoded)

Example:

`~EST` `THEODDSAPI` — **AZ vs BAL** — **60.5¢** — **SELL Arizona Diamondbacks YES @ 76¢** — **Bet Arizona Diamondbacks ML on FanDuel** — **6** — **HIGH** — **1** — **1** — **watch only**

| Column (concept) | What it means in this example |
|------------------|--------------------------------|
| **Game** | Short label for the event (here, Arizona vs Baltimore). |
| **Edge** | **60.5¢** = modeled **edge per Kalshi share**, in cents, after the scanner’s buffers (slippage on Kalshi, friction on the sportsbook leg). Larger = more theoretical value *given the inputs*. |
| **Kalshi action** | **SELL … YES @ 76¢** = the modeled instruction on Kalshi: sell YES at **76¢** because Kalshi looks **rich** vs the book’s fair probability (Kalshi implied prob higher than fair). |
| **Hedge** | **Bet … ML on FanDuel** = the **manual** sportsbook leg that offsets the Kalshi position in theory (here, moneyline on FanDuel). You must place this yourself; the app does not auto-bet sportsbooks. |
| **Books** | **6** = how many distinct sportsbook quotes contributed to the consensus / comparison for that opportunity (more books → more stable consensus, all else equal). |
| **Conf** | **HIGH** = the scanner’s **confidence score** (edge size, freshness, liquidity, overround). **Note:** for `~EST` rows, Kalshi liquidity is **synthetic**, so treat confidence as **relative ranking**, not proof the trade is real. |
| **Liq** | Kalshi-side **size** (shares) at the relevant price. In **`~EST`** mode this is **not** real market depth — it is a small placeholder so the row can appear when `min_liquidity` would otherwise filter it out. |
| **Kelly** | Suggested **Kalshi share count** from the Kelly heuristic and your configured bankroll/caps. Again, for **`~EST`** this is **illustrative only** (no real book to fill against). |
| **Action** | **`watch only`** = **Execute is disabled** for this row because it is **estimated** (`~EST`). **Never** use execution on synthetic rows. |

**How to use this in practice**

1. **If you see `~EST`:** use the row to **monitor** mispricing vs books. When Kalshi **lists real quotes**, refresh / wait for the next scan — the same mapping may produce a **non-estimated** row with real **Liq** and **Execute** (if enabled).
2. **If there is no `~EST`:** the Kalshi prices are **live**; edge, Kelly, and Execute (if enabled) are based on the actual order book subject to your `min_edge_bps` / `min_liquidity` settings.
3. **Sportsbook leg:** always **manual**; use the **Hedge** text as guidance, then verify lines and limits on the book before betting.

---

## Confidence Scoring

Each alert is scored 0–1:

| Factor | Weight | Condition |
|--------|--------|-----------|
| Edge size | 0–0.4 | ≥200 bps → 0.4, ≥100 → 0.3, ≥50 → 0.2 |
| Data freshness | 0–0.3 | <10s → 0.3, <30s → 0.2, <60s → 0.1 |
| Kalshi liquidity | 0–0.2 | ≥100 shares → 0.2, ≥50 → 0.15, ≥20 → 0.1 |
| Overround | 0–0.1 | <1.03 → 0.1, <1.05 → 0.05 |

**Levels:** HIGH ≥ 0.75 · MED ≥ 0.50 · LOW < 0.50

---

## Position Sizing

Uses **fractional Kelly Criterion** (default: quarter-Kelly):

```
kelly_shares = (edge_bps / 10000) / kalshi_price × bankroll × kelly_fraction
```

Capped by `max_notional_per_trade` and available Kalshi liquidity. Configure via `.env`:

```dotenv
KALSHI_ODDS_BANKROLL_DOLLARS=500.0
KALSHI_ODDS_KELLY_FRACTION=0.25
KALSHI_ODDS_MAX_NOTIONAL_PER_TRADE=100.0
```

---

## Dashboard API

The dashboard exposes a REST API alongside the web UI. Auth column legend: `public` · `user` (any logged-in user) · `admin` (requires `is_admin`).

### Web & health

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/` | GET | public | Web dashboard (SPA) |
| `/api/health` | GET | public | System health: Kalshi, odds providers, database, scanner |
| `/api/config` | GET | public | Current configuration values |

### Auth

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/api/auth/me` | GET | public | Current user (or `{authenticated: false}` when anonymous) |
| `/api/auth/login` | POST | public | `{ username, password }` — sets session cookie; rate-limited |
| `/api/auth/register` | POST | public | `{ username, password, email?, invite_token }` — invite-gated unless `PUBLIC_REGISTRATION_ENABLED=true` |
| `/api/auth/logout` | POST | user | Invalidates server session and clears cookie |
| `/api/waitlist` | POST | public | `{ username, email?, reason? }` — creates a pending waitlist entry; rate-limited + per-IP daily cap |

### Scanner & execution

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/api/state` | GET | user | Full scanner state: opportunities, positions, P&L, settings |
| `/api/scan` | POST | user | Trigger a manual scan |
| `/api/auto-map` | POST | user | Re-build market mappings |
| `/api/alerts/recent` | GET | user | Last 20 alerts from database |
| `/api/trades/watch` | GET | user | Insider-Watch feed — enriched large prints from the public Kalshi tape |
| `/api/execute` | POST | **admin** | Place Kalshi order (requires `EXECUTION_ENABLED=true`) |

### Admin

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/api/admin/waitlist?status_filter=` | GET | admin | List waitlist entries (filter by `pending` / `approved` / `rejected` / `consumed`) |
| `/api/admin/waitlist/{id}/approve` | POST | admin | Approve entry — returns single-use invite token + expiry |
| `/api/admin/waitlist/{id}/reject` | POST | admin | Reject entry |
| `/api/admin/users` | GET | admin | List all users |
| `/api/admin/users/{id}/active` | POST | admin | `{ value: boolean }` — toggle `is_active` (false kills existing sessions) |
| `/api/admin/users/{id}/admin` | POST | admin | `{ value: boolean }` — toggle `is_admin` |

---

## Configuration Reference

All settings use the `KALSHI_ODDS_` prefix in `.env`:

| Setting | Default | Description |
|---------|---------|-------------|
| `KALSHI_API_KEY_ID` | — | Kalshi API Key ID |
| `KALSHI_PRIVATE_KEY_PATH` | — | Path to Kalshi RSA private key (.pem) |
| `ODDS_API_KEY` | — | The Odds API key |
| `ODDSPAPI_API_KEY` | — | OddsPapi key (optional fallback) |
| `DEFAULT_SPORT` | `basketball_nba` | Comma-separated sport keys to scan |
| `MIN_EDGE_BPS` | `50.0` | Minimum edge in basis points to surface |
| `MIN_LIQUIDITY` | `10` | Minimum Kalshi orderbook size (shares) |
| `POLL_INTERVAL_SECONDS` | `60.0` | Seconds between automatic scan cycles |
| `MAX_STALENESS_SECONDS` | `60.0` | Max data age before a quote is discarded |
| `KALSHI_SLIPPAGE_BUFFER` | `0.005` | Slippage buffer applied to Kalshi prices |
| `SPORTSBOOK_EXECUTION_FRICTION` | `0.01` | Friction buffer for sportsbook execution |
| `BANKROLL_DOLLARS` | `500.0` | Total bankroll for Kelly sizing |
| `KELLY_FRACTION` | `0.25` | Fraction of full Kelly to size |
| `MAX_NOTIONAL_PER_TRADE` | `100.0` | Dollar cap per single Kalshi order |
| `EXECUTION_ENABLED` | `false` | Must be `true` to place real Kalshi orders |
| `AUTO_EXECUTE_MIN_CONFIDENCE` | `high` | Minimum confidence for auto-execute in `run` loop |
| `MAPPING_FILE` | `mappings.yaml` | Path to market mapping file |
| `FUZZY_MATCH_ENABLED` | `false` | Enable fuzzy string matching for team names |
| `DASHBOARD_PORT` | `8080` | Port for the web dashboard |
| `DATABASE_URL` | `sqlite+aiosqlite:///kalshi_odds.db` | Database connection URL |
| `OUTPUT_JSONL` | `alerts.jsonl` | Path for alert output log |

### Auth, waitlist & web security

| Setting | Default | Description |
|---------|---------|-------------|
| `CORS_ORIGINS` | *(empty)* | Comma-separated exact-match allow-list. Leave empty when frontend and backend are the same origin. |
| `SESSION_COOKIE_SECURE` | `false` | Mark the session cookie as `Secure`. **Set to `true` in any HTTPS deployment.** |
| `SESSION_COOKIE_SAMESITE` | `lax` | `lax` (same-origin) / `strict` / `none` (cross-origin, requires `secure=true`). |
| `PUBLIC_REGISTRATION_ENABLED` | `false` | When `false`, `/api/auth/register` requires a valid invite token. |
| `ADMIN_BOOTSTRAP_USERNAMES` | *(empty)* | Comma-separated usernames auto-promoted to `is_admin=true` on startup and on register/login. |
| `INVITE_TTL_HOURS` | `168` | Invite link lifetime in hours (default 7 days). |
| `IP_HASH_SECRET` | *(default constant — override!)* | HMAC secret for hashing client IPs on waitlist entries. Set to a random 32-byte hex string in production. |

---

## Testing

```bash
# Run all tests
pytest

# With coverage report
pytest --cov=kalshi_odds --cov-report=term-missing

# Specific module
pytest tests/test_odds_math.py -v
pytest tests/test_scanner.py -v
```

Tests cover: odds conversion, vig removal, edge detection, confidence scoring, staleness/liquidity filtering, alert aggregation into opportunities.

---

## Output Files

| File | Description |
|------|-------------|
| `mappings.yaml` | Auto-generated market mapping (Kalshi ↔ sportsbook) |
| `alerts.jsonl` | Append-only log of all triggered alerts |
| `kalshi_odds.db` | SQLite database (alerts, positions, settled trades, users, sessions, waitlist) |
| `.last_opportunities.json` | Last scan's opportunities, used for dashboard persistence across restarts |

---

## Risk & Limitations

- **No sportsbook automation.** The sportsbook leg must be placed manually.
- **Execution risk.** Prices can move between detection and execution on either side.
- **Partial fills.** Kalshi liquidity may be lower than displayed.
- **Kalshi fees.** Approximately 7% (taker + maker + settlement).
- **Settlement rules.** Kalshi and sportsbooks may settle the same event differently.
- **Estimated signals.** When Kalshi has no active market makers, the system shows synthetic opportunities based on sportsbook odds. These are for monitoring only.

---

## Supported Sports

| Sport key | League | Kalshi series |
|-----------|--------|---------------|
| `basketball_nba` | NBA | `KXNBAGAME` |
| `baseball_mlb` | MLB | `KXMLBGAME` |
| `americanfootball_nfl` | NFL | `KXNFLGAME` |
| `basketball_ncaab` | NCAAB | `KXNCAABGAME` |

Add new sports by extending `SPORT_TO_SERIES` in `core/automapper.py` and `SPORT_TO_ESPN_PATH` in `adapters/espn.py`.

---

## FAQ

**Q: The dashboard shows `~EST` badges on all opportunities — what does that mean?**
A: Kalshi has no active market makers for those contracts (empty orderbook). The system synthesizes a price at ~90% of the sportsbook's fair value to show what an opportunity *would* look like. Do not execute these — they are watchlist items. When Kalshi opens a live market, real opportunities will appear automatically.

**Q: I see "Odds API quota exhausted" — what do I do?**
A: Your Odds API monthly credits are used up. Options: (1) wait for the monthly reset, (2) get a new free key at [the-odds-api.com](https://the-odds-api.com/), (3) add an `ODDSPAPI_API_KEY`. The ESPN fallback still provides basic NBA/NFL odds for free.

**Q: Why are there 0 opportunities with no `~EST` badges?**
A: Check: (1) `mappings.yaml` exists and has entries, (2) the odds provider returned data (check the credits display), (3) `min_edge_bps` isn't too high, (4) Kalshi liquidity meets `min_liquidity`.

**Q: Can this place bets on sportsbooks automatically?**
A: No. Only the Kalshi leg can be placed via API. Sportsbook execution is manual.

**Q: How do I add a new sport?**
A: Add the sport key → Kalshi series mapping in `core/automapper.py` (`SPORT_TO_SERIES`) and the team code → name keywords in `TEAM_CODE_KEYWORDS`. Also add the ESPN path in `adapters/espn.py` (`SPORT_TO_ESPN_PATH`).

**Q: Can I deploy the whole thing to Vercel?**
A: Only the frontend. Vercel's serverless runtime can't host the persistent scan loop or a local SQLite file. Deploy `web/` to Vercel and the FastAPI backend to Fly.io, Railway, Render, or a VPS. See [`DEPLOY.md`](./DEPLOY.md).

**Q: Registration returns "Registration is invite-only." — is this a bug?**
A: No — that's the default. To register, either (1) have an admin approve you on `/admin` and use the invite link they send, or (2) as the operator, set `KALSHI_ODDS_PUBLIC_REGISTRATION_ENABLED=true` temporarily to bootstrap your own account, then turn it back off.

**Q: How do I become admin?**
A: Add your username to `KALSHI_ODDS_ADMIN_BOOTSTRAP_USERNAMES` (comma-separated). On the next register/login the server auto-promotes matching usernames.

**Q: Why does login keep failing after deploying behind HTTPS?**
A: Your cookie is probably being blocked. In HTTPS/production set `KALSHI_ODDS_SESSION_COOKIE_SECURE=true`. If frontend and backend are on different origins (Vercel ↔ your backend), also set `KALSHI_ODDS_SESSION_COOKIE_SAMESITE=none` and add the frontend origin to `KALSHI_ODDS_CORS_ORIGINS`.

---

## License

For personal and educational use. Review each venue's API Terms of Service before deploying commercially.
