"""Shared pieces for the two load-test programs.

- reads user emails from your seed file (no passwords are stored anywhere in these files)
- one simulated browser session per user (Bearer token, silent refresh, re-login)
- request statistics: counts by HTTP status and latency percentiles
"""
from __future__ import annotations

import argparse
import ast
import asyncio
import getpass
import json
import os
import re
import signal
import subprocess
import sys
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import httpx

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SEED = PROJECT_ROOT / "backend" / "scripts" / "seed.py"
DEFAULT_ENV = PROJECT_ROOT / "backend" / ".env"
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
ROLES = ("customer", "staff")


# --------------------------------------------------------------------------- accounts
@dataclass
class Accounts:
    customers: list[str]
    staff: list[str]


class SetupError(Exception):
    """A problem the user can fix. Shown as a plain message, no traceback."""


def _extract_users(obj) -> list[tuple[str, str | None]]:
    """Pull (email, role) pairs out of a list of tuples or dicts."""
    found: list[tuple[str, str | None]] = []
    if not isinstance(obj, (list, tuple)):
        return found
    for item in obj:
        email = role = None
        if isinstance(item, dict):
            e = item.get("email")
            email = e if isinstance(e, str) else next(
                (v for v in item.values() if isinstance(v, str) and EMAIL_RE.match(v)), None)
            role = item.get("role")
        elif isinstance(item, (list, tuple)):
            strings = [x for x in item if isinstance(x, str)]
            email = next((x for x in strings if EMAIL_RE.match(x)), None)
            role = next((x for x in strings if x in ROLES), None)
        if email and EMAIL_RE.match(email):
            found.append((email.lower(), role if role in ROLES else None))
    return found


