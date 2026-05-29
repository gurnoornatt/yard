import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field
from openai import OpenAI

MISTRAL_KEY = os.environ.get("MISTRAL_API_KEY", "")
OPENROUTER_KEY = os.environ.get("OPENROUTER_API_KEY", "")
NVIDIA_KEY = os.environ.get("NVIDIA_API_KEY", "")

_OR_BASE = "https://openrouter.ai/api/v1"
_OR_MODEL = "openai/gpt-oss-120b:free"
_NVIDIA_BASE = "https://integrate.api.nvidia.com/v1"
_NVIDIA_MODEL = "nvidia/llama-3.1-nemotron-nano-8b-v1"

ANNOTATION_PROMPT = (
    "Extract all fields from this real estate offering memorandum. "
    "For each field set source to the exact page and section where you found the value "
    "(e.g. 'page 2, Investment Terms section' or 'Financial Analysis table, Pro Forma column, page 16'). "
    "If offering_structure is Free and Clear or All Cash, set ALL loan fields (loan_type, "
    "loan_original_balance, loan_interest_rate_pct, loan_term_months) value to null. "
    "loan_term_months value must be 60-480 (5-40 years); set null if outside this range or not found. "
    "unit_mix_csv: rows as 'bedroomsN,count,sqft,in_place_rent,market_rent' separated by semicolons."
)


# ---------------------------------------------------------------------------
# Pydantic schema for Mistral document_annotation
# ---------------------------------------------------------------------------

class CitedStr(BaseModel):
    value: Optional[str] = None
    source: str = "not found"


class CitedInt(BaseModel):
    value: Optional[int] = None
    source: str = "not found"


class CitedFloat(BaseModel):
    value: Optional[float] = None
    source: str = "not found"


class OMExtraction(BaseModel):
    address: CitedStr = Field(description="Street address only e.g. '349 Edgewood Ave'")
    city: CitedStr = Field(description="City name")
    state: CitedStr = Field(description="2-letter state code e.g. TX")
    zip_code: CitedStr = Field(description="5-digit zip code")
    property_type: CitedStr = Field(description="e.g. Multifamily, NNN Retail, Industrial Park")
    asset_class: CitedStr = Field(description="One of: multifamily commercial industrial retail office mobile_home_park other")
    units: CitedInt = Field(description="Total unit count as integer")
    asking_price: CitedInt = Field(description="Asking price in dollars as integer")
    year_built: CitedInt = Field(description="Year property was built as 4-digit integer")
    occupancy_pct: CitedInt = Field(description="Current occupancy as integer 0-100")
    annual_in_place_revenue: CitedInt = Field(description="Total current annual rent revenue T12 in dollars")
    annual_projected_revenue: CitedInt = Field(description="Pro forma total annual rent revenue in dollars")
    expense_per_unit_annual: CitedInt = Field(description="Total operating expenses per unit per year in dollars")
    value_add_rent_premium: CitedInt = Field(description="Monthly rent premium per unit after renovation in dollars")
    renovation_cost_per_unit: CitedInt = Field(description="Renovation cost per unit in dollars")
    broker_cap_rate_pct: CitedFloat = Field(description="Cap rate as decimal percentage e.g. 7.76 for 7.76%")
    management_company: CitedStr = Field(description="Property management company name")
    offering_structure: CitedStr = Field(description="e.g. Free and Clear, Loan Assumption, All Cash")
    loan_type: CitedStr = Field(description="e.g. Fannie Mae DUS, Freddie Mac, CMBS. Null if free and clear.")
    loan_original_balance: CitedInt = Field(description="Original loan amount in dollars. Null if no existing loan.")
    loan_interest_rate_pct: CitedFloat = Field(description="Loan interest rate as decimal e.g. 4.84 for 4.84%. Null if no loan.")
    loan_term_months: CitedInt = Field(description="Loan term in months 60-480. Null if no existing loan.")
    unit_mix_csv: CitedStr = Field(description="bedroomsN,count,sqft,in_place_rent,market_rent rows separated by semicolons")


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _extract_json(raw: str) -> dict:
    raw = raw.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    raw = raw.strip()
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
    raise ValueError(f"No valid JSON in response: {raw[:200]!r}")


