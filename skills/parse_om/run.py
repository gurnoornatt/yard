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

FINANCIAL_PROMPT = """You are a data extraction API. Output ONLY a JSON object. No thinking, no explanation, no preamble.

Extract from this real estate offering memorandum:

{{
  "occupancy_pct": <integer 0-100 or null>,
  "annual_in_place_revenue": <total annual rent integer or null>,
  "annual_projected_revenue": <pro forma annual rent integer or null>,
  "expense_per_unit_annual": <total operating expenses per unit per year integer or null>,
  "value_add_rent_premium": <monthly $ per unit integer or null>,
  "renovation_cost_per_unit": <total $ per unit integer or null>,
  "broker_cap_rate_pct": <cap rate as percentage e.g. 6 or null>,
  "management_company": "<string or null>",
  "loan_type": "<string or null>",
  "loan_original_balance": <integer or null>,
  "loan_interest_rate_pct": <interest rate as percentage e.g. 4.84 or null>,
  "loan_term_months": <integer or null>,
  "offering_structure": "<e.g. Loan Assumption, All Cash or null>",
  "unit_mix_csv": "<rows as: bedroomsN,count,sqft,in_place_rent,market_rent separated by semicolons e.g. 1,72,480,649,750;2,143,796,772,925 or null>"
}}

OM Text:
{text}

JSON:"""

LOAN_PROMPT = """You are a data extraction API. Output ONLY a JSON object. No thinking, no explanation, no preamble.

Extract from this real estate offering memorandum:

{{
  "expense_per_unit_annual": <total operating expenses per unit per year integer or null>,
  "management_company": "<string or null>",
  "loan_type": "<e.g. Fannie Mae DUS, Freddie Mac, CMBS or null>",
  "loan_original_balance": <integer or null>,
  "loan_interest_rate_pct": <interest rate as percentage e.g. 4.84 or null>,
  "loan_term_months": <integer or null>,
  "offering_structure": "<e.g. Loan Assumption, All Cash or null>"
}}

OM Text:
{text}

JSON:"""

FINANCIAL_KEYWORDS = [
    "unit mix",
    "rent roll",
    "per unit",
    "vacancy",
    "noi",
    "net operating",
    "expense",
    "revenue",
    "cap rate",
    "value-add",
    "renovation",
    "occupancy",
    "bedroom",
    "pro forma",
    "income",
    "operating",
    "loan",
    "fannie",
    "freddie",
    "interest rate",
    "amortization",
    "debt service",
    "management fee",
    "in-place",
    "in place",
    "asking price",
    "offering price",
]


def _extract_pages(pdf_path: str) -> tuple[str, str]:
    """Open PDF once; return (basic_text from pages 1-5, financial_text from keyword pages)."""
    basic_text = ""
    scored: list[tuple[int, int, str]] = []

    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages):
            text = page.extract_text() or ""
            if i < 8:
                basic_text += text + "\n"
            lower = text.lower()
            hits = sum(1 for kw in FINANCIAL_KEYWORDS if kw in lower)
            if hits >= 2:
                scored.append((hits, i, text))

    scored.sort(key=lambda x: x[0], reverse=True)
    top = scored[:6]
    top.sort(key=lambda x: x[1])
    financial_text = "\n".join(t for _, _, t in top)

    return basic_text.strip(), financial_text.strip()


def _extract_json(raw: str) -> dict:
    raw = raw.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    raw = raw.strip()
    # nano-8b outputs American number formatting (1,234,567) which is invalid JSON.
    # One pass removes 1,234 → 1234 but leaves 1234,567; loop until stable.
    for _ in range(5):
        cleaned = re.sub(r"(\d),(\d{3})(?=[,\s\n\r}\"'\]])", r"\1\2", raw)
        if cleaned == raw:
            break
        raw = cleaned

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

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
        [r'(?:property.?type|type)[:\s]+["\']?([A-Za-z\s]+?)(?:[,.\n"\']|$)']
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
    client = OpenAI(base_url="https://integrate.api.nvidia.com/v1", api_key=NVIDIA_KEY, timeout=30.0)
    resp = client.chat.completions.create(
        model="nvidia/llama-3.1-nemotron-nano-8b-v1",
        messages=[{"role": "user", "content": EXTRACT_PROMPT.format(text=text[:6000])}],
        stream=False,
        max_tokens=600,
        temperature=0.1,
    )
    raw = resp.choices[0].message.content or ""
    return _extract_json(raw)


def _llm_extract(prompt_template: str, text: str) -> dict:
    client = OpenAI(base_url="https://integrate.api.nvidia.com/v1", api_key=NVIDIA_KEY, timeout=30.0)
    resp = client.chat.completions.create(
        model="nvidia/llama-3.1-nemotron-nano-8b-v1",
        messages=[{"role": "user", "content": prompt_template.format(text=text)}],
        stream=False,
        max_tokens=3000,
        temperature=0.1,
    )
    raw = resp.choices[0].message.content or ""
    return _extract_json(raw)


