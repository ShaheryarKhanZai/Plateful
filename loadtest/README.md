# Load simulation for Plateful

Two separate programs that make the app behave as if real people were using it:

| Program | Plays | What it does |
|---|---|---|
| `place_orders.py` | **Customers** | Logs in many customers, then places orders at random intervals on random open restaurants. Each customer also views menus, checks order history, watches the order tracker, and sometimes cancels. |
| `staff_worker.py` | **Restaurant staff** | Logs in staff accounts, finds new orders for their restaurants, then moves every order through `pending → confirmed → preparing → out_for_delivery → delivered`, waiting a random time between steps. |

Run both at once (two terminals). They share nothing except the API and the database.

User emails come from **your seed file** (`backend/scripts/seed.py` by default). The password is never stored in these files.

## One-time setup

From the project folder, in a terminal where the backend virtual environment is active:

```powershell
cd food-delivery
.\backend\.venv\Scripts\Activate.ps1
pip install -r loadtest\requirements.txt
```

Make sure the users exist in the database (run your seed script after you edit it):

```powershell
cd backend
python -m scripts.seed
cd ..
```

Set the seed users' password for this terminal only (nothing is written to disk):

```powershell
$env:LOADTEST_PASSWORD = "your-seed-password"
```

**Recommended while load testing:** open `backend\.env`, add `RATE_LIMIT_ENABLED=false`, and restart the API (`uvicorn app.main:app --port 8000`, without `--reload`). The API allows only 10 logins per minute per IP, so logging in 50 users takes about 5 minutes with the limiter on. The tools wait politely and still work, but it is slow. Turn the limiter back on afterwards.

## Run it

Terminal 1, customers:

```powershell
python loadtest\place_orders.py --users 20 --rate 60
```

Terminal 2, staff:

```powershell
python loadtest\staff_worker.py --staff 6
```

Press **Ctrl+C** in either terminal to stop. You get a full summary table.

## The settings you asked for

**Number of users and order rate** (`place_orders.py`):

| Option | Meaning | Default |
|---|---|---|
| `--users N` | How many customer accounts take part (first N from the seed, or `--pick random`) | 10 |
| `--rate R` | Average orders **per minute** across all users. Arrivals are random, so the gaps between orders vary | 30 |
| `--ramp S` | Seconds to climb from 0 up to the full rate | 0 |
| `--duration S` | Stop after S seconds (0 = until Ctrl+C) | 0 |
| `--max-orders N` | Stop after N orders | no limit |

**Staff** (`staff_worker.py`):

| Option | Meaning | Default |
|---|---|---|
| `--staff N` | How many staff accounts take part | all in the seed |
| `--delays a,b,c,d` | Base seconds an order waits before: confirmed, preparing, out_for_delivery, delivered | `6,10,20,30` |
| `--jitter J` | Random spread on every wait. `0.5` means anywhere from half to one and a half times the base | 0.5 |
| `--speed X` | Divide all waits by X (`3` = three times faster) | 1 |
| `--cancel-prob P` | Chance staff cancel an order instead of accepting or preparing it | 0.03 |
| `--poll-interval S` | Base seconds between checks for new orders (also jittered) | 3 |

Both programs: `--base-url`, `--seed-file`, `--accounts-file`, `--random-seed N` (repeatable runs), `--report-every S`. Use `--help` to see everything.

### Example scenarios

```powershell
# Quiet evening
python loadtest\place_orders.py --users 10 --rate 20
python loadtest\staff_worker.py --staff 4

# Dinner rush, building up over a minute, running 10 minutes
python loadtest\place_orders.py --users 50 --rate 300 --ramp 60 --duration 600
python loadtest\staff_worker.py --speed 3

# Very heavy (see the note on the connection pool below)
python loadtest\place_orders.py --users 30 --rate 600 --ramp 10 --duration 60
```

Match the staff speed to the order rate. If staff are slower than orders arrive, orders pile up in `pending`, which is also a useful thing to watch.

## How it behaves

**Customers**
- Orders arrive at random (Poisson) times. New orders keep arriving even if the server is slow, like real traffic.
- Each order picks a random user, a random **open** restaurant that has available items, 1 to 4 different items and a quantity of 1 to 3. Restaurants and menus are reloaded every 60 seconds, so closed restaurants or sold-out items are skipped.
- Before ordering, the customer views the menu and their order history. After ordering, they watch the tracker (checking about every 8 seconds, like the real page) and 5% cancel soon after.
- Like a browser, each user keeps a login, renews the access token when it expires, and logs in again if needed.