def _users_from_ast(path: Path) -> list[tuple[str, str | None]]:
    """Safest way: read literal lists from the file without running it."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    best: list[tuple[str, str | None]] = []
    for node in tree.body:
        value = None
        if isinstance(node, ast.Assign):
            value = node.value
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            value = node.value
        if value is None:
            continue
        try:
            users = _extract_users(ast.literal_eval(value))
        except Exception:
            continue  # not a plain literal (loops, f-strings, function calls)
        if len(users) > len(best):
            best = users
    return best


_RUNNER = r'''
import json, re, runpy, sys
EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
ns = runpy.run_path(sys.argv[1], run_name="loadtest_seed")
def users(obj):
    out = []
    if isinstance(obj, (list, tuple)):
        for it in obj:
            email = role = None
            if isinstance(it, dict):
                e = it.get("email")
                email = e if isinstance(e, str) else next((v for v in it.values() if isinstance(v, str) and EMAIL.match(v)), None)
                role = it.get("role")
            elif isinstance(it, (list, tuple)):
                s = [x for x in it if isinstance(x, str)]
                email = next((x for x in s if EMAIL.match(x)), None)
                role = next((x for x in s if x in ("customer", "staff")), None)
            if email and EMAIL.match(email):
                out.append([email.lower(), role if role in ("customer", "staff") else None])
    return out
best = []
for k, v in ns.items():
    if not k.startswith("_"):
        u = users(v)
        if len(u) > len(best):
            best = u
print("@@USERS@@" + json.dumps(best))
'''


def _users_from_running_seed(path: Path) -> list[tuple[str, str | None]]:
    """Fallback for seeds that build users with loops: run the file's top-level code
    (not its main()) in a separate process and read the lists it defines."""
    backend = path.resolve().parent.parent
    env = dict(os.environ)
    env["PYTHONPATH"] = str(backend) + os.pathsep + env.get("PYTHONPATH", "")
    try:
        proc = subprocess.run([sys.executable, "-c", _RUNNER, str(path)], cwd=backend, env=env,
                              capture_output=True, text=True, timeout=60)
    except subprocess.TimeoutExpired:
        raise SetupError(f"Reading {path.name} took too long.")
    for line in proc.stdout.splitlines():
        if line.startswith("@@USERS@@"):
            return [(e, r) for e, r in json.loads(line[len("@@USERS@@"):])]
    tail = (proc.stderr or "").strip().splitlines()[-1:] or ["no output"]
    raise SetupError(f"Could not read users from {path.name} ({tail[0][:150]}).")


def load_accounts(seed_file: Path | None, accounts_file: Path | None) -> Accounts:
    if accounts_file:
        try:
            data = json.loads(Path(accounts_file).read_text(encoding="utf-8"))
            return Accounts([e.lower() for e in data.get("customers", [])], [e.lower() for e in data.get("staff", [])])
        except Exception as e:
            raise SetupError(f"Could not read {accounts_file}: {e}")
    path = Path(seed_file or DEFAULT_SEED)
    if not path.exists():
        raise SetupError(f"Seed file not found: {path}\nUse --seed-file PATH, or --accounts-file with a JSON file "
                         '{"customers": [...], "staff": [...]}.')
    users = _users_from_ast(path) or _users_from_running_seed(path)
    if not users:
        raise SetupError(f"No users (email addresses) found in {path}.\n"
                         "Use --accounts-file with a JSON file {\"customers\": [...], \"staff\": [...]}.")
    customers: list[str] = []
    staff: list[str] = []
    guessed = 0
    for email, role in users:
        if role is None:
            guessed += 1
            role = "staff" if "staff" in email.split("@")[0] else "customer"
        target = staff if role == "staff" else customers
        if email not in target:
            target.append(email)
    if guessed:
        print(f"Note: {guessed} users had no role in the seed; guessed from the email name ('staff' in it = staff).")
    return Accounts(customers, staff)


# --------------------------------------------------------------------------- arguments
def add_common_args(p: argparse.ArgumentParser) -> None:
    g = p.add_argument_group("connection and accounts")
    g.add_argument("--base-url", default="http://localhost:8000", help="API address (default %(default)s)")
    g.add_argument("--seed-file", type=Path, default=None, help=f"seed file to read users from (default {DEFAULT_SEED.relative_to(PROJECT_ROOT)})")
    g.add_argument("--accounts-file", type=Path, default=None, help='JSON file {"customers": [...], "staff": [...]} instead of the seed file')
    g.add_argument("--password", default=None, help="password of the seed users. Better: set LOADTEST_PASSWORD, so it is not kept in your shell history")
    g.add_argument("--login-pace", type=float, default=0.1, help="seconds between logins at start (default %(default)s)")
    g.add_argument("--allow-remote", action="store_true", help="allow a base URL that is not localhost (only for servers you own)")
    r = p.add_argument_group("run control")
    r.add_argument("--duration", type=float, default=0, help="stop after this many seconds (0 = run until Ctrl+C)")
    r.add_argument("--random-seed", type=int, default=None, help="make the random choices repeatable")
    r.add_argument("--report-every", type=float, default=5, help="seconds between status lines (default %(default)s)")
    r.add_argument("--timeout", type=float, default=30, help="request timeout in seconds (default %(default)s)")


def check_target(base_url: str, allow_remote: bool) -> None:
    host = (urlparse(base_url).hostname or "").lower()
    if host not in ("localhost", "127.0.0.1", "::1") and not allow_remote:
        raise SetupError(f"Refusing to load-test {base_url}: it is not localhost.\n"
                         "Only run this against servers you own, then add --allow-remote.")


def resolve_password(args) -> str:
    pw = args.password or os.environ.get("LOADTEST_PASSWORD") or os.environ.get("SEED_USER_PASSWORD")
    if not pw and DEFAULT_ENV.exists():
        for line in DEFAULT_ENV.read_text(encoding="utf-8").splitlines():
            if line.startswith("SEED_USER_PASSWORD="):
                pw = line.split("=", 1)[1].strip().strip("\"'")
        if pw and pw.startswith("change-me"):
            pw = None
    if not pw and sys.stdin.isatty():
        pw = getpass.getpass("Password of the seed users (typing is hidden): ")
    if not pw:
        raise SetupError("No password. Set it first, for example in PowerShell:\n"
                         '  $env:LOADTEST_PASSWORD = "your-seed-password"')
    return pw


# --------------------------------------------------------------------------- timing helpers
def jitter(base: float, fraction: float, rng) -> float:
    """base seconds, randomly +/- fraction (0.5 = anywhere from half to one and a half times)."""
    return max(0.0, base * rng.uniform(1 - fraction, 1 + fraction))


async def sleep_or_stop(seconds: float, stop: asyncio.Event) -> bool:
    """Sleep, but wake early if stop is set. Returns True if we should stop."""
    try:
        await asyncio.wait_for(stop.wait(), timeout=max(0.0, seconds))
        return True
    except asyncio.TimeoutError:
        return False


def install_stop_handler(stop: asyncio.Event) -> None:
    loop = asyncio.get_running_loop()

    def handler(signum, frame):
        loop.call_soon_threadsafe(stop.set)
        signal.signal(signal.SIGINT, signal.SIG_DFL)  # a second Ctrl+C quits immediately
        print("\nStopping... finishing in-flight requests (Ctrl+C again to quit now)", flush=True)

    signal.signal(signal.SIGINT, handler)


async def reporter(interval: float, line_fn, stop: asyncio.Event) -> None:
    while not await sleep_or_stop(interval, stop):
        print(line_fn(), flush=True)


# --------------------------------------------------------------------------- stats
def _pct(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    v = sorted(values)
    return v[min(len(v) - 1, int(round(p / 100 * (len(v) - 1))))]


class Stats:
    def __init__(self) -> None:
        self.t0 = time.monotonic()
        self.codes: dict[str, Counter] = defaultdict(Counter)
        self.lat: dict[str, list[float]] = defaultdict(list)
        self.counters: Counter = Counter()
        self.instances: Counter = Counter()  # which backend instance answered (X-Instance header)

    def record(self, label: str, status: int, seconds: float) -> None:
        self.codes[label][status] += 1
        self.lat[label].append(seconds)

    def count(self, key: str, n: int = 1) -> None:
        self.counters[key] += n

    def classes(self, label: str) -> dict[str, int]:
        c = self.codes.get(label, Counter())
        out = {"ok": 0, "rejected": 0, "rate_limited": 0, "auth": 0, "missing": 0, "server": 0, "network": 0}
        for status, n in c.items():
            if 200 <= status < 300:
                out["ok"] += n
            elif status in (409, 422):
                out["rejected"] += n
            elif status == 429:
                out["rate_limited"] += n
            elif status in (401, 403):
                out["auth"] += n
            elif status == 404:
                out["missing"] += n
            elif status >= 500:
                out["server"] += n
            elif status == 0:
                out["network"] += n
        return out

    def instance_report(self) -> str:
        """Share of answers per backend instance. Only shown when the API sends X-Instance."""
        total = sum(self.instances.values())
        if not total:
            return ""
        lines = ["Requests answered per backend instance:"]
        for name, n in sorted(self.instances.items()):
            lines.append(f"  {name:20} {n:>7}  ({n / total * 100:4.1f}%)")
        return "\n".join(lines)

    def total_requests(self) -> int:
        return sum(sum(c.values()) for c in self.codes.values())

    def p95_ms(self, label: str) -> float:
        return _pct(self.lat.get(label, []), 95) * 1000

    def table(self) -> str:
        head = f"{'request':32} {'count':>7} {'2xx':>7} {'409/422':>8} {'429':>5} {'401/403':>8} {'404':>5} {'5xx':>5} {'net':>5} {'p50 ms':>8} {'p95 ms':>8} {'max ms':>8}"
        lines = [head, "-" * len(head)]
        for label in sorted(self.codes):
            c = self.classes(label)
            lat = self.lat[label]
            lines.append(f"{label[:32]:32} {sum(self.codes[label].values()):>7} {c['ok']:>7} {c['rejected']:>8} {c['rate_limited']:>5} "
                         f"{c['auth']:>8} {c['missing']:>5} {c['server']:>5} {c['network']:>5} "
                         f"{_pct(lat, 50) * 1000:>8.0f} {_pct(lat, 95) * 1000:>8.0f} {max(lat) * 1000 if lat else 0:>8.0f}")
        return "\n".join(lines)


# --------------------------------------------------------------------------- one simulated user
class LoginError(Exception):
    pass


class Account:
    """One user's browser session: own cookie jar, own access token."""

    def __init__(self, email: str, password: str, base_url: str, stats: Stats, timeout: float) -> None:
        self.email = email
        self._password = password
        self.stats = stats
        self.token: str | None = None
        self._lock = asyncio.Lock()
        self.client = httpx.AsyncClient(base_url=base_url, timeout=timeout,
                                        limits=httpx.Limits(max_connections=10, max_keepalive_connections=5))

    async def aclose(self) -> None:
        await self.client.aclose()

    async def _timed(self, method: str, path: str, label: str, auth: bool = True, **kw):
        headers = dict(kw.pop("headers", {}) or {})
        if auth and self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        t = time.perf_counter()
        try:
            resp = await self.client.request(method, path, headers=headers, **kw)
        except httpx.HTTPError as e:
            self.stats.record(label, 0, time.perf_counter() - t)
            self.stats.count(f"network error: {type(e).__name__}")
            return None
        self.stats.record(label, resp.status_code, time.perf_counter() - t)
        instance = resp.headers.get("x-instance")
        if instance and resp.status_code < 502:  # 502/503 come from the load balancer itself
            self.stats.instances[instance] += 1
        return resp

    async def login(self, log=print) -> None:
        told = False
        while True:
            resp = await self._timed("POST", "/auth/login", "login", auth=False,
                                     json={"email": self.email, "password": self._password})
            if resp is None:
                raise LoginError("cannot reach the server (is the API running?)")
            if resp.status_code == 200:
                self.token = resp.json()["access_token"]
                return
            if resp.status_code == 429:
                wait = float(resp.headers.get("retry-after", "10"))
                if not told:
                    log("  The API's login rate limit was hit, so logins are waiting. "
                        "Tip: set RATE_LIMIT_ENABLED=false in backend/.env while load testing, then restart the API.")
                    told = True
                await asyncio.sleep(wait + 0.5)
                continue
            if resp.status_code == 401:
                raise LoginError("wrong email or password (has this user been added by the seed script?)")
            if resp.status_code >= 500:
                raise LoginError(f"server error (HTTP {resp.status_code}). Is the database running? Check the API window for the reason")
            raise LoginError(f"unexpected HTTP {resp.status_code}")

    async def _renew(self, stale: str | None) -> bool:
        async with self._lock:
            if self.token != stale:
                return True  # another task already renewed it
            r = await self._timed("POST", "/auth/refresh", "refresh token", auth=False,
                                  headers={"X-Requested-With": "fetch"})
            if r is not None and r.status_code == 200:
                self.token = r.json()["access_token"]
                return True
            try:
                await self.login()
                return True
            except LoginError:
                return False

    async def request(self, method: str, path: str, label: str, **kw):
        """Like a browser: on 401, renew the token (refresh cookie, else log in again) and retry once."""
        stale = self.token
        resp = await self._timed(method, path, label, **kw)
        if resp is not None and resp.status_code == 401 and kw.get("auth", True) and stale is not None:
            if await self._renew(stale):
                resp = await self._timed(method, path, label, **kw)
        return resp


