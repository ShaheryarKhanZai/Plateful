# Running several API instances behind a load balancer

Goal: run more than one copy of the backend, so that **if one crashes, the others keep serving everyone** and the crashed one comes back by itself.

```
Browser / frontend / load tests
            |
            |  http://localhost:8000   (the only address clients use)
            v
   +-------------------+
   |  Caddy            |   checks every instance every 2 s, retries a failed request
   |  load balancer    |   on another instance, hides crashed instances
   +---------+---------+
     |       |       |
     v       v       v
  :8001    :8002    :8003         copies of the same FastAPI app
 instance-1 instance-2 instance-3
     \       |       /
      v      v      v
        PostgreSQL                all state lives here (orders, users, login tokens)

   run_cluster.py  =  starts everything, restarts any process that dies
```

Why this works with this app: login uses a **stateless JWT** and refresh tokens are stored **in the database**, so any instance can answer any request. Nothing else is kept in a process's memory, except the rate limiter (see Limitations).

## What changed

**Backend files to update** (4 files, plus the settings example):

| File | Change |
|---|---|
| `backend/app/main.py` | New `/health/ready` check (can this instance reach the database?). Every response now carries an `X-Instance` header with the instance name. |
| `backend/app/config.py` | New settings: `DB_POOL_SIZE`, `DB_MAX_OVERFLOW`, `DB_POOL_TIMEOUT`, `INSTANCE_NAME`. |
| `backend/app/database.py` | Reads the pool settings. The default pool was 5 + 10 connections, too small for the 40 requests an instance handles at once. |
| `backend/app/models.py` | `Order` fetches `updated_at` in the same UPDATE (fixes a 500 error under heavy load). |
| `backend/.env.example` | Documents the new optional settings. |

**New files:**

| File | What it is |
|---|---|
| `cluster/run_cluster.py` | Starts N instances and Caddy, restarts anything that dies, optional crash demo |
| `cluster/README.md` | This guide |
| `cluster/backend_changes.patch` | The backend changes as a patch, for merging by hand if you changed those files |
| `backend/tests/test_health.py` | 6 tests for the health check, header and pool settings |

**Small updates:** `loadtest/*.py` (the summary now shows how many requests each instance answered), `loadtest/README.md`, `docs/ARCHITECTURE.md` (new section 12), `README.md`, `.gitignore`.

The **frontend needs no change**: it keeps calling `http://localhost:8000`, which is now the load balancer instead of one API.

## Setup (Windows, VS Code)

### 1. Install Caddy (the load balancer)

Caddy is a free, single-file program. No Docker, no account.

```powershell
winget install CaddyServer.Caddy
```

Then **close and reopen the terminal** and check it works:

```powershell
caddy version
```

No winget? Download `caddy_..._windows_amd64.zip` from https://github.com/caddyserver/caddy/releases, unzip it, and put `caddy.exe` in the `cluster` folder. `run_cluster.py` finds it there.

### 2. Copy the updated files into your project

Unzip `cluster-update.zip` over your project folder, keeping the folder names. If you edited any of the 4 backend files yourself, do not overwrite them. Apply the changes by hand from `cluster/backend_changes.patch` instead (it is short and readable), or run `git apply cluster/backend_changes.patch` if you use git.

### 3. Check the backend still passes its tests

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python -m pytest
```

Expected: 83 passed.

### 4. Stop any API you started by hand

Close the window running `uvicorn ... --port 8000`. The load balancer needs port 8000 for itself. (`run_cluster.py` refuses to start if a port is already taken, and tells you which.)

### 5. Start the cluster

From the project folder, with the backend virtual environment active:

```powershell
cd ..
python cluster\run_cluster.py --instances 3
```

You should see:

```
[12:00:01] Starting 3 API instances (database connections per instance: up to 26, total up to 78).
[12:00:05] instance-1 is ready on port 8001
...
  Load balancer:  http://localhost:8000        <- use this for the frontend and the load tests
