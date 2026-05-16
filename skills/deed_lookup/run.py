import json
import os
import sys

import httpx

ATTOM_KEY = os.environ.get("ATTOM_API_KEY", "")
ATTOM_BASE = "https://api.gateway.attomdata.com/propertyapi/v1.0.0"


def _headers() -> dict:
    return {"APIKey": ATTOM_KEY, "Accept": "application/json"}


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
            f"{ATTOM_BASE}/property/expandedprofile",
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
    assessment = prop.get("assessment") or {}
    sale = prop.get("sale") or {}

    # Mortgage lives inside assessment.mortgage.FirstConcurrent
    mort = (assessment.get("mortgage") or {}).get("FirstConcurrent") or {}

    lender_first = mort.get("lenderFirstName", "")
    lender_last = mort.get("lenderLastName", "")
    lender = f"{lender_first} {lender_last}".strip() or None

    loan_amount = mort.get("amount")
    orig_date = mort.get("date")
    maturity_date = mort.get("dueDate") or mort.get("duedate") or None
    loan_type = mort.get("deedType") or mort.get("loanType") or None

    # Sale data
    sale_amt = sale.get("amount") or {}
    last_sale_price = sale_amt.get("saleAmt")
    last_sale_date = sale.get("saleTransDate") or sale.get("saleSearchDate")

    # Appraised value
    assessed = assessment.get("assessed") or {}
    appraised_value = assessed.get("assdTtlValue")

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