def _parse_unit_mix_csv(csv_val: str) -> list[dict]:
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
            units.append({"bedrooms": beds, "count": count, "sq_ft": sq_ft,
                          "in_place_rent": in_place, "market_rent": market})
        except (ValueError, IndexError):
            continue
    return units


# ---------------------------------------------------------------------------
# Stage 2: gpt-oss-120b verification pass
# ---------------------------------------------------------------------------

def _verify(financials: dict) -> dict:
    """Free contradiction check via gpt-oss-120b. Mutates and returns financials."""
    if not OPENROUTER_KEY or not financials:
        return financials

    offering = financials.get("offering_structure", "")
    is_free_clear = offering and any(p in offering.lower() for p in
                                      ["free and clear", "all cash", "no debt", "unencumbered"])

    verify_prompt = f"""Check these extracted OM values for contradictions. Output JSON only. No explanation.

Values:
{json.dumps(financials, indent=2)}

Rules:
1. If offering_structure is "Free and Clear" or "All Cash": loan_original_balance, loan_type, loan_interest_rate, loan_term_months must all be null (remove them).
2. loan_term_months must be integer 60-480; set null if outside this range.
3. broker_cap_rate must be between 0.03 and 0.15 for multifamily; flag if wildly outside.
4. occupancy_rate must be between 0.0 and 1.0.

Return ONLY fields needing correction:
{{"corrections": {{"field_name": corrected_value_or_null}}}}

If nothing needs correction return: {{"corrections": {{}}}}
JSON:"""

    try:
        client = OpenAI(base_url=_OR_BASE, api_key=OPENROUTER_KEY, timeout=30.0, max_retries=0)
        resp = client.chat.completions.create(
            model=_OR_MODEL,
            messages=[{"role": "user", "content": verify_prompt}],
            max_tokens=300,
            temperature=0,
        )
        corrections = _extract_json(resp.choices[0].message.content or "").get("corrections", {})
        for field, val in corrections.items():
            if val is None:
                financials.pop(field, None)
            else:
                financials[field] = val
        if corrections:
            print(f"Verification corrected: {list(corrections.keys())}")
        else:
            print("Verification: no corrections needed")
    except Exception as e:
        print(f"Verification pass failed (non-fatal): {e}")

    # Enforce free-and-clear directly (belt-and-suspenders)
    if is_free_clear:
        for loan_field in ["loan_original_balance", "loan_type", "loan_interest_rate", "loan_term_months"]:
            financials.pop(loan_field, None)

    return financials


# ---------------------------------------------------------------------------
# Stage 1 — Mistral OCR path
# ---------------------------------------------------------------------------

