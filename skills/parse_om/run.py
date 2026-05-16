import json
import os
import re
import sys
from pathlib import Path

import pdfplumber
from openai import OpenAI

NVIDIA_KEY = os.environ.get("NVIDIA_API_KEY", "")

EXTRACT_PROMPT = """Extract the following fields from this real estate offering memorandum.
Return ONLY valid JSON — no markdown fences, no commentary.

Fields:
- address: street address only (e.g. "4123 McCullough Ave")
- city: city name
- state: 2-letter state code (e.g. "TX")
- zip: 5-digit zip as string
- property_type: human-readable type (e.g. "Multifamily", "Retail Strip Center", "Mobile Home Park")
- asset_class: one of ["multifamily", "commercial", "industrial", "retail", "office", "mobile_home_park", "other"]
- units: integer count of residential/apartment units, null if commercial
- asking_price: integer dollar amount (no commas/symbols), null if not stated
- year_built: integer year, null if not stated

OM Text:
{text}"""


def _extract_text(pdf_path: str) -> str:
    text = ""
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages[:8]:
            text += (page.extract_text() or "") + "\n"
    return text.strip()


def _call_llm(text: str) -> dict:
    client = OpenAI(base_url="https://integrate.api.nvidia.com/v1", api_key=NVIDIA_KEY)
    resp = client.chat.completions.create(
        model="nvidia/nemotron-3-super-120b-a12b",
        messages=[{"role": "user", "content": EXTRACT_PROMPT.format(text=text[:6000])}],
        stream=False,
        max_tokens=400,
        temperature=0.1,
    )
    raw = (resp.choices[0].message.content or "").strip()
    # Strip markdown fences if model wraps in ```json ... ```
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    return json.loads(raw.strip())


def run(params: dict) -> dict:
    pdf_path = params.get("pdf_path", "")
    if not pdf_path or not Path(pdf_path).exists():
        return {
            "job": "parse_om",
            "status": "error",
            "data": None,
            "reason": "PDF path not found",
        }

    try:
        text = _extract_text(pdf_path)
    except Exception as e:
        return {
            "job": "parse_om",
            "status": "error",
            "data": None,
            "reason": f"PDF read error: {e}",
        }

    if not text:
        return {
            "job": "parse_om",
            "status": "error",
            "data": None,
            "reason": "No text extracted from PDF",
        }

    try:
        parsed = _call_llm(text)
    except Exception as e:
        return {
            "job": "parse_om",
            "status": "error",
            "data": None,
            "reason": f"LLM extraction error: {e}",
        }

    data = {
        "address": str(parsed.get("address", "")).strip(),
        "city": str(parsed.get("city", "")).strip(),
        "state": str(parsed.get("state", "")).strip().upper(),
        "zip": str(parsed.get("zip", "")).strip(),
        "property_type": str(parsed.get("property_type", "Unknown")).strip(),
        "asset_class": str(parsed.get("asset_class", "other")).strip().lower(),
        "units": parsed.get("units"),
        "asking_price": parsed.get("asking_price"),
        "year_built": parsed.get("year_built"),
    }

    if not data["address"] or not data["city"]:
        return {
            "job": "parse_om",
            "status": "error",
            "data": None,
            "reason": "Could not extract address from OM",
        }

    return {"job": "parse_om", "status": "ok", "data": data}


if __name__ == "__main__":
    raw = sys.argv[1] if len(sys.argv) > 1 else sys.stdin.read()
    print(json.dumps(run(json.loads(raw))))
