import json
import os
import re
import sys
from pathlib import Path

import pdfplumber
from openai import OpenAI

NVIDIA_KEY = os.environ.get("NVIDIA_API_KEY", "")

EXTRACT_PROMPT = """You are a data extraction API. Output ONLY a JSON object. No thinking, no explanation, no preamble.

Extract from this real estate offering memorandum:

{{
  "address": "<street address only, e.g. 349 Edgewood Ave>",
  "city": "<city>",
  "state": "<2-letter state>",
  "zip": "<5-digit zip>",
  "property_type": "<e.g. NNN Retail, Multifamily, Industrial Park>",
  "asset_class": "<one of: multifamily, commercial, industrial, retail, office, mobile_home_park, other>",
  "units": <integer or null>,
  "asking_price": <integer dollars or null>,
  "year_built": <integer year or null>
}}

OM Text:
{text}

JSON:"""


def _extract_text(pdf_path: str) -> str:
    text = ""
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages[:8]:
            text += (page.extract_text() or "") + "\n"
    return text.strip()


def _extract_json(raw: str) -> dict:
    """Extract JSON from model output even if it includes chain-of-thought reasoning."""
    raw = raw.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    raw = raw.strip()

    # Try direct parse
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # Try to find last complete JSON object (handles nested braces)
    for start in range(len(raw) - 1, -1, -1):
        if raw[start] != "{":
            continue
        depth = 0
        for i, ch in enumerate(raw[start:], start):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(raw[start : i + 1])
                    except json.JSONDecodeError:
                        break

    # Last resort: parse key-value facts from the model's reasoning text.
    # Handles patterns like: Address: "349 Edgewood Ave" or city: "Atlanta"
    def _find(patterns: list[str]) -> str | None:
        for pat in patterns:
            m = re.search(pat, raw, re.I)
            if m:
                val = m.group(1).strip().strip('"').strip("'").strip(".")
                if val.lower() not in ("none", "null", "n/a", "unknown", ""):
                    return val
        return None

    address = _find(
        [
            r'(?:address|street)[:\s]+["\']?([0-9A-Za-z][^,\n"\']{4,60})',
            r'"address"\s*:\s*"([^"]+)"',
            r"\b((?:SWC|NWC|NEC|SEC|SEC)\s+[A-Z][^,\n]{5,50})",  # intersection format
            r'([0-9]+\s+[A-Za-z][^,\n"\']{4,50})',
        ]
    )
    city = _find(
        [
            r'(?:city)[:\s]+["\']?([A-Za-z\s]+?)(?:[,.\n"\']|$)',
            r'"city"\s*:\s*"([^"]+)"',
        ]
    )
    state = _find([r'(?:state)[:\s]+["\']?([A-Z]{2})', r",\s*([A-Z]{2})\s+\d{5}"])
    zip_code = _find([r"\b(\d{5})\b", r'"zip"\s*:\s*"?(\d{5})'])
    prop_type = _find(
        [
            r'(?:property.?type|type)[:\s]+["\']?([A-Za-z\s]+?)(?:[,.\n"\']|$)',
            r'"property_type"\s*:\s*"([^"]+)"',
        ]
    )
    asset_class = _find(
        [r'"asset_class"\s*:\s*"([^"]+)"', r'asset.?class[:\s]+["\']?(\w+)']
    )

    asking_raw = _find(
        [
            r"(?:asking|list|sale).?price[:\s]+\$?([\d,]+)",
            r'"asking_price"\s*:\s*([\d]+)',
        ]
    )
    asking_price = int(re.sub(r"[^\d]", "", asking_raw)) if asking_raw else None

    year_raw = _find(
        [r"(?:year.?built|built)[:\s]+(\d{4})", r'"year_built"\s*:\s*(\d{4})']
    )
    year_built = int(year_raw) if year_raw and year_raw.isdigit() else None

    units_raw = _find(
        [r"(\d+)\s*(?:units?|apartments?|doors?)", r'"units"\s*:\s*(\d+)']
    )
    units = int(units_raw) if units_raw and units_raw.isdigit() else None

    if address and city:
        valid_classes = {
            "multifamily",
            "commercial",
            "industrial",
            "retail",
            "office",
            "mobile_home_park",
            "other",
        }
        return {
            "address": address,
            "city": city,
            "state": state or "",
            "zip": zip_code or "",
            "property_type": prop_type or "Unknown",
            "asset_class": asset_class if asset_class in valid_classes else "other",
            "units": units,
            "asking_price": asking_price,
            "year_built": year_built,
        }

    raise ValueError(f"No valid JSON or key-value facts in LLM response: {raw[:300]!r}")


def _call_llm(text: str) -> dict:
    client = OpenAI(base_url="https://integrate.api.nvidia.com/v1", api_key=NVIDIA_KEY)
    resp = client.chat.completions.create(
        model="nvidia/nemotron-3-super-120b-a12b",
        messages=[{"role": "user", "content": EXTRACT_PROMPT.format(text=text[:6000])}],
        stream=False,
        max_tokens=600,
        temperature=0.1,
    )
    raw = resp.choices[0].message.content or ""
    return _extract_json(raw)


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

    def _str(val, default="") -> str:
        if val is None or str(val).strip().lower() in ("none", "null", "n/a", ""):
            return default
        return str(val).strip()

    data = {
        "address": _str(parsed.get("address")),
        "city": _str(parsed.get("city")),
        "state": _str(parsed.get("state")).upper(),
        "zip": _str(parsed.get("zip")),
        "property_type": _str(parsed.get("property_type"), "Unknown"),
        "asset_class": _str(parsed.get("asset_class"), "other").lower(),
        "units": parsed.get("units") if isinstance(parsed.get("units"), int) else None,
        "asking_price": parsed.get("asking_price")
        if isinstance(parsed.get("asking_price"), (int, float))
        else None,
        "year_built": parsed.get("year_built")
        if isinstance(parsed.get("year_built"), int)
        else None,
    }

    if not data["city"]:
        return {
            "job": "parse_om",
            "status": "error",
            "data": None,
            "reason": "Could not extract city from OM — address withheld or unreadable",
        }

    data["source"] = "Offering Memorandum (PDF)"
    return {"job": "parse_om", "status": "ok", "data": data}


if __name__ == "__main__":
    raw = sys.argv[1] if len(sys.argv) > 1 else sys.stdin.read()
    print(json.dumps(run(json.loads(raw))))