**Staff**
- Each staff member sees only the restaurants linked to them in the seed. Orders for a restaurant with no staff account stay `pending`.
- A staff member picks up leftover active orders when it starts, then watches for new `pending` ones.
- Every wait has random jitter, and a few orders are cancelled instead of accepted.

## Reading the output

A status line is printed every few seconds, then a table at the end with counts by response type and response times (p50 = typical, p95 = the slow 5%, max = slowest).

- `409/422` on **POST order** = the server refused it by a business rule (for example an item sold out).
- `409` on **POST cancel order** is normal: staff had already confirmed that order.
- `429` = the API's rate limiter said too many requests. `5xx` or `net` (no answer, timeout) = the **API struggled**. Check the API window.

## Safety

- The tools **refuse any address that is not localhost** unless you add `--allow-remote`. Only use that on servers you own.
- The password is read from `LOADTEST_PASSWORD` (or `--password`, but that stays in your shell history), or from `SEED_USER_PASSWORD` in `backend\.env`, or typed at a hidden prompt. It is never printed or saved.
- Load tests create real rows. Use a development database.

## Seed file reading

The tools read the users from your seed file in this order, so you rarely need to change anything:

1. Plain lists such as `USERS = [("a@x.com", "Name", "customer", []), ...]` (tuples or dictionaries) are read **without running the file**.
2. If your seed builds users with loops or f-strings, the file's top-level code is run once in a separate process and the lists it defines are read.
3. If neither works, give the accounts yourself with `--accounts-file users.json`:
   ```json
   {"customers": ["a@example.com", "b@example.com"], "staff": ["s1@example.com"]}
   ```

A user's role comes from the word `customer` or `staff` in its entry. If there is none, an email containing "staff" before the `@` counts as staff.

## Testing failover with the load balancer

Start the cluster (`python cluster\run_cluster.py --instances 3 --chaos-every 8`, see `cluster/README.md`) and run the same two programs against it. They already use `http://localhost:8000`, which is the load balancer.

- The summary of both programs now ends with **Requests answered per backend instance**: roughly equal shares show the load is spread.
- While instances are being killed, you should see only a handful of `5xx` (requests that were in flight on an instance at the moment it crashed) and no lost orders. In my test: 1 failed request out of about 1,900 during 9 crashes.
- To follow what happens, watch the cluster window (`CHAOS: killing instance-2`, `restarted`).

## Findings from testing (please read)

I tested both programs against the real API and PostgreSQL with 30 customers at about 600 orders per minute plus 8 staff. The **current backend** struggled, and the cause is in the app, not in these tools:

1. **The database connection pool is too small.** `app/database.py` uses SQLAlchemy's default of 5 connections plus 10 overflow, while FastAPI handles up to 40 requests at once. Extra requests wait for a free connection, and after 30 seconds they fail. Errors in the API log: `QueuePool limit of size 5 overflow 10 reached`.
2. **An extra hidden query.** After a status update the `updated_at` value is read again from the database while the response is built. When the pool is busy that read fails, and it shows up as a confusing `ResponseValidationError` and a 500.

Two small changes fix both. I tried them on a copy of the backend and re-ran the identical test:

| | Before | After |
|---|---|---|
| Orders created | 217 of 228 | 321 of 321 |
| All orders finished | no, staff stalled | yes (299 delivered, 22 cancelled) |
| 5xx or dropped requests | 11 and many errors | 0 |
| Slowest order request | 25.7 s | 1.2 s |
| API error log lines | 349 | 0 |

**`backend/app/database.py`**
```python
engine = create_engine(get_settings().database_url, pool_pre_ping=True, hide_parameters=True,
                       pool_size=20, max_overflow=20, pool_timeout=10)
```

**`backend/app/models.py`**, inside `class Order(Base):`
```python
    __mapper_args__ = {"eager_defaults": True}
```

PostgreSQL allows 100 connections by default, so 40 per API process is fine for one process. These numbers came from a small Linux sandbox, so expect different timings on your PC. The pattern (errors without the fix, none with it) is what matters.

## Troubleshooting

| You see | Do this |
|---|---|
| `wrong email or password` | Run `python -m scripts.seed` after editing the seed. Check `LOADTEST_PASSWORD`. |
| `cannot reach the server` | Start the API: `uvicorn app.main:app --port 8000` |
| `No open restaurant with available items` | Seed the database, or open at least one restaurant. |
| Logins are slow, or the tip about the login rate limit appears | Set `RATE_LIMIT_ENABLED=false` in `backend\.env`, restart the API. |
| Orders stay `pending` | The restaurant has no staff account in the seed, or `staff_worker.py` is not running. |
| `Could not read users from ...` | Use `--accounts-file` (see above). |
