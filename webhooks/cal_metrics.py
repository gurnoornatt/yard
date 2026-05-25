"""
Pull and display Cal.com booking metrics.

Usage:
  python webhooks/cal_metrics.py               # all bookings
  python webhooks/cal_metrics.py --status past  # past only
  python webhooks/cal_metrics.py --days 30      # last 30 days
  python webhooks/cal_metrics.py --json         # raw JSON
"""

import argparse
import json
import os
import subprocess
from collections import defaultdict
from datetime import datetime, timezone

CAL_API_KEY = os.getenv("CAL_API_KEY", "")
BASE = "https://api.cal.com/v2"


def _get(path: str) -> dict:
    result = subprocess.run(
        [
            "curl",
            "-s",
            f"{BASE}{path}",
            "-H",
            f"Authorization: Bearer {CAL_API_KEY}",
            "-H",
            "cal-api-version: 2024-06-14",
        ],
        capture_output=True,
        text=True,
        timeout=15,
    )
    return json.loads(result.stdout)


def fetch_all_bookings(
    status: str | None = None, after: str | None = None
) -> list[dict]:
    params = "?limit=100&sortCreated=desc"
    if status:
        params += f"&status={status}"
    if after:
        params += f"&afterStart={after}"

    all_bookings = []
    cursor = None

    while True:
        url = f"/bookings{params}"
        if cursor:
            url += f"&cursor={cursor}"
        data = _get(url).get("data", {})
        bookings = data.get("bookings", [])
        all_bookings.extend(bookings)
        cursor = data.get("nextCursor")
        if not cursor or not bookings:
            break

    return all_bookings


def print_summary(bookings: list[dict]) -> None:
    total = len(bookings)
    by_status: dict[str, int] = defaultdict(int)
    by_event: dict[str, int] = defaultdict(int)
    leads: list[dict] = []

    for b in bookings:
        by_status[b.get("status", "UNKNOWN")] += 1
        event_title = b.get("eventType", {}).get("title", "Unknown")
        by_event[event_title] += 1

        responses = b.get("responses", {})
        firm = (
            responses.get("firm_name", {}).get("value", "")
            if isinstance(responses.get("firm_name"), dict)
            else ""
        )
        market = (
            responses.get("target_market", {}).get("value", "")
            if isinstance(responses.get("target_market"), dict)
            else ""
        )
        if firm or market:
            leads.append(
                {
                    "name": responses.get("name", {}).get("value", "")
                    if isinstance(responses.get("name"), dict)
                    else responses.get("name", ""),
                    "email": responses.get("email", {}).get("value", "")
                    if isinstance(responses.get("email"), dict)
                    else responses.get("email", ""),
                    "firm": firm,
                    "market": market,
                    "status": b.get("status"),
                    "time": b.get("startTime", ""),
                }
            )

    print(f"\n{'=' * 50}")
    print("CAL.COM BOOKING METRICS")
    print(f"{'=' * 50}")
    print(f"Total bookings: {total}")
    print()
    print("By status:")
    for status, count in sorted(by_status.items()):
        print(f"  {status:<20} {count}")
    print()
    print("By event type:")
    for event, count in sorted(by_event.items(), key=lambda x: -x[1]):
        print(f"  {event:<30} {count}")

    if leads:
        print()
        print(f"Discovery Call leads ({len(leads)}):")
        print(f"  {'Name':<20} {'Firm':<25} {'Market':<30} {'Status'}")
        print(f"  {'-' * 20} {'-' * 25} {'-' * 30} {'-' * 10}")
        for lead in leads:
            print(
                f"  {lead['name'][:20]:<20} {lead['firm'][:25]:<25} {lead['market'][:30]:<30} {lead['status']}"
            )
    print()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--status",
        choices=["upcoming", "past", "cancelled", "recurring", "unconfirmed"],
        help="Filter by booking status",
    )
    parser.add_argument(
        "--days", type=int, help="Only show bookings from the last N days"
    )
    parser.add_argument(
        "--json", action="store_true", dest="as_json", help="Output raw JSON"
    )
    args = parser.parse_args()

    after = None
    if args.days:
        from datetime import timedelta

        cutoff = datetime.now(timezone.utc) - timedelta(days=args.days)
        after = cutoff.strftime("%Y-%m-%dT%H:%M:%SZ")

    bookings = fetch_all_bookings(status=args.status, after=after)

    if args.as_json:
        print(json.dumps(bookings, indent=2))
        return

    print_summary(bookings)


if __name__ == "__main__":
    main()
