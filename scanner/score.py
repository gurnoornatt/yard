"""
Motivation scoring for multifamily properties.
Higher score = more seller pressure signals.
Score is internal only — never shown to clients.
"""
from __future__ import annotations

import datetime
from typing import NamedTuple


class ScoredProperty(NamedTuple):
    attom_id: str
    address: str
    units: int | None
    year_built: int | None
    appraised_value: float | None
    zip_code: str
    score: int
    signals: list[str]
    raw: dict


def score_property(p: dict) -> ScoredProperty:
    today = datetime.date.today()
    score = 0
    signals: list[str] = []

    # --- Loan maturity pressure (up to 40 pts) ---
    orig_raw = (
        p.get("mortgage", {}).get("FirstMortgageDate")
        or p.get("mortgage", {}).get("originationDate")
    )
    if orig_raw:
        try:
            orig = datetime.date.fromisoformat(str(orig_raw)[:10])
            years = (today - orig).days / 365.25
            if 4 <= years < 6:
                score += 30
                signals.append("Loan approaching 5-yr maturity (est.)")
            elif 9 <= years < 11:
                score += 40
                signals.append("Loan approaching 10-yr maturity (est.)")
            elif years >= 11:
                score += 20
                signals.append(f"Loan past typical term ({years:.0f} yrs since origination)")
        except (ValueError, TypeError):
            pass

    # --- Long hold period (up to 15 pts) ---
    sale_raw = (
        p.get("sale", {}).get("saleTransDate")
        or p.get("sale", {}).get("salesearchdate")
    )
    if sale_raw:
        try:
            sale_date = datetime.date.fromisoformat(str(sale_raw)[:10])
            hold_years = (today - sale_date).days / 365.25
            if hold_years >= 10:
                score += 15
                signals.append(f"Long hold: {hold_years:.0f} years since acquisition")
            elif hold_years >= 7:
                score += 8
                signals.append(f"Extended hold: {hold_years:.0f} years")
        except (ValueError, TypeError):
            pass

    # --- Out-of-state owner (15 pts) ---
    owner_state = (
        p.get("owner", {}).get("mailingState")
        or p.get("owner", {}).get("ownerState", "")
    )
    if owner_state and str(owner_state).upper() not in ("TX", ""):
        score += 15
        signals.append(f"Out-of-state owner ({str(owner_state).upper()})")

    # --- Low leverage / equity-rich (10 pts) ---
    loan_amt = _safe_float(
        p.get("mortgage", {}).get("FirstMortgageAmount")
        or p.get("mortgage", {}).get("amount")
    )
    appraised = _safe_float(
        p.get("assessment", {}).get("assessed", {}).get("assdTtlValue")
        or p.get("assessment", {}).get("market", {}).get("mktTtlValue")
    )
    if loan_amt and appraised and appraised > 0 and (loan_amt / appraised) < 0.40:
        score += 10
        signals.append("Low leverage — equity-rich asset")

    # --- Build address string ---
    addr_obj = p.get("address") or {}
    address = (
        addr_obj.get("oneLine")
        or addr_obj.get("oneline")
        or f"{addr_obj.get('line1', '')} {addr_obj.get('line2', '')}".strip()
        or "Unknown"
    )

    units = _safe_int(p.get("building", {}).get("size", {}).get("universalSize")) or _safe_int(
        p.get("summary", {}).get("levels")
    )
    year_built = _safe_int(p.get("summary", {}).get("yearbuilt"))
    zip_code = str(addr_obj.get("postal") or addr_obj.get("zip", ""))[:5]
    attom_id = str(p.get("identifier", {}).get("attomId") or p.get("identifier", {}).get("Id") or "")

    return ScoredProperty(
        attom_id=attom_id,
        address=address,
        units=units,
        year_built=year_built,
        appraised_value=appraised,
        zip_code=zip_code,
        score=score,
        signals=signals,
        raw=p,
    )


def _safe_float(val) -> float | None:
    try:
        v = float(val)
        return v if v > 0 else None
    except (TypeError, ValueError):
        return None


def _safe_int(val) -> int | None:
    try:
        v = int(val)
        return v if v > 0 else None
    except (TypeError, ValueError):
        return None
