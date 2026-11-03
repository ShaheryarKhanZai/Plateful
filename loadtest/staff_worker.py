"""Staff simulator: staff accounts accept new orders and move them through every status,
waiting a random (jittered) time between steps.

Examples (PowerShell, from the project folder, with the backend venv active):

    $env:LOADTEST_PASSWORD = "your-seed-password"
    python loadtest\\staff_worker.py                       # use every staff account in the seed
    python loadtest\\staff_worker.py --staff 6 --speed 3   # 6 staff, everything 3x faster

Each order a staff member can see is walked through
    pending -> confirmed -> preparing -> out_for_delivery -> delivered
and each wait is  base delay x random(1 - jitter, 1 + jitter).
Orders for a restaurant that has no staff account in the seed will stay pending.
"""
from __future__ import annotations

import argparse
import asyncio
import random
import sys
import time

from loadtest_common import (
    Account, SetupError, Stats, add_common_args, check_target, install_stop_handler, jitter,
    load_accounts, login_accounts, reporter, resolve_password, server_hint, sleep_or_stop,
)

FLOW = {"pending": "confirmed", "confirmed": "preparing", "preparing": "out_for_delivery", "out_for_delivery": "delivered"}
STEPS = list(FLOW)  # the status an order is in BEFORE each step
ACTIVE = tuple(STEPS)


class Worker:
    """One staff member: finds orders for their restaurants and drives each one forward."""

    def __init__(self, acct: Account, args, delays: dict[str, float], rng: random.Random, stats: Stats, stop: asyncio.Event) -> None:
        self.acct, self.args, self.delays, self.rng, self.stats, self.stop = acct, args, delays, rng, stats, stop
        self.driving: set[str] = set()
        self.tasks: set[asyncio.Task] = set()
        self.full_poll = True  # first poll looks at every active status, to pick up leftovers

    async def list_status(self, status: str) -> list[dict]:
        out: list[dict] = []
        for page in range(self.args.max_pages):
            r = await self.acct.request("GET", "/staff/orders", f"GET staff orders ({status})",
                                        params={"status": status, "limit": 100, "offset": page * 100})
            if r is None or r.status_code != 200:
                break
            batch = r.json()
            out += batch
            if len(batch) < 100:
                break
        return out

    async def poll_loop(self) -> None:
        while not self.stop.is_set():
            statuses = ACTIVE if (self.full_poll or self.args.poll_all) else ("pending",)
            self.full_poll = False
            for status in statuses:
                for order in await self.list_status(status):
                    if order["id"] not in self.driving:
                        self.driving.add(order["id"])
                        self.stats.count("orders picked up")
                        t = asyncio.create_task(self.drive(order))
                        self.tasks.add(t)
                        t.add_done_callback(self.tasks.discard)
            if await sleep_or_stop(jitter(self.args.poll_interval, self.args.jitter, self.rng), self.stop):
                return

    async def drive(self, order: dict) -> None:
        order_id, status = order["id"], order["status"]
        try:
            while status in FLOW and not self.stop.is_set():
                if await sleep_or_stop(jitter(self.delays[status], self.args.jitter, self.rng), self.stop):
                    return
                target = FLOW[status]
                if status in ("pending", "confirmed") and self.rng.random() < self.args.cancel_prob:
                    target = "cancelled"
                r = await self.acct.request("PATCH", f"/staff/orders/{order_id}/status", f"PATCH status -> {target}",
                                            json={"status": target})
                if r is None:
                    return
                if r.status_code == 200:
                    status = r.json()["status"]
                    self.stats.count(f"order now {status}")
                    continue
                if r.status_code == 409:
                    # someone else changed it first (a customer cancel, or another staff member)
                    self.stats.count("order changed by someone else (409)")
                    self.full_poll = True
                return
        finally:
            self.driving.discard(order_id)


