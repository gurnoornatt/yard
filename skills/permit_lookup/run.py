import json
import sys

import httpx

SA_RESOURCE = "c21106f9-3ef5-4f3a-8604-f992b4db7512"
CKAN_URL = "https://data.sanantonio.gov/api/3/action/datastore_search"


def run(params: dict) -> dict:
    city = params.get("city", "").strip().lower()
    state = params.get("state", "").strip().upper()

    if state != "TX" or city not in ("san antonio", ""):
        return {
            "job": "permit_lookup",
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
            "job": "permit_lookup",
            "status": "error",
            "reason": str(e),
            "data": None,
        }

    permits = [
        {
            "description": rec.get("WORK_DESC", ""),
            "value": rec.get("JOB_VALUE"),
            "date": rec.get("ISSUED_DATE"),
            "status": rec.get("STATUS"),
            "type": rec.get("PERMIT_TYPE"),
        }
        for rec in records
    ]

    return {
        "job": "permit_lookup",
        "status": "ok",
        "data": {
            "permits": permits,
            "count": len(permits),
            "source": "SA Open Data Portal",
        },
    }


if __name__ == "__main__":
    raw = sys.argv[1] if len(sys.argv) > 1 else sys.stdin.read()
    print(json.dumps(run(json.loads(raw))))
