import base64
import json
import os
import urllib.request
from http.server import BaseHTTPRequestHandler
from pathlib import Path


SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL", "")

PDF_PATH = Path(__file__).parent.parent / "assets" / "sample-memo.pdf"


def _post(url: str, body: dict, headers: dict) -> str:
    data = json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        resp = urllib.request.urlopen(req, timeout=10)
        return resp.read().decode()
    except urllib.error.HTTPError as e:
        msg = e.read().decode()
        print(f"POST error {url} [{e.code}]: {msg}")
        return msg
    except Exception as e:
        print(f"POST error {url}: {e}")
        return ""


def _insert_contact(email: str, firm: str, submarket: str) -> None:
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("Supabase not configured")
        return
    _post(
        f"{SUPABASE_URL}/rest/v1/contacts",
        {"email": email, "firm": firm or None, "submarket": submarket or None},
        {
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "apikey": SUPABASE_KEY,
            "Content-Type": "application/json",
            "Prefer": "return=minimal",
        },
    )


def _send_email(email: str) -> None:
    if not RESEND_API_KEY:
        print("Resend not configured")
        return

    import resend as _resend

    _resend.api_key = RESEND_API_KEY

    params: dict = {
        "from": "Noor <noor@nidoandkey.com>",
        "to": [email],
        "subject": "Your sample OM analysis — Nido & Key",
        "text": (
            "Hi,\n\n"
            "Attached is a sample one-page OM analysis — same format we deliver on every deal.\n\n"
            "If you have an OM you're evaluating right now, forward it to noor@nidoandkey.com "
            "and I'll turn it around within 48 hours, no charge for the first one.\n\n"
            "— Nido & Key"
        ),
    }

    if PDF_PATH.exists():
        pdf_b64 = base64.b64encode(PDF_PATH.read_bytes()).decode()
        params["attachments"] = [
            {"filename": "Nido_Key_Sample_Analysis.pdf", "content": pdf_b64}
        ]
    else:
        print("sample-memo.pdf not found — sending without attachment")

    resp = _resend.Emails.send(params)
    print(f"Resend response: {resp}")


def _slack_alert(email: str, firm: str, submarket: str) -> None:
    if not SLACK_WEBHOOK_URL:
        print(f"[inbound] {email} | {firm} | {submarket}")
        return
    lines = [":email: *New memo request*", f"*Email:* {email}"]
    if firm:
        lines.append(f"*Firm:* {firm}")
    if submarket:
        lines.append(f"*Submarket:* {submarket}")
    _post(
        SLACK_WEBHOOK_URL,
        {"text": "\n".join(lines)},
        {"Content-Type": "application/json"},
    )


def _handle(body: bytes) -> None:
    data = json.loads(body)
    email = data.get("email", "").strip()
    firm = data.get("firm", "").strip()
    submarket = data.get("submarket", "").strip()

    if not email or "@" not in email:
        raise ValueError("invalid email")

    _insert_contact(email, firm, submarket)
    _send_email(email)
    _slack_alert(email, firm, submarket)


class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200)
        self._cors()
        self.end_headers()

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        try:
            _handle(body)
            self.send_response(200)
        except ValueError as e:
            self.send_response(400)
            self._cors()
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())
            return
        except Exception as e:
            print(f"submit error: {e}")
            self.send_response(500)
            self._cors()
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"error":"internal"}')
            return
        self._cors()
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"ok":true}')

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def log_message(self, *args):
        pass
