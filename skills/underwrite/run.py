import json
import os
import sys

import httpx

HUD_TOKEN = os.environ.get("HUD_API_TOKEN", "")
CENSUS_KEY = os.environ.get("CENSUS_API_KEY", "")
CENSUS_BASE = "https://api.census.gov/data/2023/acs/acs5"

BED_KEY = {0: "studio", 1: "1br", 2: "2br", 3: "3br", 4: "4br"}


def _get_hud_safmr(zip_code: str) -> dict:
    """HUD Small Area Fair Market Rents by ZIP — free, San Antonio is a SAFMR area."""
    if not HUD_TOKEN or not zip_code:
        return {}
    try:
        r = httpx.get(
            f"https://www.huduser.gov/hudapi/public/fmr/listSAFMRs/{zip_code}",
            headers={"Authorization": f"Bearer {HUD_TOKEN}"},
            timeout=15,
        )
        if r.status_code != 200:
            print(f"HUD SAFMR {r.status_code}: {r.text[:200]}")
            return {}
        data = r.json()
        records = (data.get("data") or {}).get("basicdata") or []
        if not records:
            return {}
        rec = records[0]
        return {
            "studio": _safe_int(rec.get("Efficiency")),
            "1br": _safe_int(rec.get("One-Bedroom")),
            "2br": _safe_int(rec.get("Two-Bedroom")),
            "3br": _safe_int(rec.get("Three-Bedroom")),
            "4br": _safe_int(rec.get("Four-Bedroom")),
        }
    except Exception as e:
        print(f"HUD SAFMR error: {e}")
        return {}


def _get_census_b25031(zip_code: str) -> dict:
    """Census ACS5 B25031 — median gross rent by bedroom count at ZIP level."""
    if not CENSUS_KEY or not zip_code:
        return {}
    try:
        r = httpx.get(
            CENSUS_BASE,
            params={
                "get": "B25031_001E,B25031_002E,B25031_003E,B25031_004E,B25031_005E",
                "for": f"zip code tabulation area:{zip_code}",
                "key": CENSUS_KEY,
            },
            timeout=15,
        )
        r.raise_for_status()
        rows = r.json()
        if len(rows) < 2:
            return {}
        header, values = rows[0], rows[1]
        d = dict(zip(header, values, strict=False))
        return {
            "all": _safe_int(d.get("B25031_001E")),
            "studio": _safe_int(d.get("B25031_002E")),
            "1br": _safe_int(d.get("B25031_003E")),
            "2br": _safe_int(d.get("B25031_004E")),
            "3br": _safe_int(d.get("B25031_005E")),
        }
    except Exception as e:
        print(f"Census B25031 error: {e}")
        return {}


def _safe_int(val) -> int | None:
    try:
        v = int(val)
        return v if v > 0 else None
    except Exception:
        return None


def run(params: dict) -> dict:
    units = params.get("units")
    asking_price = params.get("asking_price")
    zip_code = params.get("zip", "")
    unit_mix = params.get("unit_mix") or []
    annual_revenue = params.get("annual_in_place_revenue")
    occupancy = params.get("occupancy_rate")
    expense_pu = params.get("total_expense_per_unit_annual")
    value_add_premium = params.get("value_add_rent_premium_per_unit")
    reno_cost_pu = params.get("renovation_cost_per_unit")

    if not annual_revenue and not unit_mix:
        return {
            "job": "underwrite",
            "status": "data_unavailable",
            "reason": "No financial data extracted from OM — financial section may be missing or unreadable",
            "data": None,
        }

    hud = _get_hud_safmr(zip_code)
    census = _get_census_b25031(zip_code)

    result: dict = {}

    # NOI estimation — only from real OM numbers
    noi = None
    noi_source = "unavailable"
    if annual_revenue and expense_pu and units:
        occ = occupancy if occupancy else 0.90
        egi = annual_revenue * occ
        total_expenses = expense_pu * units
        noi = round(egi - total_expenses)
        if occupancy:
            noi_source = "calculated from OM"
        else:
            noi_source = "calculated from OM (occupancy not stated — assumed 90%)"

    result["noi_estimate"] = noi
    result["noi_source"] = noi_source

    # Cap rate at asking price
    if noi and asking_price:
        result["cap_rate_at_ask"] = round(noi / asking_price, 4)
        result["cap_rate_source"] = "calculated from OM"
    else:
        result["cap_rate_at_ask"] = None
        reason = "no asking price in OM" if noi else "NOI unavailable"
        result["cap_rate_source"] = f"unavailable — {reason}"

    # Price per unit and gross rent multiplier
    result["price_per_unit"] = round(asking_price / units) if (asking_price and units) else None
    result["grm"] = round(asking_price / annual_revenue, 2) if (asking_price and annual_revenue) else None

    # Value-add return math
    if value_add_premium and reno_cost_pu and units:
        annual_rev_increase = value_add_premium * units * 12
        total_reno = reno_cost_pu * units
        payback = round(total_reno / annual_rev_increase, 1)
        result["value_add"] = {
            "monthly_premium_per_unit": value_add_premium,
            "annual_revenue_increase": annual_rev_increase,
            "total_renovation_cost": total_reno,
            "payback_years": payback,
            "source": "from OM",
        }
    else:
        result["value_add"] = None

    # Market rent benchmarks per bedroom type
    benchmarks: dict = {}
    for unit in unit_mix:
        beds = unit.get("bedrooms")
        if beds is None:
            continue
        key = BED_KEY.get(beds, f"{beds}br")
        in_place = unit.get("in_place_rent")
        fmr = hud.get(key)
        census_med = census.get(key)
        entry: dict = {
            "unit_type": unit.get("type"),
            "count": unit.get("count"),
            "in_place_rent": in_place,
            "hud_fmr": fmr,
            "hud_fmr_source": "HUD SAFMR (ZIP-level)" if fmr else None,
            "census_median_rent": census_med,
            "census_source": "Census ACS5 B25031 (ZIP-level)" if census_med else None,
        }
        if fmr and in_place:
            entry["discount_to_fmr_pct"] = round((fmr - in_place) / fmr * 100, 1)
        if census_med and in_place:
            entry["discount_to_census_pct"] = round((census_med - in_place) / census_med * 100, 1)
        benchmarks[key] = entry

    result["market_rent_benchmark"] = benchmarks or None

    sources = ["OM"]
    if hud:
        sources.append("HUD SAFMR")
    if census:
        sources.append("Census ACS B25031")
    result["source"] = " + ".join(sources)

    return {"job": "underwrite", "status": "ok", "data": result}


if __name__ == "__main__":
    raw = sys.argv[1] if len(sys.argv) > 1 else sys.stdin.read()
    print(json.dumps(run(json.loads(raw))))
