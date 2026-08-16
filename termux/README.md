# Termux Deployment Guide

Host the drilling-costing app on your Android phone using Termux. The frontend runs
natively on Termux; the Python backend runs inside a **Debian container**
(proot-distro); the database lives in **Supabase** (free tier, PostgreSQL in the cloud).

## Architecture

```
Your phone                              Supabase (cloud)
┌──────────────────────────────────┐    ┌──────────────────┐
│ Termux                           │    │                  │
│  ├─ Nuxt frontend  :3000  ───────┼────┼──▶ PostgreSQL    │
│  │                               │    │   (free tier)    │
│  └─ proot-distro Debian          │    │                  │
│      └─ FastAPI backend :8000 ───┼────┼──▶               │
└──────────────────────────────────┘    └──────────────────┘
         ▲
         │  Wi-Fi / USB / localhost
    Browser (phone or LAN)
```

## Why the backend runs in Debian (pydantic-core fix)

Termux's Python is linked against Android's **bionic** libc, so PyPI has **no
prebuilt wheels** for it. Installing the backend natively makes pip compile every
C/Rust extension from source on the phone — most visibly `pydantic-core`
(a [known upstream issue](https://github.com/pydantic/pydantic-core/issues/855)),
which sits compiling for 15+ minutes or crashes out of memory. **This is the
"stuck while setting up the Python environment" symptom.** `uvicorn[standard]`
pulls in `watchfiles` (also Rust) and `uvloop`, so the hang would repeat even if
pydantic-core somehow succeeded.

The Debian container is a real **glibc** Linux user-space, so `pip install -e .`
inside it resolves **every** package in `backend/pyproject.toml` to an official
`manylinux_aarch64` wheel — nothing compiles, nothing hangs, and versions stay
exactly what the project pins. Termux's home directory is bind-mounted at the same
path inside Debian, so the repository you cloned is shared; the resulting
virtualenv (`backend/.venv`) is created and used **only** from inside Debian and
carries a `.debian-managed` marker file so the scripts can detect and safely
recreate stale native venvs (including `.venv-debian`, left behind by the old
broken deploy script — it is removed automatically).

## Requirements

- Termux (from **F-Droid**; not the Play Store version)
- Android 10+, **~3 GB free storage** (Debian rootfs + Python + Node modules)
- A free [Supabase](https://supabase.com) project
- Internet connection for the initial setup and data access

## Supabase setup (do this first)

1. Create a free project at [supabase.com](https://supabase.com)
2. Go to **Settings → Database → Connection string → URI**
3. Copy the **Transaction pooler** URL (port **6543**) — it works best on mobile
4. It looks like: `postgresql://postgres.xxxx:PASSWORD@aws-0-region.pooler.supabase.com:6543/postgres`

## First-time Termux setup

```bash
# 1. Install Termux from F-Droid, then open it and run:
pkg install -y git

# 2. Clone the repo
git clone https://github.com/praveen-christuraj/Well-Costing.git drilling-costing
cd drilling-costing

# 3. One-shot setup + start (recommended)
bash termux/deploy.sh
```

`deploy.sh` installs the Termux packages and the Debian container, creates the
Python environment inside Debian, writes both `.env` files, **prompts for your
Supabase DATABASE_URL** (you can paste it right there), runs migrations, builds
the frontend, and starts both servers.

Prefer the step-by-step flow? Use the individual scripts instead:

```bash
bash termux/setup.sh      # steps 1–6 (no server start)
nano backend/.env         # set DATABASE_URL
bash termux/migrate.sh    # run migrations
bash termux/start.sh      # start servers
```

The app is available at:
- **On this phone**: `http://localhost:3000`
- **On the same Wi-Fi network**: `http://<phone-LAN-IP>:3000`

## Daily usage

| Command | Purpose |
|---------|---------|
| `bash termux/start.sh` | Start backend + frontend |
| `bash termux/stop.sh` | Stop servers |
| `bash termux/update.sh` | `git pull` + reinstall deps + migrate |
| `bash termux/migrate.sh` | Run Alembic migrations only |
| `bash termux/deploy.sh` | One-shot: setup or update, then migrate + start |
| `bash termux/backend-exec.sh <cmd>` | Run any backend command inside Debian |
| `bash termux/share.sh` | Open a public tunnel URL for testers off your Wi-Fi |

## Connecting testers

Once `bash termux/deploy.sh` (or `start.sh`) finishes, it prints an access banner
with two URLs. Testers only ever need port **3000** — the frontend proxies all
`/api/v1/*` calls to the backend internally, so nobody connects to port 8000 directly.

### Testers on the same Wi-Fi network as your phone

Give them the LAN URL from the banner, e.g. `http://192.168.1.42:3000`. Any
device (laptop, tablet, another phone) on the same Wi-Fi/router can open that
URL directly in a browser — no install needed.

Requirements:
- Your phone stays connected to that Wi-Fi network
- Termux keeps running (don't force-close the app; see the wake-lock note below)
- Some routers isolate devices from each other ("AP/client isolation" or "guest
  network"); if testers can't connect, check that setting on the router or use
  a phone hotspot instead (see below) so everyone is on your phone's own network.

### Testers on a different network (mobile data, another Wi-Fi, anywhere)

Your LAN IP (`192.168.1.X`) is private and cannot be reached from outside your
router. Use one of these:

**Option A — Cloudflare Tunnel (recommended, works from anywhere):**

```bash
# In a SECOND Termux session (keep the app running in the first one):
bash termux/share.sh
```

This prints a public HTTPS URL like `https://random-words.trycloudflare.com`.
Share that with testers on any network. Keep `share.sh` running; press Ctrl+C
to stop sharing (the app itself keeps running).

**Option B — Personal hotspot:**
Turn on your phone's Wi-Fi hotspot and have testers join it directly — they're
then on your phone's own network and can use the LAN URL from the banner.

### Fully offline testing (no internet, no Wi-Fi at all)

You (or a tester) can still use the app entirely offline as long as you're on
the same device or a direct connection:
- **On the phone itself**: `http://localhost:3000` always works, no network needed.
- **Phone-to-phone/laptop with no router**: turn on the phone's hotspot (no
  internet required for the hotspot itself) and have the other device join it;
  then use the LAN URL. The app only needs *internet* for the Supabase database
  calls — the frontend and backend serving pages works over local Wi-Fi alone,
  but every API call (login, saving data, etc.) still requires the phone to
  reach Supabase online.

## After pushing code changes from your PC

```bash
bash termux/update.sh
```

This pulls the latest code, updates Python (inside Debian) and Node dependencies,
clears the Nuxt build output, runs any new migrations against Supabase. Restart with
`bash termux/start.sh` (or just run `bash termux/deploy.sh` which does both).

## Running backend commands manually (seed a user, shell, tests)

The backend venv cannot run under Termux's Python — use the wrapper:

```bash
# Open a shell inside Debian, in the backend directory:
bash termux/backend-exec.sh bash

# Seed a local user (SEED_USER_* vars are forwarded into the container):
SEED_USER_EMAIL=admin@example.com SEED_USER_PASSWORD=your-password \
SEED_USER_FULL_NAME="Termux Admin" \
  bash termux/backend-exec.sh python scripts/seed_user.py

# Alembic / pytest:
bash termux/backend-exec.sh alembic current
bash termux/backend-exec.sh pytest
```

Bare tool names (`python`, `alembic`, `pytest`, `uvicorn`) are resolved against
`backend/.venv/bin` automatically.

## Development mode (hot-reload frontend)

```bash
TERMUX_DEV=1 bash termux/start.sh
```

## Force a Nuxt rebuild

```bash
TERMUX_REBUILD=1 bash termux/start.sh
```

## Finding your phone's LAN IP

```bash
ip addr show wlan0 | grep 'inet '
```

## Logs

```
termux/backend.log   — Uvicorn / FastAPI output (from inside Debian)
termux/frontend.log  — Nuxt server output
termux/build.log     — Nuxt build output (first start or rebuild)
```

## Environment files

- `backend/.env` — auto-generated; you must set the Supabase `DATABASE_URL`
- `frontend/.env` — auto-generated

Neither file is committed to git.

## Troubleshooting

### `openssl: command not found` while configuring `backend/.env`

Termux provides the OpenSSL command in `openssl-tool` (the package named
`openssl` contains the libraries). Updated scripts install the right package and
can also generate the key with Node as a fallback. On an older checkout, repair
and resume setup with:

```bash
pkg install -y openssl-tool
bash termux/deploy.sh
```

The completed Python and Node installation steps are safe to run again.

### "Stuck" installing Python packages / pydantic-core build errors

That was the old native-Termux path. Delete any half-created environments and run
the Debian-based deploy:

```bash
rm -rf backend/.venv backend/.venv-debian termux/.setup_done
bash termux/deploy.sh
```

Inside Debian, `pip install` is **wheels-only** (`--only-binary :all:`): if a
prebuilt manylinux aarch64 wheel exists, pip downloads it; if one is missing,
pip **fails in seconds with a clear message** instead of compiling C/Rust on the
phone. A normal step-3 run finishes in a couple of minutes. The deploy script
also verifies the environment by importing `fastapi`, `pydantic` (+
`pydantic_core`), `sqlalchemy`, `uvicorn`, `alembic`, and `psycopg` right after
install, so problems surface immediately instead of at first run.

If step 3 still picks `.tar.gz` files and fails:

1. The install ignores your phone's pip config and uses **pypi.org** by default.
   If your network can't reach it (or you must use a mirror), point it at one
   that serves aarch64 wheels:
   ```bash
   TERMUX_PIP_INDEX_URL=https://pypi.org/simple bash termux/deploy.sh
   ```
2. Stale pip state can survive inside the container (it persists across
   `rm -rf backend/.venv`). Reset it once — the deploy script rebuilds
   everything automatically:
   ```bash
   proot-distro reset debian
   bash termux/deploy.sh
   ```
3. Native-code package versions are pinned in `termux/requirements-constraints.txt`
   to releases whose aarch64 wheels are confirmed on PyPI. If a future update
   hits a missing wheel, the fix is usually to bump (or temporarily relax) the
   pin there — the failure message will name the exact package and version, and
   the script prints the container's architecture, glibc version, and supported
   wheel tags so an outdated container (glibc older than a wheel's manylinux
   floor) is immediately recognizable. Every pinned native wheel resolves down
   to manylinux2014 (glibc 2.17): password hashing uses bcrypt exactly because
   `argon2-cffi-bindings` ships only manylinux_2_26/2_28 aarch64 wheels, which
   older containers cannot accept.

### Python version too new/old in Debian

The backend requires Python `>=3.12,<3.14` (see `backend/pyproject.toml`). If
Debian's system Python ever falls outside that window, the scripts automatically
install a standalone CPython 3.12 via [uv](https://astral.sh/uv) and build the
venv from it — no manual action needed.

### Nuxt build fails with esbuild errors

Some Termux/Node combinations cannot run esbuild's bundled binary. The scripts
detect this automatically: they install Termux's `esbuild` package and export
`ESBUILD_BINARY_PATH` so Vite uses it on subsequent builds. To force the fix
manually: `pkg install -y esbuild`.

### Port 3000 or 8000 already in use

```bash
bash termux/stop.sh
# or find the culprit:
ss -tlnp | grep -E ':(3000|8000)'
```

### Servers die when the phone sleeps

`start.sh` takes a Termux **wake lock** automatically (best effort). Also disable
battery optimization for Termux: Android Settings → Apps → Termux → Battery →
Unrestricted. Release the lock via `bash termux/stop.sh` (or `termux-wake-unlock`).

### Reset the Debian container completely

```bash
bash termux/stop.sh
proot-distro reset debian        # wipes the container (venv is recreated on next deploy)
rm -f termux/.setup_done
bash termux/deploy.sh
```

You can inspect the container at any time: `proot-distro login debian`.

## psycopg note

The project depends on the pure-Python `psycopg` driver (not `psycopg[binary]`), so
no libpq toolchain is needed anywhere — it connects to Supabase identically from
inside the Debian container. `backend/app/core/config.py` normalizes provider URLs
(`postgresql://` / `postgres://`) to `postgresql+psycopg://` automatically; the
deploy prompt also normalizes pasted URLs.
