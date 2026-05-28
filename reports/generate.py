"""PDF generation via WeasyPrint + Jinja2.

Install system deps first (macOS):
  brew install cairo pango gdk-pixbuf libffi
Then add to project:
  uv add weasyprint jinja2
"""

from __future__ import annotations

import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

TEMPLATES_DIR = Path(__file__).parent / "templates"
_env = Environment(
    loader=FileSystemLoader(str(TEMPLATES_DIR)),
    autoescape=True,
)

# Register helpers
_env.filters["currency"] = lambda v: f"${v:,.0f}" if v else "—"
_env.filters["pct"] = lambda v: f"{v:.1f}%" if v is not None else "—"
_env.filters["maybe"] = lambda v: str(v) if v else "—"


def render_pdf(template_name: str, context: dict) -> bytes:
    from weasyprint import HTML  # deferred so import error is clear

    html = _env.get_template(template_name).render(**context)
    return HTML(string=html, base_url=str(TEMPLATES_DIR)).write_pdf()


def build_monthly_context(
    properties: list[dict],
    month_label: str | None = None,
) -> dict:
    if not month_label:
        month_label = datetime.date.today().strftime("%B %Y")
    return {
        "month_label": month_label,
        "generated": datetime.date.today().strftime("%B %d, %Y"),
        "properties": properties,  # list of enriched ScoredProperty dicts
        "top5": properties[:5],
    }


def build_om_context(
    synthesis_text: str,
    verdict: str,
    all_data: dict,
    data_quality: dict | None = None,
) -> dict:
    parse = all_data.get("parse_om") or {}
    owner = all_data.get("owner_lookup") or {}
    deed = all_data.get("deed_lookup") or {}
    uw = all_data.get("underwrite") or {}
    comps = all_data.get("comps_lookup") or {}
    tax = all_data.get("tax_lookup") or {}
    violations = all_data.get("violations_lookup") or {}
    fin = parse.get("financials") or {}

    sections = _split_sections(synthesis_text)

    return {
        "verdict": verdict,
        "verdict_label": verdict,
        "generated": datetime.date.today().strftime("%B %d, %Y"),
        # Property
        "address": parse.get("address", ""),
        "city": parse.get("city", ""),
        "state": parse.get("state", ""),
        "zip": parse.get("zip", ""),
        "units": parse.get("units"),
        "year_built": parse.get("year_built"),
        "asset_class": parse.get("asset_class", ""),
        "asking_price": parse.get("asking_price"),
        # ATTOM is the authoritative appraised value; deed was a placeholder
        "appraised_value": owner.get("appraised_value") or deed.get("appraised_value"),
        # Owner
        "owner_name": owner.get("owner_name", ""),
        "owner_state": owner.get("owner_state", ""),
        "out_of_state": owner.get("out_of_state", False),
        "absentee_owner": owner.get("absentee_owner", False),
        "corporate_owner": owner.get("corporate_owner", False),
        # Lender — ATTOM origination record; county clerk UCC is in deed_lender
        "attom_lender": owner.get("attom_lender", ""),
        "attom_loan_amount": owner.get("attom_loan_amount"),
        "attom_loan_date": owner.get("attom_loan_date", ""),
        "deed_lender": deed.get("lender", ""),
        "deed_lender_date": deed.get("origination_date", ""),
        "mechanics_lien_count": deed.get("mechanics_lien_count", 0) or 0,
        "distress_signals": deed.get("distress_signals") or [],
        # Loan fields from OM (usually null — kept for edge cases)
        "loan_type": fin.get("loan_type", ""),
        "loan_balance": fin.get("loan_original_balance"),
        "loan_rate": fin.get("loan_interest_rate"),
        "loan_term_months": fin.get("loan_term_months"),
        # Underwrite
        "noi_estimate": uw.get("noi_estimate"),
        "noi_source": uw.get("noi_source", ""),
        "cap_rate_at_ask": uw.get("cap_rate_at_ask"),
        "price_per_unit": uw.get("price_per_unit"),
        "value_add": uw.get("value_add"),
        "unit_mix": fin.get("unit_mix") or [],
        "benchmarks": uw.get("market_rent_benchmark") or {},
        # Market
        "market": comps.get("market") or {},
        "comp_count": comps.get("comp_count", 0),
        # Flags
        "tax_delinquent": tax.get("delinquent", False),
        "tax_year": tax.get("tax_year"),
        "open_violations": violations.get("open_count", 0),
        # Synthesis sections
        "sections": sections,
        # Quality
        "data_quality": data_quality or {},
    }


def _split_sections(text: str) -> list[dict]:
    """Parse synthesis text into list of {heading, body} dicts."""
    result = []
    current_heading = None
    current_lines: list[str] = []

    for line in text.split("\n"):
        if line.startswith("## "):
            if current_heading is not None:
                result.append(
                    {
                        "heading": current_heading,
                        "body": "\n".join(current_lines).strip(),
                    }
                )
            current_heading = line[3:].strip()
            current_lines = []
        else:
            if current_heading is not None:
                current_lines.append(line)

    if current_heading is not None:
        result.append(
            {"heading": current_heading, "body": "\n".join(current_lines).strip()}
        )

    return result
