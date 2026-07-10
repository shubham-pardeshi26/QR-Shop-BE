# QueueGames — Backend (`QR-Shop-BE`)

FastAPI + Supabase backend for **QueueGames**, a multi-tenant *"gamified queue"*
platform. Shoppers waiting in line scan a QR code, register with just a name +
phone, play a quick game, and win a discount coupon that staff redeem at the
counter — turning dead queue time into engagement, captured leads, and repeat
visits.

> The React frontend lives in a separate repository: **`QR-Shop-FE`**.

---

## Features

- **Multi-tenant SaaS** — one platform, many shops, with strict per-shop data isolation.
- **Three roles** — `super_admin` (platform owner) → `shop_admin` (shop owner) → `staff` (counter).
- **Pluggable games** — Spin-the-Wheel, Scratch Card (weighted-random) and Reflex Tap, Trivia Quiz (skill-based), plus two reserved placeholder slots. New games are a registry entry, not a rewrite.
- **Prize engine** — admin-configured prize tiers with weighted odds (random) or score bands (skill) and optional stock limits.
- **Coupons** — unique per-shop codes, expiry, single-use, staff validation & redemption.
- **Frictionless customer auth** — password-less, signed httpOnly session cookie (no Supabase user per shopper).
- **Anti-abuse** — per-phone coupon caps, IP rate limiting, and row-locked coupon/stock issuance (race-safe).
- **Analytics & leads** — per-shop dashboards + CSV lead export.
- **QR generation**, **Alembic migrations**, **RLS + access-token hook** SQL, and a **pytest** suite.

## Tech stack

FastAPI · SQLAlchemy 2.0 · Alembic · Pydantic v2 · python-jose · slowapi ·
segno · httpx · psycopg 3 · **Supabase** (Postgres / Auth / Storage).

---

## Prerequisites

- Python 3.12+
- A **Supabase** project (Postgres + Auth). Optionally the Supabase CLI for a fully local stack.

## Getting started

```bash
# 1. Environment
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. Configure (create backend/.env — see the table below)

# 3. Database schema
alembic revision --autogenerate -m "initial schema"   # first time only
alembic upgrade head

# 4. Supabase SQL (run in the Supabase SQL editor, in order):
#    - sql/access_token_hook.sql   then enable it under
#      Authentication → Hooks → "Custom Access Token"
#    - sql/rls_policies.sql        (defense-in-depth RLS)

# 5. Seed the platform super-admin
python -m scripts.seed_super_admin --email you@example.com --password '<strong-password>'

# 6. Run
uvicorn app.main:app --reload        # http://localhost:8000
```

- Interactive API docs: **http://localhost:8000/docs**
- Health: `GET /api/health` (liveness) · `GET /api/health/db` (DB connectivity)

### Environment variables (`backend/.env`)

| Variable | Required | Description |
|---|---|---|
| `ENVIRONMENT` | – | `development` (default) / `production` |
| `API_V1_PREFIX` | – | API path prefix (default `/api`) |
| `CORS_ORIGINS` | – | Comma-separated allowed origins (default `http://localhost:5173`) |
| `FRONTEND_BASE_URL` | – | Public SPA URL, used to build QR codes (default `http://localhost:5173`) |
| `DATABASE_URL` | ✅ | Supabase Postgres URI (Settings → Database → Connection string) |
| `SUPABASE_URL` | ✅ | Bare project URL `https://<ref>.supabase.co` (no `/rest/v1`) |
| `SUPABASE_ANON_KEY` | ✅ | Public anon key (Settings → API) |
| `SUPABASE_SERVICE_ROLE_KEY` | ✅ | Service-role key — **server only, never expose** |
| `SUPABASE_JWT_SECRET` | ✅* | JWT secret (only used for legacy HS256 projects; ES256 uses JWKS) |
| `CUSTOMER_JWT_SECRET` | ✅ | Long random string for customer session tokens (`openssl rand -hex 32`) |
| `CUSTOMER_SESSION_TTL_MINUTES` | – | Customer session lifetime (default `120`) |

> **Never commit `.env`.** It's git-ignored; it holds your DB password and the
> service-role key.

---

## API surface

All routes are under `/api`.

| Group | Auth | Examples |
|---|---|---|
| Health | none | `GET /health`, `GET /health/db` |
| Auth | staff/admin JWT | `GET /auth/me` |
| Public (customer) | session cookie | `GET /public/s/{slug}`, `POST /public/s/{slug}/register`, `POST /public/play/games/{id}/start`, `POST /public/play/sessions/{id}/complete`, `GET /public/play/coupons/mine` |
| Platform | `super_admin` | `CRUD /platform/shops`, `POST /platform/shops/{id}/admins`, `GET /platform/stats` |
| Shop-admin | `shop_admin` | `CRUD /admin/games`, `/admin/games/{id}/prizes`, `/admin/staff`, `GET /admin/qr`, `GET /admin/analytics`, `GET /admin/leads.csv` |
| Staff | `staff` / `shop_admin` | `POST /staff/coupons/validate`, `POST /staff/coupons/{id}/redeem`, `GET /staff/activity` |

### Authentication model

- **Staff/admin** authenticate via **Supabase Auth**. The backend verifies the
  Supabase JWT (ES256 via the project JWKS, or legacy HS256) and joins a
  `profiles` row for `role` + `shop_id`. Accounts are admin-provisioned (no
  public sign-up).
- **Customers** get a short-lived, password-less JWT in an httpOnly cookie
  minted by this API.
- Tenant scoping is enforced in the app layer; Supabase **RLS** is
  defense-in-depth (the backend connects with the service role and bypasses it).

---

## Testing

```bash
pip install -r requirements-dev.txt
pytest
```

Runs against in-memory SQLite (no Supabase needed) — covering the prize engine,
coupon issuance, token security, the customer play flow, admin CRUD/analytics,
tenant isolation, and staff redemption.

## Project structure

```
app/
  main.py            # app factory, router mounting, CORS, rate limiter
  core/              # config, db, security (JWT/JWKS), deps (auth+tenant), rate_limit, utils
  models/            # SQLAlchemy models (base.py + tables.py)
  schemas/           # Pydantic request/response models
  api/               # health, auth, platform, admin, public, staff routers
  games/             # registry (GAME_CATALOG) + prize resolvers
  services/          # coupon, provisioning, qr, supabase_admin
alembic/             # migrations
sql/                 # access_token_hook.sql, rls_policies.sql
scripts/             # seed_super_admin.py, get_token.py
tests/               # pytest suite
```

## Deployment notes

- Serve over **HTTPS** in production (required for secure cookies).
- Set a real `CUSTOMER_JWT_SECRET`; the app refuses to start customer sessions
  if it's empty and rejects the placeholder value in production.
- The in-memory rate limiter is per-process; use a shared store (e.g. Redis)
  behind multiple instances.
