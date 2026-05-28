"""Email delivery via Resend. Attaches a PDF report."""

from __future__ import annotations

import base64
import os

import resend

resend.api_key = os.environ.get("RESEND_API_KEY", "")

FROM_ADDRESS = "noor@nidoandkey.com"

_MONTHLY_BODY = """\
<div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;max-width:560px;margin:0 auto;color:#1a1a1a">
  <p style="font-size:15px;line-height:1.6">Hi,</p>
  <p style="font-size:15px;line-height:1.6">
    Your monthly Motivated Seller Intelligence report for San Antonio is attached.
    Inside you'll find:
  </p>
  <ul style="font-size:14px;line-height:1.8;color:#374151">
    <li>Top 20 multifamily properties ranked by seller pressure signals</li>
    <li>Deep dives on the 5 highest-priority assets</li>
    <li>Submarket rent benchmarks and ownership notes</li>
  </ul>
  <p style="font-size:13px;color:#6b7280;margin-top:24px;border-top:1px solid #e5e7eb;padding-top:16px">
    Loan maturity figures are estimates based on origination dates from public deed records.
    Texas is a non-disclosure state — recent sale prices are not available from public sources.
  </p>
  <p style="font-size:14px;margin-top:16px">— Nido & Key</p>
</div>
"""

_OM_BODY = """\
<div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;max-width:560px;margin:0 auto;color:#1a1a1a">
  <p style="font-size:15px;line-height:1.6">Hi,</p>
  <p style="font-size:15px;line-height:1.6">
    Your offering memorandum analysis is attached. The report covers:
  </p>
  <ul style="font-size:14px;line-height:1.8;color:#374151">
    <li>Property snapshot and financial underwrite</li>
    <li>Owner profile and loan situation</li>
    <li>Market rent benchmarks (Census ACS) vs. in-place rents</li>
    <li>Public record flags (tax status, violations)</li>
    <li>Bottom-line recommendation</li>
  </ul>
  <p style="font-size:13px;color:#6b7280;margin-top:24px;border-top:1px solid #e5e7eb;padding-top:16px">
    All figures cited include their data source. Numbers marked "calculated from OM"
    are derived from PDF text; verify independently before underwriting a purchase.
  </p>
  <p style="font-size:14px;margin-top:16px">— Nido & Key</p>
</div>
"""


def _send(payload: dict) -> str:
    """Send via Resend and surface errors clearly."""
    try:
        resp = resend.Emails.send(payload)
    except Exception as e:
        raise RuntimeError(f"Resend API error: {e}") from e
    if isinstance(resp, dict):
        if "id" in resp:
            return resp["id"]
        # Resend returns {"name": "...", "message": "..."} on error
        err = resp.get("message") or resp.get("name") or repr(resp)
        raise RuntimeError(f"Resend rejected email: {err}")
    # New SDK returns object with .id
    return getattr(resp, "id", "")


def send_monthly_report(recipient: str, pdf_bytes: bytes, month_label: str) -> str:
    filename = f"Noor_Motivated_Sellers_{month_label.replace(' ', '_')}.pdf"
    return _send(
        {
            "from": FROM_ADDRESS,
            "to": [recipient],
            "subject": f"Motivated Seller Intelligence — {month_label}",
            "html": _MONTHLY_BODY,
            "attachments": [_attachment(filename, pdf_bytes)],
        }
    )


def send_om_report(recipient: str, pdf_bytes: bytes, property_address: str) -> str:
    safe = property_address.replace(",", "").replace(" ", "_")[:40]
    filename = f"Noor_Analysis_{safe}.pdf"
    return _send(
        {
            "from": FROM_ADDRESS,
            "to": [recipient],
            "subject": f"OM Analysis — {property_address}",
            "html": _OM_BODY,
            "attachments": [_attachment(filename, pdf_bytes)],
        }
    )


def _attachment(filename: str, pdf_bytes: bytes) -> dict:
    return {
        "filename": filename,
        "content": base64.b64encode(pdf_bytes).decode(),
        "content_type": "application/pdf",
    }