def _build_output_from_extraction(raw: OMExtraction) -> dict:
    """Normalize OMExtraction → standard parse_om output dict + citations."""
    citations: dict[str, str] = {}

    def cite(field, key: str):
        """Return field value and record citation if source is meaningful."""
        if field is None:
            return None
        src = getattr(field, "source", "not found")
        if src and src != "not found":
            citations[key] = src
        return getattr(field, "value", None)

    city = cite(raw.city, "city")
    if not city or not str(city).strip():
        return {
            "job": "parse_om",
            "status": "error",
            "data": None,
            "reason": "City not extracted — address withheld or unreadable",
        }

    financials: dict = {}

    # Occupancy
    occ = cite(raw.occupancy_pct, "occupancy_rate")
    if isinstance(occ, (int, float)) and 0 < occ <= 100:
        financials["occupancy_rate"] = round(occ / 100, 4)

    # Integer revenue / expense fields
    for attr, dst in [
        ("annual_in_place_revenue", "annual_in_place_revenue"),
        ("annual_projected_revenue", "annual_projected_revenue"),
        ("expense_per_unit_annual", "total_expense_per_unit_annual"),
        ("value_add_rent_premium", "value_add_rent_premium_per_unit"),
        ("renovation_cost_per_unit", "renovation_cost_per_unit"),
        ("loan_original_balance", "loan_original_balance"),
        ("loan_term_months", "loan_term_months"),
    ]:
        val = cite(getattr(raw, attr), dst)
        if isinstance(val, (int, float)) and val > 0:
            financials[dst] = int(val)

    # Rates (model returns percentage, we store as decimal)
    cap = cite(raw.broker_cap_rate_pct, "broker_cap_rate")
    if isinstance(cap, (int, float)) and cap > 0:
        financials["broker_cap_rate"] = round(float(cap) / 100, 4)

    rate = cite(raw.loan_interest_rate_pct, "loan_interest_rate")
    if isinstance(rate, (int, float)) and rate > 0:
        financials["loan_interest_rate"] = round(float(rate) / 100, 6)

    # Loan term sanity check
    if "loan_term_months" in financials:
        term = financials["loan_term_months"]
        if not (60 <= term <= 480):
            financials.pop("loan_term_months")
            citations.pop("loan_term_months", None)

    # String fields
    for attr, dst in [
        ("loan_type", "loan_type"),
        ("management_company", "management_company"),
        ("offering_structure", "offering_structure"),
    ]:
        val = cite(getattr(raw, attr), dst)
        if val and isinstance(val, str) and val.strip().lower() not in ("null", "none", ""):
            financials[dst] = val.strip()

    # Unit mix
    mix_val = cite(raw.unit_mix_csv, "unit_mix")
    if mix_val and isinstance(mix_val, str) and mix_val.strip().lower() not in ("null", "none", ""):
        parsed = _parse_unit_mix_csv(mix_val)
        if parsed:
            financials["unit_mix"] = parsed

    # Verification pass (Stage 2)
    financials = _verify(financials)

    def _s(field, default="") -> str:
        val = field.value if field else None
        if val is None or str(val).strip().lower() in ("none", "null", "n/a", ""):
            return default
        return str(val).strip()

    data = {
        "address": _s(raw.address),
        "city": str(city).strip(),
        "state": _s(raw.state).upper(),
        "zip": _s(raw.zip_code),
        "property_type": _s(raw.property_type, "Unknown"),
        "asset_class": _s(raw.asset_class, "other").lower(),
        "units": raw.units.value if raw.units and isinstance(raw.units.value, int) else None,
        "asking_price": raw.asking_price.value if raw.asking_price and isinstance(raw.asking_price.value, (int, float)) else None,
        "year_built": raw.year_built.value if raw.year_built and isinstance(raw.year_built.value, int) else None,
        "source": "Offering Memorandum (PDF) via Mistral OCR",
        "financials": financials,
        "citations": citations,
    }
    return {"job": "parse_om", "status": "ok", "data": data}


def _run_mistral_path(pdf_path: str) -> dict:
    """Mistral OCR + document_annotation in one call. Upload → signed URL → OCR."""
    from mistralai.client import Mistral
    from mistralai.client.models import File, DocumentURLChunk
    from mistralai.extra import response_format_from_pydantic_model

    t0 = time.time()
    client = Mistral(api_key=MISTRAL_KEY, timeout_ms=120_000)

    # Upload PDF to Mistral Files API → get signed URL
    pdf_name = Path(pdf_path).name
    with open(pdf_path, "rb") as f:
        uploaded = client.files.upload(
            file=File(file_name=pdf_name, content=f, content_type="application/pdf"),
            purpose="ocr",
        )
    signed = client.files.get_signed_url(file_id=uploaded.id, expiry=1)
    print(f"Uploaded {pdf_name} in {time.time()-t0:.1f}s, file_id={uploaded.id}")

    # OCR + structured extraction in one call
    t1 = time.time()
    resp = client.ocr.process(
        model="mistral-ocr-latest",
        document=DocumentURLChunk(document_url=signed.url),
        table_format="html",
        document_annotation_format=response_format_from_pydantic_model(OMExtraction),
        document_annotation_prompt=ANNOTATION_PROMPT,
        confidence_scores_granularity="page",
    )
    print(f"Mistral OCR + annotation in {time.time()-t1:.1f}s")

    if not resp.document_annotation:
        raise ValueError("Mistral returned no document_annotation")

    # document_annotation is a JSON string — parse into typed model
    raw_dict = json.loads(resp.document_annotation)
    extraction = OMExtraction.model_validate(raw_dict)

    result = _build_output_from_extraction(extraction)
    print(f"Total Mistral path: {time.time()-t0:.1f}s")
    return result


