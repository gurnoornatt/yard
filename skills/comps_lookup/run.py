import json
import os
import sys

import httpx

ATTOM_KEY = os.environ.get("ATTOM_API_KEY", "")
CENSUS_KEY = os.environ.get("CENSUS_API_KEY", "")
ATTOM_BASE = "https://api.gateway.attomdata.com/propertyapi/v1.0.0"
CENSUS_BASE = "https://api.census.gov/data/2023/acs/acs5"

CENSUS_VARS = "B25003_001E,B25003_003E,B25064_001E,B25002_001E,B25002_003E,B25031_003E,B25031_004E,B25031_005E"


def _attom_headers() -> dict:
    return {"APIKey": ATTOM_KEY, "Accept": "application/json"}


def _get_comps(address: str, city: str, state: str, zip_: str) -> list:
    address2 = f"{city}, {state} {zip_}".strip(", ")
    try:
        r = httpx.get(
            f"{ATTOM_BASE}/sale/snapshot",
            params={"address1": address, "address2": address2, "radius": "1.5",
                    "PROPERTYTYPE": "apartment|multi+family"},
            headers=_attom_headers(),
            timeout=20,
        )
        r.raise_for_status()
        sales = r.json().get("property") or []
        comps = []
        for s in sales[:10]:
            sale = s.get("sale") or {}
            sale_amt = sale.get("amount") or {}
            loc = s.get("address") or {}
            comps.append(
                {
                    "address": loc.get("oneLine") or loc.get("oneline", ""),
                    "sale_price": sale_amt.get("saleamt") or sale_amt.get("saleAmt"),
                    "sale_date": sale.get("saleTransDate")
                    or sale.get("salesearchdate"),
                    "property_type": s.get("summary", {}).get("proptype", ""),
                }
            )
        return comps
    except Exception:
        return []


def _get_market(zip_: str) -> dict:
    if not zip_ or not CENSUS_KEY:
        return {}
    try:
        r = httpx.get(
            CENSUS_BASE,
            params={
                "get": f"NAME,{CENSUS_VARS}",
                "for": f"zip code tabulation area:{zip_}",
                "key": CENSUS_KEY,
            },
            timeout=15,
        )
        r.raise_for_status()
        rows = r.json()
        if len(rows) < 2:
            return {}
        header, values = rows[0], rows[1]
        d = dict(zip(header, values))

        def _si(val) -> int | None:
            try:
                v = int(val)
                return v if v > 0 else None
            except Exception:
                return None

        total_occupied = int(d.get("B25003_001E") or 0)
        renter_occ = int(d.get("B25003_003E") or 0)
        total_units = int(d.get("B25002_001E") or 1)
        vacant = int(d.get("B25002_003E") or 0)
        median_rent = int(d.get("B25064_001E") or 0)

        return {
            "median_rent": median_rent,
            "renter_pct": round(renter_occ / total_occupied * 100, 1)
            if total_occupied
            else None,
            "vacancy_pct": round(vacant / total_units * 100, 1)
            if total_units
            else None,
            "median_rent_1br": _si(d.get("B25031_003E")),
            "median_rent_2br": _si(d.get("B25031_004E")),
            "median_rent_3br": _si(d.get("B25031_005E")),
            "zip": zip_,
        }
    except Exception:
        return {}


def run(params: dict) -> dict:
    address = params.get("address", "")
    city = params.get("city", "")
    state = params.get("state", "")
    zip_ = params.get("zip", "")

    if not address:
        return {
            "job": "comps_lookup",
            "status": "data_unavailable",
            "reason": "No address available",
            "data": None,
        }

    comps = _get_comps(address, city, state, zip_)
    market = _get_market(zip_)

    return {
        "job": "comps_lookup",
        "status": "ok",
        "data": {
            "comps": comps,
            "comp_count": len(comps),
            "market": market,
            "source": "ATTOM + US Census ACS5",
        },
    }


if __name__ == "__main__":
    raw = sys.argv[1] if len(sys.argv) > 1 else sys.stdin.read()
    print(json.dumps(run(json.loads(raw))))
