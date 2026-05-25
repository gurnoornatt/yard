"""
Cal.com webhook handler — receives booking events and routes them.

Deploy this as a Vercel serverless function or add it to the Sentinel FastAPI app.
Register the webhook URL in Cal.com via:
  python webhooks/cal_register.py --url https://yourdomain.com/webhooks/cal

Supported triggers (configured in cal_register.py):
  BOOKING_CREATED, BOOKING_CANCELLED, BOOKING_RESCHEDULED, MEETING_ENDED,
  RECORDING_TRANSCRIPTION_GENERATED
"""

import hashlib
import hmac
import json
import os
from datetime import datetime

from fastapi import FastAPI, Header, HTTPException, Request

app = FastAPI()

CAL_WEBHOOK_SECRET = os.getenv("CAL_WEBHOOK_SECRET", "")
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", "")  # #scheduling channel


def _verify_signature(body: bytes, signature: str, secret: str) -> bool:
    if not secret:
        return True
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature.lstrip("sha256="))


def _slack(text: str) -> None:
    if not SLACK_WEBHOOK_URL:
        print("[slack]", text)
        return
    import urllib.request

    data = json.dumps({"text": text}).encode()
    req = urllib.request.Request(
        SLACK_WEBHOOK_URL, data=data, headers={"Content-Type": "application/json"}
    )
    urllib.request.urlopen(req, timeout=5)


def _fmt_booking(payload: dict) -> str:
    """Extract readable booking info from the Cal.com webhook payload."""
    responses = payload.get("responses", {})
    name = responses.get("name", {}).get("value", "Unknown")
    email = responses.get("email", {}).get("value", "")
    firm = responses.get("firm_name", {}).get("value", "")
    market = responses.get("target_market", {}).get("value", "")
    deal_size = responses.get("deal_size", {}).get("value", "")
    notes = responses.get("notes", {}).get("value", "")

    start = payload.get("startTime", "")
    if start:
        try:
            dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
            start = dt.strftime("%b %d, %Y at %I:%M %p UTC")
        except Exception:
            pass

    lines = [
        f"*Name:* {name}",
        f"*Email:* {email}",
    ]
    if firm:
        lines.append(f"*Firm:* {firm}")
    if market:
        lines.append(f"*Market:* {market}")
    if deal_size:
        lines.append(f"*Deal size:* {deal_size}")
    if notes:
        lines.append(f"*Notes:* {notes}")
    lines.append(f"*Time:* {start}")
    return "\n".join(lines)


@app.post("/webhooks/cal")
async def cal_webhook(
    request: Request,
    x_cal_signature_256: str = Header(default=""),
):
    body = await request.body()

    if CAL_WEBHOOK_SECRET and not _verify_signature(
        body, x_cal_signature_256, CAL_WEBHOOK_SECRET
    ):
        raise HTTPException(status_code=401, detail="Bad signature")

    event = json.loads(body)
    trigger = event.get("triggerEvent", "")
    payload = event.get("payload", {})

    if trigger == "BOOKING_CREATED":
        booking_url = payload.get("metadata", {}).get("videoCallUrl", "")
        info = _fmt_booking(payload)
        msg = f":calendar: *New Discovery Call booked*\n{info}"
        if booking_url:
            msg += f"\n*Video link:* {booking_url}"
        _slack(msg)

    elif trigger == "BOOKING_CANCELLED":
        name = payload.get("responses", {}).get("name", {}).get("value", "Someone")
        reason = payload.get("cancellationReason", "no reason given")
        _slack(f":x: *Booking cancelled* by {name} — {reason}")

    elif trigger == "BOOKING_RESCHEDULED":
        name = payload.get("responses", {}).get("name", {}).get("value", "Someone")
        start = payload.get("startTime", "")
        _slack(
            f":arrows_counterclockwise: *Booking rescheduled* by {name} — new time: {start}"
        )

    elif trigger == "MEETING_ENDED":
        uid = payload.get("uid", "")
        _slack(f":checkered_flag: *Meeting ended* — uid: {uid}")

    elif trigger == "RECORDING_TRANSCRIPTION_GENERATED":
        download_url = payload.get("downloadUrl", "")
        _slack(f":memo: *Transcript ready* — {download_url}")

    return {"ok": True}
