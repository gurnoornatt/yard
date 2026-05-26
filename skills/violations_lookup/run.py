import json
import sys

import httpx

SA_RESOURCE = "8cb8d6c9-93df-4c7a-b897-85793b21c60e"
CKAN_URL = "https://data.sanantonio.gov/api/3/action/datastore_search"


def run(params: dict) -> dict:
    city = params.get("city", "").strip().lower()
    state = params.get("state", "").strip().upper()

    if state != "TX" or city not in ("san antonio", ""):
        return {
            "job": "violations_lookup",
            "status": "data_unavailable",
            "reason": "SA Open Data covers San Antonio, TX only",
            "data": None,
        }

    address = params.get("address", "")
    try:
        r = httpx.get(
            CKAN_URL,
            params={"resource_id": SA_RESOURCE, "q": address, "limit": 15},
            timeout=15,
        )
        r.raise_for_status()
        records = r.json()["result"]["records"]
    except Exception as e:
        return {
            "job": "violations_lookup",
            "status": "error",
            "reason": str(e),
            "data": None,
        }

    violations = [
        {
            "description": rec.get("TYPENAME", ""),
            "category": rec.get("Category", ""),
            "status": rec.get("CaseStatus", ""),
            "date_opened": rec.get("OPENEDDATETIME"),
            "date_closed": rec.get("CLOSEDDATETIME"),
            "case_number": rec.get("CASEID"),
        }
        for rec in records
    ]

    open_count = sum(
        1
        for v in violations
        if (v.get("status") or "").lower() in ("open", "active")
    )

    return {
        "job": "violations_lookup",
        "status": "ok",
        "data": {
            "violations": violations,
            "count": len(violations),
            "source": "SA Open Data Portal",
            "open_count": open_count,
        },
    }


if __name__ == "__main__":
    raw = sys.argv[1] if len(sys.argv) > 1 else sys.stdin.read()
    print(json.dumps(run(json.loads(raw))))