async def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    add_common_args(ap)
    g = ap.add_argument_group("staff behaviour")
    g.add_argument("--staff", type=int, default=0, help="number of staff accounts to use (default: all in the seed)")
    g.add_argument("--pick", choices=["first", "random"], default="first", help="which staff from the seed: the first N or a random N")
    g.add_argument("--delays", default="6,10,20,30",
                   help="base seconds an order waits before: confirmed, preparing, out_for_delivery, delivered (default %(default)s)")
    g.add_argument("--jitter", type=float, default=0.5, help="random spread on every wait, 0.5 = from half to 1.5 times (default %(default)s)")
    g.add_argument("--speed", type=float, default=1.0, help="divide all delays by this (2 = twice as fast)")
    g.add_argument("--cancel-prob", type=float, default=0.03, help="chance staff cancel an order instead of accepting or preparing it (default %(default)s)")
    g.add_argument("--poll-interval", type=float, default=3, help="base seconds between checks for new orders (default %(default)s)")
    g.add_argument("--poll-all", action="store_true", help="check every active status on every poll (more load, catches more)")
    g.add_argument("--max-pages", type=int, default=5, help="pages of 100 orders read per status (default %(default)s)")
    args = ap.parse_args()

    check_target(args.base_url, args.allow_remote)
    try:
        base = [float(x) for x in args.delays.split(",")]
        if len(base) != 4 or min(base) < 0:
            raise ValueError
    except ValueError:
        raise SetupError("--delays needs four numbers like 6,10,20,30")
    if args.speed <= 0:
        raise SetupError("--speed must be above 0")
    delays = {status: base[i] / args.speed for i, status in enumerate(STEPS)}

    accounts = load_accounts(args.seed_file, args.accounts_file)
    if not accounts.staff:
        raise SetupError("No staff accounts found in the seed file.")
    rng = random.Random(args.random_seed)
    emails = list(accounts.staff)
    if args.pick == "random":
        rng.shuffle(emails)
    wanted = args.staff or len(emails)
    if wanted > len(emails):
        print(f"Only {len(emails)} staff in the seed, using all of them (asked for {wanted}).")
    emails = emails[:wanted]
    password = resolve_password(args)

    stats = Stats()
    stop = asyncio.Event()
    install_stop_handler(stop)
    staff = await login_accounts(emails, password, args.base_url, stats, args.timeout, args.login_pace, "staff")
    if not staff:
        raise SetupError("No staff member could log in, so there is nothing to simulate.")
    stats = Stats()
    for a in staff:
        a.stats = stats

    workers = [Worker(a, args, delays, random.Random(rng.random()), stats, stop) for a in staff]
    print(f"{len(staff)} staff accounts. Waits (seconds, before jitter): "
          + ", ".join(f"{s}={delays[s]:g}" for s in STEPS) + ". Ctrl+C to stop.", flush=True)

    def status_line() -> str:
        c = stats.counters
        return (f"t={time.monotonic() - stats.t0:5.0f}s  picked_up={c['orders picked up']}  "
                f"handling_now={sum(len(w.driving) for w in workers)}  "
                f"confirmed={c['order now confirmed']}  preparing={c['order now preparing']}  "
                f"out={c['order now out_for_delivery']}  delivered={c['order now delivered']}  "
                f"cancelled={c['order now cancelled']}  conflicts={c['order changed by someone else (409)']}  "
                f"5xx={sum(stats.classes(l)['server'] for l in stats.codes)}")

    pollers = [asyncio.create_task(w.poll_loop()) for w in workers]
    pollers.append(asyncio.create_task(reporter(args.report_every, status_line, stop)))
    start = time.monotonic()
    if args.duration:
        await sleep_or_stop(args.duration, stop)
        stop.set()
    else:
        await stop.wait()

    # give running requests a few seconds to finish, then cancel whatever is stuck
    await asyncio.wait(pollers, timeout=3)
    drivers = [t for w in workers for t in w.tasks]
    for t in drivers + pollers:
        t.cancel()
    await asyncio.gather(*drivers, *pollers, return_exceptions=True)
    for a in staff:
        await a.aclose()

    print("\n=== Staff simulation finished ===")
    print(f"ran {time.monotonic() - start:.0f}s, {stats.total_requests()} requests in total\n")
    print(stats.table())
    if stats.counters:
        print()
        for k, v in sorted(stats.counters.items()):
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
