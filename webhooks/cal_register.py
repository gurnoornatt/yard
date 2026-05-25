"""
Register (or re-register) the Cal.com webhook.

Usage:
  python webhooks/cal_register.py --url https://yourdomain.com/webhooks/cal

Run once after deploying. If the webhook already exists, it updates the subscriber URL.
"""

import argparse
import json
import os
import subprocess

CAL_API_KEY = os.getenv("CAL_API_KEY", "cal_live_39312ce66f64d8fc4e25dbe30a23f05a")
BASE = "https://api.cal.com/v2"

TRIGGERS = [
    "BOOKING_CREATED",
    "BOOKING_CANCELLED",
    "BOOKING_RESCHEDULED",
    "MEETING_ENDED",
    "RECORDING_TRANSCRIPTION_GENERATED",
]


def _request(method: str, path: str, body: dict | None = None) -> dict:
    cmd = [
        "curl",
        "-s",
        "-X",
        method,
        f"{BASE}{path}",
        "-H",
        f"Authorization: Bearer {CAL_API_KEY}",
        "-H",
        "cal-api-version: 2024-06-14",
        "-H",
        "Content-Type: application/json",
    ]
    if body:
        cmd += ["-d", json.dumps(body)]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
    return json.loads(result.stdout)


def list_webhooks():
    return _request("GET", "/webhooks").get("data", [])


def create_webhook(url: str, secret: str = ""):
    payload = {
        "active": True,
        "subscriberUrl": url,
        "triggers": TRIGGERS,
    }
    if secret:
        payload["secret"] = secret
    return _request("POST", "/webhooks", payload)


def delete_webhook(webhook_id: str):
    return _request("DELETE", f"/webhooks/{webhook_id}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--url", required=True, help="Public URL for the webhook endpoint"
    )
    parser.add_argument(
        "--secret", default="", help="Optional HMAC secret for signature verification"
    )
    parser.add_argument(
        "--list", action="store_true", help="List existing webhooks and exit"
    )
    args = parser.parse_args()

    existing = list_webhooks()

    if args.list:
        print(json.dumps(existing, indent=2))
        return

    # Remove any existing webhook pointing to the same host
    for wh in existing:
        if wh.get("subscriberUrl", "") == args.url:
            print(f"Deleting existing webhook {wh['id']} pointing to {args.url}")
            delete_webhook(wh["id"])

    result = create_webhook(args.url, args.secret)
    print("Webhook registered:")
    print(json.dumps(result, indent=2))
    print(f"\nTriggers: {', '.join(TRIGGERS)}")


if __name__ == "__main__":
    main()