# ---------------------------------------------------------------------------
# Legacy path (pdfplumber + gpt-oss-120b) — kept as fallback
# ---------------------------------------------------------------------------

import pdfplumber  # noqa: E402

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
  "unit_mix_csv": "<rows as: bedroomsN,count,sqft,in_place_rent,market_rent separated by semicolons or null>"
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
    "unit mix", "rent roll", "per unit", "vacancy", "noi", "net operating",
    "expense", "revenue", "cap rate", "value-add", "renovation", "occupancy",
    "bedroom", "pro forma", "income", "operating", "loan", "fannie", "freddie",
    "interest rate", "amortization", "debt service", "management fee",
    "in-place", "in place", "asking price", "offering price",
]

_FREE_AND_CLEAR_PHRASES = ["free and clear", "all cash", "no existing debt", "unencumbered", "no debt"]


def _is_free_and_clear(text: str) -> bool:
    lower = text.lower()
    return any(phrase in lower for phrase in _FREE_AND_CLEAR_PHRASES)


def _extract_pages(pdf_path: str) -> tuple[str, str]:
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


def _llm_call(prompt: str, max_tokens: int = 600) -> str:
    if OPENROUTER_KEY:
        try:
            client = OpenAI(base_url=_OR_BASE, api_key=OPENROUTER_KEY, timeout=30.0, max_retries=0)
            resp = client.chat.completions.create(
                model=_OR_MODEL,
                messages=[{"role": "user", "content": prompt}],
                stream=False,
                max_tokens=max_tokens,
                temperature=0,
            )
            return resp.choices[0].message.content or ""
        except Exception as e:
            print(f"OpenRouter failed, falling back to nano-8b: {e}")
    client = OpenAI(base_url=_NVIDIA_BASE, api_key=NVIDIA_KEY, timeout=90.0, max_retries=0)
    resp = client.chat.completions.create(
        model=_NVIDIA_MODEL,
        messages=[{"role": "user", "content": prompt}],
        stream=False,
        max_tokens=max_tokens,
        temperature=0.1,
    )
    return resp.choices[0].message.content or ""


def _llm_extract(prompt_template: str, text: str) -> dict:
    raw = _llm_call(prompt_template.format(text=text), max_tokens=3000)
    return _extract_json(raw)


def _clean_financials(raw: dict) -> dict:
    if not isinstance(raw, dict):
        return {}
    cleaned: dict = {}
    csv_val = raw.get("unit_mix_csv")
    if csv_val and isinstance(csv_val, str) and csv_val.strip().lower() not in ("null", "none", ""):
        parsed = _parse_unit_mix_csv(csv_val)
        if parsed:
            cleaned["unit_mix"] = parsed
    occ_pct = raw.get("occupancy_pct")
    if isinstance(occ_pct, (int, float)) and 0 < occ_pct <= 100:
        cleaned["occupancy_rate"] = round(occ_pct / 100, 4)
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
    rate = raw.get("loan_interest_rate_pct")
    if isinstance(rate, (int, float)) and rate > 0:
        cleaned["loan_interest_rate"] = round(float(rate) / 100, 6)
    cap = raw.get("broker_cap_rate_pct")
    if isinstance(cap, (int, float)) and cap > 0:
        cleaned["broker_cap_rate"] = round(float(cap) / 100, 4)
    for key in ["loan_type", "management_company", "offering_structure"]:
        val = raw.get(key)
        if val and isinstance(val, str) and val.strip().lower() not in ("null", "none", ""):
            cleaned[key] = val.strip()
    # Loan term sanity check
    if "loan_term_months" in cleaned:
        term = cleaned["loan_term_months"]
        if not (60 <= term <= 480):
            cleaned.pop("loan_term_months")
    return cleaned


