"""Customer simulator: places orders at random intervals on random open restaurants.

Examples (PowerShell, from the project folder, with the backend venv active):

    $env:LOADTEST_PASSWORD = "your-seed-password"
    python loadtest\\place_orders.py --users 20 --rate 60            # about 60 orders per minute
    python loadtest\\place_orders.py --users 50 --rate 300 --ramp 60 --duration 600

Arrivals are random (Poisson): --rate is the AVERAGE number of orders per minute. New orders
keep arriving even when the server is slow (open-loop), which is how real traffic behaves.
Run staff_worker.py in another terminal so the orders get accepted and moved along.
"""
from __future__ import annotations

import argparse
import asyncio
import random
import sys
import time

import httpx

from loadtest_common import (
    Account, SetupError, Stats, add_common_args, check_target, install_stop_handler, jitter,
    load_accounts, login_accounts, reporter, resolve_password, server_hint, sleep_or_stop,
)

ADDRESSES = [
    "12 Example Street", "48 Sample Road, Flat 3", "7 Fictional Avenue", "221 Demo Lane",
    "5 Test Close", "90 Imaginary Boulevard", "33 Placeholder Way", "16 Make-Believe Court",
]
NOTES = ["No onions please", "Ring the bell twice", "Leave at the door", "Extra napkins", "Allergic to nuts"]
FINAL = ("delivered", "cancelled")


class Catalog:
    """Open restaurants that have at least one available item. Refreshed from the API."""

    def __init__(self) -> None:
        self.restaurants: list[dict] = []

    async def refresh(self, base_url: str, stats: Stats, timeout: float) -> None:
        async with httpx.AsyncClient(base_url=base_url, timeout=timeout) as c:
            try:
                r = await c.get("/restaurants")
                if r.status_code != 200:
                    return
                found = []
                for rest in r.json():
                    if not rest["is_open"]:
                        continue
                    m = await c.get(f"/restaurants/{rest['id']}/menu")
                    if m.status_code != 200:
                        continue
                    items = [i for i in m.json()["items"] if i["is_available"]]
                    if items:
                        found.append({"id": rest["id"], "name": rest["name"], "items": items})
                self.restaurants = found
            except httpx.HTTPError:
                stats.count("catalog refresh failed")

    def pick(self, rng: random.Random) -> dict | None:
        return rng.choice(self.restaurants) if self.restaurants else None


def build_order(rng: random.Random, rest: dict, max_items: int) -> dict:
    lines = rng.sample(rest["items"], rng.randint(1, min(max_items, len(rest["items"]))))
    body = {
        "restaurant_id": rest["id"],
        "items": [{"menu_item_id": i["id"], "quantity": rng.choice([1, 1, 1, 2, 2, 3])} for i in lines],
        "delivery_address": rng.choice(ADDRESSES),
        "payment_method": rng.choice(["mock_cash", "mock_card"]),
    }
    if rng.random() < 0.2:
        body["note"] = rng.choice(NOTES)
    return body


async def follow_order(acct: Account, order_id: str, rng, args, stop: asyncio.Event) -> None:
    """After ordering: watch the tracker like the real page (every ~8 s), sometimes cancel."""
    will_cancel = rng.random() < args.cancel_prob
    if args.track_seconds <= 0 and not will_cancel:
        return
    cancel_after = rng.uniform(3, 12)
    t0 = time.monotonic()
    while not stop.is_set():
        elapsed = time.monotonic() - t0
        if will_cancel and elapsed >= cancel_after:
            await acct.request("POST", f"/orders/{order_id}/cancel", "POST cancel order")
            return
        if not will_cancel and elapsed >= args.track_seconds:
            return
        r = await acct.request("GET", f"/orders/{order_id}", "GET order (tracker poll)")
        if r is not None and r.status_code == 200 and r.json()["status"] in FINAL:
            return
        wait = jitter(8, 0.25, rng)
        if will_cancel:
            wait = min(wait, max(0.1, cancel_after - elapsed))
        if await sleep_or_stop(wait, stop):
            return


async def place_one(acct: Account, rest: dict, rng, args, stats: Stats, stop: asyncio.Event, followups: set) -> None:
    # like a real visitor: look at the menu (and their order history) first
    for i in range(args.reads_per_order):
        if i == 0:
            await acct.request("GET", f"/restaurants/{rest['id']}/menu", "GET menu", auth=False)
        else:
            await acct.request("GET", "/orders", "GET my orders", params={"limit": 10})
    await asyncio.sleep(rng.uniform(0.2, 1.5))  # a moment to decide
    resp = await acct.request("POST", "/orders", "POST order", json=build_order(rng, rest, args.max_items))
    if resp is not None and resp.status_code == 201:
        t = asyncio.create_task(follow_order(acct, resp.json()["id"], rng, args, stop))
        followups.add(t)
        t.add_done_callback(followups.discard)
    elif resp is not None and resp.status_code == 409:
        stats.count("orders refused by a business rule (409)")


