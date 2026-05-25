import json
import os
import urllib.request
from datetime import datetime
from http.server import BaseHTTPRequestHandler


def _slack(text: str) -> None:
    url = os.environ.get("SLACK_WEBHOOK_URL", "")
    if not url:
        return
    data = json.dumps({"text": text}).encode()
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        urllib.request.urlopen(req, timeout=8)
    except Exception as e:
        print(f"Slack error: {e}")


def _fmt(responses: dict) -> str:
    def val(key):
        v = responses.get(key, "")
        return v.get("value", "") if isinstance(v, dict) else str(v)

    lines = []
    if val("name"):
        lines.append(f"*Name:* {val('name')}")
    if val("email"):
        lines.append(f"*Email:* {val('email')}")
    if val("firm_name"):
        lines.append(f"*Firm:* {val('firm_name')}")
    if val("target_market"):
        lines.append(f"*Market:* {val('target_market')}")
    if val("deal_size"):
        lines.append(f"*Deal size:* {val('deal_size')}")
    if val("notes"):
        lines.append(f"*Notes:* {val('notes')}")
    return "\n".join(lines)


def _handle(body: bytes) -> None:
    event = json.loads(body)
    trigger = event.get("triggerEvent", "")
    payload = event.get("payload", {})
    responses = payload.get("responses", {})

    if trigger == "BOOKING_CREATED":
        start = payload.get("startTime", "")
        try:
            dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
            start = dt.strftime("%b %d, %Y at %I:%M %p UTC")
        except Exception:
            pass
        video = payload.get("metadata", {}).get("videoCallUrl", "")
        msg = f":calendar: *New Discovery Call booked — {start}*\n{_fmt(responses)}"
        if video:
            msg += f"\n*Video:* {video}"
        _slack(msg)

    elif trigger == "BOOKING_CANCELLED":
        name = responses.get("name", {})
        name = name.get("value", "Someone") if isinstance(name, dict) else str(name)
        reason = payload.get("cancellationReason") or "no reason given"
        _slack(f":x: *Booking cancelled* by {name} — {reason}")

    elif trigger == "BOOKING_RESCHEDULED":
        name = responses.get("name", {})
        name = name.get("value", "Someone") if isinstance(name, dict) else str(name)
        start = payload.get("startTime", "")
        _slack(
            f":arrows_counterclockwise: *Booking rescheduled* by {name} — new time: {start}"
        )

    elif trigger == "MEETING_ENDED":
        _slack(":checkered_flag: *Meeting ended* — send your follow-up now.")

    elif trigger == "RECORDING_TRANSCRIPTION_GENERATED":
        url = payload.get("downloadUrl", "")
        _slack(f":memo: *Transcript ready* — {url}")


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        try:
            _handle(body)
        except Exception as e:
            print(f"handler error: {e}")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"ok":true}')

    def log_message(self, *args):
        pass
