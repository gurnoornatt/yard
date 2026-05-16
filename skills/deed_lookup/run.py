import json
import os
import sys

import httpx

ATTOM_KEY = os.environ.get("ATTOM_API_KEY", "")
ATTOM_BASE = "https://api.attomdata.com"


def _headers() -> dict:
    return {"apikey": ATTOM_KEY, "accept": "application/json"}


def run(params: dict) -> dict:
    address = params.get("address", "")
    city = params.get("city", "")
    state = params.get("state", "")
    zip_ = params.get("zip", "")

    if not address or not city:
        return {
            "job": "deed_lookup",
            "status": "data_unavailable",
            "reason": "No address available",
            "data": None,
        }

    address2 = f"{city}, {state} {zip_}".strip(", ")

    try:
        r = httpx.get(
            f"{ATTOM_BASE}/v4/property/detail",
            params={"address1": address, "address2": address2},
            headers=_headers(),
            timeout=20,
        )
        r.raise_for_status()
        body = r.json()
    except Exception as e:
        return {"job": "deed_lookup", "status": "error", "reason": str(e), "data": None}

    props = body.get("property") or []
    if not props:
        return {
            "job": "deed_lookup",
            "status": "data_unavailable",
            "reason": "Property not found in ATTOM",
            "data": None,
        }

    prop = props[0]

    # Extract mortgage/deed info — ATTOM nests differently per account tier
    mort = prop.get("mortgage") or {}
    sale = prop.get("sale") or {}
    assessment = prop.get("assessment") or {}

    # Primary loan fields
    lender = (
        mort.get("lender1fullname")
        or mort.get("lenderName")
        or sale.get("lenderName", "")
    )
    loan_amount = mort.get("amount1stmortgage") or mort.get("loanAmount")
    orig_date = mort.get("recordingdate1stmortgage") or mort.get("originationDate")
    maturity_date = mort.get("duedate1stmortgage") or mort.get("maturityDate")
    loan_type = mort.get("loantype1stmortgage") or mort.get("loanType", "")

    # Last sale
    last_sale_price = sale.get("saleamt") or sale.get("saleamount")
    last_sale_date = sale.get("salesearchdate") or sale.get("saledate")

    # Appraised value
    appraised_value = (assessment.get("assessed") or {}).get(
        "assdttlvalue"
    ) or assessment.get("appraisedValue")

    data = {
        "lender": lender,
        "loan_amount": loan_amount,
        "origination_date": orig_date,
        "maturity_date": maturity_date,
        "loan_type": loan_type,
        "last_sale_price": last_sale_price,
        "last_sale_date": last_sale_date,
        "appraised_value": appraised_value,
    }

    return {"job": "deed_lookup", "status": "ok", "data": data}


if __name__ == "__main__":
    raw = sys.argv[1] if len(sys.argv) > 1 else sys.stdin.read()
    print(json.dumps(run(json.loads(raw))))