def _run_legacy_path(pdf_path: str) -> dict:
    """Original pdfplumber + gpt-oss-120b path — kept as fallback."""
    t0 = time.time()
    try:
        basic_text, financial_text = _extract_pages(pdf_path)
    except Exception as e:
        return {"job": "parse_om", "status": "error", "data": None, "reason": f"PDF read error: {e}"}

    print(f"Pages extracted in {time.time()-t0:.1f}s")
    print(f"Basic text length: {len(basic_text)} chars")
    print(f"Financial text length: {len(financial_text)} chars")

    if not basic_text:
        return {"job": "parse_om", "status": "error", "data": None, "reason": "No text extracted from PDF"}

    try:
        t1 = time.time()
        raw = _llm_call(EXTRACT_PROMPT.format(text=basic_text[:6000]), max_tokens=600)
        parsed = _extract_json(raw)
        print(f"LLM basic extract in {time.time()-t1:.1f}s")
        print(f"BASIC EXTRACTED: {json.dumps(parsed, indent=2)}")
    except Exception as e:
        return {"job": "parse_om", "status": "error", "data": None, "reason": f"LLM extraction error: {e}"}

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
        "asking_price": parsed.get("asking_price") if isinstance(parsed.get("asking_price"), (int, float)) else None,
        "year_built": parsed.get("year_built") if isinstance(parsed.get("year_built"), int) else None,
        "source": "Offering Memorandum (PDF)",
    }

    if not data["city"]:
        return {"job": "parse_om", "status": "error", "data": None,
                "reason": "Could not extract city — address withheld or unreadable"}

    free_clear = _is_free_and_clear(basic_text)
    merged: dict = {}
    if free_clear:
        merged["offering_structure"] = "Free and Clear"

    if financial_text.strip():
        try:
            t2 = time.time()
            merged.update(_llm_extract(FINANCIAL_PROMPT, financial_text[:8000]))
            print(f"Financial extract in {time.time()-t2:.1f}s")
        except Exception as e:
            print(f"Financial pass-1 error: {e}")

        if not free_clear:
            loan_text = financial_text[5000:13000]
            if loan_text.strip():
                try:
                    loan_data = _llm_extract(LOAN_PROMPT, loan_text)
                    term = loan_data.get("loan_term_months")
                    if isinstance(term, (int, float)) and not (60 <= term <= 480):
                        loan_data.pop("loan_term_months", None)
                    merged.update(loan_data)
                except Exception as e:
                    print(f"Financial pass-2 error: {e}")

    data["financials"] = _clean_financials(merged)
    data["citations"] = {}  # legacy path has no citations
    return {"job": "parse_om", "status": "ok", "data": data}


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def run(params: dict) -> dict:
    pdf_path = params.get("pdf_path", "")
    if not pdf_path or not Path(pdf_path).exists():
        return {"job": "parse_om", "status": "error", "data": None, "reason": "PDF path not found"}

    if MISTRAL_KEY:
        try:
            return _run_mistral_path(pdf_path)
        except Exception as e:
            print(f"Mistral OCR failed, falling back to legacy path: {e}")

    return _run_legacy_path(pdf_path)


if __name__ == "__main__":
    raw = sys.argv[1] if len(sys.argv) > 1 else sys.stdin.read()
    print(json.dumps(run(json.loads(raw))))