async def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    add_common_args(ap)
    g = ap.add_argument_group("load shape")
    g.add_argument("--users", type=int, default=10, help="number of customer accounts to use (default %(default)s)")
    g.add_argument("--pick", choices=["first", "random"], default="first", help="which users from the seed: the first N or a random N")
    g.add_argument("--rate", type=float, default=30, help="average orders per MINUTE across all users (default %(default)s)")
    g.add_argument("--ramp", type=float, default=0, help="seconds to ramp from 0 up to the full rate")
    g.add_argument("--max-orders", type=int, default=0, help="stop after this many orders (0 = no limit)")
    g.add_argument("--max-inflight", type=int, default=200, help="skip new orders if this many are still waiting for a reply")
    b = ap.add_argument_group("how each simulated customer behaves")
    b.add_argument("--max-items", type=int, default=4, help="most different items in one order (default %(default)s)")
    b.add_argument("--reads-per-order", type=int, default=2, help="menu and history page views before each order (default %(default)s)")
    b.add_argument("--cancel-prob", type=float, default=0.05, help="chance a customer cancels soon after ordering (default %(default)s)")
    b.add_argument("--track-seconds", type=float, default=40, help="how long each customer watches the tracker, polling every ~8 s (0 = never)")
    b.add_argument("--catalog-refresh", type=float, default=60, help="seconds between reloading restaurants and menus (default %(default)s)")
    args = ap.parse_args()

    check_target(args.base_url, args.allow_remote)
    accounts = load_accounts(args.seed_file, args.accounts_file)
    if not accounts.customers:
        raise SetupError("No customer accounts found in the seed file.")
    rng = random.Random(args.random_seed)
    emails = list(accounts.customers)
    if args.pick == "random":
        rng.shuffle(emails)
    if args.users > len(emails):
        print(f"Only {len(emails)} customers in the seed, using all of them (asked for {args.users}).")
    emails = emails[: args.users]
    password = resolve_password(args)

    stats = Stats()
    stop = asyncio.Event()
    install_stop_handler(stop)

    users = await login_accounts(emails, password, args.base_url, stats, args.timeout, args.login_pace, "customer")
    if not users:
        raise SetupError("No customer could log in, so there is nothing to simulate.")
    stats = Stats()  # do not count the login phase in the load numbers

    # reuse the same Stats object inside accounts
    for u in users:
        u.stats = stats

    catalog = Catalog()
    await catalog.refresh(args.base_url, stats, args.timeout)
    if not catalog.restaurants:
        raise SetupError("No open restaurant with available items. Is the database seeded and the API running?")
    print(f"{len(users)} customers, {len(catalog.restaurants)} open restaurants, about {args.rate:g} orders/min. "
          f"Ctrl+C to stop.", flush=True)

    inflight: set[asyncio.Task] = set()
    followups: set[asyncio.Task] = set()
    sent = 0
    window = {"t": time.monotonic(), "sent": 0}

    def status_line() -> str:
        nonlocal window
        now = time.monotonic()
        per_min = (sent - window["sent"]) / max(now - window["t"], 1e-9) * 60
        window = {"t": now, "sent": sent}
        c = stats.classes("POST order")
        return (f"t={now - stats.t0:5.0f}s  sent={sent}  created={c['ok']}  refused={c['rejected']}  "
                f"429={c['rate_limited']}  5xx={c['server']}  net={c['network']}  "
                f"waiting={len(inflight)}  rate={per_min:4.0f}/min  p95={stats.p95_ms('POST order'):.0f}ms")

    async def refresh_catalog_loop() -> None:
        while not await sleep_or_stop(args.catalog_refresh, stop):
            await catalog.refresh(args.base_url, stats, args.timeout)

    background = [asyncio.create_task(reporter(args.report_every, status_line, stop)),
                  asyncio.create_task(refresh_catalog_loop())]

    start = time.monotonic()
    next_t = start
    while not stop.is_set():
        if args.duration and time.monotonic() - start >= args.duration:
            break
        if args.max_orders and sent >= args.max_orders:
            break
        elapsed = time.monotonic() - start
        factor = min(1.0, max(elapsed / args.ramp, 0.05)) if args.ramp > 0 else 1.0
        next_t += rng.expovariate(args.rate * factor / 60.0)
        now = time.monotonic()
        if next_t < now - 1:  # we fell behind: do not fire a catch-up burst
            next_t = now
        if await sleep_or_stop(next_t - now, stop):
            break
        if len(inflight) >= args.max_inflight:
            stats.count("skipped: too many orders still waiting")
            continue
        rest = catalog.pick(rng)
        if rest is None:
            stats.count("skipped: no open restaurant")
            continue
        sent += 1
        t = asyncio.create_task(place_one(rng.choice(users), rest, rng, args, stats, stop, followups))
        inflight.add(t)
        t.add_done_callback(inflight.discard)

    stop.set()
    if inflight:
        await asyncio.wait(inflight, timeout=20)
    # anything still running now is stuck: cancel it, wait for the cancellations, then close the clients
    leftovers = list(inflight) + list(followups) + background
    for t in leftovers:
        t.cancel()
    await asyncio.gather(*leftovers, return_exceptions=True)
    for u in users:
        await u.aclose()

    secs = time.monotonic() - start
    print("\n=== Customer simulation finished ===")
    print(f"ran {secs:.0f}s, {sent} orders attempted ({sent / max(secs, 1) * 60:.0f}/min), {stats.total_requests()} requests in total\n")
    print(stats.table())
    if stats.counters:
        print()
        for k, v in stats.counters.most_common():
            print(f"{k}: {v}")
    report = stats.instance_report()
    if report:
        print("\n" + report)
    print(server_hint(stats))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    except SetupError as e:
        print(f"\nError: {e}")
        sys.exit(2)
    except KeyboardInterrupt:
        sys.exit(130)
