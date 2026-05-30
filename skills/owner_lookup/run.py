import json
import os
import re
import sys

import httpx

ATTOM_KEY = os.environ.get("ATTOM_API_KEY", "")
ATTOM_BASE = "https://api.gateway.attomdata.com/propertyapi/v1.0.0"
ARCGIS = "https://maps.bexar.org/arcgis/rest/services/Parcels/MapServer/0/query"


def _headers() -> dict:
    return {"APIKey": ATTOM_KEY, "Accept": "application/json"}


def _parse_state(mailing_address: str) -> str:
    m = re.search(r"\b([A-Z]{2})\s+\d{5}", mailing_address.upper())
    return m.group(1) if m else ""


def _attom_fetch(address: str, city_state_zip: str) -> dict:
    r = httpx.get(
        f"{ATTOM_BASE}/property/expandedprofile",
        params={"address1": address, "address2": city_state_zip},
        headers=_headers(),
        timeout=20,
    )
    r.raise_for_status()
    props = r.json().get("property") or []
    return props[0] if props else {}


def _arcgis_fetch(address: str) -> dict:
    """Bexar County ArcGIS parcel layer — free, returns full owner mailing address."""
    m = re.match(r"^(\d+)\s+(\S+)", address.strip())
    if not m:
        return {}
    number = m.group(1)
    street_first = m.group(2)[:6].upper()
    r = httpx.get(
        ARCGIS,
        params={
            "where": f"Situs LIKE '%{number}%{street_first}%'",
            "outFields": "Situs,Owner,AddrLn1,AddrLn2,AddrLn3,AddrCity,AddrSt,Zip,TotVal,PropID",
            "returnGeometry": "false",
            "resultRecordCount": 1,
            "f": "json",
        },
        timeout=15,
    )
    feats = r.json().get("features") or []
    if not feats:
        return {}
    a = feats[0]["attributes"]
    # Build full mailing address from all AddrLn fields
    street_lines = [
        a.get("AddrLn1") or "",
        a.get("AddrLn2") or "",
        a.get("AddrLn3") or "",
    ]
    street = " ".join(line.strip() for line in street_lines if line and line.upper() != "NULL")
    city = (a.get("AddrCity") or "").strip()
    state = (a.get("AddrSt") or "").strip()
    zipcode = (a.get("Zip") or "").strip()
    parts = [street, city, state, zipcode]
    mailing = ", ".join(p for p in parts if p and p.upper() != "NULL")
    return {
        "owner_name": a.get("Owner") or "",
        "owner_address": mailing,
        "owner_state": state,
        "appraised_value": a.get("TotVal"),
        "prop_id": str(int(a["PropID"])) if a.get("PropID") else "",
        "source": "Bexar County ArcGIS",
    }


def _build_result(
    owner_name,
    owner_address,
    owner_state,
    appraised_value,
    absentee=False,
    corporate=False,
    attom_lender="",
    attom_loan_amount=None,
    attom_loan_date="",
    attom_id="",
    apn="",
    source="",
):
    out_of_state = bool(owner_state and owner_state.upper() != "TX")
    val_str = str(int(appraised_value)) if appraised_value else ""
    return {
        "job": "owner_lookup",
        "status": "ok",
        "data": {
            "owner_name": owner_name,
            "owner_address": owner_address,
            "owner_state": owner_state.upper() if owner_state else "",
            "out_of_state": out_of_state,
            "absentee_owner": absentee,
            "corporate_owner": corporate,
            "appraised_value": val_str,
            "attom_lender": attom_lender,
            "attom_loan_amount": attom_loan_amount,
            "attom_loan_date": attom_loan_date,
            "attom_id": str(attom_id) if attom_id else "",
            "apn": apn,
            "source": source,
        },
    }


def run(params: dict) -> dict:
    state = params.get("state", "").strip().upper()
    if state and state != "TX":
        return {
            "job": "owner_lookup",
            "status": "data_unavailable",
            "reason": "Owner lookup covers TX (Bexar County) only",
            "data": None,
        }

    address = params.get("address", "").strip()
    if not address:
        return {
            "job": "owner_lookup",
            "status": "data_unavailable",
            "reason": "No address provided",
            "data": None,
        }

    city = params.get("city", "San Antonio").strip()
    zip_code = params.get("zip", "").strip()
    city_state_zip = f"{city}, {state or 'TX'} {zip_code}".strip(", ")

    try:
        # --- Option A: ATTOM (often 504s on our plan tier — fall through to ArcGIS) ---
        try:
            prop = _attom_fetch(address, city_state_zip)
        except Exception:
            prop = {}
        if prop:
            assessment = prop.get("assessment") or {}
            owner_block = assessment.get("owner") or {}
            market = assessment.get("market") or {}
            mortgage_block = assessment.get("mortgage") or {}

            owner1 = owner_block.get("owner1") or {}
            owner_name = owner1.get("fullName") or owner1.get("lastName") or ""
            mailing_address = owner_block.get("mailingAddressOneLine") or ""
            absentee_status = owner_block.get("absenteeOwnerStatus") or ""
            corporate_indicator = owner_block.get("corporateIndicator") or ""

            appraised_value = (
                market.get("mktTtlValue")
                or market.get("mktttlvalue")
                or assessment.get("assessed", {}).get("assdTtlValue")
                or assessment.get("assessed", {}).get("assdttlvalue")
            )

            first_mtg = mortgage_block.get("FirstConcurrent") or {}
            identifier = prop.get("identifier") or {}

            if owner_name:
                owner_state = _parse_state(mailing_address)
                return _build_result(
                    owner_name=owner_name,
                    owner_address=mailing_address,
                    owner_state=owner_state,
                    appraised_value=appraised_value,
                    absentee=(absentee_status == "A"),
                    corporate=(corporate_indicator == "Y"),
                    attom_lender=first_mtg.get("lenderLastName") or "",
                    attom_loan_amount=first_mtg.get("amount"),
                    attom_loan_date=first_mtg.get("date") or "",
                    attom_id=identifier.get("attomId") or identifier.get("Id") or "",
                    apn=identifier.get("apn") or "",
                    source="ATTOM (property/expandedprofile)",
                )

        # --- Option B: Bexar County ArcGIS fallback ---
        arc = _arcgis_fetch(address)
        if arc and arc.get("owner_name"):
            owner_state = arc.get("owner_state") or _parse_state(
                arc.get("owner_address", "")
            )
            return _build_result(
                owner_name=arc["owner_name"],
                owner_address=arc.get("owner_address", ""),
                owner_state=owner_state,
                appraised_value=arc.get("appraised_value"),
                source=arc.get("source", "Bexar County ArcGIS"),
            )

        return {
            "job": "owner_lookup",
            "status": "data_unavailable",
            "reason": f"No owner data found via ATTOM or ArcGIS for: {address}",
            "data": None,
        }

    except httpx.HTTPStatusError as e:
        return {
            "job": "owner_lookup",
            "status": "error",
            "reason": f"HTTP {e.response.status_code}: {e.response.text[:200]}",
            "data": None,
        }
    except Exception as e:
        return {
            "job": "owner_lookup",
            "status": "error",
            "reason": str(e),
            "data": None,
        }


if __name__ == "__main__":
    raw = sys.argv[1] if len(sys.argv) > 1 else sys.stdin.read()
    print(json.dumps(run(json.loads(raw))))
