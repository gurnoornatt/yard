import json
import sys
from datetime import date

PRESSURE_LABELS = {
    "past_due": "CRITICAL — loan is past maturity, forced seller likely",
    "critical": "HIGH — matures within 6 months, refinance pressure imminent",
    "high": "ELEVATED — matures within 12 months",
    "moderate": "MODERATE — matures within 24 months",
    "low": "LOW — 2+ years to maturity, no near-term pressure",
}


def _level(months: int) -> str:
    if months < 0:
        return "past_due"
    if months < 6:
        return "critical"
    if months < 12:
        return "high"
    if months < 24:
        return "moderate"
    return "low"


def run(params: dict) -> dict:
    maturity_str = params.get("deed_maturity_date")

    if not maturity_str:
        return {
            "job": "maturity_estimator",
            "status": "data_unavailable",
            "reason": "No loan maturity date available from deed records",
            "data": None,
        }

    try:
        maturity = date.fromisoformat(str(maturity_str)[:10])
    except ValueError:
        return {
            "job": "maturity_estimator",
            "status": "error",
            "reason": f"Cannot parse maturity date: {maturity_str}",
            "data": None,
        }

    today = date.today()
    months = (maturity.year - today.year) * 12 + (maturity.month - today.month)
    level = _level(months)

    return {
        "job": "maturity_estimator",
        "status": "ok",
        "data": {
            "maturity_date": str(maturity_str),
            "months_remaining": months,
            "pressure_level": level,
            "interpretation": PRESSURE_LABELS[level],
        },
    }


if __name__ == "__main__":
    raw = sys.argv[1] if len(sys.argv) > 1 else sys.stdin.read()
    print(json.dumps(run(json.loads(raw))))