def _extract_financials(text: str) -> dict:
    if not text.strip():
        return {}
    merged: dict = {}
    # Pass 1: rent roll / revenue / unit mix (first 8000 chars)
    try:
        merged.update(_llm_extract(FINANCIAL_PROMPT, text[:8000]))
    except Exception as e:
        print(f"Financial pass-1 error: {e}")
    # Pass 2: loan terms / expenses (chars 5000 onward, capped at 8000)
    loan_text = text[5000:13000]
    if loan_text.strip():
        try:
            merged.update(_llm_extract(LOAN_PROMPT, loan_text))
        except Exception as e:
            print(f"Financial pass-2 error: {e}")
    return merged


def _parse_unit_mix_csv(csv_val: str) -> list[dict]:
    """Parse unit_mix_csv: '1,72,480,649,750;2,143,796,772,925' into structured list."""
    units = []
    for row in csv_val.split(";"):
        parts = [p.strip() for p in row.strip().split(",")]
        if len(parts) < 2:
            continue
        try:
            beds = int(parts[0])
            count = int(parts[1]) if len(parts) > 1 else None
            sq_ft = int(parts[2]) if len(parts) > 2 and parts[2] else None
            in_place = int(parts[3]) if len(parts) > 3 and parts[3] else None
            market = int(parts[4]) if len(parts) > 4 and parts[4] else None
            units.append(
                {
                    "bedrooms": beds,
                    "count": count,
                    "sq_ft": sq_ft,
                    "in_place_rent": in_place,
                    "market_rent": market,
                }
            )
        except (ValueError, IndexError):
            continue
    return units


def _clean_financials(raw: dict) -> dict:
    if not isinstance(raw, dict):
        return {}

    cleaned: dict = {}

    # Parse unit_mix_csv if present (simplified format)
    csv_val = raw.get("unit_mix_csv")
    if (
        csv_val
        and isinstance(csv_val, str)
        and csv_val.strip().lower() not in ("null", "none", "")
    ):
        parsed = _parse_unit_mix_csv(csv_val)
        if parsed:
            cleaned["unit_mix"] = parsed

    # Occupancy: model returns 0-100 integer (occupancy_pct)
    occ_pct = raw.get("occupancy_pct")
    if isinstance(occ_pct, (int, float)) and 0 < occ_pct <= 100:
        cleaned["occupancy_rate"] = round(occ_pct / 100, 4)

    # Revenue and expense integers
    for src_key, dst_key in [
        ("annual_in_place_revenue", "annual_in_place_revenue"),
        ("annual_projected_revenue", "annual_projected_revenue"),
        ("expense_per_unit_annual", "total_expense_per_unit_annual"),
        ("value_add_rent_premium", "value_add_rent_premium_per_unit"),
        ("renovation_cost_per_unit", "renovation_cost_per_unit"),
        ("loan_original_balance", "loan_original_balance"),
        ("loan_term_months", "loan_term_months"),
    ]:
        val = raw.get(src_key)
        if isinstance(val, (int, float)) and val > 0:
            cleaned[dst_key] = int(val)

    # Interest rate and cap rate: model returns as percentage (e.g. 4.84, 6)
    rate = raw.get("loan_interest_rate_pct")
    if isinstance(rate, (int, float)) and rate > 0:
        cleaned["loan_interest_rate"] = round(float(rate) / 100, 6)

    cap = raw.get("broker_cap_rate_pct")
    if isinstance(cap, (int, float)) and cap > 0:
        cleaned["broker_cap_rate"] = round(float(cap) / 100, 4)

    for key in ["loan_type", "management_company", "offering_structure"]:
        val = raw.get(key)
        if (
            val
            and isinstance(val, str)
            and val.strip().lower() not in ("null", "none", "")
        ):
            cleaned[key] = val.strip()

    return cleaned


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
        basic_text, financial_text = _extract_pages(pdf_path)
    except Exception as e:
        return {
            "job": "parse_om",
            "status": "error",
            "data": None,
            "reason": f"PDF read error: {e}",
        }

    if not basic_text:
        return {
            "job": "parse_om",
            "status": "error",
            "data": None,
            "reason": "No text extracted from PDF",
        }

    try:
        parsed = _call_llm(basic_text)
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
        "source": "Offering Memorandum (PDF)",
    }

    if not data["city"]:
        return {
            "job": "parse_om",
            "status": "error",
            "data": None,
            "reason": "Could not extract city — address withheld or unreadable",
        }

    # Second pass: financial extraction
    try:
        raw_financials = _extract_financials(financial_text)
        data["financials"] = _clean_financials(raw_financials)
    except Exception as e:
        print(f"Financial extraction failed (non-fatal): {e}")
        data["financials"] = {}

    return {"job": "parse_om", "status": "ok", "data": data}


if __name__ == "__main__":
    raw = sys.argv[1] if len(sys.argv) > 1 else sys.stdin.read()
    print(json.dumps(run(json.loads(raw))))