```

Leave this window open. **Ctrl+C stops everything.** Windows may ask whether to allow Python or Caddy through the firewall. Everything listens on `127.0.0.1` only, so you can click Cancel.

### 6. Use the app as before

```powershell
cd frontend
npm run dev
```

Open http://localhost:5173. Nothing looks different, which is the point. Swagger is at http://localhost:8000/docs.

## See it work

**Which instance answered?** Every response has an `X-Instance` header:

```powershell
1..9 | ForEach-Object { curl.exe -s -i http://localhost:8000/health | Select-String "x-instance" }
```

You will see `instance-1`, `instance-2` and `instance-3` take turns.

**Crash one instance by hand.** Find and kill whatever listens on port 8002 (hard crash, no warning):

```powershell
Get-NetTCPConnection -LocalPort 8002 -State Listen | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }
```

Keep using the app. Nothing breaks. In the cluster window you see:

```
instance-2 STOPPED (exit code 1). Restarting in 2s. Traffic goes to the others.
instance-2 restarted (restart #1). It receives traffic again once its health check passes.
```

**Automatic crash demo.** Kill a random healthy instance every ~15 seconds (it never kills the last healthy one):

```powershell
python cluster\run_cluster.py --instances 3 --chaos-every 15
```

**Crash demo under load.** Start the cluster with `--chaos-every 8`, then in two other terminals run the load programs (see `loadtest/README.md`). Their summary shows how many requests each instance answered and how many failed:

```powershell
python loadtest\staff_worker.py --speed 4
python loadtest\place_orders.py --users 20 --rate 240 --duration 60
```

**Logs** are in the `logs` folder: one file per instance (`instance-1.log`, ...) and `caddy.log`. Follow one live:

```powershell
Get-Content logs\instance-1.log -Wait
```

**Load balancer view:** `curl.exe http://localhost:2019/reverse_proxy/upstreams` lists each instance with its current number of requests and failures.

## How failover works

1. **Active health check.** Caddy calls `/health/ready` on every instance every 2 seconds. That route runs `SELECT 1` on the database. An instance that is down, hung, or cannot reach the database gets no traffic until it answers `200` again.
2. **Passive check and retry.** If Caddy cannot connect to an instance while forwarding a request, it marks it unhealthy for 3 seconds and **tries the same request on another instance** (for up to 6 seconds). The user never notices.
3. **Restart.** `run_cluster.py` restarts a crashed instance after 2 seconds. If an instance crashes within 5 seconds of starting 5 times in a row (for example, a broken `.env`), it stops restarting it and prints the log lines, rather than looping forever.
4. **Rejoin.** The restarted instance gets traffic again after its first successful health check.
5. **Everyone down.** For up to 6 seconds Caddy holds requests waiting for an instance, then answers `502` with the same JSON error shape the API uses (`"The service is temporarily unavailable. Please try again in a moment."`, with CORS headers). The frontend shows that message and its **Try again** button.

**Database connections are shared fairly.** PostgreSQL allows 100 connections by default. `--db-connections 80` (default) is divided between instances: 3 instances get up to 26 each. If you run many instances, each gets fewer. Raise `max_connections` in PostgreSQL if you need more.

## Test results

Tested on Linux with Caddy v2.11.7, PostgreSQL 16 and 3 instances:

| Test | Result |
|---|---|
| Spread of 60 requests over 3 instances | 20 / 19 / 21 |
| Crash 1 instance, send 40 requests at once | 40 of 40 succeeded |
| Probe every 0.25 s for 15 s after a crash | 0 of 60 failed; instance back in rotation about 8 s after the crash |
| 9 hard crashes in 47 s while 20 customers and 8 staff ran (about 1,900 requests) | 1 request failed (one in flight on a crashing instance); no order lost; every order total matched its items |
| All 3 instances crashed at once | JSON error after 6 s of waiting, normal service again within about 6 s of the crash |
| Ctrl+C on the cluster | every API process and Caddy stopped |

I could not run this on Windows. The Windows-specific parts (process handling in `run_cluster.py`, the PowerShell commands above) follow standard behaviour but are untested.

## Limits (be aware)

- **A request that is being processed when its instance crashes fails.** Caddy only retries when it could not connect. It will not re-send a `POST /orders` that may already have run, because that could create a duplicate order. The user sees the error and presses **Try again**. In the chaos test that was 1 request in 1,900.
- **The rate limiter is per instance.** The limit is counted in each process's memory, so with 3 instances a user can make up to about 3 times more attempts per minute. Fix for real use: keep the counters in Redis or the database.
- **Caddy is now a single point of failure**, and so is PostgreSQL, and so is your computer. This protects against an API process crashing, not against the machine or the database failing. Production setups run two load balancers, a database standby, and instances on separate machines.
- **Python's thread limit still applies per instance** (40 simultaneous requests). More instances means more total capacity, but they share one database.
- **Not a Windows service.** If you log out or close the cluster window, everything stops.

## Options

| Option | Meaning | Default |
|---|---|---|
| `--instances N` | Number of API copies | 3 |
| `--lb-port P` | Port clients use | 8000 |
| `--base-port P` | First instance port (the others follow) | 8001 |
| `--policy` | `least_conn`, `round_robin`, `random`, `first` | `least_conn` |
| `--restart-delay S` | Seconds before a crashed instance restarts | 2 |
| `--chaos-every S` | Crash a random healthy instance about every S seconds (demo) | off |
| `--db-connections N` | Database connections shared by all instances | 80 |
| `--no-access-log` | Do not log every request (smaller logs) | off |
| `--caddy PATH` | Where `caddy` is | on PATH, or `cluster/caddy.exe` |
| `--frontend-origin` | Must match `FRONTEND_ORIGIN` in `backend/.env` | `http://localhost:5173` |

## Troubleshooting

| You see | Do this |
|---|---|
| `Caddy ... is not installed or not on PATH` | Install it (step 1) and open a **new** terminal, or put `caddy.exe` in `cluster\`. |
| `Port 8000 is already in use` | Stop the API or an old cluster that is still running. |
| `Every instance stopped right after starting` | The log lines printed above say why. Usually `backend/.env` is missing or PostgreSQL is not running. |
| `instance-N GAVE UP` | It crashed 5 times right after starting. Read `logs\instance-N.log`. |
| Login fails with 429 under load | Per-IP rate limit. Add `RATE_LIMIT_ENABLED=false` to `backend\.env` for load tests. |
| Browser shows "Can't reach the server" | The cluster is not running, or every instance is down. Check the cluster window. |