async def login_accounts(emails: list[str], password: str, base_url: str, stats: Stats,
                         timeout: float, pace: float, kind: str) -> list[Account]:
    ok: list[Account] = []
    failed: list[tuple[str, str]] = []
    print(f"Logging in {len(emails)} {kind} account(s)...", flush=True)
    for i, email in enumerate(emails, 1):
        acct = Account(email, password, base_url, stats, timeout)
        try:
            await acct.login()
            ok.append(acct)
        except LoginError as e:
            failed.append((email, str(e)))
            await acct.aclose()
            if "cannot reach" in str(e):
                break
        if i % 10 == 0 or i == len(emails):
            print(f"  {len(ok)} logged in, {len(failed)} failed", flush=True)
        await asyncio.sleep(pace)
    for email, why in failed[:5]:
        print(f"  could not log in {email}: {why}")
    if len(failed) > 5:
        print(f"  ...and {len(failed) - 5} more")
    return ok


def server_hint(stats: Stats) -> str:
    """Plain-language pointer when the API struggled during the run."""
    server = sum(stats.classes(label)["server"] for label in stats.codes)
    network = sum(stats.classes(label)["network"] for label in stats.codes)
    if not server and not network:
        return ""
    return (f"\nThe API had trouble: {server} server errors (5xx) and {network} requests with no answer (timeouts or dropped connections).\n"
            "Look in the API window (or logs\\instance-N.log) for the reason. A common one under load is 'QueuePool limit ... reached':\n"
            "the database connection pool is smaller than the number of requests handled at once. See loadtest/README.md.\n"
            "With the load balancer: a few 502/503 right when an instance crashes is expected (requests that were in flight on it).")
